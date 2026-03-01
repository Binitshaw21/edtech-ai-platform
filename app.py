import os
import tempfile
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
import whisper
import yt_dlp
import google.generativeai as genai
from models import User

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "fallback_secret_key")

# Database Setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client.voice_notes_db 

# Security Setup
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(db, user_id)

# --- LOAD AI MODELS ---
print("Loading Whisper AI Model...")
ai_model = whisper.load_model("base") 

print("Configuring Google Gemini...")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-2.5-flash')
print("All systems ready!")

# --- ROUTES ---

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if db.users.find_one({"username": username}):
            flash("Username already exists.", "error")
            return redirect(url_for('register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        db.users.insert_one({"username": username, "password": hashed_password})
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_data = db.users.find_one({"username": username})
        
        if user_data and bcrypt.check_password_hash(user_data["password"], password):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user_notes = list(db.notes.find({"user_id": current_user.id}).sort("timestamp", -1))
    return render_template("dashboard.html", username=current_user.username, notes=user_notes)

# --- NEW: SETTINGS & ACCOUNT ROUTE ---
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        
        user_data = db.users.find_one({"_id": ObjectId(current_user.id)})
        
        if bcrypt.check_password_hash(user_data["password"], current_password):
            hashed_new = bcrypt.generate_password_hash(new_password).decode('utf-8')
            db.users.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"password": hashed_new}})
            flash("Password updated successfully!", "success")
        else:
            flash("Incorrect current password.", "error")
            
        return redirect(url_for('settings'))
        
    # Get stats for the dashboard
    notes_count = db.notes.count_documents({"user_id": current_user.id})
    return render_template("settings.html", username=current_user.username, notes_count=notes_count)

# --- 1. HANDLE MIC & FILE UPLOADS ---
@app.route("/upload-audio", methods=["POST"])
@login_required
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({"success": False, "error": "No media file received"})
        
    audio_file = request.files['audio']
    ext = os.path.splitext(audio_file.filename)[1] or ".webm"
        
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"temp_media_{current_user.id}{ext}")
    audio_file.save(temp_path)
    
    try:
        result = ai_model.transcribe(temp_path)
        transcription_text = result["text"].strip()
        
        if transcription_text:
            db.notes.insert_one({
                "user_id": current_user.id,
                "text": transcription_text,
                "timestamp": datetime.utcnow().strftime("%B %d, %Y - %I:%M %p")
            })
            
        os.remove(temp_path)
        return jsonify({"success": True, "text": transcription_text})
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)})

# --- 2. HANDLE YOUTUBE LINKS ---
@app.route("/process-link", methods=["POST"])
@login_required
def process_link():
    data = request.get_json()
    url = data.get("url")
    
    if not url:
        return jsonify({"success": False, "error": "No URL provided"})
        
    temp_dir = tempfile.gettempdir()
    temp_filename = os.path.join(temp_dir, f"temp_yt_{current_user.id}.m4a")
    
    ydl_opts = {'format': 'm4a/bestaudio/best', 'outtmpl': temp_filename, 'quiet': True}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        result = ai_model.transcribe(temp_filename)
        transcription_text = result["text"].strip()
        
        if transcription_text:
            db.notes.insert_one({
                "user_id": current_user.id,
                "text": transcription_text,
                "timestamp": datetime.utcnow().strftime("%B %d, %Y - %I:%M %p")
            })
            
        if os.path.exists(temp_filename): os.remove(temp_filename)
        return jsonify({"success": True, "text": transcription_text})
    except Exception as e:
        if os.path.exists(temp_filename): os.remove(temp_filename)
        return jsonify({"success": False, "error": "Failed to process video."})

# --- 3. GENERATE STUDY MATERIALS ---
@app.route("/generate-study-pack/<note_id>", methods=["POST"])
@login_required
def generate_study_pack(note_id):
    try:
        note = db.notes.find_one({"_id": ObjectId(note_id), "user_id": current_user.id})
        if not note: return jsonify({"success": False, "error": "Note not found"})
            
        prompt = f"""
        Analyze the following lecture transcript and create a study pack. 
        Return ONLY a valid JSON object with exactly this structure:
        {{
            "summary": "A clear, 3-paragraph summary of the core concepts.",
            "flashcards": [{{"front": "Term", "back": "Definition"}}],
            "quiz": [{{"question": "What is...", "options": ["A", "B", "C", "D"], "answer": "The correct option string"}}]
        }}
        Transcript: {note.get("text", "")}
        """
        
        response = gemini_model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        study_data = json.loads(clean_json)
        
        db.notes.update_one({"_id": ObjectId(note_id)}, {"$set": {"study_pack": study_data}})
        return jsonify({"success": True, "message": "Study pack generated!"})
        
    except Exception as e:
        print(f"Gemini Error: {e}")
        return jsonify({"success": False, "error": "Failed to generate study materials."})

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
@app.route("/help")
def help_page():
    return render_template("help.html")

if __name__ == "__main__":
    app.run(debug=True)