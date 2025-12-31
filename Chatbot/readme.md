# NCDB Chatbot System

This project is a RAG chatbot designed for the Cadillac V16 Registry. It is built to run efficiently in Machine Learning environments.
cd /home/ncdbproj/NCDBContent/Chatbot/
source /home/metacomp/python_virtualenv/py3.11.4_ml/bin/activate
python get_llm_answer.py

## System Architecture
The system uses a Socket Server design. The AI model and database stay loaded in a background process (Server), while the Django website acts as a lightweight Client. 

### 1. ingest.py in /home/ncdbproj/NCDBContent/Chatbot/
Processes source documents (PDF, CSV, JSON, TXT) into a searchable format. Migrated from ChromaDB to FAISS to remove SQLite dependencies. 
It chunks text and converts it into vectors using the MiniLM model.

### 2. get_llm_answer.py in /home/ncdbproj/NCDBContent/Chatbot/
The main Socket Server hub. It loads the FLAN-T5-base model and FAISS index once at startup. It keeps the model in memory to avoid reloading delays and listens for queries on port 12345.

### 3. llm.py in /home/ncdbproj/NCDBContent/Chatbot/
The core intelligence logic which filters user intent and performs semantic searches. 
It includes specific instructions to ensure the AI focuses on V16 history (1930-1940) and ignores irrelevant data.

### 4. views.py (Django) 
It's located in /home/ncdbproj/CadillacDBProj/Chatbot/
The web interface controller that connects the website to the AI backend.
We removed AI libraries from Django to prevent crashes. It now simply sends strings to the socket server and displays the result.

## Setup Instructions
1. Run `python ingest.py` to build the knowledge index.
2. Run `python get_llm_answer.py` to start the AI service.
3. Run `python manage.py runserver` to start the website.
