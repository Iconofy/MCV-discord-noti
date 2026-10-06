import json
import re
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
COOKIE_FILE = BASE_DIR / "cookie.txt"

# --- Cookie Parsing Functions (Adapted from TikTok_Streak) ---

def normalize_cookie(cookie: dict) -> dict:
    name = cookie.get("name")
    value = cookie.get("value")
    if not name or value is None:
        raise ValueError(f"Invalid cookie: {cookie}")

    normalized = {
        "name": str(name),
        "value": str(value),
        "domain": cookie.get("domain") or "www.mycourseville.com",
        "path": cookie.get("path") or "/",
    }

    if "expirationDate" in cookie:
        normalized["expiry"] = int(cookie["expirationDate"])
    elif "expiry" in cookie:
        normalized["expiry"] = int(cookie["expiry"])
    elif "expires" in cookie and isinstance(cookie["expires"], (int, float)):
        normalized["expiry"] = int(cookie["expires"])

    if "secure" in cookie:
        normalized["secure"] = bool(cookie["secure"])

    if "httpOnly" in cookie:
        normalized["httpOnly"] = bool(cookie["httpOnly"])

    same_site = cookie.get("sameSite") or cookie.get("same_site")
    if same_site:
        same_site = str(same_site).capitalize()
        if same_site in {"Strict", "Lax", "None"}:
            normalized["sameSite"] = same_site

    return normalized


def parse_json_cookies(text: str) -> list[dict]:
    data = json.loads(text)

    if isinstance(data, dict):
        if isinstance(data.get("cookies"), list):
            data = data["cookies"]
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError("JSON cookies must be a list, or an object with a cookies key")

    return [normalize_cookie(cookie) for cookie in data]


def parse_expiry(value: str) -> int | None:
    value = value.strip()
    if not value or value.lower() == "session":
        return None

    if value.isdigit():
        return int(value)

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(parsed.astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def is_checked(value: str) -> bool:
    return value.strip().lower() in {
        "1", "true", "yes", "y", "\u2713", "\u00e2\u0153\u201c",
    }


def parse_browser_table_cookies(text: str) -> list[dict]:
    cookies = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t") if "\t" in line else re.split(r"\s{2,}", line)
        if len(parts) < 5:
            raise ValueError("Not a browser table cookie format")

        name, value, domain, path, expires = parts[:5]
        cookie = {
            "name": name,
            "value": value,
            "domain": domain or "www.mycourseville.com",
            "path": path or "/",
        }

        expiry = parse_expiry(expires)
        if expiry:
            cookie["expiry"] = expiry

        if len(parts) > 6 and is_checked(parts[6]):
            cookie["httpOnly"] = True

        if len(parts) > 7 and is_checked(parts[7]):
            cookie["secure"] = True

        if len(parts) > 8 and parts[8].strip() in {"Strict", "Lax", "None"}:
            cookie["sameSite"] = parts[8].strip()

        cookies.append(normalize_cookie(cookie))

    if not cookies:
        raise ValueError("No browser table cookies found")

    return cookies


def parse_netscape_cookies(text: str) -> list[dict]:
    cookies = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) != 7:
            raise ValueError("Not a Netscape cookie format")

        domain, _flag, path, secure, expires, name, value = parts
        cookie = {
            "domain": domain,
            "path": path or "/",
            "secure": secure.upper() == "TRUE",
            "name": name,
            "value": value,
        }

        if expires and expires != "0":
            cookie["expiry"] = int(expires)

        cookies.append(normalize_cookie(cookie))

    if not cookies:
        raise ValueError("No Netscape cookies found")

    return cookies


def parse_header_cookies(text: str) -> list[dict]:
    cookies = []

    for item in text.replace("\n", ";").split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue

        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()

        if name.lower() in {
            "domain", "path", "expires", "max-age", "secure", "httponly", "samesite",
        }:
            continue

        cookies.append(
            normalize_cookie(
                {
                    "name": name,
                    "value": value,
                    "domain": "www.mycourseville.com",
                    "path": "/",
                    "secure": True,
                }
            )
        )

    if not cookies:
        raise ValueError("No name=value cookies found")

    return cookies


def parse_cookies(text: str) -> list[dict]:
    if text.startswith("[") or text.startswith("{"):
        return parse_json_cookies(text)

    try:
        return parse_browser_table_cookies(text)
    except ValueError:
        pass

    try:
        return parse_netscape_cookies(text)
    except ValueError:
        return parse_header_cookies(text)

# --- End Cookie Parsing Functions ---


