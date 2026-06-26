from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import os
from groq import Groq
from gtts import gTTS
import hashlib
from config import config

app = Flask(__name__, template_folder="templates")

# Render uses /tmp for writable files
AUDIO_DIR = "/tmp/bcorp_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Configure Groq - FREE, no billing
client = Groq(api_key=config.GROQ_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json
        user_question = data.get("question", "").strip()
        memory = data.get("memory", []) # Get memory from frontend

                # Build messages with memory + system prompt - FIXED FOR PRO SPELLING
        system_prompt = """You are BCorp Tech AI, a professional engineer and teacher.
        Rules:
        1. Use correct English grammar and spelling always
        2. Add space after markdown symbols: ### Heading, **bold**, *italic*
        3. Put space between words and code: "In Python" not "InPython"
        4. Be clear, helpful, professional tone
        5. Use Pidgin only if user uses it first"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(memory) # Add old chat
        messages.append({"role": "user", "content": user_question})

        def generate():
            # Stream from Groq - FIXED TEMPERATURE FOR NATURAL WRITING
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=800, # Increased from 500 for better answers
                temperature=0.6, # Changed from 0.3. Higher = more natural, better spacing
                stream=True
            )

            full_answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content

                    # FIX: Add space after markdown symbols if missing
                    text = text.replace('###', '### ').replace('**', '** ').replace('*', '* ')
                    text = text.replace('InPython', 'In Python').replace('da difference', 'the difference')

                    full_answer += text
                    yield f"data: {text}\n\n" # Send chunk fast to browser
        
            # After stream done, save memory + generate audio
            memory.append({"role": "user", "content": user_question})
            memory.append({"role": "assistant", "content": full_answer})

            # Generate audio after full answer
            audio_url = generate_audio(full_answer)
            if audio_url:
                yield f"data: [AUDIO]{audio_url}\n\n" # Send audio url at end

            yield f"data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/explain-tech", methods=["POST"])
def explain_tech():
    try:
        topic = request.form.get("topic", "").strip()
        file = request.files.get("file")

        if not file and not topic:
            return jsonify({"error": "Upload image or send topic"}), 400

        if file and file.filename:
            # Groq doesn't do image yet, so we describe
            explanation = "Image analysis not available on free tier yet. Please describe the component in text for now. E.g: 'Black cylinder with 3 terminals labeled L1 L2 L3'"
        else:
            prompt = f"Explain '{topic}' as B.CORP Engineering Agent for Nigeria. Cover: what it is, how it works, key components, applications, safety. Use professional technical English. Max 6 sentences."

            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                max_tokens=500,
                temperature=0.3
            )
            explanation = chat_completion.choices[0].message.content

        audio_url = generate_audio(explanation)

        return jsonify({
            "answer": explanation,
            "audio_url": audio_url,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_audio(text: str):
    """gTTS - Google Text-to-Speech, 100% free"""
    try:
        file_hash = hashlib.md5(text.encode()).hexdigest()[:10]
        filename = f"audio_{file_hash}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        if not os.path.exists(filepath):
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(filepath)

        return f"/audio/{filename}"
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
