import os
import time
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
import openai
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)  # Enable CORS for frontend requests
app.secret_key = "your-secret-key"  # Required for session storage

# OpenAI API Key (Stored securely as an environment variable)
openai.api_key = os.getenv("OPENAI_API_KEY")

# OpenAI Assistant ID (Replace with the correct one)
ASSISTANT_ID = "asst_BVHJcqvmsENpjqhBlHI07sre"

# Database file path
DB_FILE = "chat_history.db"

# Create database and table if they don't exist
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()  # Ensure the DB is set up when the server starts

# Serve the frontend
@app.route('/')
def serve_frontend():
    return send_from_directory("static", "index.html")

@app.route('/history-page')
def serve_history_page():
    return send_from_directory("static", "history.html")

# API Endpoint to process user questions and save to DB
@app.route('/ask', methods=['POST'])
def ask_hope_ai():
    try:
        data = request.json
        user_query = data.get("question")

        if not user_query:
            return jsonify({"error": "Question is required"}), 400

        print("Creating thread for conversation tracking...")

        # Create a new thread for each conversation
        thread = openai.beta.threads.create()

        # Send the user's question to the Assistant
        message = openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_query
        )

        print("Starting assistant run...")

        # Start an assistant run
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Wait for completion
        while run.status not in ["completed", "failed"]:
            time.sleep(2)  # Wait 2 seconds before checking again
            run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status == "failed":
            print("Assistant failed to generate a response.")
            return jsonify({"error": "Assistant failed to generate a response."})

        print("Retrieving assistant's response...")

        # Retrieve the assistant's response
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        answer = messages.data[0].content[0].text.value  # Extract the response

        # Save to SQLite database
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chat (question, answer) VALUES (?, ?)", (user_query, answer))
            conn.commit()

        return jsonify({"answer": answer})

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500

# API Endpoint to Retrieve Full Chat History (Sorted by Most Recent First)
@app.route('/history', methods=['GET'])
def get_chat_history():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Retrieve messages sorted by timestamp in descending order (most recent first)
        cursor.execute("SELECT question, answer, timestamp FROM chat ORDER BY datetime(timestamp) DESC")
        history = [{"question": row[0], "answer": row[1], "timestamp": row[2]} for row in cursor.fetchall()]
    return jsonify({"history": history})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)