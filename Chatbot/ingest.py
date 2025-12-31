#!/usr/bin/env python3
import os
import subprocess
import glob
import json
import csv
import time
from typing import List
from multiprocessing import Pool
from tqdm import tqdm
from pathlib import Path
from dotenv import load_dotenv

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

# we switch from Chroma to FAISS
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
# we use pdfplumber that is already in ml environment
from langchain_community.document_loaders import PDFPlumberLoader, TextLoader, CSVLoader

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

persist_directory = "faiss_index" 
source_directory = "source_documents"

class MiniLMSentenceEmbeddings():
    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        batch_size = 32  
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            encoded_input = self.tokenizer(batch, padding=True, truncation=True, return_tensors='pt')
            
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            
            embeddings = self.mean_pooling(model_output, encoded_input['attention_mask'])
            normalized_embeddings = F.normalize(embeddings, p=2, dim=1)
            all_embeddings.extend(normalized_embeddings.tolist())
            
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        # Reuse document embedding logic for single user queries
        return self.embed_documents([text])[0]

    def mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


LOADER_MAPPING = {
    ".csv": (CSVLoader, {}),
    ".pdf": (PDFPlumberLoader, {}), 
    ".txt": (TextLoader, {"encoding": "utf8"}),
}

def load_single_document(file_path: str) -> List[Document]:
    # Logic to parse specific file types into LangChain Document objects.
    ext = "." + file_path.rsplit(".", 1)[-1]
    # handler for JSON files
    if ext == ".json":
        with open(file_path, 'r') as file:
            json_data = json.load(file)
        documents = []
        for idx, question_data in enumerate(json_data):
            content = f"question: {question_data.get('question','')}; answer: {question_data.get('answer','')}"
            metadata = {'source': os.path.basename(file_path), 'num': idx}
            documents.append(Document(page_content=content, metadata=metadata))
        return documents
    
    # parsing for Cadillac specific CSV datasets
    if os.path.basename(file_path) in ["car_model.csv", "important-cadillac-categories.csv"]:
        documents = []
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csvreader = csv.DictReader(csvfile)
            for row_number, row in enumerate(csvreader, start=1):
                if os.path.basename(file_path) == "car_model.csv":
                    content = f"Answer that respond {row.get('cadillac_car_model','')}: {row.get('introduction','')}"
                else:
                    content = f"{row.get('Introduction/examples','')} at link: {row.get('Link','')}"
                documents.append(Document(page_content=content, metadata={'source': os.path.basename(file_path), 'num': row_number}))
            return documents

    if ext in LOADER_MAPPING:
        loader_class, loader_args = LOADER_MAPPING[ext]
        loader = loader_class(file_path, **loader_args)
        return loader.load()
    return []

def main():
    # load emdedding model
    embeddings = MiniLMSentenceEmbeddings('embedding_model')
    

    all_files = []
    for ext in [".csv", ".pdf", ".txt", ".json"]:
        all_files.extend(glob.glob(os.path.join(source_directory, f"**/*{ext}"), recursive=True))
    
    print(f"Loading {len(all_files)} documents...")
    documents = []
    for f in all_files:
        try:
            documents.extend(load_single_document(f))
        except Exception as e:
            print(f"Error loading {f}: {e}")

    # Split documents into chunks. 
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    print(f"Split into {len(texts)} chunks.")

    # we no longer use sqllite so build the index directly in RAM
    print("Creating FAISS index...")
    vectorstore = FAISS.from_documents(texts, embeddings)
    
    # Save the vector index as a local binary file
    vectorstore.save_local(persist_directory)
    print(f"Success! FAISS index saved to {persist_directory}")

if __name__ == "__main__":
    main()
