import os

# Path to the fb_page_credentials.txt from this file's location
credentials_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'fb_page_credentials.txt'))

# Read the first line
with open(credentials_path, 'r') as file:
    lines = file.readlines()
    page_id = lines[0].strip()
    token = lines[1].strip()

print("Page ID:", page_id)
print("Token: ", token)