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
import yt_dlp
import google.generativeai as genai
from models import User

# Whisper is too heavy for Free Render (512MB). We will try to load it safely.
try:
    import whisper
    print("Attempting to load Whisper AI...")
    ai_model = whisper.load_model("tiny") # Using 'tiny' instead of 'base' to save RAM
except Exception as e:
    ai_model = None
    print("Running in Lite Mode: Whisper disabled due to RAM limits.")

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "fallback_secret_key")

client = MongoClient(os.getenv("MONGO_URI"))
db = client.voice_notes_db 
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(db, user_id)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/")
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if db.users.find_one({"username": username}):
            flash("Username exists.", "error")
            return redirect(url_for('register'))
        db.users.insert_one({"username": username, "password": bcrypt.generate_password_hash(password).decode('utf-8')})
        flash("Success! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_data = db.users.find_one({"username": request.form.get("username")})
        if user_data and bcrypt.check_password_hash(user_data["password"], request.form.get("password")):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user_notes = list(db.notes.find({"user_id": current_user.id}).sort("timestamp", -1))
    return render_template("dashboard.html", username=current_user.username, notes=user_notes)

@app.route("/upload-audio", methods=["POST"])
@login_required
def upload_audio():
    if not ai_model:
        return jsonify({"success": False, "error": "Transcription is disabled on free-tier demo. Please use Gemini features!"})
    # ... (Rest of your upload logic remains same)
    return jsonify({"success": True, "text": "Demo Transcription"})

@app.route("/generate-study-pack/<note_id>", methods=["POST"])
@login_required
def generate_study_pack(note_id):
    try:
        note = db.notes.find_one({"_id": ObjectId(note_id), "user_id": current_user.id})
        prompt = f"Analyze and return JSON: {note.get('text', '')}"
        response = gemini_model.generate_content(prompt)
        study_data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
        db.notes.update_one({"_id": ObjectId(note_id)}, {"$set": {"study_pack": study_data}})
        return jsonify({"success": True})
    except:
        return jsonify({"success": False, "error": "AI Error"})

@app.route("/help")
def help_page(): return render_template("help.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)