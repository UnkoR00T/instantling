import json
import os
import random
import shutil
import sys
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "instaling"


CREDS_FILE = config_dir() / "credentials.json"
DATA_FILE = config_dir() / "data.json"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# One-time migration of an old data.json that sits next to this script
_old_data = Path(__file__).resolve().parent / "data.json"
if _old_data.exists() and not DATA_FILE.exists():
    shutil.move(str(_old_data), DATA_FILE)
    print(f"Moved existing data.json to {DATA_FILE}")


def show_error(text):
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Instaling bot", text)
        root.destroy()
    except Exception:
        pass


def read_saved_credentials():
    try:
        with open(CREDS_FILE, "r", encoding="utf-8") as f:
            creds = json.load(f)
        return creds.get("login", ""), creds.get("password", "")
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return "", ""


def save_credentials(login, password):
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 0o600 = owner read/write only (ignored on Windows)
    fd = os.open(CREDS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"login": login, "password": password}, f, indent=4)


def ask_credentials():
    """Popup with creds + run options. Returns (login, password, runs, mode)."""
    saved_login, saved_password = read_saved_credentials()
    result = {}

    root = tk.Tk()
    root.title("Instaling bot")
    root.resizable(False, False)
    # Errors inside button callbacks are normally invisible; show them
    root.report_callback_exception = lambda exc, val, tb: messagebox.showerror(
        "Error", f"{exc.__name__}: {val}"
    )

    frame = tk.Frame(root, padx=20, pady=15)
    frame.pack()

    tk.Label(frame, text="Login:").grid(row=0, column=0, sticky="e", pady=4)
    login_var = tk.StringVar(value=saved_login)
    login_entry = tk.Entry(frame, textvariable=login_var, width=28)
    login_entry.grid(row=0, column=1, pady=4, padx=(8, 0))

    tk.Label(frame, text="Password:").grid(row=1, column=0, sticky="e", pady=4)
    password_var = tk.StringVar(value=saved_password)
    password_entry = tk.Entry(frame, textvariable=password_var, width=28, show="*")
    password_entry.grid(row=1, column=1, pady=4, padx=(8, 0))

    # Runs: three toggle buttons (1, 2, 3)
    tk.Label(frame, text="Runs:").grid(row=2, column=0, sticky="e", pady=4)
    runs_var = tk.IntVar(value=1)
    runs_frame = tk.Frame(frame)
    runs_frame.grid(row=2, column=1, sticky="w", padx=(8, 0))
    for n in (1, 2, 3):
        tk.Radiobutton(
            runs_frame,
            text=str(n),
            variable=runs_var,
            value=n,
            indicatoron=False,
            width=6,
        ).pack(side="left", padx=(0, 4))

    # What to do between runs
    tk.Label(frame, text="Between runs:").grid(row=3, column=0, sticky="e", pady=4)
    mode_var = tk.StringVar(value="tab")
    mode_frame = tk.Frame(frame)
    mode_frame.grid(row=3, column=1, sticky="w", padx=(8, 0))
    tk.Radiobutton(mode_frame, text="New tab", variable=mode_var, value="tab").pack(
        side="left"
    )
    tk.Radiobutton(
        mode_frame, text="Restart browser", variable=mode_var, value="restart"
    ).pack(side="left")

    remember_var = tk.BooleanVar(value=True)
    tk.Checkbutton(frame, text="Remember credentials", variable=remember_var).grid(
        row=4, column=0, columnspan=2, pady=(6, 8)
    )

    def on_start(event=None):
        login = login_var.get().strip()
        password = password_var.get()
        if not login or not password:
            messagebox.showwarning("Missing data", "Enter both login and password.")
            return
        if remember_var.get():
            try:
                save_credentials(login, password)
            except OSError as e:
                messagebox.showwarning(
                    "Could not save credentials", f"{e}\n\nContinuing without saving."
                )
        result["creds"] = (login, password, runs_var.get(), mode_var.get())
        root.destroy()

    tk.Button(frame, text="Start", width=12, command=on_start).grid(
        row=5, column=0, columnspan=2
    )
    root.bind("<Return>", on_start)

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 3
    root.geometry(f"+{x}+{y}")

    (password_entry if saved_login else login_entry).focus_set()
    root.mainloop()

    if "creds" not in result:  # window closed without pressing Start
        sys.exit(0)
    return result["creds"]


