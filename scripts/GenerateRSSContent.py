import hashlib
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from feedgen.feed import FeedGenerator

URL = "https://sta-russell.cdsbeo.on.ca/apps/news/"
HASH_FILE = "data/last_hash.txt"
RSS_FILE = "public/rss.xml"

def normalize(text: str) -> str:
    return " ".join(text.split())

def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

os.makedirs("data", exist_ok=True)
os.makedirs("public", exist_ok=True)

res = requests.get(
    URL,
    headers={"User-Agent": "RSS-Monitor/1.0"},
    timeout=15
)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

# 🔑 target stable content only
main = soup.find("main")
content = normalize(main.get_text()) if main else normalize(soup.get_text())

new_hash = hash_content(content)
old_hash = None

if os.path.exists(HASH_FILE):
    old_hash = open(HASH_FILE).read().strip()

if new_hash == old_hash:
    print("No change detected")
    exit(0)

print("Change detected!")

# Save new hash
with open(HASH_FILE, "w") as f:
    f.write(new_hash)

# Create or update RSS
fg = FeedGenerator()
fg.title("Change Monitor Feed")
fg.link(href="https://dustindoucette.github.io/Demo-RSS-Feed", rel="alternate")
fg.description("Updates only when content changes")

fe = fg.add_entry()
fe.title("Content Updated")
fe.link(href=URL)
fe.description(content[:1000] + "…")
fe.pubDate(datetime.utcnow())

fg.rss_file(RSS_FILE)
