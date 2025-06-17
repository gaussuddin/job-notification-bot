# main.py এর শুরুতে যোগ করুন:
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Job Notice Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

import json
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Dict, Any
import logging
from urllib.parse import urljoin
from urllib3.exceptions import InsecureRequestWarning
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Suppress only the InsecureRequestWarning from requests
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

from helpers_postgres import init_db, load_last_link, set_last_link, send_telegram_message, get_webdriver, close_webdriver

init_db()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

KEYWORDS = [
    "নিয়োগ", "বিজ্ঞপ্তি", "চাকরি", "recruitment", "job", "circular",
    "exam", "admit", "entry card", "প্রবেশপত্র", "ফলাফল", "result",
    "সংশোধনী", "corrigendum", "interview", "সাক্ষাৎকার", "seat plan", "যোগদান", "আসন বিন্যাস"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def is_relevant(text: str) -> bool:
    """Checks if the given text contains any of the defined keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORDS)

def extract_text_and_link(element: BeautifulSoup, base_url: str) -> Tuple[str, str]:
    """Extracts text and constructs an absolute URL from a BeautifulSoup element."""
    text = ""
    link = ""

    a_tag = element if element.name == 'a' else element.find("a")

    if a_tag and a_tag.has_attr('href'):
        text = a_tag.get_text(strip=True)
        raw_link = a_tag.get("href")
        if raw_link and not raw_link.startswith(("http://", "https://", "javascript:")):
            link = urljoin(base_url, raw_link)
        elif raw_link and raw_link.startswith("javascript:"):
            link = ""
        else:
            link = raw_link
    else:
        text = element.get_text(strip=True)

    return text.strip(), link if link else ""

def fetch_site_data(site: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Fetches and parses data from a given website based on its configuration."""
    notices = []
    site_name = site.get("name", "Unknown Site")
    site_url = site["url"]
    site_selector = site["selector"]
    site_base_url = site.get("base_url", site_url)
    selenium_enabled = site.get("selenium_enabled", False) # New flag

    logging.info(f"Fetching data from {site_name} ({site_url}) using {'Selenium' if selenium_enabled else 'Requests'}")

    driver = None
    try:
        if selenium_enabled:
            driver = get_webdriver(browser=site.get("browser", "chrome"), headless=site.get("headless", True))
            if not driver:
                logging.error(f"Could not initialize Selenium WebDriver for {site_name}. Skipping.")
                return []

            driver.get(site_url)
            
            # Wait for the elements to be present and visible. Adjust the timeout as needed.
            # Using presence_of_element_located on the parent container if multiple links are expected.
            # Then use find_elements on the located container.
            wait_time = site.get("wait_time", 15) # Default wait time in seconds, increased to 15
            
            # For sites like MOWCA, MOR, BPSC, we often wait for the table or a parent container to be present.
            # Then we can find the 'a' tags within that container.
            
            # Trying a more robust wait condition for the parent element of the notices
            parent_selector = site.get("parent_selector", site_selector) # New optional parent_selector
            
            # If site_selector directly points to 'a' tags, try to find a common parent for the wait.
            # For example, if site_selector is 'div.table-responsive table.table-striped tbody tr a',
            # parent_selector could be 'div.table-responsive table.table-striped tbody'
            try:
                # Wait for at least one element matching the main selector to be present
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, site_selector))
                )
            except TimeoutException:
                # If direct element not found, try waiting for a broader parent if defined
                if parent_selector and parent_selector != site_selector:
                    logging.warning(f"Direct selector '{site_selector}' timed out for {site_name}. Trying parent selector '{parent_selector}'.")
                    WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, parent_selector))
                    )
                else:
                    raise # Re-raise if no parent_selector or parent_selector is same as site_selector


            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

        else: # Use requests
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
            elif text:
                logging.debug(f"Skipping irrelevant notice from {site_name}: '{text}'")

    except TimeoutException:
        logging.error(f"Selenium: Timed out waiting for elements for {site_name} with selector '{site_selector}'. Please check the selector or increase wait_time.")
    except WebDriverException as e:
        logging.error(f"Selenium WebDriver error for {site_name}: {e}", exc_info=True)
    except requests.exceptions.RequestException as e:
        logging.error(f"Requests network error fetching {site_name}: {e}")
    except Exception as e:
        logging.error(f"Error processing {site_name}: {e}", exc_info=True)
    finally:
        if driver:
            close_webdriver(driver)
    
    return notices

def main():
    """Main function to load configuration, fetch data, and send notifications."""
    config_path = "config.json"
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found: {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading or parsing config.json: {e}")
        return

    for site in config:
        site_id = site.get("id")
        site_name = site.get('name', site_id)
        if not site_id:
            logging.warning(f"Skipping site due to missing 'id' in config: {site_name}")
            continue

        notices = fetch_site_data(site)
        if not notices:
            logging.info(f"No relevant notices found for {site_name}")
            continue

        last_seen_id = load_last_link(site_id)
        
        new_notices = []
        found_last_seen = False
        # Iterate from the latest notice to the oldest
        for text, link in notices:
            current_id = link if link else text
            if current_id == last_seen_id and last_seen_id:
                found_last_seen = True
                break
            new_notices.append((text, link))
        
        if found_last_seen:
            new_notices.reverse() # If last seen was found, new_notices has newest first, so reverse to send oldest first
        # else: if last_seen_id was NOT found, new_notices contains all fetched notices (newest to oldest), no reversal needed.

        if not new_notices:
            logging.info(f"No new notices for {site_name}")
            continue

        for text, link in new_notices:
            msg = f"*{site_name}*\n\n{text}"
            if link:
                msg += f"\n\n[ডাউনলোড/বিস্তারিত]({link})"
            send_telegram_message(msg)
            logging.info(f"Sent Telegram message for {site_name}: {text}")

        # Update last seen link with the absolute newest notice, even if it was sent already in this run (to cover cases where last_seen_id was not found)
        newest_notice_text, newest_notice_link = notices[0] 
        latest_id_to_save = newest_notice_link if newest_notice_link else newest_notice_text
        set_last_link(site_id, latest_id_to_save)
        logging.info(f"Updated last seen ID for {site_name} to: {latest_id_to_save}")

if __name__ == "__main__":
    main()
