import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
import csv
import time
import urllib.parse
import re
import os

def setup_driver():
    """Setup Chrome driver with appropriate options"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    return webdriver.Chrome(options=options)

def create_search_url(what, where):
    """Create a Google Maps search URL with proper encoding"""
    query = f"best {what} in {where}"
    encoded_query = urllib.parse.quote(query)
    base_url = "https://www.google.com/search"
    params = f"?tbm=lcl&q={encoded_query}"
    return base_url + params

def wait_and_get_element(driver, by, value, timeout=10):
    """Wait for element to be present and return it"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        return None

def check_next_button(driver):
    """Check if next button exists and is clickable"""
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, 'span.oeN89d[style*="margin-left:53px"]')
        return next_button if next_button.is_displayed() else None
    except NoSuchElementException:
        return None

def get_phone_number(driver):
    """Extract phone number using multiple selectors"""
    selectors = [
        'a[data-local-attribute="d3ph"] span[aria-label^="Call phone number"]',
        'span[aria-label^="Call phone number"]',
        'a[data-dtype="d3ph"]',
        '[data-local-attribute="d3ph"]'
    ]
    
    for selector in selectors:
        try:
            phone_element = wait_and_get_element(driver, By.CSS_SELECTOR, selector)
            if phone_element:
                aria_label = phone_element.get_attribute('aria-label')
                if aria_label and 'Call phone number' in aria_label:
                    return aria_label.replace('Call phone number ', '')
                return phone_element.text
        except:
            continue
    return None  

def find_email(driver, business_name):
    """Search for business email in a new tab with improved validation"""
    try:

        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        search_query = f"{business_name} email contact"
        driver.get(f"https://www.google.com/search?q={urllib.parse.quote(search_query)}")
        time.sleep(2)
        page_text = driver.page_source
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        valid_emails = []
        for email in emails:
            if any(ext in email.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']): 
                continue
            if re.search(r'@\d+x', email.lower()): 
                continue
            if email.lower().split('.')[-1] not in ['com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'us', 'uk', 'ca']: 
                continue
            if any(pattern in email.lower() for pattern in ['novalidation', 'empty', 'null', 'undefined']): 
                continue
                
            valid_emails.append(email)
        
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        
        if valid_emails:
            return valid_emails[0] 
        return None
        
    except Exception as e:
        print(f"Error searching for email: {str(e)}")
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        return None

def create_or_append_csv(business, filename="business_data.csv"):
    """Create CSV if it doesn't exist or append a single business entry"""
    file_exists = os.path.exists(filename)
    
    try:
        mode = 'a' if file_exists else 'w'
        with open(filename, mode, newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['name', 'phone', 'email'])
            if not file_exists:
                writer.writeheader()
            writer.writerow(business)
        print(f"Saved: {business['name']}")
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")

def scrape_page_businesses(driver):
    """Scrape all businesses from current page with immediate CSV saving"""
    businesses = []
    
    try:
        business_elements = driver.find_elements(By.CLASS_NAME, 'VkpGBb')
        
        for element in business_elements:
            try:
                try:
                    element.click()
                    time.sleep(1.5)
                except:
                    print("Couldn't click on business element")
                    continue
                
                # Get business name
                try:
                    name = element.find_element(By.CLASS_NAME, 'dbg0pd').text
                except NoSuchElementException:
                    continue  # Skip if no name found
                
                # Get phone number and skip if not found
                phone = get_phone_number(driver)
                if not phone:
                    print(f"Skipped {name} - No phone number found")
                    continue
                
                # Search for email in new tab
                email = find_email(driver, name)
                if not email:
                    print(f"Skipped {name} - No email found")
                    continue
                
                # Create business entry
                business = {
                    'name': name,
                    'phone': phone,
                    'email': email
                }
                
                # Save immediately to CSV
                create_or_append_csv(business)
                businesses.append(business)
                
                print(f"Scraped: {name} - {phone} - {email}")
                time.sleep(2)
                
            except Exception as e:
                print(f"Error processing business: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Error processing page: {str(e)}")
    
    return businesses

def scrape_business_data(what, where):
    """Scrape business data using Selenium with pagination"""
    all_businesses = []
    driver = setup_driver()
    page_num = 1
    
    try:
        # Load initial page
        url = create_search_url(what, where)
        driver.get(url)
        time.sleep(3)
        
        while True:
            print(f"\nScraping page {page_num}...")
            
            # Scrape current page
            page_businesses = scrape_page_businesses(driver)
            all_businesses.extend(page_businesses)
            
            # Check for next button
            next_button = check_next_button(driver)
            if next_button:
                try:
                    next_button.click()
                    print(f"Moving to page {page_num + 1}...")
                    page_num += 1
                    time.sleep(3)  # Wait for new page to load
                except Exception as e:
                    print(f"Error clicking next button: {str(e)}")
                    break
            else:
                print("No more pages available")
                break
    
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    finally:
        driver.quit()
    
    return all_businesses

def main():
    st.title('Business Data Scraper')

    what = st.text_input("What type of business are you looking for?", "restaurant")
    where = st.text_input("In which location?", "New York")

    if st.button('Start Scraping'):
        st.write(f"Searching for {what} in {where}...")
        businesses = scrape_business_data(what, where)

        if businesses:
            st.write(f"\nFinished scraping!")
            st.write(f"Total businesses found with both phone and email: {len(businesses)}")
            df = pd.DataFrame(businesses)
            st.write(df)
        else:
            st.write("No businesses found or an error occurred")

if __name__ == "__main__":
    main()