@app.route('/assignments', methods=['GET'])
def get_assignments():
    print("Received request from n8n. Launching Chrome...")
    
    options = Options()
    options.add_argument("--headless") # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # 1. Navigate to the domain first to allow setting cookies
        driver.get("https://www.mycourseville.com")
        
        # 2. Load and set cookies from cookie.txt
        if COOKIE_FILE.exists():
            cookie_text = COOKIE_FILE.read_text(encoding="utf-8").strip()
            if cookie_text:
                cookies = parse_cookies(cookie_text)
                for cookie in cookies:
                    driver.add_cookie(cookie)
            else:
                print("Warning: cookie.txt is empty.")
        else:
            print("Warning: cookie.txt not found.")

        # 3. Navigate to the assignments dashboard
        driver.get("https://www.mycourseville.com/?q=courseville/home")
        
        # Wait a bit for the page to render (can use WebDriverWait for specific elements if needed)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 4. Scrape the data using asynchronous JavaScript execution
        # We use async script to fetch and check each assignment page quickly without reloading Selenium
        driver.set_script_timeout(60)
        
        result = driver.execute_async_script("""
            const callback = arguments[arguments.length - 1];

            (async () => {
                try {
                    // Step 4.1: Safely click the notification bell to load the panel
                    // We use preventDefault to stop the browser from navigating away and causing a timeout
                    let items = document.querySelectorAll('.cv-active-panel .cv-item');
                    if (items.length === 0) {
                        const bellBtn = document.querySelector('a[aria-label="Notifications"]');
                        if (bellBtn) {
                            bellBtn.addEventListener('click', e => e.preventDefault());
                            bellBtn.click();
                        }
                        // Wait for the notification panel to appear (max 5 seconds)
                        for (let i = 0; i < 10; i++) {
                            items = document.querySelectorAll('.cv-active-panel .cv-item');
                            if (items.length > 0) break;
                            await new Promise(r => setTimeout(r, 500));
                        }
                    }

                    // Step 4.2: Build a dictionary of Course ID -> Course Full Name
                    // This uses the course cards on the dashboard to get the full name
                    const courseMap = {};
                    const courseContainers = document.querySelectorAll('.course-container');
                    courseContainers.forEach(c => {
                        const idDiv = c.querySelector('.course-content div:first-child');
                        const nameDiv = c.querySelector('.course-content .course-title');
                        if (idDiv && nameDiv) {
                            const cid = idDiv.innerText.split(' ')[0].trim();
                            courseMap[cid] = nameDiv.innerText.trim();
                        }
                    });

                    // Step 4.3: Extract basic assignment info from the loaded notification panel
                    const tasks = [];
                    
                    for (const item of items) {
                        const linkEl = item.querySelector('a[href*="worksheet"]');
                        if (!linkEl) continue;
                        
                        const badge = item.querySelector('.cvui-course-badge');
                        const titleEl = item.querySelector('strong');
                        
                        if (badge && titleEl) {
                            tasks.push({
                                courseId: badge.innerText.trim(),
                                title: titleEl.innerText.replace(/["“”]/g, '').trim(),
                                url: linkEl.href
                            });
                        }
                    }
                    
                    // Step 4.4: Fetch each assignment page to check if it's submitted and extract due date
                    const upcomingAssignments = [];
                    for (const task of tasks) {
                        const res = await fetch(task.url);
                        const html = await res.text();
                        
                        let isSubmitted = false;
                        // Check if the submission status exists and indicates a previous submission
                        if (html.includes('id="courseville-worksheet-work-status"')) {
                            const match = html.match(/id="courseville-worksheet-work-status"[^>]*>([^<]+)</);
                            if (match && match[1].includes('latest submission was made')) {
                                isSubmitted = true;
                            }
                        }
                        
                        // Parse the due date from the hidden screen-reader span
                        // Example: <span class="sr-only">Out on 02 October 2026 Due on 08 October 2026 [due] at 09:00</span>
                        const dueMatch = html.match(/Due on (.*?) \\[[^\\]]+\\] at (\\d{2}:\\d{2})/);
                        let dueAt = "Unknown Date";
                        if (dueMatch) {
                            dueAt = dueMatch[1].trim() + ' ' + dueMatch[2].trim(); // e.g., "08 October 2026 09:00"
                        }

                        let finalTitle = task.title;
                        if (isSubmitted) {
                            finalTitle = finalTitle + " (✅ ส่งแล้ว)";
                        }
                        
                        upcomingAssignments.push({
                            course: {
                                id: task.courseId,
                                label: courseMap[task.courseId] || task.courseId
                            },
                            title: finalTitle,
                            dueAt: dueAt,
                            url: task.url
                        });
                    }
                    
                    callback({ success: true, data: upcomingAssignments });
                    
                } catch (err) {
                    callback({ success: false, error: err.toString() });
                }
            })();
        """)
        
        if result.get('success'):
            return jsonify({"upcomingAssignments": result.get('data', [])})
        else:
            print("Error inside JS execution:", result.get('error'))
            return jsonify({"error": result.get('error')}), 500
        
    except Exception as e:
        print("Error during scraping:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        driver.quit()

if __name__ == '__main__':
    # Run on port 3000 to match the n8n HTTP Request node configuration
    app.run(port=3000)
