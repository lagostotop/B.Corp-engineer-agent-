from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import openai
from elevenlabs.client import ElevenLabs
from elevenlabs import save
import base64
import hashlib

app = Flask(__name__, template_folder="templates")

# Render Environment Variables - no load_dotenv needed
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not OPENAI_API_KEY or not ELEVENLABS_API_KEY:
    raise ValueError("b.corp ERROR: OPENAI_API_KEY or ELEVENLABS_API_KEY missing in Render env vars")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Render uses /tmp for writable files. Audio deletes after restart - normal for v1
AUDIO_DIR = "/tmp/bcorp_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    """
    Handle text question from user
    Returns: answer + audio_url
    """
    try:
        data = request.json
        user_question = data.get("question", "").strip()

        if not user_question:
            return jsonify({"error": "No question provided"}), 400

        # Get answer from OpenAI - professional English for b.corp Nigeria
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are B.CORP Engineering Agent for Nigeria. Provide clear, accurate, technical explanations for engineers. Use professional English. Max 6 sentences."},
                {"role": "user", "content": user_question}
            ],
            max_tokens=500
        )

        answer = response.choices[0].message.content

        # Convert to speech with ElevenLabs
        audio_url = generate_audio(answer)

        return jsonify({
            "answer": answer,
            "audio_url": audio_url,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/explain-tech", methods=["POST"])
def explain_tech():
    """
    NEW: Handle image upload + text topic
    User uploads tech image OR types topic
    Returns: explanation + audio_url
    """
    try:
        topic = request.form.get("topic", "").strip()
        file = request.files.get("file")

        if not file and not topic:
            return jsonify({"error": "Upload image or send topic"}), 400

        # Case 1: Image uploaded
        if file and file.filename:
            image_bytes = file.read()
            image_b64 = base64.b64encode(image_bytes).decode()

            prompt = (
                "You are B.CORP Engineering Agent for Nigeria. "
                "Analyze this technical device/component image. "
                "Identify it, explain how it works, key parts, common failures, safety notes. "
                "Use professional technical English. Max 6 sentences."
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "content": {"image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}}
                    ]
                }],
                max_tokens=500
            )
            explanation = response.choices[0].message.content

        # Case 2: Text topic only
        else:
            prompt = (
                f"Explain '{topic}' as B.CORP Engineering Agent for Nigeria. "
                "Cover: what it is, how it works, key components, applications, safety. "
                "Use professional technical English. Max 6 sentences."
            )
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            explanation = response.choices[0].message.content

        # Generate voice
        audio_url = generate_audio(explanation)

        return jsonify({
            "answer": explanation,
            "audio_url": audio_url,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_audio(text: str):
    """Generate MP3 with ElevenLabs and save to /tmp/"""
    try:
        # Use hash so same text = same file, saves API credits
        file_hash = hashlib.md5(text.encode()).hexdigest()[:10]
        filename = f"audio_{file_hash}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        # Only generate if file doesn't exist
        if not os.path.exists(filepath):
            audio = elevenlabs_client.generate(
                text=text,
                voice="Rachel",
                model="eleven_multilingual_v2"
            )
            save(audio, filepath)

        return f"/audio/{filename}"
    except Exception:
        return None

@app.route("/audio/<filename>")
def serve_audio(filename):
    """Serve audio files from /tmp/bcorp_audio/"""
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
