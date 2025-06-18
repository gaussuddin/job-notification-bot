import os
import psycopg2
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Bot

# PostgreSQL connection setup from environment variables
PG_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(PG_URL)

def init_db():
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
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT link FROM last_seen WHERE site = %s", (site,))
            row = cur.fetchone()
            return row[0] if row else None

def set_last_link(site, link):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO last_seen (site, link) VALUES (%s, %s) ON CONFLICT (site) DO UPDATE SET link = EXCLUDED.link",
                (site, link)
            )
            conn.commit()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

def send_telegram_message(message: str):
    # Markdown বাদ দিয়ে সোজা টেক্সট পাঠানো হচ্ছে
    bot.send_message(chat_id=CHAT_ID, text=message)

# Selenium WebDriver
def get_webdriver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

def close_webdriver(driver):
    try:
        driver.quit()
    except Exception:
        pass
