from flask_login import UserMixin
from bson.objectid import ObjectId

class User(UserMixin):
    def __init__(self, user_data):
        # Map MongoDB's unique _id to Flask-Login's required string ID
        self.id = str(user_data["_id"])
        self.username = user_data["username"]
        self.password_hash = user_data["password"]

    @staticmethod
    def get_by_username(mongo_db, username):
        """Fetches a user from MongoDB by their username."""
        user_data = mongo_db.users.find_one({"username": username})
        if user_data:
            return User(user_data)
        return None

    @staticmethod
    def get_by_id(mongo_db, user_id):
        """Fetches a user from MongoDB by their unique ID."""
        try:
            user_data = mongo_db.users.find_one({"_id": ObjectId(user_id)})
            if user_data:
                return User(user_data)
        except Exception:
            return None
        return None