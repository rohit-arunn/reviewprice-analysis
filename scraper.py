import argparse
import os
import re
import sys
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


SEARCH_QUERY = "sony wireless over-ear noise cancelling headphones"
NUM_PAGES = 10


parser = argparse.ArgumentParser()
parser.add_argument("--scrape", type=int, help="Scrape only the first N rows and print them")
parser.add_argument("--save", type=str, help="Save the complete scraped dataset to this path")
args = parser.parse_args()


def clean_rating(text):
    if not text:
        return None
    match = re.search(r"\d+\.\d+", text)
    return float(match.group()) if match else None


options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

rows = []

try:
    for page in range(1, NUM_PAGES + 1):
        if args.scrape is not None and len(rows) >= args.scrape:
            break

        url = f"https://www.amazon.com/s?k={SEARCH_QUERY.replace(' ', '+')}&page={page}"
        driver.get(url)

        if "Sorry! Something went wrong!" in driver.title:
            print(f"Amazon returned an error page on page {page}. Stopping.", file=sys.stderr)
            break

        try:
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
                )
            )
        except:
            print(f"No product cards found on page {page}. Stopping.", file=sys.stderr)
            break

        time.sleep(2)
        product_cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')

        for card in product_cards:
            if args.scrape is not None and len(rows) >= args.scrape:
                break

            title = None
            rating = None
            review_count = None
            price = None
            asin = None

            try:
                asin = card.get_attribute("data-asin")
            except:
                pass

            try:
                title = card.find_element(By.CSS_SELECTOR, "h2[aria-label]").get_attribute("aria-label")
            except:
                pass

            if not title:
                try:
                    h2_tags = card.find_elements(By.CSS_SELECTOR, "h2 span")
                    title_parts = []

                    for el in h2_tags:
                        text = el.text.strip()
                        if text and text.lower() != "sponsored ad -":
                            title_parts.append(text)

                    title = " ".join(title_parts) if title_parts else None
                except:
                    pass

            rating_text = None
            selectors_to_try = [
                "span.a-icon-alt",
                "i span.a-icon-alt",
                '[aria-label*="out of 5 stars"]',
                '[aria-label*="stars"]'
            ]

            for sel in selectors_to_try:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    rating_text = el.text.strip() or el.get_attribute("aria-label")
                    if rating_text:
                        break
                except:
                    continue

            rating = clean_rating(rating_text)

            try:
                review_tag = card.find_element(
                    By.CSS_SELECTOR,
                    'span.a-size-mini.puis-normal-weight-text.s-underline-text'
                )

                review_text = review_tag.text.strip()
                review_text = review_text.replace("(", "").replace(")", "").lower()

                if "k" in review_text:
                    number = float(review_text.replace("k", ""))
                    review_count = int(number * 1000)
                else:
                    review_count = int(review_text.replace(",", ""))
            except:
                pass

            try:
                whole = card.find_element(By.CSS_SELECTOR, ".a-price-whole").text
                fraction = card.find_element(By.CSS_SELECTOR, ".a-price-fraction").text
                price = float(f"{whole}.{fraction}")
            except:
                pass

            if title:
                rows.append({
                    "asin": asin,
                    "title": title,
                    "rating": rating,
                    "number_of_reviews": review_count,
                    "price": price,
                    "page": page,
                    "source": "Amazon"
                })

        time.sleep(2)

finally:
    driver.quit()

df = pd.DataFrame(rows)

if args.save:
    os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
    df.to_csv(args.save, index=False)
    print(f"Saved {len(df)} rows to {args.save}", file=sys.stderr)
elif args.scrape is not None:
    print(df.head(args.scrape).to_csv(index=False), end="")
else:
    print(df.to_csv(index=False), end="")