from extensions import db
from sqlalchemy import text
import numpy as np
from langchain.schema import Document
from typing import List
import json
import re

class PostgresVectorStore:
    def __init__(self, department, user=None):
        self.department = department
        self.user = user
    
    def build(self, vectors, documents, access_level='public', is_cross_dept=False, 
              source_type='primary', uploaded_by=None, file_name=None, file_type=None,
              feedback_id=None, file_hash=None):  # ✅ BUG #5 & #11 FIX
        """Store vectors and documents in PostgreSQL"""
        try:
            # Convert vectors to numpy array if needed
            if isinstance(vectors, list):
                vectors = np.array(vectors, dtype='float32')
            
            print(f"📤 Uploading {len(vectors)} vectors for department: {self.department}")
            
            # Insert documents in batches
            batch_size = 50
            total_inserted = 0
            
            for i in range(0, len(vectors), batch_size):
                batch_vectors = vectors[i:i+batch_size]
                batch_docs = documents[i:i+batch_size]
                
                for vector, doc in zip(batch_vectors, batch_docs):
                    try:
                        vector_list = vector.tolist() if isinstance(vector, np.ndarray) else vector
                        metadata_json = json.dumps(doc.metadata) if doc.metadata else '{}'
                        
                        db.session.execute(
                            text("""
                                INSERT INTO document_embeddings 
                                (department, content, metadata, embedding, access_level, 
                                 is_cross_dept, source_type, uploaded_by, file_name, file_type, feedback_id, file_hash)
                                VALUES (
                                    :dept,
                                    :content,
                                    CAST(:metadata AS jsonb),
                                    CAST(:embedding AS vector),
                                    :access,
                                    :cross,
                                    :source,
                                    :uploader,
                                    :fname,
                                    :ftype,
                                    :fid,
                                    :fhash
                                )
                            """),
                            {
                                "dept": self.department,
                                "content": doc.page_content,
                                "metadata": metadata_json,
                                "embedding": str(vector_list),
                                "access": access_level,
                                "cross": is_cross_dept,
                                "source": source_type,
                                "uploader": uploaded_by,
                                "fname": file_name,
                                "ftype": file_type,
                                "fid": feedback_id,
                                "fhash": file_hash
                            }
                        )
                        total_inserted += 1
                        
                    except Exception as e:
                        print(f"⚠️ Error inserting vector {total_inserted + 1}: {str(e)}")
                        continue
                
                db.session.commit()
                print(f"  ✅ Inserted batch: {total_inserted}/{len(vectors)} vectors")
            
            print(f"✅ Successfully stored {total_inserted} vectors")
            return total_inserted
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error storing vectors: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def search(self, query_vector, k=5, similarity_threshold=0.7, query_text=None, hybrid_alpha=0.7):
        """
        ENHANCED: Hybrid search combining vector similarity and keyword matching
        
        Search strategy:
        1. Vector search (semantic understanding)
        2. Keyword search (exact term matching) - if query_text provided
        3. Combine with weighted scoring
        4. Primary KB → Secondary KB fallback
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            similarity_threshold: Minimum similarity for Primary KB (0.7 = 70%)
            query_text: Original text query for keyword matching (optional)
            hybrid_alpha: Weight for vector vs keyword (0.7 = 70% vector, 30% keyword)
        
        Returns:
            List[Document]: Retrieved documents with metadata
        """
        try:
            if isinstance(query_vector, np.ndarray):
                query_vector = query_vector.tolist()
            
            # Build access level filter
            access_levels = ['public']
            if self.user:
                levels = ['public', 'employee', 'manager', 'senior_mgmt', 'executive']
                try:
                    user_level_index = levels.index(self.user.access_level)
                    access_levels = levels[:user_level_index + 1]
                except ValueError:
                    pass
            
            # ✅ BUG #8 FIX: Hybrid search implementation
            if query_text and len(query_text.strip()) > 0:
                print(f"🔍 Using HYBRID search (vector + keyword)...")
                return self._hybrid_search_internal(
                    query_vector, query_text, k, similarity_threshold, 
                    hybrid_alpha, access_levels
                )
            else:
                print(f"🔍 Using vector-only search...")
                return self._vector_only_search(
                    query_vector, k, similarity_threshold, access_levels
                )
            
        except Exception as e:
            print(f"❌ Error searching vectors: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _hybrid_search_internal(self, query_vector, query_text, k, similarity_threshold, 
                                hybrid_alpha, access_levels):
        """
        Internal hybrid search combining vector and keyword matching
        """
        # Extract keywords from query
        keywords = self._extract_keywords(query_text)
        
        # STEP 1: Vector search Primary KB
        print(f"  📊 Vector search Primary KB...")
        vector_primary = self._get_vector_results(
            query_vector, 'primary', k * 2, access_levels
        )
        
        # STEP 2: Keyword search Primary KB
        print(f"  🔤 Keyword search Primary KB (keywords: {keywords})...")
        keyword_primary = self._get_keyword_results(
            query_text, keywords, 'primary', k * 2, access_levels
        )
        
        # STEP 3: Combine and score Primary KB results
        combined_primary = self._combine_results(
            vector_primary, keyword_primary, hybrid_alpha
        )
        
        # Check if Primary KB has good results
        has_good_primary = False
        if combined_primary:
            max_score = max(r['score'] for r in combined_primary)
            has_good_primary = max_score >= similarity_threshold
            print(f"  📈 Primary KB: {len(combined_primary)} results, max score: {max_score:.2f}")
        
        # STEP 4: If Primary weak, also search Secondary KB
        combined_secondary = []
        if not has_good_primary:
            print(f"  🔍 Primary KB weak, searching Secondary KB...")
            
            vector_secondary = self._get_vector_results(
                query_vector, 'secondary', k * 2, access_levels
            )
            keyword_secondary = self._get_keyword_results(
                query_text, keywords, 'secondary', k * 2, access_levels
            )
            combined_secondary = self._combine_results(
                vector_secondary, keyword_secondary, hybrid_alpha
            )
            
            if combined_secondary:
                max_sec_score = max(r['score'] for r in combined_secondary)
                print(f"  📈 Secondary KB: {len(combined_secondary)} results, max score: {max_sec_score:.2f}")
        
        # STEP 5: Merge and sort all results
        all_results = combined_primary + combined_secondary
        all_results.sort(key=lambda x: x['score'], reverse=True)
        all_results = all_results[:k]
        
        # STEP 6: Convert to Document objects
        documents = self._results_to_documents(all_results)
        
        # Log summary
        primary_count = sum(1 for d in documents if d.metadata['source_type'] == 'primary')
        secondary_count = sum(1 for d in documents if d.metadata['source_type'] == 'secondary')
        print(f"✅ Hybrid search: {len(documents)} results ({primary_count} Primary, {secondary_count} Secondary)")
        
        return documents
    
    def _vector_only_search(self, query_vector, k, similarity_threshold, access_levels):
        """
        Original vector-only search (fallback when no query_text)
        """
        # Search Primary KB
        print(f"🔍 Searching Primary KB...")
        primary_results = db.session.execute(
            text("""
                SELECT 
                    content, metadata, file_name, source_type,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
                FROM document_embeddings
                WHERE 
                    (department = :dept OR is_cross_dept = true)
                    AND access_level = ANY(:access_levels)
                    AND source_type = 'primary'
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :k
            """),
            {
                "query_embedding": str(query_vector),
                "dept": self.department,
                "access_levels": access_levels,
                "k": k
            }
        ).fetchall()
        
        # Check if good results
        has_good_primary = False
        if primary_results:
            max_similarity = max(row.similarity for row in primary_results)
            has_good_primary = max_similarity >= similarity_threshold
            print(f"📊 Primary KB: {len(primary_results)} results, max: {max_similarity:.2f}")
        
        # Search Secondary if needed
        secondary_results = []
        if not has_good_primary:
            print(f"🔍 Searching Secondary KB...")
            secondary_results = db.session.execute(
                text("""
                    SELECT 
                        content, metadata, file_name, source_type,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
                    FROM document_embeddings
                    WHERE 
                        source_type = 'secondary'
                        AND access_level = ANY(:access_levels)
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :k
                """),
                {
                    "query_embedding": str(query_vector),
                    "access_levels": access_levels,
                    "k": k
                }
            ).fetchall()
            
            if secondary_results:
                max_sec = max(row.similarity for row in secondary_results)
                print(f"📊 Secondary KB: {len(secondary_results)} results, max: {max_sec:.2f}")
        
        # Merge and convert
        all_results = list(primary_results) + list(secondary_results)
        all_results.sort(key=lambda x: x.similarity, reverse=True)
        all_results = all_results[:k]
        
        documents = []
        for row in all_results:
            try:
                metadata = json.loads(row.metadata) if row.metadata else {}
            except:
                metadata = {}
            
            metadata['file_name'] = row.file_name
            metadata['similarity'] = float(row.similarity)
            metadata['source_type'] = row.source_type
            metadata['source_label'] = "📝 From User Feedback" if row.source_type == 'secondary' else "📄 From Documents"
            
            documents.append(Document(page_content=row.content, metadata=metadata))
        
        return documents
    
    def _extract_keywords(self, query_text):
        """Extract important keywords from query"""
        # Remove common words and punctuation
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'when', 'where', 'who', 'which'}
        words = re.findall(r'\b\w+\b', query_text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords[:5]  # Top 5 keywords
    
    def _get_vector_results(self, query_vector, source_type, limit, access_levels):
        """Get vector similarity results"""
        results = db.session.execute(
            text("""
                SELECT 
                    id, content, metadata, file_name, source_type,
                    1 - (embedding <=> CAST(:vec AS vector)) as similarity
                FROM document_embeddings
                WHERE 
                    source_type = :source
                    AND access_level = ANY(:access_levels)
                    AND (department = :dept OR is_cross_dept = true OR :source = 'secondary')
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :lim
            """),
            {
                "vec": str(query_vector),
                "source": source_type,
                "access_levels": access_levels,
                "dept": self.department,
                "lim": limit
            }
        ).fetchall()
        
        return [{'id': r.id, 'content': r.content, 'metadata': r.metadata, 
                 'file_name': r.file_name, 'source_type': r.source_type,
                 'vector_score': float(r.similarity), 'keyword_score': 0.0} 
                for r in results]
    
    def _get_keyword_results(self, query_text, keywords, source_type, limit, access_levels):
        """Get keyword matching results using ILIKE"""
        if not keywords:
            return []
        
        # Build ILIKE conditions for each keyword
        ilike_conditions = []
        params = {
            "source": source_type,
            "access_levels": access_levels,
            "dept": self.department,
            "lim": limit
        }
        
        for i, kw in enumerate(keywords):
            param_name = f"kw{i}"
            ilike_conditions.append(f"content ILIKE :{param_name}")
            params[param_name] = f"%{kw}%"
        
        where_clause = " OR ".join(ilike_conditions)
        
        query = f"""
            SELECT 
                id, content, metadata, file_name, source_type
            FROM document_embeddings
            WHERE 
                source_type = :source
                AND access_level = ANY(:access_levels)
                AND (department = :dept OR is_cross_dept = true OR :source = 'secondary')
                AND ({where_clause})
            LIMIT :lim
        """
        
        results = db.session.execute(text(query), params).fetchall()
        
        # Calculate keyword match score
        keyword_results = []
        for r in results:
            content_lower = r.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            keyword_score = matches / len(keywords)  # Proportion of keywords found
            
            keyword_results.append({
                'id': r.id,
                'content': r.content,
                'metadata': r.metadata,
                'file_name': r.file_name,
                'source_type': r.source_type,
                'vector_score': 0.0,
                'keyword_score': keyword_score
            })
        
        return keyword_results
    
    def _combine_results(self, vector_results, keyword_results, alpha):
        """
        Combine vector and keyword results with weighted scoring
        alpha: weight for vector score (1-alpha for keyword score)
        """
        # Create a dictionary indexed by document id
        combined = {}
        
        # Add vector results
        for r in vector_results:
            combined[r['id']] = r.copy()
        
        # Merge keyword results
        for r in keyword_results:
            if r['id'] in combined:
                # Document found in both - update keyword score
                combined[r['id']]['keyword_score'] = max(
                    combined[r['id']]['keyword_score'],
                    r['keyword_score']
                )
            else:
                # New document from keyword search
                combined[r['id']] = r.copy()
        
        # Calculate final hybrid score
        for doc_id in combined:
            vec_score = combined[doc_id]['vector_score']
            kw_score = combined[doc_id]['keyword_score']
            # Weighted combination
            combined[doc_id]['score'] = (alpha * vec_score) + ((1 - alpha) * kw_score)
        
        return list(combined.values())
    
    def _results_to_documents(self, results):
        """Convert result dictionaries to Document objects"""
        documents = []
        for r in results:
            try:
                metadata = json.loads(r['metadata']) if r['metadata'] else {}
            except:
                metadata = {}
            
            metadata['file_name'] = r['file_name']
            metadata['similarity'] = r['score']  # Hybrid score
            metadata['vector_score'] = r['vector_score']
            metadata['keyword_score'] = r['keyword_score']
            metadata['source_type'] = r['source_type']
            metadata['source_label'] = "📝 From User Feedback" if r['source_type'] == 'secondary' else "📄 From Documents"
            
            documents.append(Document(
                page_content=r['content'],
                metadata=metadata
            ))
        
        return documents
    
    def delete_department_data(self):
        """Delete all vectors for this department"""
        try:
            result = db.session.execute(
                text("DELETE FROM document_embeddings WHERE department = :dept"),
                {"dept": self.department}
            )
            db.session.commit()
            print(f"✅ Deleted {result.rowcount} records for department: {self.department}")
            return result.rowcount
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error deleting department data: {str(e)}")
            raise
    
    def get_stats(self):
        """Get statistics about stored vectors"""
        try:
            result = db.session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_vectors,
                        COUNT(DISTINCT file_name) as total_files,
                        MIN(created_at) as first_upload,
                        MAX(created_at) as last_upload
                    FROM document_embeddings
                    WHERE department = :dept
                """),
                {"dept": self.department}
            ).fetchone()
            
            if result:
                return {
                    "total_vectors": result.total_vectors,
                    "total_files": result.total_files,
                    "first_upload": result.first_upload,
                    "last_upload": result.last_upload
                }
            return {
                "total_vectors": 0,
                "total_files": 0,
                "first_upload": None,
                "last_upload": None
            }
        except Exception as e:
            print(f"❌ Error getting stats: {str(e)}")
            return None