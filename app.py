from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
import openai
from elevenlabs import generate, set_api_key
import tempfile

load_dotenv()

app = Flask(__name__)

# API Keys from Render Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
eleven lab 

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json
        user_question = data.get("question", "")

        if not user_question:
            return jsonify({"error": "No question provided"}), 400

        # Get answer from OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are B.CORP Engineering Agent. Give clear, technical answers."},
                {"role": "user", "content": user_question}
            ]
        )

        answer = response.choices[0].message.content

        # Convert to speech with ElevenLabs
        audio = elevenlabs_client.generate(
            text=answer,
            voice="Rachel",
            model="eleven_multilingual_v2"
        )

        # Save temp audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            save(audio, fp.name)
            audio_path = fp.name

        return jsonify({
            "answer": answer,
            "audio_url": f"/audio/{os.path.basename(audio_path)}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
