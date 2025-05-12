import os
import time
import uuid
import pickle
import fitz  # PyMuPDF
import cloudinary
import cloudinary.api
import psycopg2
import requests
from docx import Document
from docx import Document
from pdfminer.high_level import extract_text as extract_pdf_text
from dotenv import load_dotenv
from datetime import datetime
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# Load .env variables
load_dotenv()

# Init Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Init Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

# Hugging Face model
embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Establish PostgreSQL Connection
db_conn = psycopg2.connect(os.getenv("DATABASE_URL"))
db_conn.autocommit = True
cursor = db_conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    title TEXT,
    url TEXT,
    file_type TEXT,
    content TEXT,
    uploaded_at TIMESTAMP
)
""")

# Cache file path
CACHE_FILE = 'vector_cache.pkl'

# Load existing cache or initialize empty
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'rb') as f:
        vector_cache = pickle.load(f)
else:
    vector_cache = {}

def extract_text_from_file(file_path, file_type):
    try:
        if file_type == 'pdf':
            try:
                doc = fitz.open(file_path)
                text = "\n".join([page.get_text() for page in doc])
                if text.strip():
                    print(f"[✓] Extracted PDF text using PyMuPDF: {file_path}")
                    return text
                else:
                    raise ValueError("Empty text from PyMuPDF")
            except Exception as mupdf_error:
                print(f"[!] PyMuPDF failed, trying pdfminer: {mupdf_error}")
                try:
                    text = extract_pdf_text(file_path)
                    print(f"[✓] Extracted PDF text using pdfminer: {file_path}")
                    return text
                except Exception as pdfminer_error:
                    print(f"[ERROR] Both PDF parsers failed: {pdfminer_error}")
                    return ""

        elif file_type == 'docx':
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            print(f"[✓] Extracted DOCX text: {file_path}")
            return text

        elif file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                print(f"[✓] Extracted TXT text: {file_path}")
                return text

    except Exception as e:
        print(f"[ERROR] Failed to extract text from {file_type.upper()} '{file_path}': {e}")
        return ""

def fetch_cloudinary_files():
    return cloudinary.api.resources(type='upload', resource_type='image', prefix='', max_results=100)['resources']

def already_processed(file_url):
    cursor.execute("SELECT 1 FROM documents WHERE url = %s", (file_url,))
    return cursor.fetchone() is not None

def process_file(file):
    file_url = file['secure_url']
    file_name = file['public_id'].split('/')[-1]
    file_ext = file['format'].lower()

    if file_ext not in ['pdf', 'docx', 'txt'] or already_processed(file_url):
        return

    temp_filename = f"temp_{uuid.uuid4()}.{file_ext}"
    r = requests.get(file_url)
    with open(temp_filename, 'wb') as f:
        f.write(r.content)

    text = extract_text_from_file(temp_filename, file_ext)
    os.remove(temp_filename)

    file_id = str(uuid.uuid4())
    uploaded_at = datetime.now()

    # Save to DB
    cursor.execute("""
    INSERT INTO documents (id, title, url, file_type, content, uploaded_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    """, (file_id, file_name, file_url, file_ext, text, uploaded_at))

    # Embed & store in Pinecone
    embedding = embedder.encode(text[:3000])  # Truncate for safety
    pinecone_index.upsert([(file_id, embedding.tolist(), {"title": file_name, "url": file_url})])

    # Update cache
    vector_cache[file_id] = {
        "embedding": embedding,
        "title": file_name,
        "url": file_url,
        "text": text
    }

    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(vector_cache, f)

    print(f"[+] Processed and cached: {file_name}")

# Loop Forever
if __name__ == "__main__":
    print("[~] Worker started. Checking Cloudinary every 10 seconds.")
    while True:
        try:
            files = fetch_cloudinary_files()
            for file in files:
                process_file(file)
        except Exception as e:
            print("❌ Error:", e)
        time.sleep(10)
