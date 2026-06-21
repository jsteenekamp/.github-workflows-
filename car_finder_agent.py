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
    """Applies professional mechanical filters against listing texts."""
    full_text = f"{title} {description}".lower()
    
    for discard in CONFIG["filters"]["hard_discards"]:
        if discard in full_text:
            return "DISCARD"
            
    for leverage in CONFIG["filters"]["leverage_points"]:
        if leverage in full_text:
            return "HIGHLIGHT"
            
    return "KEEP"

def scrape_gumtree(page, make, model):
    """Connects to Gumtree and extracts live local listings within our radius."""
    # Build search query (e.g., "Toyota Hilux")
    search_query = f"{make} {model}"
    encoded_query = urllib.parse.quote(search_query)
    
    # Target URL utilizing the 150km radius and max price constraints
    # Leopold postcode 3224 sits within the broader Victoria regional boundaries
    url = f"https://www.gumtree.com.au/s-cars-vehicles/victoria/{encoded_query}/k0c18320l3008842?price=__10000.00&radius=150"
    
    listings = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000) # Quick settling time
        
        # Locate item card elements using a generic URL pattern instead of volatile class names
        # Gumtree ads always contain '/s-ad/' in their hyperlinks
        cards = page.locator("a[href*='/s-ad/']").all()
        
        for card in cards:
            try:
                # Target elements safely using relaxed, partial text matches or relative structural positions
                title = card.locator("p, span, h3").first.text_content() or ""
                price_text = card.text_content() or "0"
                ad_url = card.get_attribute("href") or ""
                
                if ad_url and not ad_url.startswith("http"):
                    ad_url = "https://www.gumtree.com.au" + ad_url
                
                # Skip duplicate tracking elements or empty blocks
                if not title.strip() or "$" not in price_text:
                    continue
                
                # Clean the price string to an integer
                price = int(''.join(filter(str.isdigit, price_text))) if any(char.isdigit() for char in price_text) else 0
                
                listings.append({
                    "make": make,
                    "model": model,
                    "year": "N/A",
                    "price": price,
                    "area": "Victoria (150km Radius)",
                    "url": ad_url,
                    "title": title.strip(),
                    "desc": "Check live listing for description details."
                })
            except Exception:
                continue
                
                # Clean the price string to an integer
                price = int(''.join(filter(str.isdigit, price_text))) if any(char.isdigit() for char in price_text) else 0
                
                # Snag a snippet description if available on the card layout
                desc = card.locator("p.user-ad-row-new-design__description").text_content() or ""
                
                listings.append({
                    "make": make,
                    "model": model,
                    "year": "N/A", # Will parse out from text or direct detail pages later
                    "price": price,
                    "area": location.strip(),
                    "url": ad_url,
                    "title": title.strip(),
                    "desc": desc.strip()
                })
            except Exception:
                continue # Skip any weirdly formatted ad cards or banners
    except Exception as e:
        print(f"[ERROR] Failed scraping Gumtree for {search_query}: {e}")
        
    return listings

def process_and_save_listings():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"car_hunt_results_{timestamp}.csv"
    compiled_matches = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Emulating a real browser footprint to avoid instant blocking
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        # Loop over every vehicle target listed in your config file
        for target in CONFIG["search_config"]["targets"]:
            make = target["make"]
            for model in target["models"]:
                print(f"[INFO] Hunting live listings for {make} {model}...")
                raw_listings = scrape_gumtree(page, make, model)
                
                for item in raw_listings:
                    status = evaluate_mechanical_condition(item["title"], item["desc"])
                    
                    if status == "DISCARD":
                        continue
                        
                    item["agent_evaluation"] = status
                    compiled_matches.append(item)
                
                page.wait_for_timeout(2000) # Graceful delay between target categories
                
        browser.close()

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
        print("[INFO] Run finished. Zero live vehicles matched parameters or passed filters today.")

def dispatch_alerts(csv_filename, count):
    print(f"[NOTIFICATION] Found {count} viable listings. Stored in {csv_filename}")
    # Communication API endpoints connect here

if __name__ == "__main__":
    process_and_save_listings()
