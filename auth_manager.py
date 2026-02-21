import json
import os
import hashlib

USER_DB = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_user(user_id, password):
    if not os.path.exists(USER_DB): return False
    with open(USER_DB, "r") as f:
        users = json.load(f)
    return users.get(user_id) == hash_password(password)

def register_user(user_id, password):
    users = {}
    if os.path.exists(USER_DB):
        with open(USER_DB, "r") as f: users = json.load(f)
    if user_id in users: return False
    users[user_id] = hash_password(password)
    with open(USER_DB, "w") as f: json.dump(users, f)
    return True