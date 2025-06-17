from urllib.parse import quote_plus
from pymongo import MongoClient
import streamlit as st

mongo_secrets = st.secrets["mongodb"]

# Username und Passwort URL-kodieren
MONGO_USERNAME = quote_plus(mongo_secrets["MONGO_USERNAME"])
MONGO_PASSWORD = quote_plus(mongo_secrets["MONGO_PASSWORD"])
MONGO_CLUSTER = mongo_secrets["MONGO_CLUSTER"]

# Verbindungs-URI zusammensetzen
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER}/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["Wuzzelapp"]
collection = db["Wuzzelapp_2"]

def load_data():
    data = collection.find_one({"_id": "app_state"})
    if data:
        return data["data"]
    return {"tournaments": {}, "current_tournament": None}

def save_data(data):
    collection.update_one(
        {"_id": "app_state"},
        {"$set": {"data": data}},
        upsert=True
    )
