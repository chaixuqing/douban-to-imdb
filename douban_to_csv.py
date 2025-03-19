import os                     # File and directory operations
import sys                    # System-specific parameters and functions
import csv                    # CSV file reading and writing
import time                   # Time access and conversions
import random                 # Generate random numbers
import requests               # HTTP library for making requests
import pickle                 # Python object serialization
import json                   # JSON encoder and decoder
from datetime import datetime # Date and time manipulation
from typing import List, Dict, Optional, Union, Tuple, Any, Iterator, TypeVar  # Type hinting
from bs4 import BeautifulSoup # HTML parsing library
from selenium import webdriver                     # Browser automation
from selenium.webdriver.chrome.options import Options  # Chrome browser options
from selenium.webdriver.chrome.service import Service  # Chrome driver service
from selenium.webdriver.common.by import By            # Element locating strategies
from selenium.webdriver.support.ui import WebDriverWait # Wait functionality
from selenium.webdriver.support import expected_conditions as EC  # Wait conditions
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException  # Exception handling
from webdriver_manager.chrome import ChromeDriverManager  # Auto-download ChromeDriver
import argparse               # Command-line argument parsing
import re                     # Regular expression operations
from pathlib import Path      # Object-oriented filesystem paths

# Modern user agent strings to appear as legitimate browsers
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# Global configuration variables
START_DATE = '20050502'  # Default date cutoff for movie collection (YYYYMMDD format)
IS_OVER = False  # Flag indicating when date-based processing is complete
MAX_RETRIES = 3  # Maximum number of retry attempts for failed requests
RETRY_DELAY = 5  # Base delay in seconds between retry attempts (random additional delay is added)
DRIVER: Optional[webdriver.Chrome] = None  # Global WebDriver instance for browser automation
IS_LOGGED_IN = False  # Flag tracking login state
COOKIE_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "douban_cookies.pkl"  # Path for storing authentication cookies

# At the top of the file, add these environment variables to disable proxies system-wide
os.environ['NO_PROXY'] = '*'
if 'HTTP_PROXY' in os.environ:
    os.environ.pop('HTTP_PROXY')
if 'HTTPS_PROXY' in os.environ:
    os.environ.pop('HTTPS_PROXY')

