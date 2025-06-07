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

def init_driver(user_id):
    user_profile_path = os.path.join(BASE_DIR, f"user_profiles/{user_id}")
    os.makedirs(user_profile_path, exist_ok=True)  # ensure the folder exists

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_profile_path}")
    options.add_argument("--start-maximized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def scrape_reviews(asin, max_pages,user_id):
    driver = init_driver(user_id)
    all_reviews = []

    try:
        url = f"https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"
        driver.get(url)
        print("Waiting for login if needed...")
        time.sleep(35)  # Time for manual login if required

        page = 1
        while page <= max_pages:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".review")))
            reviews = driver.find_elements(By.CSS_SELECTOR, ".review")

            for r in reviews:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", r)
                    time.sleep(0.1)

                    #Extract Review Date
                    try:
                        date_element = r.find_element(By.CSS_SELECTOR, "span[data-hook='review-date']")
                        raw_date_text = date_element.text.strip()
                        # Extract the part after "on" (e.g., "18 May 2025")
                        date_part = raw_date_text.split("on")[-1].strip()
                        # Parse it and format as dd/mm/yyyy
                        parsed_date = datetime.strptime(date_part, "%d %B %Y")
                        date = parsed_date.strftime("%d/%m/%Y")
                    except:
                        date = "N/A"

                    # Extract Rating
                    try:
                        rating_element = r.find_element(By.CSS_SELECTOR, "i[data-hook='review-star-rating'], i[data-hook='cmps-review-star-rating']")
                        rating_text = rating_element.get_attribute('textContent').strip()
                        rating_match = re.search(r"(\d+\.?\d*) out of 5", rating_text)
                        rating = rating_match.group(1) if rating_match else "N/A"
                    except:
                        rating = "N/A"

                    # Extract Review Title
                    try:
                        title = r.find_element(By.CSS_SELECTOR, ".a-size-base.a-link-normal.review-title.a-color-base.review-title-content.a-text-bold").text.strip()
                    except:
                        title = "N/A"

                    # Extract Review Body
                    try:
                        body = "N/A"
                        try:
                            review_body_container = r.find_element(By.CSS_SELECTOR, "span[data-hook='review-body']")
                            direct_text = review_body_container.text.strip()
                            if direct_text:
                                body = direct_text
                            else:
                                span_children = review_body_container.find_elements(By.TAG_NAME, "span")
                                for s in span_children:
                                    text = s.text.strip()
                                    if text:
                                        body = text
                                        break
                        except:
                            pass

                        if body == "N/A":
                            try:
                                username_element = None
                                try:
                                    username_element = r.find_element(By.CSS_SELECTOR, "span.a-profile-name")
                                except:
                                    pass

                                candidates = r.find_elements(By.CSS_SELECTOR, "div.a-row, span")
                                for c in candidates:
                                    if username_element and username_element.is_displayed():
                                        if c == username_element or c.find_elements(By.XPATH, ".//ancestor-or-self::*[contains(@class, 'a-profile-content')]"):
                                            continue
                                    text = c.text.strip()
                                    if text and not any(kw in text.lower() for kw in ["reviewed in", "verified purchase", "report", "helpful", "video", "click", "reader", "customer"]):
                                        body = text
                                        break
                            except:
                                pass
                    except:
                        body = "N/A"

                    if body != "N/A":
                        body = body.replace("Click to play video", "").strip()
                        if not body:
                            body = "N/A"

                    all_reviews.append({
                        "Review_Date": date,
                        "User_Rating_out_of_5": rating,
                        "Review_Title": title,
                        "Review_Body": body
                    })
                except:
                    continue

            try:
                next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "li.a-last a")))
                driver.execute_script("arguments[0].click();", next_button)
                page += 1
                time.sleep(3)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            except:
                print("No more pages or next button not found.")
                break
    finally:
        driver.quit()
        with open(filename, mode="w", encoding="utf-8") as output_file:
            json.dump(all_reviews, output_file, ensure_ascii=False, indent=4)

    return filename

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        product_url = request.form.get('product_url')
        pages = int(request.form.get('pages', 1))

        if not product_url:
            return render_template("index.html", error="Please enter a valid product URL")

        asin_match = re.search(r"/([A-Z0-9]{10})(?:[/?]|$)", product_url)
        if asin_match:
            asin = asin_match.group(1)
        else:
            return render_template("index.html", error="Invalid Amazon product URL")

        try:
            user_id = request.remote_addr.replace(".", "_")  # Create a user-specific ID based on IP
            json_filename = scrape_reviews(asin, pages, user_id)

            # Only render page with download button
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
