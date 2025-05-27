# utils/fb_data.py (create this file or put in an existing utils module)
import json

FB_DATA_PATH = "fb_data.json"

def load_fb_data():
    with open(FB_DATA_PATH, "r") as file:
        return json.load(file)

def save_fb_data(data):
    with open(FB_DATA_PATH, "w") as file:
        json.dump(data, file, indent=2)