def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Configure and initialize a Chrome WebDriver instance with anti-detection measures.
    
    This function creates a new Chrome WebDriver if none exists, configuring it with 
    various options to evade bot detection mechanisms employed by websites. These include
    disabling automation flags, setting a realistic window size, using random user agents,
    and executing JavaScript to modify browser properties that could reveal automation.
    
    Args:
        headless (bool): Whether to run the browser in headless mode without UI.
                         Default is True. Set to False for debugging or manual interaction.
    
    Returns:
        webdriver.Chrome: A configured Chrome WebDriver instance
        
    Raises:
        SystemExit: If WebDriver setup fails critically
    """
    global DRIVER
    
    # Return existing driver if already initialized
    if DRIVER is not None:
        return DRIVER
        
    try:
        # Initialize Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")  # Modern headless mode
        
        # Anti-detection measures for evasion of bot detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disables Chrome's automation flag
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcomes limited /dev/shm size in some environments
        chrome_options.add_argument("--no-sandbox")  # Less secure but more stable in some environments
        chrome_options.add_argument("--window-size=1920,1080")  # Realistic screen resolution
        chrome_options.add_argument(f"--user-agent={get_random_user_agent()}")  # Random user agent
        
        # Network and security options to fix connection issues
        chrome_options.add_argument("--ignore-certificate-errors")  # Ignore SSL certificate errors
        chrome_options.add_argument("--allow-insecure-localhost")  # Allow insecure connections to localhost
        chrome_options.add_argument("--disable-web-security")  # Disable same-origin policy
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")  # Disable site isolation
        
        # Disable proxy usage in Chrome
        chrome_options.add_argument("--no-proxy-server")  # Don't use any proxy
        chrome_options.add_argument("--proxy-bypass-list=*")  # Bypass proxy for all connections
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Hides automation flags
        chrome_options.add_experimental_option("useAutomationExtension", False)  # Disables automation extension
        
        # Browser preferences for additional stealth
        prefs = {
            "profile.default_content_setting_values.notifications": 2,  # Block notifications that might interrupt
            "credentials_enable_service": False,  # Disable password saving prompts
            "profile.password_manager_enabled": False,  # Disable password manager
            "profile.default_content_settings.popups": 0,  # Block popups
            "profile.managed_default_content_settings.images": 2,  # Don't load images for better performance
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Two approaches to initializing WebDriver with different ChromeDriver sources
        try:
            # First try with explicit driver path
            driver_path = Path.home() / ".wdm" / "drivers" / "chromedriver" / "win64" / "129.0.6668.100" / "chromedriver-win32" / "chromedriver.exe"
            if driver_path.exists():
                service = Service(executable_path=str(driver_path))
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                raise FileNotFoundError("ChromeDriver not found at the expected path")
        except:
            # Fall back to automatic ChromeDriver download and installation
            print("Using automatic ChromeDriver download...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute JavaScript to modify browser properties for enhanced stealth
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")  # Remove webdriver flag
        driver.execute_script("window.navigator.chrome = {runtime: {}};")  # Add chrome object to navigator
        # Override permissions API to prevent fingerprinting
        driver.execute_script("const originalQuery = window.navigator.permissions.query; window.navigator.permissions.query = (parameters) => { return Promise.resolve({state: 'prompt'}); };")
        
        # Set page load timeout to avoid hanging indefinitely
        driver.set_page_load_timeout(30)
        
        # Store and return the configured driver
        DRIVER = driver
        return driver
    except Exception as e:
        print(f"Error setting up Chrome WebDriver: {e}")
        print("Please make sure you have Chrome installed and compatible chromedriver in your PATH")
        sys.exit(1)  # Exit on critical driver setup failure


def quit_driver() -> None:
    """
    Safely close and quit the WebDriver instance.
    
    This function attempts to gracefully terminate the WebDriver session,
    ensuring the browser process is properly closed and resources are freed.
    It handles any exceptions that might occur during the shutdown process
    and resets the global DRIVER reference.
    """
    global DRIVER
    if DRIVER is not None:
        try:
            DRIVER.quit()  # Properly close the browser and end the session
        except Exception as e:
            print(f"Error closing WebDriver: {e}")
        DRIVER = None  # Reset the global reference


def get_random_user_agent() -> str:
    """
    Select a random user agent string from the predefined list.
    
    Using different user agents helps avoid detection by making each request
    appear to come from different browsers/devices. This function randomly
    selects one from the USER_AGENTS global list.
    
    Returns:
        str: A randomly selected user agent string
    """
    return random.choice(USER_AGENTS)


def handle_login_challenge(driver: webdriver.Chrome, url: str) -> bool:
    """
    Handle Douban's login challenge if it appears during page access.
    
    This function detects if Douban requires authentication and guides
    the user through the login process. It can attempt to automatically
    click login buttons and then waits for manual user completion of the
    authentication flow.
    
    Args:
        driver (webdriver.Chrome): The WebDriver instance
        url (str): The URL being accessed when the challenge appeared
        
    Returns:
        bool: True if login was successful or no challenge was detected,
              False if login failed
    """
    global IS_LOGGED_IN
    
    try:
        # Check for specific text indicating login requirement
        if "有异常请求从你的 IP 发出" in driver.page_source or "请 登录 使用豆瓣" in driver.page_source:
            print("\n检测到需要登录挑战！请在浏览器中完成登录流程...")
            
            # Try to automate initial login button click
            try:
                login_link = driver.find_element(By.LINK_TEXT, "登录")
                login_link.click()
                print("已自动点击登录按钮，请在弹出的窗口中完成登录")
            except Exception as e:
                print(f"无法自动点击登录按钮 ({e})，请手动点击登录并完成验证")
            
            # Wait for user to complete manual login steps
            input("请在浏览器中完成登录后，按回车键继续...")
            
            # Refresh page to apply login session
            driver.get(url)
            
            # Wait for page load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Verify login success by checking for presence of challenge text
            if "有异常请求从你的 IP 发出" in driver.page_source or "请 登录 使用豆瓣" in driver.page_source:
                print("登录似乎未成功，请再次尝试")
                return False
            else:
                print("登录成功！")
                IS_LOGGED_IN = True
                # Save cookies after successful login
                save_cookies()
                return True
        elif "个人主页" in driver.page_source or "我读" in driver.page_source:
            # User is already logged in (detected by presence of personal page elements)
            print("已检测到用户已登录豆瓣")
            IS_LOGGED_IN = True
            return True
        else:
            return True  # No challenge detected
    except Exception as e:
        print(f"处理登录挑战时出错: {e}")
        return False


def url_generator(user_id: str) -> Iterator[str]:
    """
    Generate URLs for all pages of a user's movie collection.
    
    This function yields URLs for each page of a user's movie collection,
    calculating the proper pagination parameters. It ensures grid view
    mode is used for consistent parsing and handles the case where
    there is only a single page.
    
    Args:
        user_id (str): Douban user ID
        
    Yields:
        str: URL for each page of the user's movie collection
    """
    # Base URL for user's movie collection
    url = f"https://movie.douban.com/people/{user_id}/collect"
    
    # Ensure grid mode for better parsing consistency
    if "mode=grid" not in url:
        url = f"{url}?sort=time&rating=all&filter=all&mode=grid"
    
    # Get page to analyze pagination
    r = make_request(url)
    if not r:
        print("Failed to access user's collection page. Assuming one page only.")
        yield url
        return
    
    # Parse pagination information
    soup = BeautifulSoup(r.text, "lxml")
    paginator = soup.find("div", {"class": "paginator"})
    
    # Handle single page case
    if not paginator:
        print("总共 1 页")
        yield url
        return
    
    # Process multi-page collections
    try:
        page_links = paginator.find_all("a")
        if not page_links:
            print("总共 1 页")
            yield url
            return
            
        # Find maximum page number by checking all numeric link texts
        max_page = 1
        for link in page_links:
            if link.text.isdigit():
                page_num = int(link.text)
                if page_num > max_page:
                    max_page = page_num
        
        print(f"总共 {max_page} 页")
        
        # Generate URL for each page with proper start parameter
        for page in range(1, max_page + 1):
            # Douban uses 0-based indexing with 15 items per page
            start_index = (page - 1) * 15
            page_url = f"https://movie.douban.com/people/{user_id}/collect?start={start_index}&sort=time&rating=all&filter=all&mode=grid"
            yield page_url
            
    except Exception as e:
        print(f"解析分页时出错: {e}")
        print("继续使用单页...")
        yield url


def export(user_id: str) -> None:
    """
    Main function to export a user's movie collection to a CSV file.
    
    This function processes all pages of a user's movie collection,
    extracting movie information and saving it to a CSV file. It
    handles pagination, date filtering, and provides progress updates.
    
    Args:
        user_id (str): Douban user ID to scrape
    """
    # Get URLs for all pages
    urls = list(url_generator(user_id))  # Convert to list to get count
    info: List[List[Union[str, int, None]]] = []
    page_no = 1
    
    # Process each page URL
    for url in urls:
        # Stop if we've reached a movie before the cutoff date
        if IS_OVER:
            break
                
        print(f"Scraping page {page_no}/{len(urls)}")
        
        # Get movie information from current page
        page_info = get_info(url)
        if page_info:  # Only add data if the page had valid results
            info.extend(page_info)
            
        # Add random delay between pages to avoid rate limiting
        if not IS_OVER:
            delay = random.uniform(2, 5)
            time.sleep(delay)
            
        page_no += 1
    
    # Handle case where no movie data was collected
    if not info:
        print("未能获取到任何电影数据。这可能是由于豆瓣的反爬虫机制导致的。")
        print("请尝试：")
        print("1. 在浏览器中手动登录豆瓣，然后再运行脚本")
        print("2. 尝试使用非无头模式的浏览器")
        return
        
    # Save collected data to CSV file
    print(f'处理完成, 总共处理了 {len(info)} 部电影')
    file_name = Path(os.path.dirname(os.path.abspath(__file__))) / 'movie.csv'
    with open(file_name, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerows(info)
    print('保存电影评分至：', file_name)


def check_user_exist(user_id: str) -> bool:
    """
    Check if a Douban user ID exists.
    
    This function attempts to access a user's profile page
    and determines if the user exists based on page content.
    
    Args:
        user_id (str): Douban user ID to check
        
    Returns:
        bool: True if user exists, False otherwise
    """
    r = make_request(f'https://movie.douban.com/people/{user_id}/')
    if not r:
        return False
        
    soup = BeautifulSoup(r.text, 'lxml')
    if soup.title and '页面不存在' in soup.title.text:
        return False
    else:
        return True


def save_cookies() -> bool:
    """
    Save browser session cookies to a file for later use.
    
    This function serializes the current WebDriver's cookies to a pickle file,
    allowing authentication state to be preserved between script runs.
    
    Returns:
        bool: True if cookies were saved successfully, False otherwise
    """
    if DRIVER:
        try:
            print("保存登录cookies...")
            # Create directory if it doesn't exist
            COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Serialize cookies to pickle file
            pickle.dump(DRIVER.get_cookies(), open(COOKIE_FILE, "wb"))
            print(f"Cookies已保存到: {COOKIE_FILE}")
            return True
        except Exception as e:
            print(f"保存cookies时出错: {e}")
    return False


def load_cookies() -> bool:
    """
    Load previously saved cookies into the current browser session.
    
    This function attempts to restore a previous authentication state
    by loading cookies from a file and adding them to the WebDriver.
    It verifies if login was successful after loading the cookies.
    
    Returns:
        bool: True if cookies were loaded and login was successful, False otherwise
    """
    global IS_LOGGED_IN
    
    if not DRIVER:
        return False
        
    if not COOKIE_FILE.exists():
        print("No saved cookies found")
        return False
        
    try:
        print("正在加载已保存的cookies...")
        cookies = pickle.load(open(COOKIE_FILE, "rb"))
        
        # Visit domain first to ensure cookies can be set
        DRIVER.get("https://www.douban.com")
        time.sleep(1)
        
        # Add each cookie to the browser session
        for cookie in cookies:
            try:
                DRIVER.add_cookie(cookie)
            except Exception as e:
                print(f"Error adding cookie: {e}")
                
        # Refresh to apply cookies
        DRIVER.refresh()
        time.sleep(2)
        
        # Verify login success by checking for user-specific elements
        if "你的账号" in DRIVER.page_source or "我的豆瓣" in DRIVER.page_source:
            print("通过保存的Cookies成功登录!")
            IS_LOGGED_IN = True
            return True
        else:
            print("使用保存的cookies登录失败")
            return False
    except Exception as e:
        print(f"加载cookies时出错: {e}")
        return False


def make_request(url: str, use_selenium: bool = False) -> Optional[Union[requests.Response, Any]]:
    """
    Make an HTTP request with retry functionality and anti-bot detection measures.
    
    This function attempts to retrieve content from a URL using either requests library 
    (for efficiency) or Selenium WebDriver (for handling pages requiring JavaScript). 
    It includes retry logic for handling transient failures.
    
    Args:
        url (str): The URL to request
        use_selenium (bool): If True, use Selenium WebDriver instead of requests.
                           Default is False.
                           
    Returns:
        requests.Response or Any: The response object or page source if using Selenium.
                                 None if all retries fail.
    """
    global DRIVER
    
    # For Douban, let's default to using Selenium first since 
    # it's more likely to work with current access restrictions
    if "douban.com" in url and not use_selenium:
        print("Using Selenium for Douban access by default")
        use_selenium = True
    
    for attempt in range(MAX_RETRIES):
        try:
            if use_selenium or DRIVER:
                # Use Selenium for JavaScript-heavy pages or if driver already exists
                driver = setup_driver(headless=False)  # Use visible browser to debug issues
                
                print(f"Attempting to access URL: {url}")
                # Navigate to the URL
                driver.get(url)
                
                # Wait for page to load
                WebDriverWait(driver, 20).until(  # Extended timeout
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Debug output - check if we're getting a blank page or connection issues
                if "无法访问此网站" in driver.page_source or "ERR_" in driver.page_source:
                    print(f"Browser connection error detected: {driver.page_source[:200]}")
                    raise WebDriverException("Connection error in browser")
                
                # Handle login challenges if they appear
                if not handle_login_challenge(driver, url):
                    if attempt < MAX_RETRIES - 1:
                        # Add increasing delay between retries
                        delay = RETRY_DELAY * (2 ** attempt) + random.uniform(1, 5)
                        print(f"Login failed. Retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return None
                
                # Return an object with a 'text' attribute that contains the page source
                return type('ResponseLike', (), {'text': driver.page_source})()
            else:
                # Use requests library for efficiency with simple pages
                headers = {
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache',
                }
                
                # Explicitly disable proxies to avoid connection issues
                response = requests.get(
                    url, 
                    headers=headers, 
                    timeout=20, 
                    proxies={},
                    verify=False  # Disable SSL verification
                )
                
                # Check for successful response
                if response.status_code == 200:
                    return response
                else:
                    print(f"HTTP error {response.status_code} for {url}")
                    
                    # Switch to Selenium for better handling on next retry
                    if response.status_code == 403:
                        print("Received 403 Forbidden, switching to Selenium WebDriver for next attempt")
                        use_selenium = True
                        
        except requests.exceptions.SSLError as e:
            print(f"SSL Error: {e}")
            print("Trying with SSL verification disabled...")
            # Try immediate retry with SSL verification disabled
            try:
                headers = {'User-Agent': get_random_user_agent()}
                response = requests.get(url, headers=headers, timeout=20, proxies={}, verify=False)
                if response.status_code == 200:
                    return response
            except:
                # If immediate retry fails, continue with normal retry process
                pass
                
        except requests.exceptions.ProxyError as e:
            print(f"Proxy connection error: {e}")
            print("Disabling proxy settings for next attempt...")
            # Clear any environment variables that might be setting proxies
            if 'HTTP_PROXY' in os.environ:
                os.environ.pop('HTTP_PROXY')
            if 'HTTPS_PROXY' in os.environ:
                os.environ.pop('HTTPS_PROXY')
            os.environ['NO_PROXY'] = '*'
            
            # For the next attempt, try with Selenium which may handle proxies differently
            if attempt < MAX_RETRIES - 1 and not use_selenium:
                print("Switching to Selenium for next attempt due to proxy issues")
                use_selenium = True
                
        except requests.RequestException as e:
            print(f"Request error: {e}")
            # If we're getting connectivity errors, try with Selenium next
            if "ConnectionError" in str(e) and not use_selenium:
                print("Connection error detected, switching to Selenium WebDriver for next attempt")
                use_selenium = True
        except (TimeoutException, WebDriverException) as e:
            print(f"Browser error: {e}")
            # Try refreshing the page
            if DRIVER:
                try:
                    print("Attempting to refresh the page...")
                    DRIVER.refresh()
                    time.sleep(5)  # Give it time to reload
                except:
                    pass
        except Exception as e:
            print(f"Unexpected error: {e}")
            
        # Add increasing delay between retries with exponential backoff
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAY * (2 ** attempt) + random.uniform(1, 5)
            print(f"Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
    
    print(f"Failed to retrieve {url} after {MAX_RETRIES} attempts")
    print("Network troubleshooting tips:")
    print("1. Check if you can access douban.com manually in your browser")
    print("2. Verify your network connection is stable")
    print("3. Try using a VPN if Douban is restricted in your region")
    print("4. Try running with the --visible flag to see browser interactions")
    return None


def get_rating(rating_class: Optional[str]) -> Optional[int]:
    """
    Extract rating value from Douban's CSS class name.
    
    Args:
        rating_class (str): CSS class name, e.g., "rating4-t" 
        
    Returns:
        int or None: Rating value (1-5) or None if no rating
    """
    if not rating_class:
        return None
        
    # Expected format is "ratingX-t" where X is 1-5
    try:
        # Extract the digit from the class name
        rating_digit = int(rating_class.replace("rating", "").replace("-t", ""))
        return rating_digit if 1 <= rating_digit <= 5 else None
    except (ValueError, AttributeError):
        return None


def get_imdb_id(douban_url: str) -> Optional[str]:
    """
    Extract IMDb ID from a Douban movie page.
    
    Retrieves the IMDb ID (ttXXXXXXX format) from the movie's Douban page
    by analyzing the page's sidebar where external links are listed.
    
    Args:
        douban_url (str): URL of the Douban movie page
        
    Returns:
        str or None: IMDb ID in ttXXXXXXX format, or None if not found
    """
    try:
        # Get the movie page
        r = make_request(douban_url, use_selenium=True)
        if not r:
            print(f"Failed to access movie page: {douban_url}")
            return None
            
        # Parse the page
        soup = BeautifulSoup(r.text, "lxml")
        
        # Look for IMDb ID in the info section
        info_section = soup.select_one("#info")
        if not info_section:
            print(f"Could not find info section on page: {douban_url}")
            return None
            
        # Try different approaches to find the IMDb ID
        
        # 1. Look for 'IMDb' text followed by the ID
        for span in info_section.find_all("span", class_="pl"):
            if "IMDb" in span.text:
                imdb_text = span.next_sibling
                if imdb_text and isinstance(imdb_text, str):
                    imdb_id = imdb_text.strip()
                    if imdb_id.startswith("tt"):
                        return imdb_id
        
        # 2. Look for external links containing IMDb
        imdb_link = soup.select_one('a[href*="imdb.com/title/tt"]')
        if imdb_link:
            href = imdb_link.get("href", "")
            match = re.search(r'(tt\d+)', href)
            if match:
                return match.group(1)
                
        # 3. Last resort: look for any text that looks like an IMDb ID
        for text in info_section.stripped_strings:
            if text.startswith("tt") and len(text) > 3 and text[2:].isdigit():
                return text
                
        print(f"No IMDb ID found for: {douban_url}")
        return None
    except Exception as e:
        print(f"Error retrieving IMDb ID: {e}")
        return None


def get_info(url: str) -> Optional[List[List[Union[str, Optional[int], Optional[str]]]]]:
    """
    Extract movie information from a page of a user's Douban collection.
    
    This function parses a page of the user's movie collection in grid view,
    extracting the title, rating, IMDb ID, and date information for each movie.
    It handles various Douban page structures and edge cases.
    
    Args:
        url (str): URL of a page from the user's Douban collection
        
    Returns:
        list or None: List of movies, each as [title, rating, imdb_id]
                    None if parsing fails
    """
    info: List[List[Union[str, Optional[int], Optional[str]]]] = []
    
    # Make the request to get the page
    r = make_request(url)
    if not r:
        return None
        
    # Parse the HTML content
    soup = BeautifulSoup(r.text, "lxml")
    
    # Find all movie items on the page
    movie_items = soup.find_all("div", {"class": "item"})
    
    # If no items were found, the page might have a different structure
    # or could be empty (e.g., end of collection)
    if not movie_items:
        print("No movie items found on page. Page might be empty or have a different structure.")
        return None
        
    # Process each movie item
    for item in movie_items:
        try:
            # 1. Get the movie title
            title_elem = item.find("li", {"class": "title"})
            if not title_elem or not title_elem.em:
                title_elem = item.select_one(".title a") or item.select_one("a.title")
                
            if title_elem:
                title = title_elem.text.strip() if not title_elem.em else title_elem.em.text.strip()
            else:
                print("Could not find title element, skipping item")
                continue
                
            # 2. Get the movie's Douban link for further processing
            link_elem = item.find("a", href=True)
            if not link_elem:
                print(f"No link element found for movie: {title}")
                continue
                
            douban_link = link_elem["href"]
            
            # 3. Get user's rating (1-5 stars)
            rating = None
            rating_elem = item.find("span", class_=lambda c: c and c.startswith("rating"))
            
            if rating_elem:
                rating = get_rating(rating_elem["class"][0])
            else:
                # Try alternative rating elements
                rating_elem = (
                    item.select_one(".rate-stars") or 
                    item.select_one(".rating")
                )
                if rating_elem:
                    # Parse stars directly if available
                    stars = rating_elem.get("class", [])
                    for star_class in stars:
                        if star_class.startswith("rating") and star_class.endswith("-t"):
                            rating = get_rating(star_class)
                            break
            
            # 4. Get comment date
            comment_date = None
            date_span = item.find("span", {"class": "date"})
            
            if date_span:
                comment_date = date_span.text.strip()
            else:
                # Alternative date selectors
                date_elem = (
                    item.select_one(".date") or
                    item.select_one("time") or
                    item.select_one(".time") or
                    item.select_one(".collect-date")
                )
                if date_elem:
                    comment_date = date_elem.text.strip()
            
            # Use current date as fallback if no date found
            if not comment_date:
                print(f"无法获取日期，使用当前日期: {title}")
                from datetime import date
                comment_date = date.today().strftime('%Y-%m-%d')
            
            # Normalize date format across different possible formats
            if comment_date:
                date_formats = ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d']
                normalized_date = None
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(comment_date, fmt)
                        normalized_date = parsed_date.strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        continue
                
                if normalized_date:
                    comment_date = normalized_date
                else:
                    print(f"警告: 无法解析日期格式 '{comment_date}'，使用原始格式")
            
            # 5. Check if date is earlier than cutoff date, stop processing if it is
            try:
                if datetime.strptime(comment_date, '%Y-%m-%d') <= datetime.strptime(START_DATE, '%Y%m%d'):
                    global IS_OVER
                    IS_OVER = True
                    break
            except ValueError as e:
                print(f"Date parsing error: {e} for date {comment_date}")
                continue
            
            # 6. Get IMDB ID with delay to avoid rate limiting
            time.sleep(random.uniform(1, 2))
            imdb = get_imdb_id(douban_link)
            
            # 7. Store the extracted information
            info.append([title, rating, imdb])
            print(f"Processing: {title[:20]}{'...' if len(title) > 20 else ''}")
            
        except Exception as e:
            print(f"Error processing movie item: {str(e)}")
            continue
    
    return info


if __name__ == '__main__':
    """
    Main execution entry point.
    
    This code block handles command-line argument parsing, cookie management,
    user verification, and the overall execution flow of the scraping process.
    It includes error handling and cleanup to ensure proper resource management.
    """
    # Command-line argument configuration using argparse
    parser = argparse.ArgumentParser(description='Scrape Douban movie ratings and export to CSV')
    parser.add_argument('user_id', help='Douban user ID')
    parser.add_argument('start_date', nargs='?', default='20050502', help='Start date in YYYYMMDD format (default: 20050502)')
    parser.add_argument('--visible', '-v', action='store_true', help='Run in visible browser mode (non-headless)')
    parser.add_argument('--manual-login', '-m', action='store_true', help='Open browser for manual login before scraping')
    parser.add_argument('--no-cache', '-n', action='store_true', help='Do not use or save cookies cache')
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Configure global variables based on command-line arguments
    user_id = args.user_id
    if args.start_date:
        # Use module-level START_DATE without global declaration
        # This is valid in Python because we're modifying it at module level
        globals()['START_DATE'] = args.start_date
        
    print(f'Starting to scrape {"all" if START_DATE == "20050502" else f"post {START_DATE}"} movie ratings...')
    
    # Verify user exists
    if not check_user_exist(user_id):
        print('Invalid Douban user ID. Please check and try again.')
        print('For help finding your ID, see: https://github.com/fisheepx/douban-to-imdb')
        sys.exit(1)
        
    # Initialize browser if automated session is needed
    try:
        # Set up the browser (visible or headless based on command-line flag)
        driver = setup_driver(headless=not args.visible)
        
        # Try to load existing cookies unless no-cache flag is set
        if not args.no_cache and load_cookies():
            print("Using saved login session")
        elif args.manual_login:
            # Open browser for manual login if requested
            driver.get("https://www.douban.com/")
            print("Please log in to Douban in the browser window")
            input("Press Enter after logging in...")
            if "个人主页" in driver.page_source or "我的豆瓣" in driver.page_source:
                print("Login successful!")
                IS_LOGGED_IN = True
                save_cookies()  # Save the new session cookies
            else:
                print("Login unsuccessful or couldn't be detected")
                
        # Start the export process
        export(user_id)
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Cleaning up...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Clean up resources
        quit_driver()
        print("Done!")
