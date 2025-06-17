import sqlite3
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from telegram import Bot

# === SQLite Setup ===
DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite3")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS last_seen (site TEXT PRIMARY KEY, link TEXT)")

def load_last_link(site):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT link FROM last_seen WHERE site = ?", (site,))
        row = cursor.fetchone()
        return row[0] if row else None

def set_last_link(site, link):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("REPLACE INTO last_seen (site, link) VALUES (?, ?)", (site, link))

# === Telegram ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8147310659:AAFU7HA_vb7UbFCjGUboUOmZ578JjUQMzNE")  # Replace with real token in environment
CHAT_ID = os.getenv("CHAT_ID", "5247051269")

bot = Bot(token=BOT_TOKEN)

def send_telegram_message(message: str):
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

# === Selenium WebDriver ===
def get_webdriver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service()
    return webdriver.Chrome(service=service, options=chrome_options)

def close_webdriver(driver):
    try:
        driver.quit()
    except Exception:
        pass