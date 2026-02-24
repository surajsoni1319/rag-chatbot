from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from config import Config

class RAGChatbot:
    def __init__(self, store):
        self.store = store
        self.llm = AzureChatOpenAI(
            azure_deployment=Config.AZURE_OPENAI_CHAT_DEPLOYMENT,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            temperature=0.1,
            max_tokens=800,
            timeout=30
        )
        self.embedder = AzureOpenAIEmbeddings(
            azure_deployment=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION
        )
        self.conversation_history = []
        
        # ✅ BUG #9 FIX: Minimum similarity threshold for LLM
        self.MIN_SIMILARITY = 0.6  # 60% - can be adjusted
    
    def _enhance_query_with_context(self, question):
        """
        Enhance the current query with conversation context to resolve pronouns
        and references like 'the candidate', 'his', 'her', etc.
        """
        if not self.conversation_history:
            return question
        
        pronouns = ['he', 'she', 'his', 'her', 'their', 'him', 'them', 'the candidate', 'that person']
        needs_enhancement = any(pronoun in question.lower() for pronoun in pronouns)
        
        if not needs_enhancement:
            return question
        
        recent_context = "\n".join([
            f"Q: {q}\nA: {a}" 
            for q, a in self.conversation_history[-2:]
        ])
        
        rewrite_prompt = f"""
Given this conversation history:
{recent_context}

Current question: {question}

If the current question contains pronouns (he, she, his, her, their, the candidate, etc.) or references to previous context, 
rewrite it as a standalone question with full context. Otherwise, return the question as-is.

Return ONLY the rewritten question, nothing else.
"""
        
        enhanced_query = self.llm.invoke(rewrite_prompt).content.strip()
        return enhanced_query
    
    def ask(self, question):
        # Enhance query with conversation context
        enhanced_question = self._enhance_query_with_context(question)
        
        # ✅ BUG #8 FIX: Use HYBRID search (vector + keyword)
        # Generate embedding for vector search
        q_emb = self.embedder.embed_query(enhanced_question)
        
        # Pass both vector AND text for hybrid search
        docs = self.store.search(
            query_vector=q_emb, 
            k=5,  # Get more docs to filter
            query_text=enhanced_question,
            hybrid_alpha=0.7
        )
        
        # ✅ BUG #9 FIX: Filter documents by similarity threshold
        # Only use docs with similarity >= 60% to prevent hallucinations
        filtered_docs = [
            d for d in docs 
            if d.metadata.get('similarity', 0) >= self.MIN_SIMILARITY
        ]
        
        print(f"📊 Retrieved {len(docs)} docs, {len(filtered_docs)} above {self.MIN_SIMILARITY} threshold")
        
        # If no high-quality docs, try with original question
        if not filtered_docs:
            print("⚠️ No docs above threshold, trying original question...")
            q_emb = self.embedder.embed_query(question)
            docs = self.store.search(
                query_vector=q_emb, 
                k=5,
                query_text=question,
                hybrid_alpha=0.7
            )
            
            filtered_docs = [
                d for d in docs 
                if d.metadata.get('similarity', 0) >= self.MIN_SIMILARITY
            ]
            
            print(f"📊 Second attempt: {len(docs)} docs, {len(filtered_docs)} above threshold")
        
        # If still no confident results, return "no answer" response
        if not filtered_docs:
            print(f"❌ No documents with similarity >= {self.MIN_SIMILARITY}")
            return self._generate_no_confident_answer_response(question)
        
        # Use top 3 filtered docs
        top_docs = filtered_docs[:3]
        
        # Log similarity scores
        for i, doc in enumerate(top_docs, 1):
            sim = doc.metadata.get('similarity', 0)
            source = doc.metadata.get('source_label', 'Unknown')
            print(f"  Doc {i}: {sim:.2f} similarity - {source}")
        
        context = "\n\n".join([d.page_content for d in top_docs])
        
        # Include recent conversation for better answers
        recent_context = ""
        if self.conversation_history:
            recent_context = "Previous conversation:\n" + "\n".join([
                f"Q: {q}\nA: {a}" 
                for q, a in self.conversation_history[-1:]
            ]) + "\n\n"
        
        prompt = f"""
You are a professional assistant helping with candidate and document inquiries.

{recent_context}Context:
{context}

Question: {question}

Instructions:
- Answer directly and naturally
- Use the information from the context above
- Do not say "based on the context" or "according to the documents"
- If the answer is not in the context, simply say "I don't know"
- Be specific and use names when available
- Keep answers brief and to the point
- Do NOT add suggestions like "feel free to ask" or "if you have questions"
- Do NOT offer help unless specifically asked
- For greetings (hi, hello), respond with ONLY a brief greeting

FORMATTING for multiple items:
- Use numbered lists (1., 2., 3.) for multiple items
- Add a blank line between each numbered item
- Start with a brief introduction if listing multiple items

Answer:
"""
        
        answer = self.llm.invoke(prompt).content
        
        # ✅ ADD SOURCE ATTRIBUTION
        sources = []
        seen_sources = set()  # Avoid duplicate sources
        
        for doc in top_docs:
            # Get metadata
            file_name = doc.metadata.get('file_name', 'Unknown')
            department = doc.metadata.get('department', 'unknown').upper()
            source_type = doc.metadata.get('source_type', 'primary')
            
            # Format source based on type
            if source_type == 'secondary':
                # Secondary KB (approved feedback)
                source_text = f"💡 Knowledge Base (Admin Reviewed) - {department}"
            else:
                # Primary KB (uploaded documents)
                source_text = f"📄 {file_name} ({department})"
            
            # Avoid duplicates
            if source_text not in seen_sources:
                sources.append(source_text)
                seen_sources.add(source_text)
        
        # Append sources to answer (max 3 unique sources)
        if sources:
            answer += "\n\n" + "\n".join([f"<small>Source: {s}</small>" for s in sources[:3]])
        
        # Store in conversation history
        self.conversation_history.append((question, answer))
        
        # Keep only last 5 exchanges
        if len(self.conversation_history) > 5:
            self.conversation_history = self.conversation_history[-5:]
        
        return answer
    
    def _generate_no_confident_answer_response(self, question):
        """
        ✅ BUG #9 FIX: Response when no documents meet similarity threshold
        Prevents hallucinations from low-quality matches
        """
        return f"""I don't have confident information to answer your question accurately.

The available documents don't seem to closely match your query. To ensure I give you accurate information, I'd recommend:

1. Rephrasing your question with different keywords
2. Contacting our administrator at admin@starcement.co.in to add relevant documentation

I'd rather admit I don't know than provide potentially incorrect information!"""
    
    def _generate_no_data_response(self, question):
        """
        ADDED: Generate polite response when no relevant data is found
        """
        return f"""I apologize, but I don't have sufficient information in my current knowledge base to answer your question.

Please contact our administrator at admin@starcement.co.in to request the relevant documentation be added to the system.

Thank you for your patience!"""
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []