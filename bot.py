import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import os
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

def fetch_assignments():
    print("Launching Chrome to fetch assignments...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://www.mycourseville.com")
        
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

        driver.get("https://www.mycourseville.com/?q=courseville/home")
        
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        driver.set_script_timeout(60)
        
        result = driver.execute_async_script("""
            const callback = arguments[arguments.length - 1];

            (async () => {
                try {
                    let items = document.querySelectorAll('.cv-active-panel .cv-item');
                    if (items.length === 0) {
                        const bellBtn = document.querySelector('a[aria-label="Notifications"]');
                        if (bellBtn) {
                            bellBtn.addEventListener('click', e => e.preventDefault());
                            bellBtn.click();
                        }
                        for (let i = 0; i < 10; i++) {
                            items = document.querySelectorAll('.cv-active-panel .cv-item');
                            if (items.length > 0) break;
                            await new Promise(r => setTimeout(r, 500));
                        }
                    }

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
                    
                    const upcomingAssignments = [];
                    for (const task of tasks) {
                        const res = await fetch(task.url);
                        const html = await res.text();
                        
                        let isSubmitted = false;
                        if (html.includes('id="courseville-worksheet-work-status"')) {
                            const match = html.match(/id="courseville-worksheet-work-status"[^>]*>([^<]+)</);
                            if (match && match[1].includes('latest submission was made')) {
                                isSubmitted = true;
                            }
                        }
                        
                        const dueMatch = html.match(/Due on (.*?) \\[[^\\]]+\\] at (\\d{2}:\\d{2})/);
                        let dueAt = "Unknown Date";
                        if (dueMatch) {
                            dueAt = dueMatch[1].trim() + ' ' + dueMatch[2].trim();
                        }

                        let finalTitle = task.title;
                        if (isSubmitted) {
                            finalTitle = finalTitle + " (✅ Submitted)";
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
            return result.get('data', [])
        else:
            print("Error inside JS execution:", result.get('error'))
            return []
            
    except Exception as e:
        print("Error during scraping:", e)
        return []
    finally:
        driver.quit()

def format_discord_message(assignments):
    if not assignments:
        return "🎉 **No pending assignments!** Enjoy your break."
        
    courses = {}
    for task in assignments:
        cid = task['course']['id']
        if cid not in courses:
            courses[cid] = {
                'name': task['course']['label'],
                'tasks': []
            }
        courses[cid]['tasks'].append(task)
        
    message_lines = ["📚 **MyCourseVille Assignment Update**\n"]
    
    for cid, course_data in courses.items():
        # Remove extra text from course name like "(2024/1) [Section 1] LMS Student"
        clean_name = re.sub(r'\s*\(\d{4}/\d+\)', '', course_data['name'])
        clean_name = re.sub(r'\s*\[Section[^\]]*\]', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s+LMS\s+Student\s*$', '', clean_name, flags=re.IGNORECASE).strip()
        
        message_lines.append(f"**{clean_name}**")
        for task in course_data['tasks']:
            due_text = task['dueAt']
            title = task['title']
            url = task['url']
            message_lines.append(f"- [{title}](<{url}>) — Due by {due_text}")
        message_lines.append("") 
        
    return "\n".join(message_lines)

def send_discord_webhook(content):
    webhook_file = BASE_DIR / "discord_webhook.txt"
    if webhook_file.exists():
        WEBHOOK_URL = webhook_file.read_text(encoding="utf-8").strip()
    else:
        WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        
    if not WEBHOOK_URL:
        print("❌ Error: Webhook URL is missing. Please set DISCORD_WEBHOOK_URL or create discord_webhook.txt")
        return

    payload = {"content": content}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        WEBHOOK_URL, 
        data=data, 
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    try:
        urllib.request.urlopen(req)
        print("✅ Discord message sent successfully!")
    except Exception as e:
        print("❌ Error sending Discord message:", e)

def job():
    print(f"[{datetime.now()}] Fetching assignments from MyCourseVille...")
    assignments = fetch_assignments()
    message = format_discord_message(assignments)
    send_discord_webhook(message)
    print(f"[{datetime.now()}] Job completed.")

if __name__ == '__main__':
    import schedule
    import time
    import os
    
    print("🚀 MyCourseVille Notification Bot is running...")
    
    if os.environ.get("GITHUB_ACTIONS"):
        import configparser
        config = configparser.ConfigParser()
        config_file = BASE_DIR / "config.ini"
        wait_until_target = True
        
        if config_file.exists():
            config.read(config_file, encoding='utf-8')
            if config.has_option('Settings', 'WAIT_UNTIL_TARGET_TIME'):
                val = config.get('Settings', 'WAIT_UNTIL_TARGET_TIME').strip().lower()
                wait_until_target = val in ('true', '1', 'yes', 'y', 'on')
                
        print(f"Running in GitHub Actions mode (Wait until target: {wait_until_target})")
        
        if wait_until_target:
            bkk_tz = timezone(timedelta(hours=7))
            now = datetime.now(bkk_tz)
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            
            if now < target:
                wait_seconds = (target - now).total_seconds()
                print(f"Waiting for {int(wait_seconds)} seconds until {target.strftime('%H:%M:%S')} (BKK)...")
                remaining = wait_seconds
                while remaining > 0:
                    sleep_time = min(10, remaining)
                    time.sleep(sleep_time)
                    remaining -= sleep_time
                    
            print("Target time reached!")
            
        print("Executing job...")
        job()
    else:
        # Test run once immediately
        job()
        
        # Schedule to run automatically every day at 08:00
        schedule.every().day.at("08:00").do(job)
        print("⏳ Scheduled to run automatically every day at 08:00. (Leave this window open)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)
