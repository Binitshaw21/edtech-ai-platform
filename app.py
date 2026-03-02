import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
import google.generativeai as genai
from models import User

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "8f4e9a2b7c6d1f3e5a8b9c0d2e4f6a7b")

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

# Gemini Config
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# --- ALL ENDPOINTS (MUST MATCH YOUR HTML) ---

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if db.users.find_one({"username": username}):
            flash("Username exists.", "error")
            return redirect(url_for('register'))
        db.users.insert_one({"username": username, "password": bcrypt.generate_password_hash(password).decode('utf-8')})
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_data = db.users.find_one({"username": request.form.get("username")})
        if user_data and bcrypt.check_password_hash(user_data["password"], request.form.get("password")):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        flash("Invalid login.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user_notes = list(db.notes.find({"user_id": current_user.id}).sort("timestamp", -1))
    return render_template("dashboard.html", username=current_user.username, notes=user_notes)

@app.route("/settings")
@login_required
def settings():
    notes_count = db.notes.count_documents({"user_id": current_user.id})
    return render_template("settings.html", username=current_user.username, notes_count=notes_count)

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/generate-study-pack/<note_id>", methods=["POST"])
@login_required
def generate_study_pack(note_id):
    # (Kept simple for demo stability)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)