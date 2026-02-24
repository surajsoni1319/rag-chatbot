from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, CSVLoader, Docx2txtLoader
)

def load_documents(folder_path):
    documents = []
    for file in Path(folder_path).glob("*"):
        if file.suffix == ".pdf":
            documents.extend(PyPDFLoader(str(file)).load())
        elif file.suffix == ".txt":
            documents.extend(TextLoader(str(file)).load())
        elif file.suffix == ".csv":
            documents.extend(CSVLoader(str(file)).load())
        elif file.suffix == ".docx":
            documents.extend(Docx2txtLoader(str(file)).load())
    return documents