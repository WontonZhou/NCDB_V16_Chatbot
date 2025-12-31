import time
import os
import logging
import numpy as np
import socket
import signal
import subprocess
import transformers
from dotenv import load_dotenv
from ingest import MiniLMSentenceEmbeddings
from langchain_community.vectorstores import FAISS
from llm import generate_reply

# Original version used Chroma which dependended on sqlite3 so we migrated to FAISS
# We moved the RAG logic into llm.py.

HOST = 'localhost'
PORT = 12345
load_dotenv()

# setting logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# the LLM and Tokenizer are loaded once at startup and kept in memory for server based architecture
model_name = "Google/flan-t5-base"
tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)
model = transformers.AutoModelForSeq2SeqLM.from_pretrained(model_name)

# load FAISS with custom MiniLM embeddings
embeddings_model = MiniLMSentenceEmbeddings('embedding_model')
if os.path.exists("faiss_index"):
    #  loading local pickle based FAISS files
    db = FAISS.load_local("faiss_index", embeddings_model.embed_query, allow_dangerous_deserialization=True)
    print("FAISS index loaded successfully.")
else:
    db = None
    print("Warning: No FAISS index found. Run ingest.py first.")

def delRunningProcess():
    # ensure only one instance of the server runs at a time
    process_name = "get_llm_answer.py"
    try:
        output = subprocess.check_output(f"ps aux | grep {process_name} | grep -v grep", shell=True, text=True)
        for line in output.strip().split('\n'):
            pid = int(line.split()[1])
            if pid != os.getpid():
                os.kill(pid, signal.SIGTERM)
    except:
        pass

if __name__ == "__main__":
    delRunningProcess()
     # Added SO_REUSEADDR to allow the server to restart immediately without waiting clearing the socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Chatbot server started on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            with conn:
                 # Receive the query from the Django client
                query = conn.recv(1024).decode('utf-8')
                if not query:
                    break
                print(f"Query received: {query}")
                
                # call generate_reply which handles context retrieval and polishing.
                response = generate_reply(query, db=db) 
                # Send the generated answer back to Django
                conn.sendall(response.encode('utf-8'))