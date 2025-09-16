import json
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
import time

# OPTIONS
url = 'https://instaling.pl/teacher.php?page=login'
login_set = ""
password_set = ""
# Load JSON Data Safely
try:
    with open('data.json', 'r') as file:
        data = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    data = []

options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = webdriver.Chrome(options=options)
action = ActionChains(driver)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
driver.get(url)

# Wait for Cookie Button and Click
try: 
    WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CLASS_NAME, "fc-primary-button"))).click()
except: 
    print("Cookie button not found or already clicked.")


# Login
login = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "log_email")))
login.send_keys(login_set)
password = driver.find_element(By.ID, "log_password")
password.send_keys(password_set)

login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
action.move_to_element(login_button).click().perform()

btn_common = "btn-start-session"

session_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CLASS_NAME, btn_common)))
action.move_to_element(session_button).click().perform()

# Wait for Session Buttons
try:
    start_session_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CLASS_NAME, btn_common)))
    action.move_to_element(start_session_button).click().perform()
except:
    try:
        continue_session_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "continue_session_button")))
        action.move_to_element(continue_session_button).click().perform()
    except:
        print("No session buttons found.")

# Answer Handling
def input_answer(ans):
    answer_field = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "answer"))
    )
    answer_field.clear()
    answer_field.send_keys(ans)
    time.sleep(random.uniform(0.5, 1.0))

while True:
    try:
        time.sleep(random.uniform(0.5, 1))
        given = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "translation"))).text
        german_word = next((entry['german'] for entry in data if entry['polish'] == given), None)

        if german_word:
            input_answer(german_word)
            check = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "check")))
            action.move_to_element(check).click().perform()
        else:
            try:
                new_word_var = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "dont_know_new")))
                if new_word_var.is_displayed():
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "dont_know_new"))).click()
                    time.sleep(random.uniform(0.1, 1))
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "skip"))).click()
                    continue
            except NoSuchElementException:
                pass

            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "check"))).click()
            time.sleep(random.uniform(0.5, 1))
            while True:
                correct = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "word")))
                correct_text = correct.text;
                if correct_text == "":
                    print("Correct text is null")
                    continue;
                new_entry = {"german": correct_text, "polish": given}
                data.append(new_entry)

                with open('data.json', 'w') as file:
                    json.dump(data, file, indent=4)
                    break;
        nextword = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID,"nextword")))
        action.move_to_element(nextword).click().perform()
    except NoSuchElementException:
        print("No more words. Exiting.")
        break