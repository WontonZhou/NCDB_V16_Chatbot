import os
import re
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

#Configuration
KB_DIR = os.environ.get("KB_DIR", "/home/metacomp/NCDBContent/CDB/Dbas_txt/")
LLM_MODEL = os.environ.get("LLM_MODEL", "google/flan-t5-base")
RETRIEVAL_THRESHOLD = 0.05
TOP_K = 5

# LIMITED the size chunk to the llm
MAX_CHARS_PER_CHUNK = 500

_MODEL = None
_TOKENIZER = None

#Greeting Keywords
_GREETINGS = (
    "hi", "hello", "hey",
    "how are you", "how r u",
    "what's up", "whats up",
    "thanks", "thank you",
)

# Mandatory Main Keywords
_DOMAIN_HINTS = (
    "cadillac", "v16", "v-16", "v 16", "fleetwood", "fisher",
    "coachbuilder", "body style", "body styles", "style", "chassis", "engine",
    "town car", "phaeton", "touring", "limousine", "sedan", "coupe", "landaulet",
)

def is_greeting(q: str) -> bool:
    ql = (q or "").strip().lower()
    return any(ql == g or ql.startswith(g) for g in _GREETINGS)

def is_domain_question(q: str) -> bool:
    ql = (q or "").strip().lower()
    if not ql: return False
    return any(h in ql for h in _DOMAIN_HINTS)

#Extract the docusments and clean text
def clean_text(t: str) -> str:
    t = (t or "").replace("&nbsp;", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def get_llm():
    global _MODEL, _TOKENIZER
    if _MODEL is not None and _TOKENIZER is not None:
        return _MODEL, _TOKENIZER
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _TOKENIZER = AutoTokenizer.from_pretrained(LLM_MODEL)
    _MODEL = AutoModelForSeq2SeqLM.from_pretrained(LLM_MODEL).to(device)
    _MODEL.eval()
    return _MODEL, _TOKENIZER


@torch.inference_mode()
def polish_with_llm(question: str, context_text: str) -> str:
    model, tok = get_llm()
    prompt = f"""
Read the context carefully. It contains historical facts about Cadillac cars. 
Your task is to answer the question specifically about the Cadillac V16 (produced 1930-1940).
If the context mentions other models like Eldorados or years after 1940, IGNORE them.

Context: {context_text} 
Question: {question} 

Answer (focused ONLY on V16):""".strip()
    inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    out = model.generate(
        **inputs,
        max_new_tokens=150,
        do_sample=False,
        num_beams=4,
        repetition_penalty=2.5, 
    )
    text = tok.decode(out[0], skip_special_tokens=True).strip()
    
    if text.lower().strip("?") == question.lower().strip("?"):
        return "I am sorry, I could not find specific details about that in the database."
    return text if len(text) > 3 else "I do not know."


@torch.inference_mode()
def generate_reply(user_text: str, db=None) -> str: 
    q = (user_text or "").strip()

    if is_greeting(q):
        return "Hi! I'm the NCDB chatbot. I'm doing well, how can I help you today?"

    if not is_domain_question(q):
        return "Hi! I specialize in Cadillac V16 (1930-1940) questions. Feel free to ask about history, styles, or engines."


    if db is None:
        return "Error: Knowledge base (FAISS) not loaded."


    raw_hits = db.similarity_search(q, k=TOP_K)
    
    v16_hits = []
    for doc in raw_hits:
        content = doc.page_content.lower()
        if "v16" in content or "v-16" in content or "sixteen" in content:
            v16_hits.append(doc)
            
    final_hits = v16_hits[:2] if v16_hits else raw_hits[:2]

    if not final_hits:
        return "I am sorry, I do not have enough information."

    blocks = []
    for doc in final_hits:
        cleaned_content = clean_text(doc.page_content)
        source = doc.metadata.get('source', 'Unknown Document')
        blocks.append(f"[Source: {source}]: {cleaned_content[:MAX_CHARS_PER_CHUNK]}")

    full_context = "\n\n".join(blocks)
    return polish_with_llm(q, full_context)
