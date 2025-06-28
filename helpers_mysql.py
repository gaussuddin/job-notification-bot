import os
import pymysql
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# === MySQL Configuration ===
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_DB = os.getenv("MYSQL_DB")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

def get_connection():
    if not all([MYSQL_HOST, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD]):
        raise ValueError("MySQL database credentials are missing.")
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS last_seen (
                    site VARCHAR(255) PRIMARY KEY,
                    link TEXT
                )
            """)
        conn.commit()

def load_last_link(site):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT link FROM last_seen WHERE site = %s", (site,))
            row = cur.fetchone()
            return row['link'] if row else None

def set_last_link(site, link):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO last_seen (site, link)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE link = VALUES(link)
            """, (site, link))
        conn.commit()

def clear_all_last_links():
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
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

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
    try:
        driver.quit()
    except Exception:
        pass
