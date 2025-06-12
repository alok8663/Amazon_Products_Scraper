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
filename = os.path.join(BASE_DIR, "amazon_reviews.json")

def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--start-maximized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def scrape_from_landing_page(landing_url, max_pages):
    driver = init_driver()
    all_products = []

    try:
        print("Waiting for login if needed...")
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
                        except:
                            about = "N/A"

                        # Extracting Product Description
                        try:
                            aplus_html = ""
                            cleaned_text = ""
                            unique_images = []
                            video_url = "N/A"

                            try:
                                aplus_element = driver.find_element(By.ID, "aplus")
                                aplus_html = aplus_element.get_attribute("innerHTML")
                                text_content = aplus_element.text.strip()

                                # Remove unwanted phrases
                                cleaned_lines = [
                                    line for line in text_content.splitlines()
                                    if line.strip().lower() not in ["product description", "click to play video"]
                                ]
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

                            # Video extraction from full page source
                            full_html = driver.page_source
                            video_match = re.search(r'<video[^>]*src="([^"]+\.mp4)"', full_html)
                            video_url = video_match.group(1) if video_match else "N/A"

                            desc = {
                                "text": cleaned_text if cleaned_text else "N/A",
                                "images": unique_images,
                                "video": video_url
                            }

                        except Exception as e:
                            print("Could not extract product description:", e)
                            desc = {
                                "text": "N/A",
                                "images": [],
                                "video": "N/A"
                            }





                        all_products.append({
                            "Title": title,
                            "Price": price,
                            "About_this_Item": about,
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
