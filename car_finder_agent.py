import json
import csv
import os
import datetime
from playwright.sync_api import sync_playwright

# Load Configuration Setup
with open("config.json", "r") as f:
    CONFIG = json.load(f)

def evaluate_mechanical_condition(title, description):
    """
    Applies professional mechanical filters against listing texts.
    Returns: 'DISCARD', 'HIGHLIGHT' (fixable leverage), or 'KEEP' (clean baseline)
    """
    full_text = f"{title} {description}".lower()
    
    # 🛑 Rule 1: Auto-Reject Scrap Pile / Structural Discards
    for discard in CONFIG["filters"]["hard_discards"]:
        if discard in full_text:
            return "DISCARD"
            
    # ⚠️ Rule 2: Identify Fixable Opportunities (Price Leverage)
    for leverage in CONFIG["filters"]["leverage_points"]:
        if leverage in full_text:
            return "HIGHLIGHT"
            
    return "KEEP"

def scrape_platform_mock(page, search_url):
    """
    Core extraction loop template. Employs randomized stealth human-scrolling 
    to trick anti-bot telemetry on Carsales, Facebook Marketplace, etc.
    """
    page.goto(search_url)
    page.wait_for_timeout(3000) # Wait for JS hydration
    
    # Simulate erratic user scrolling behavior down the page
    for _ in range(3):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(1200)

    # Mocked structured parsing payload simulating DOM/JSON extraction return
    return [
        {
            "make": "Toyota", "model": "Landcruiser 105", "year": "1999", 
            "price": 8500, "area": "Geelong", "url": "https://example.com/ad1",
            "title": "105 Series Landcruiser Manual", 
            "desc": "Runs well but has an engine oil leak from the rocker cover. No RWC."
        },
        {
            "make": "Nissan", "model": "Patrol GU", "year": "2002", 
            "price": 9000, "area": "Melbourne", "url": "https://example.com/ad2",
            "title": "Nissan Patrol GU project car", 
            "desc": "Great project car for someone who wants to fix a blown head gasket."
        }
    ]

def process_and_save_listings():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"car_hunt_results_{timestamp}.csv"
    
    compiled_matches = []
    
    with sync_playwright() as p:
        # Launching a stealth fingerprint browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # In production execution, this loops through dynamically generated search target strings
        raw_listings = scrape_platform_mock(page, "https://www.carsales.com.au/cars/victoria/leopold-region/")
        
        for item in raw_listings:
            status = evaluate_mechanical_condition(item["title"], item["desc"])
            
            # If it trips our project car or write-off triggers, drop it entirely
            if status == "DISCARD":
                continue
                
            item["agent_evaluation"] = status
            compiled_matches.append(item)
            
        browser.close()

    # Save to clean Spreadsheet File Structure
    if compiled_matches:
        with open(filename, mode="w", newline="", encoding="utf-8") as csv_file:
            fieldnames = ["make", "model", "year", "price", "area", "agent_evaluation", "url", "title", "desc"]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for match in compiled_matches:
                writer.writerow(match)
                
        print(f"[SUCCESS] {len(compiled_matches)} safe vehicles extracted to {filename}")
        dispatch_alerts(filename, len(compiled_matches))
    else:
        print("[INFO] Run finished. Zero viable cars matched parameters today.")

def dispatch_alerts(csv_filename, count):
    """Integrates delivery targets for email payloads and SMS gateways."""
    email = CONFIG["delivery"]["email_recipient"]
    mobile = CONFIG["delivery"]["mobile_number"]
    
    print(f"[SMS OUTBOUND] Sending to {mobile}: 'Car Finder Agent: {count} new matches found. Spreadsheet generated: {csv_filename}'")
    print(f"[EMAIL OUTBOUND] Sending compiled report along with {csv_filename} to {email}")

if __name__ == "__main__":
    process_and_save_listings()
