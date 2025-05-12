from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2
from pinecone import Pinecone
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
model = SentenceTransformer('all-MiniLM-L6-v2') 

app = Flask(__name__)
CORS(app)

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))


def embed_text(text):
    return model.encode(text).tolist()


@app.route("/search", methods=["POST"])
def search_documents():
    user_input = request.json.get("query")
    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # Step 1: Embed query
    try:
        query_vector = embed_text(user_input)
    except Exception as e:
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500

    # Step 2: Pinecone search
    try:
        search_results = pinecone_index.query(vector=query_vector, top_k=10, include_metadata=True)
    except Exception as e:
        return jsonify({"error": f"Pinecone query failed: {str(e)}"}), 500

    matches = search_results.get("matches", [])

    # Step 3: Fetch metadata from Postgres
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cursor = conn.cursor()
        document_ids = [match['id'] for match in matches]

        cursor.execute(
            f"SELECT id, title, url, file_type FROM documents WHERE id = ANY(%s::UUID[])",
            (document_ids,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    id_to_meta = {str(row[0]): {"title": row[1], "url": row[2], "type": row[3]} for row in rows}

    # Step 4: Format response
    documents = []
    for match in matches:
        doc_id = str(match["id"])
        if doc_id in id_to_meta:
            documents.append({
                "score": match["score"],
                "id": doc_id,
                "title": id_to_meta[doc_id]["title"],
                "url": id_to_meta[doc_id]["url"],
                "type": id_to_meta[doc_id]["type"]
            })

    return jsonify({
        "message": "Here's what I found:",
        "results": documents[:10],       # top 1
        "more": documents[10:]           # remaining up to 50
    })

if __name__ == "__main__":
    app.run(debug=True)