import json
import csv
import os
import datetime
import urllib.parse
from playwright.sync_api import sync_playwright

# Load Configuration Setup
with open("config.json", "r") as f:
    CONFIG = json.load(f)

def evaluate_mechanical_condition(title, description):
    full_text = f"{title} {description}".lower()
    for discard in CONFIG["filters"]["hard_discards"]:
        if discard in full_text:
            return "DISCARD"
    for leverage in CONFIG["filters"]["leverage_points"]:
        if leverage in full_text:
            return "HIGHLIGHT"
    return "KEEP"

def scrape_gumtree(page, make, model):
    search_query = f"{make} {model}"
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://www.gumtree.com.au/s-cars-vehicles/victoria/{encoded_query}/k0c18320l3008842?price=__10000.00&radius=150"
    
    listings = []
    try:
        print(f"[DEBUG] Navigating to: {url}")
        response = page.goto(url, wait_until="load", timeout=45000)
        print(f"[DEBUG] HTTP Response Status: {response.status if response else 'No Response'}")
        
        page.wait_for_timeout(3000)
        
        # Check if we got hit by a security wall
        page_title = page.title()
        print(f"[DEBUG] Page Title loaded: '{page_title}'")
        if "Access Denied" in page_title or "Cloudflare" in page_title or "Just a moment" in page_title:
            print("[WARNING] Anti-bot wall detected. Attempting behavior masking patterns...")
            page.mouse.move(200, 200)
            page.keyboard.press("PageDown")
            page.wait_for_timeout(4000)

        # Diagnostics: Total links found on page
        all_links = page.locator("a").all()
        print(f"[DEBUG] Total links found on page: {len(all_links)}")

        # Find any listing URLs containing '/s-ad/'
        cards = page.locator("a[href*='/s-ad/']").all()
        print(f"[DEBUG] Found {len(cards)} matching listing links.")
        
        for index, card in enumerate(cards[:15]): # Inspect first 15 links
            try:
                href = card.get_attribute("href") or ""
                text = card.text_content() or ""
                cleaned_text = " ".join(text.split())
                
                if "$" in cleaned_text:
                    print(f"   -> Link {index}: Found price indicator in text: '{cleaned_text[:60]}...'")
                    
                    # Extract numeric price
                    price = 0
                    price_words = cleaned_text.split("$")
                    if len(price_words) > 1:
                        digits = "".join(filter(str.isdigit, price_words[1].split()[0]))
                        if digits:
                            price = int(digits)

                    listings.append({
                        "make": make,
                        "model": model,
                        "year": "N/A",
                        "price": price,
                        "area": "Victoria (150km Radius)",
                        "url": "https://www.gumtree.com.au" + href if not href.startswith("http") else href,
                        "title": cleaned_text[:50],
                        "desc": cleaned_text
                    })
            except Exception as e:
                print(f"[DEBUG] Card parsing error at index {index}: {e}")
                continue
                
    except Exception as e:
        print(f"[ERROR] Engine failure for {search_query}: {e}")
        
    return listings

def process_and_save_listings():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"car_hunt_results_{timestamp}.csv"
    compiled_matches = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            }
        )
        page = context.new_page()
        
        for target in CONFIG["search_config"]["targets"]:
            make = target["make"]
            for model in target["models"]:
                print(f"\n[INFO] Starting live scan: {make} {model}")
                raw_listings = scrape_gumtree(page, make, model)
                
                for item in raw_listings:
                    status = evaluate_mechanical_condition(item["title"], item["desc"])
                    if status != "DISCARD":
                        item["agent_evaluation"] = status
                        compiled_matches.append(item)
                
                page.wait_for_timeout(3000)
                
        browser.close()

    if compiled_matches:
        with open(filename, mode="w", newline="", encoding="utf-8") as csv_file:
            fieldnames = ["make", "model", "year", "price", "area", "agent_evaluation", "url", "title", "desc"]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for match in compiled_matches:
                writer.writerow(match)
        print(f"\n[SUCCESS] Extracted {len(compiled_matches)} vehicles into {filename}")
    else:
        print("\n[INFO] Complete. No items saved to CSV on this cycle.")

if __name__ == "__main__":
    process_and_save_listings()
