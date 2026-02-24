from src.data_loader import load_documents
from src.embeddings import EmbeddingPipeline
from src.vectorstore import FaissStore

# Load docs
docs = load_documents("uploads/it")

pipeline = EmbeddingPipeline()

# Split only (no bulk embedding)
chunks = pipeline.splitter.split_documents(docs)

print("Total chunks:", len(chunks))
print("\n--- SAMPLE CHUNK TEXT ---")
print(chunks[0].page_content)

print("\n--- METADATA ---")
print(chunks[0].metadata)

# ONE embedding call only
vector = pipeline.embeddings.embed_query(chunks[0].page_content)

print("\n--- VECTOR INFO ---")
print("Vector length:", len(vector))
print("First 10 values:", vector[:10])
