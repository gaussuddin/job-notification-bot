# === Flask Server for Render Keep-Alive & Status ===
import threading
from flask import Flask
from datetime import datetime

app = Flask(__name__)
last_check_time = None  # Track last check time

@app.route('/')
def home():
    return "✅ Job Notice Bot is Running!"

@app.route('/last-check')
def show_last_check():
    global last_check_time
    if last_check_time:
        return f"🕒 Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')}"
    return "❌ No check performed yet."

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

# === Rest of Your Code ===

import json
import os
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict, Any
from urllib.parse import urljoin
from urllib3.exceptions import InsecureRequestWarning
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from apscheduler.schedulers.background import BackgroundScheduler  # Added

from helpers_postgres import init_db, load_last_link, set_last_link, send_telegram_message, get_webdriver, close_webdriver

# Suppress insecure request warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

init_db()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

KEYWORDS = [
    "নিয়োগ", "চাকরি", "recruitment", "job", "নিয়োগে", "career", "opportunity"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def is_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS)

def extract_text_and_link(element: BeautifulSoup, base_url: str) -> Tuple[str, str]:
    text, link = "", ""
    a_tag = element if element.name == 'a' else element.find("a")

    if a_tag and a_tag.has_attr('href'):
        text = a_tag.get_text(strip=True)
        raw_link = a_tag.get("href")
        link = urljoin(base_url, raw_link) if raw_link and not raw_link.startswith(("http://", "https://", "javascript:")) else raw_link
    else:
        text = element.get_text(strip=True)

    return text.strip(), link if link else ""

def fetch_site_data(site: Dict[str, Any]) -> List[Tuple[str, str]]:
    notices = []
    site_name = site.get("name", "Unknown Site")
    site_url = site["url"]
    site_selector = site["selector"]
    site_base_url = site.get("base_url", site_url)
    selenium_enabled = site.get("selenium_enabled", False)

    logging.info(f"Fetching data from {site_name} ({site_url}) using {'Selenium' if selenium_enabled else 'Requests'}")
    driver = None

    try:
        if selenium_enabled:
            driver = get_webdriver(browser=site.get("browser", "chrome"), headless=site.get("headless", True))
            if not driver:
                logging.error(f"Could not initialize Selenium WebDriver for {site_name}. Skipping.")
                return []

            driver.get(site_url)
            wait_time = site.get("wait_time", 15)
            parent_selector = site.get("parent_selector", site_selector)

            try:
                WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, site_selector)))
            except TimeoutException:
                if parent_selector and parent_selector != site_selector:
                    logging.warning(f"Trying fallback selector: {parent_selector}")
                    WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.CSS_SELECTOR, parent_selector)))
                else:
                    raise

            soup = BeautifulSoup(driver.page_source, "html.parser")

        else:
            response = requests.get(site_url, verify=False, timeout=20, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

        elements = soup.select(site_selector)

        if not elements:
            logging.warning(f"No elements found for selector '{site_selector}' on {site_name}.")
            return []

        for el in elements:
            text, link = extract_text_and_link(el, site_base_url)
            if text and is_relevant(text):
                notices.append((text, link))

    except Exception as e:
        logging.error(f"Error processing {site_name}: {e}", exc_info=True)
    finally:
        if driver:
            close_webdriver(driver)

    return notices

def check_all_sites():
    global last_check_time
    last_check_time = datetime.now()
    print(f"\n🕒 Checking all sites at {last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")

    config_path = "config.json"
    if not os.path.exists(config_path):
        logging.error(f"Config file not found: {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config.json: {e}")
        return

    for site in config:
        site_id = site.get("id")
        site_name = site.get("name", site_id)
        if not site_id:
            logging.warning(f"Skipping site due to missing 'id': {site_name}")
            continue

        notices = fetch_site_data(site)
        if not notices:
            logging.info(f"No relevant notices for {site_name}")
            continue

        last_seen_id = load_last_link(site_id)
        new_notices, found_last_seen = [], False

        for text, link in notices:
            current_id = link if link else text
            if current_id == last_seen_id and last_seen_id:
                found_last_seen = True
                break
            new_notices.append((text, link))

        if found_last_seen:
            new_notices.reverse()

        if not new_notices:
            logging.info(f"No new notices for {site_name}")
            continue

        for text, link in new_notices:
            msg = f"*{site_name}*\n\n{text}"
            if link:
                msg += f"\n\n[ডাউনলোড/বিস্তারিত]({link})"
            send_telegram_message(msg)
            logging.info(f"Sent Telegram message for {site_name}: {text}")

        latest_id = notices[0][1] if notices[0][1] else notices[0][0]
        set_last_link(site_id, latest_id)
        logging.info(f"Updated last seen ID for {site_name} to: {latest_id}")

# === Scheduler: Run every 1 hour ===
scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Dhaka"))
scheduler.add_job(check_all_sites, 'interval', minutes=60)
scheduler.start()

# ✅ Run once after deploy
check_all_sites()

# Prevent exit
import time
while True:
    time.sleep(60)
