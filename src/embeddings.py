from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from config import Config

class EmbeddingPipeline:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,      # Reduced from 1000 for faster processing
            chunk_overlap=100    # Reduced from 200
        )
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            chunk_size=16  # Process embeddings in batches of 16
        )
    
    def process(self, documents):
        chunks = self.splitter.split_documents(documents)
        texts = [c.page_content for c in chunks]
        vectors = self.embeddings.embed_documents(texts)
        return chunks, vectors