import undetected_chromedriver as uc
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import pickle
import os
import time
import subprocess
from dotenv import load_dotenv
from datetime import datetime  
import requests
import re
import json
import pyperclip

load_dotenv()

class LeetCodeSessionManager:
    def __init__(self):
        self.driver = None
        self.cookie_file = "leetcode_cookies.pkl"
        self.credentials = {
            "email": os.getenv("LEETCODE_EMAIL"),
            "password": os.getenv("LEETCODE_PASSWORD")
        }
        self.max_wait = 15  # Seconds for element waits

    def create_driver(self):
        """Create Chrome driver with proper configuration"""
        try:
            options = ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--log-level=3")
            
            return uc.Chrome(
                options=options,
                version_main=self._get_chrome_major_version(),
                auto_install=True,
                use_subprocess=False,
                suppress_welcome=True,
                service_log_path=os.devnull
            )
        except Exception as e:
            print(f"Driver creation failed: {str(e)}")
            return None

    def _get_chrome_major_version(self):
        """Get Chrome's major version number"""
        try:
            result = subprocess.check_output(
                r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
                shell=True, stderr=subprocess.DEVNULL
            ).decode()
            return int(result.split()[-1].split('.')[0])
        except:
            return None  # Auto-detect if version check fails

    def start_session(self):
        """Start and manage browser session"""
        try:
            self.driver = self.create_driver()
            if not self.driver:
                raise Exception("Driver initialization failed")
            
            self.driver.set_page_load_timeout(30)
            
            # Try cookie-based authentication first
            if self._try_cookie_auth():
                return True
                
            # Manual login for first time
            if self._manual_login():
                self._save_cookies()
                return True
                
            return False
            
        except Exception as e:
            print(f"Session error: {str(e)}")
            self._safe_quit()
            return False

    def _manual_login(self):
        """Handle manual login with user interaction"""
        try:
            self.driver.get("https://leetcode.com/accounts/login/")
            
            # Fill credentials automatically
            email_field = WebDriverWait(self.driver, self.max_wait).until(
                EC.presence_of_element_located((By.ID, "id_login"))
            )
            email_field.send_keys(self.credentials["email"])
            
            password_field = self.driver.find_element(By.ID, "id_password")
            password_field.send_keys(self.credentials["password"])
            
            # Wait for manual sign-in
            print("Please manually click 'Sign In' and complete CAPTCHA...")
            print("You have 2 minutes to complete the process.")
            
            # Wait for successful login
            WebDriverWait(self.driver, 120).until(
                lambda d: "problemset" in d.current_url
            )
            return True
            
        except Exception as e:
            print(f"Manual login error: {str(e)}")
            return False

    def _try_cookie_auth(self):
        """Attempt cookie authentication"""
        if not os.path.exists(self.cookie_file):
            return False
            
        try:
            self.driver.get("https://leetcode.com")
            with open(self.cookie_file, "rb") as f:
                cookies = pickle.load(f)
                
            for cookie in cookies:
                if 'expiry' in cookie:
                    del cookie['expiry']
                self.driver.add_cookie(cookie)
                
            self.driver.refresh()
            return self._is_authenticated()
            
        except Exception as e:
            print(f"Cookie auth failed: {str(e)}")
            return False

    def _is_authenticated(self):
        """Verify authentication status"""
        try:
            self.driver.get("https://leetcode.com/problemset/all/")
            WebDriverWait(self.driver, self.max_wait).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(@id, 'navbar_user_avatar')]"))
        )
            return True
        except:
            return False

    def _save_cookies(self):
        """Save cookies for future sessions"""
        with open(self.cookie_file, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)
        print("Session cookies saved successfully")

    def _safe_quit(self):
        """Proper resource cleanup"""
        try:
            if self.driver:
                self.driver.service.process.kill()
                self.driver.quit()
        except:
            pass

    def __enter__(self):
        """Context manager entry"""
        return self if self.start_session() else None

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._safe_quit()
    
    def get_daily_problem(self):
        """Fetch today's daily problem with full URL"""
        script = """
        var callback = arguments[arguments.length - 1];
        const query = {
            "query": `query questionOfToday {
                activeDailyCodingChallengeQuestion {
                    link
                    question {
                        title
                    }
                }
            }`
        };
        
        fetch('https://leetcode.com/graphql', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Referer': 'https://leetcode.com/'
            },
            body: JSON.stringify(query)
        })
        .then(response => response.json())
        .then(data => callback(data))
        .catch(error => callback({ error: error.message }));
        """
        
        try:
            result = self.driver.execute_async_script(script)
            if 'error' in result:
                print(f"API Error: {result['error']}")
                return None
                
            base_link = result['data']['activeDailyCodingChallengeQuestion']['link']
            title = result['data']['activeDailyCodingChallengeQuestion']['question']['title']
            
            # Construct full URL with description and date parameters
            today_date = datetime.today().strftime('%Y-%m-%d')
            full_url = f"https://leetcode.com{base_link}description/?envType=daily-question&envId={today_date}"
            
            return {
                'url': full_url,
                'title': title,
                "base_link":base_link
            }
        except Exception as e:
            print(f"Daily problem fetch failed: {str(e)}")
            return None
        
    def select_python_language(self):
        """Select Python3 from the language dropdown"""
        try:
            # Click the language selector button
            # lang_button = WebDriverWait(self.driver, 15).until(
            #     EC.element_to_be_clickable((By.XPATH, 
            #         "//button[contains(@class, 'rounded') and contains(., 'C++')]"))
            # )
            # lang_button.click()

            lang_button = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'rounded') and contains(., 'C++')]"))
            )
            self.driver.execute_script("arguments[0].click();", lang_button)
            
            # Wait for dropdown to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "div[class*='p-2 rounded-lg']"))
            )
            
            # Find and click Python3 option
            python3_option = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//div[contains(@class, 'group') and contains(., 'Python3')]"))
            )
            python3_option.click()
            
            # Verify Python3 is selected
            selected_lang = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, 
                    "//button[contains(@class, 'rounded') and contains(., 'Python3')]"))
            ).text
            if "Python3" not in selected_lang:
                raise Exception("Python3 selection failed")
                
            return True
            
        except Exception as e:
            print(f"Language selection failed: {str(e)}")
            return False

    def get_problem_details(self,slug):
        """Extract problem details with improved reliability"""
        try:
            description = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "elfjS"))
            ).text
            # inputarea, view-lines 
            python_code_template=WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "view-lines"))
            ).text

            print(python_code_template)
            return {
                    "description":description,
                    "python_code_template":python_code_template
                    }

        except Exception as e:
            print(e)
            return None
    
    def insert_code(self,code):
        """
        This function use to insert code in code editor.
        """
        try:
            editor = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "inputarea"))
            )
            self.driver.execute_script("arguments[0].click();", editor)
            

            # Clear existing code
            editor.send_keys(Keys.CONTROL, "a")
            editor.send_keys(Keys.DELETE)
            
            pyperclip.copy(code)  # Copy code to clipboard
            # Paste code (maintaining indentation)
            editor.send_keys(Keys.CONTROL, 'v')
            editor.send_keys(Keys.RETURN)  # New line

            return True
        except Exception as e:
            print(f"Code insertion failed: {str(e)}")
            return False
        
    def test_generated_code(self,code):
        """
        This function use to test generated code.
        """
        try:
            if self.insert_code(code):
                test_button = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Run')]"))
                )
                test_button.click()
                #check test result
                #test_result=self.driver.find_element(By.CSS_SELECTOR, 'div[data-layout-path="/c1/ts1/t1"]')
                test_result=WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-layout-path="/c1/ts1/t1"]'))
                )
                print(test_result.text)
                return "Test Result: \n"+test_result.text
            return "Unable to insert code in code editor."
        except Exception as e:
            print(f"Code testing failed: {str(e)}")
            return "Code testing failed."

    def submit_generated_code(self):
        """
        This function use to submit generated code.
        """
        try:
            submit_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Submit')]"))
            )
            submit_button.click()

            time.sleep(5)
            submit_result=WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-layout-path="/ts0/t1"]'))
            )
            submit_result=submit_result.text
            print(submit_result)
            return submit_result
        except Exception as e:
            print(f"Code submission failed: {str(e)}")
            return "Code submission failed."