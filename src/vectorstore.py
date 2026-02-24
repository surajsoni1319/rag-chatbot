import faiss, os, pickle
import numpy as np

class FaissStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(path, exist_ok=True)
    
    def build(self, vectors, documents):
        # Convert to numpy array first
        vectors = np.array(vectors, dtype='float32')
        
        dim = vectors.shape[1]  # Use shape instead of len
        self.index = faiss.IndexFlatIP(dim)
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        
        with open(f"{self.path}/meta.pkl", "wb") as f:
            pickle.dump(documents, f)
        faiss.write_index(self.index, f"{self.path}/index.faiss")
    
    def load(self):
        self.index = faiss.read_index(f"{self.path}/index.faiss")
        with open(f"{self.path}/meta.pkl", "rb") as f:
            self.docs = pickle.load(f)
    
    def search(self, query_vector, k=5):
        # Convert query to numpy array and reshape
        query_vector = np.array([query_vector], dtype='float32')
        faiss.normalize_L2(query_vector)
        _, I = self.index.search(query_vector, k)
        return [self.docs[i] for i in I[0]]