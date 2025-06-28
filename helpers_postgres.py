import os
import psycopg2
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Bot

# === Database connection ===
PG_URL = os.getenv("DATABASE_URL")

def get_connection():
    if not PG_URL:
        raise ValueError("DATABASE_URL environment variable not set.")
    return psycopg2.connect(PG_URL)

def init_db():
    """Initialize last_seen table if not exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS last_seen (
                    site TEXT PRIMARY KEY,
                    link TEXT
                )
            """)
            conn.commit()

def load_last_link(site):
    """Load last seen link for a site."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT link FROM last_seen WHERE site = %s", (site,))
            row = cur.fetchone()
            return row[0] if row else None

def set_last_link(site, link):
    """Set or update last seen link for a site."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO last_seen (site, link)
                VALUES (%s, %s)
                ON CONFLICT (site) DO UPDATE SET link = EXCLUDED.link
                """,
                (site, link)
            )
            conn.commit()

def clear_all_last_links():
    """Clear all saved last_seen data."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM last_seen")
            conn.commit()

# === Telegram ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN or CHAT_ID environment variable not set.")

bot = Bot(token=BOT_TOKEN)

def send_telegram_message(message: str):
    """Send a Telegram message without Markdown to avoid formatting issues."""
    bot.send_message(chat_id=CHAT_ID, text=message)

# === Selenium WebDriver ===
def get_webdriver(headless=True) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(options=chrome_options)

def close_webdriver(driver):
    """Close WebDriver safely."""
    try:
        driver.quit()
    except Exception:
        pass
