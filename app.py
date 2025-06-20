from flask import Flask, render_template, request, send_file
import os
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import random

app = Flask(__name__)

from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
filename = os.path.join(BASE_DIR, "amazon_product_details.json")

def init_driver():
    options = webdriver.ChromeOptions()
    USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--start-maximized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--lang=en-US,en;q=0.9")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def clean_amazon_url(url):
    return url.split('?')[0] if '?ref=' in url or '/ref=' in url else url



def scrape_from_landing_page(landing_url, max_pages):
    driver = init_driver()
    all_products = []

    try:
        print("Waiting for login if needed...")
        landing_url = clean_amazon_url(landing_url)
        driver.get(landing_url)
        time.sleep(random.uniform(3, 7))  # wait for login

        page = 1
        while page <= max_pages:
            try:
                print(f"\n🔎 Scraping page {page}...")

                WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.a-link-normal.s-no-outline"))
                )

                product_links = driver.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
                product_urls = [link.get_attribute("href") for link in product_links if link.get_attribute("href")]
                print(f"🧮 Found {len(product_urls)} products on page {page}")

                for idx, product_url in enumerate(product_urls):
                    try:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(product_url)
                        time.sleep(random.uniform(3, 6))

                        # Extracting Title of the product
                        try:
                            title = driver.find_element(By.ID, "productTitle").text.strip()
                        except:
                            title = "N/A"

                        # Extracting Price of the product
                        try:
                            price = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
                        except:
                            price = "N/A"


                        # Extracting About this item section
                        try:
                            raw_about = driver.find_element(By.ID, "feature-bullets").text.strip()
                            about_lines = raw_about.splitlines()

                            # Remove "About this item" if it's the first line
                            if about_lines and "about this item" in about_lines[0].lower():
                                about_lines.pop(0)

                            # Remove "› See more product details" if it's the last line
                            if about_lines and "see more product details" in about_lines[-1].lower():
                                about_lines.pop()

                            about = "\n".join(about_lines).strip()

                            # If still empty after cleaning, try fallback for books
                            if not about:
                                raise Exception("Empty after cleaning, try book fallback")

                        except:
                            # Fallback for books (like in bookDescription_feature_div)
                            try:
                                book_desc_div = driver.find_element(By.ID, "bookDescription_feature_div")
                                book_span = book_desc_div.find_element(By.TAG_NAME, "span")
                                about = book_span.text.strip()
                            except:
                                about = "N/A"



                        # Extracting Product Information / Product Details
                        try:
                            product_info = "N/A"  # Default fallback

                            # Step 1: Slowly scroll down to load all dynamic content
                            scroll_height = driver.execute_script("return document.body.scrollHeight")
                            for y in range(0, scroll_height, 300):
                                driver.execute_script(f"window.scrollTo(0, {y});")
                                time.sleep(0.3)

                            # Step 2: Expand all expander buttons (reliable span click)
                            try:
                                expander_spans = driver.find_elements(
                                    By.XPATH, "//div[contains(@class, 'a-expander-header') and contains(@class, 'a-declarative')]/span"
                                )
                                for span in expander_spans:
                                    try:
                                        if span.is_displayed():
                                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", span)
                                            time.sleep(0.5)
                                            driver.execute_script("arguments[0].click();", span)
                                            time.sleep(1)
                                            print("[+] Clicked expander span")
                                    except Exception as e:
                                        print(f"[!] Expander click error: {e}")
                                        continue
                            except Exception as e:
                                print(f"[!] Expander span fetch error: {e}")

                            # Step 3: Extract key-value table pairs
                            try:
                                table_rows = driver.find_elements(By.XPATH, "//table[contains(@class, 'a-keyvalue')]//tr")

                                pairs = []
                                for row in table_rows:
                                    try:
                                        key = row.find_element(By.XPATH, ".//th").text.strip()
                                        value = row.find_element(By.XPATH, ".//td").text.strip()
                                        if key and value:
                                            pairs.append(f"{key}: {value}")
                                    except Exception as e:
                                        print(f"[Row Parse Error] {e}")
                                        continue

                                if pairs:
                                    product_info = "\n".join(pairs)
                                else:
                                    raise Exception("No product info found in key-value table.")

                            except Exception as e:
                                print(f"[Expandable Section Error] {e}")

                                # Fallback 1: Try normal Product Information block
                                try:
                                    product_info_element = driver.find_element(By.XPATH, "//div[@id='productDetails_feature_div']")
                                    raw_info = product_info_element.text.strip()
                                    lines = raw_info.splitlines()
                                    filtered_lines = [
                                        line for line in lines
                                        if line.strip().lower() not in [
                                            "product information",
                                            "feedback",
                                            "would you like to tell us about a lower price?"
                                        ]
                                    ]
                                    if filtered_lines:
                                        product_info = "\n".join(filtered_lines).strip()
                                    else:
                                        raise Exception("Empty product info block.")

                                except Exception as e:
                                    print(f"[Fallback 1 Error] {e}")

                                    # Fallback 2: Try detail bullets
                                    try:
                                        detail_element = driver.find_element(By.ID, "detailBullets_feature_div")
                                        raw_detail = detail_element.text.strip()
                                        detail_lines = raw_detail.splitlines()
                                        filtered_detail_lines = [
                                            line for line in detail_lines
                                            if line.strip().lower() not in [
                                                "product details",
                                                "feedback",
                                                "would you like to tell us about a lower price?"
                                            ]
                                        ]
                                        if filtered_detail_lines:
                                            product_info = "\n".join(filtered_detail_lines).strip()
                                    except Exception as e:
                                        print(f"[Fallback 2 Error] {e}")
                                        product_info = "N/A"

                        except Exception as e:
                            print(f"[Main Block Error] {e}")
                            product_info = "N/A"





                        # Extracting Product Description
                        try:
                            aplus_html = ""
                            cleaned_text = ""
                            unique_images = []

                            try:
                                aplus_element = driver.find_element(By.ID, "aplus")
                                aplus_html = aplus_element.get_attribute("innerHTML")
                                text_content = aplus_element.text.strip()

                                # Remove unwanted sections like "From the Brand", "Click to play video"
                                cleaned_lines = []
                                skip_section = False
                                for line in text_content.splitlines():
                                    lower_line = line.strip().lower()
                                    if "from the brand" in lower_line or "click to play video" in lower_line:
                                        skip_section = True
                                    elif skip_section and lower_line == "":
                                        skip_section = False
                                    elif not skip_section and lower_line not in ["product description"]:
                                        cleaned_lines.append(line.strip())

                                cleaned_text = "\n".join(cleaned_lines).strip()

                                # Unique image URLs
                                image_tags = re.findall(r'<img[^>]+src="([^">]+)"', aplus_html)
                                unique_images = list(dict.fromkeys(image_tags))

                            except:
                                # Fallback to basic product description
                                try:
                                    basic_desc_element = driver.find_element(By.ID, "productDescription")
                                    cleaned_text = basic_desc_element.text.strip()
                                except:
                                    cleaned_text = "N/A"

                            desc = {
                                "text": cleaned_text if cleaned_text else "N/A",
                                "images": unique_images,
                            }

                        except Exception as e:
                            print("Could not extract product description:", e)
                            desc = {
                                "text": "N/A",
                                "images": [],
                            }


                        all_products.append({
                            "Title": title,
                            "Price": price,
                            "About_this_Item": about,
                            "Product_Information": product_info,
                            "Product_Description": desc
                        })

                        print(f"✅ Scraped {idx + 1}: {title[:50]}")

                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    except Exception as e:
                        print(f"❌ Error scraping product: {e}")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue

                # Go to next page if not the last one
                if page < max_pages:
                    try:
                        old_first = product_urls[0] if product_urls else ""

                        next_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.s-pagination-next"))
                        )
                        driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                        time.sleep(random.uniform(2, 4))
                        driver.execute_script("arguments[0].click();", next_btn)
                        print(f"➡️ Clicked to go to page {page + 1}")

                        WebDriverWait(driver, 15).until(lambda d: (
                            d.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline") and
                            d.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")[0].get_attribute("href") != old_first
                        ))

                        print(f"🔄 Loaded page {page + 1} successfully")
                        time.sleep(random.uniform(2, 4))
                    except Exception as e:
                        print("⛔ Pagination failed or no more pages:", e)
                        break

                # This is the important part — must be outside pagination block
                page += 1

            except Exception as e:
                print(f"⚠️ Error on page {page}: {e}")
                break
    finally:
        driver.quit()
        with open(filename, mode="w", encoding="utf-8") as output_file:
            json.dump(all_products, output_file, ensure_ascii=False, indent=4)

    return filename



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        landing_url = request.form.get('product_url')
        pages = int(request.form.get('pages', 1))

        if not landing_url:
            return render_template("index.html", error="Please enter a valid Amazon landing page URL")

        try:
            json_filename = scrape_from_landing_page(landing_url, pages)
            return render_template("index.html", download_ready=True, filename=os.path.basename(json_filename))
        except Exception as e:
            return render_template("index.html", error=f"An error occurred: {str(e)}")

    return render_template("index.html")



@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return "File not found", 404


if __name__ == "__main__":
    app.run(debug=True)