def save_data(entries):
    # Write to a temp file first so a crash mid-write can't corrupt the data
    tmp = DATA_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=4, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


# OPTIONS
url = "https://instaling.pl/teacher.php?page=login"
login_set, password_set, runs, mode = ask_credentials()

# Load JSON Data Safely
try:
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    data = []

driver: webdriver.Chrome
action: ActionChains


def find_browser_binary():
    """On Linux, pick whichever Chrome/Chromium is installed."""
    if sys.platform == "win32":
        return None
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        path = shutil.which(name)
        if path:
            return path
    return None


def make_driver():
    global driver, action
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    binary = find_browser_binary()
    if binary:
        options.binary_location = binary
    driver = webdriver.Chrome(options=options)
    action = ActionChains(driver)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )


def browser_alive():
    try:
        return len(driver.window_handles) > 0
    except Exception:
        return False


def new_tab_and_close_old():
    old = driver.current_window_handle
    driver.switch_to.new_window("tab")
    new = driver.current_window_handle
    driver.switch_to.window(old)
    driver.close()
    driver.switch_to.window(new)


def click(element):
    action.move_to_element(element).click().perform()


def log_in():
    try:
        login = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "log_email"))
        )
    except Exception:
        print("Login form not shown, assuming already logged in.")
        return
    login.send_keys(login_set)
    driver.find_element(By.ID, "log_password").send_keys(password_set)
    click(driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]'))


def start_session():
    try:
        click(driver.find_element(By.ID, "streak-button-close"))
    except Exception:
        pass

    btn_common = "btn-start-session"
    session_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.CLASS_NAME, btn_common))
    )
    click(session_button)

    try:
        click(
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, btn_common))
            )
        )
    except Exception:
        try:
            click(
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "continue_session_button"))
                )
            )
        except Exception:
            print("No session buttons found.")


def click_check():
    try:
        check = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "check"))
        )
    except Exception:
        check = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "check_answer"))
        )
    click(check)


def input_answer(ans):
    answer_field = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "answer"))
    )
    answer_field.clear()
    answer_field.send_keys(ans)
    time.sleep(random.uniform(0.5, 1.0))


def run_once():
    """One full session. Returns when it looks finished or the browser closed."""
    driver.get(url)
    try:
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "fc-primary-button"))
        ).click()
    except Exception:
        print("Cookie button not found or already clicked.")

    log_in()
    start_session()

    misses = 0
    while browser_alive():
        try:
            time.sleep(random.uniform(0.5, 1))
            given = (
                WebDriverWait(driver, 5)
                .until(EC.presence_of_element_located((By.CLASS_NAME, "translation")))
                .text
            )
            misses = 0
        except Exception:
            misses += 1
            if misses >= 2:
                print("No more words, run finished.")
                return
            continue

        try:
            german_word = next(
                (e["german"] for e in data if e["polish"] == given), None
            )
            print(f"Given: {given}, Found German: {german_word}")

            if german_word:
                input_answer(german_word)
                click_check()
            else:
                try:
                    new_word_var = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "dont_know_new"))
                    )
                    if new_word_var.is_displayed():
                        new_word_var.click()
                        time.sleep(random.uniform(0.1, 1))
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.ID, "skip"))
                        ).click()
                        continue
                except Exception:
                    pass

                click_check()
                time.sleep(random.uniform(0.5, 1))
                tries = 0
                while tries < 3:
                    correct = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "word"))
                    )
                    correct_text = correct.text
                    if correct_text == "":
                        print("Correct text is null")
                        tries += 1
                        time.sleep(0.5)
                        continue
                    data.append({"german": correct_text, "polish": given})
                    save_data(data)
                    break
            try:
                click(
                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "nextword"))
                    )
                )
            except Exception:
                pass
        except Exception:
            pass


def main():
    make_driver()
    for i in range(runs):
        print(f"=== Run {i + 1}/{runs} ===")
        if i > 0:
            if mode == "restart":
                driver.quit()
                make_driver()
            else:
                new_tab_and_close_old()
        run_once()
        if not browser_alive():
            break

    if browser_alive():
        print("All runs finished. Browser left open.")
    else:
        print("Browser closed, exiting.")
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        print(err)
        show_error(err)
