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

app = Flask(__name__)

from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
filename = os.path.join(BASE_DIR, "amazon_reviews.json")

def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def scrape_from_landing_page(landing_url, max_pages):
    driver = init_driver()
    all_products = []

    try:
        print("Waiting for login if needed...")
        driver.get(landing_url)
        time.sleep(35)  # for login if needed

        page = 1
        while page <= max_pages:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.a-link-normal.s-no-outline"))
            )

            product_links = driver.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
            product_urls = [link.get_attribute("href") for link in product_links if link.get_attribute("href")]

            for product_url in product_urls:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(product_url)
                time.sleep(4)

                try:
                    title = driver.find_element(By.ID, "productTitle").text.strip()
                except:
                    title = "N/A"

                try:
                    price = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
                except:
                    price = "N/A"

                try:
                    about = driver.find_element(By.ID, "feature-bullets").text.strip()
                except:
                    about = "N/A"

                try:
                    desc = driver.find_element(By.ID, "productDescription").text.strip()
                except:
                    desc = "N/A"

                all_products.append({
                    "Title": title,
                    "Price": price,
                    "About_This_Item": about,
                    "Product_Description": desc
                })

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "ul.a-pagination li.a-last a")
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(4)
                page += 1
            except:
                print("No more pages or next button not found.")
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
