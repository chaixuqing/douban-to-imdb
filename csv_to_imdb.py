"""
Douban to IMDb Rating Transfer Script
------------------------------------
This script transfers movie ratings from a Douban export CSV file to IMDb.
It automates the process of searching for movies on IMDb using their IMDb IDs 
and applying the corresponding ratings from Douban (with optional adjustment).

Requirements:
- A CSV file named 'movie.csv' with movie names, ratings, and IMDb IDs
- Firefox browser installed
- Selenium WebDriver for Firefox

The CSV format should be:
- Column 0: Movie name
- Column 1: Douban rating (1-5 scale)
- Column 2: IMDb ID (starting with 'tt')

Usage:
- Basic: python csv_to_imdb.py
- With rating adjustment: python csv_to_imdb.py -1 (adjust rating by -1)
- To remove ratings: python csv_to_imdb.py unmark
"""

import os
import sys
import time
import csv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options

def login():
    """
    Initializes the Firefox WebDriver, navigates to IMDb sign-in page,
    and waits for the user to manually log in.
    
    The function customizes the signin page to display a Chinese message
    prompting the user to log in. It then monitors the URL to detect
    when login has completed successfully.
    
    Returns:
        WebDriver: The initialized and authenticated Firefox WebDriver session
        
    Raises:
        Exception: If there's any error during the setup or login process
    """
    try:
        # Use Firefox instead of Chrome
        options = Options()
        options.add_argument("--start-maximized")  # Maximize browser window for better visibility
        
        # Create Firefox driver with the specified options
        driver = webdriver.Firefox(options=options)
        
        # Navigate to IMDb login page
        driver.get('https://www.imdb.com/registration/signin')
        
        # Wait for the page to load completely
        time.sleep(2)
        
        try:
            # Find the sign-in perks element to modify
            element = driver.find_element(By.ID, 'signin-perks')
            
            # Make the text more visible with CSS styling
            driver.execute_script("arguments[0].setAttribute('style', 'color: red;font-size: larger; font-weight: 700;')",
                                element)
            
            # Change text to Chinese instructions for the user
            driver.execute_script("arguments[0].innerText = '请登录自己的IMDB账号, 程序将等待至登录成功。'", element)
        except NoSuchElementException:
            # Continue even if we can't find the element to modify
            # (IMDb might have updated their page structure)
            print("Could not find signin-perks element, but continuing...")
        
        # Store the current URL to detect when it changes after login
        current_url = driver.current_url
        
        # Wait until the user completes the login process
        # The loop continues until the URL changes to a non-signin page
        while True:
            # Wait for up to 10 minutes for URL to change
            WebDriverWait(driver, 600).until(EC.url_changes(current_url))
            new_url = driver.current_url
            
            # Check if we've been redirected away from the signin page
            if 'imdb.com' in new_url and 'signin' not in new_url:
                break
                
        print('IMDB登录成功')  # Print success message in Chinese
        return driver
    except Exception as e:
        # Log error details and re-raise the exception
        print(f"Login error: {e}")
        raise


def mark(is_unmark=False, rating_ajust=-1):
    """
    Main function that processes the CSV file and marks/unmarks movies on IMDb.
    
    This function reads the movie.csv file, searches for each movie on IMDb using
    its IMDb ID, and then either adds a rating or removes an existing rating.
    
    Args:
        is_unmark (bool): If True, removes ratings instead of adding them.
                         Default is False (adding ratings).
        rating_ajust (int): Adjustment to apply to Douban ratings when converting to IMDb.
                           Range is -2 to +2, default is -1.
                           
    The function handles various edge cases and errors:
    - Movies without IMDb IDs
    - Movies that already have ratings (when marking)
    - Movies that don't have ratings (when unmarking)
    - Various UI interaction failures
    
    It keeps track of successes, failures, and provides a summary at the end.
    """
    # Initialize the WebDriver with user authentication
    driver = login()
    
    # Counters and lists for tracking results
    success_marked = 0     # Successfully rated movies
    success_unmarked = 0   # Successfully unrated movies
    can_not_found = []     # Movies without valid IMDb IDs
    already_marked = []    # Movies already rated on IMDb
    never_marked = []      # Movies without ratings on IMDb
    error_movies = []      # Movies that encountered errors during processing
    
    # Get the full path to the CSV file in the same directory as the script
    file_name = os.path.dirname(os.path.abspath(__file__)) + '/movie.csv'
    
    # Open and process the CSV file
    with open(file_name, 'r', encoding='utf-8') as file:
        content = csv.reader(file, lineterminator='\n')
        for line in content:
            try:
                # Skip entries that don't have ratings on Douban
                if not line[1]:
                    continue
                    
                # Extract data from the CSV line
                movie_name = line[0]  # Movie name/title
                
                # Convert Douban rating (1-5) to IMDb rating (1-10) with adjustment
                movie_rate = int(line[1]) * 2 + rating_ajust
                
                # Get the IMDb ID
                imdb_id = line[2]
                
                # Skip movies without valid IMDb IDs
                if not imdb_id or not imdb_id.startswith('tt'):
                    can_not_found.append(movie_name)
                    print('无法在IMDB上找到：', movie_name)  # "Cannot find on IMDb" message
                    continue

                # Wait for the search box to be available (up to 60 seconds)
                WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, 'suggestion-search')))
                
                # Find, clear, and use the search box
                search_bar = driver.find_element(By.ID, 'suggestion-search')
                search_bar.clear()  # Clear any previous input
                search_bar.send_keys(imdb_id)  # Enter the IMDb ID
                search_bar.submit()  # Submit the search
                
                # Allow time for the page to load
                time.sleep(3)
                
                try:
                    # Check if the movie already has a rating by looking for specific elements
                    if is_unmark:
                        # When unmarking, look for the user rating score element
                        driver.find_element(By.XPATH, '//div[@data-testid="hero-rating-bar__user-rating__score"]')
                    else:
                        # When marking, look for the user rating container
                        driver.find_element(By.XPATH, '//div[@data-testid="hero-rating-bar__user-rating"]')
                except NoSuchElementException:
                    # Handle cases where the movie doesn't have the expected rating status
                    if is_unmark:
                        # If trying to unmark but no rating exists
                        never_marked.append(f'{movie_name}({imdb_id})')
                        print(f'并没有在IMDB上打过分：{movie_name}({imdb_id})')  # "No rating on IMDb" message
                    else:
                        # If trying to mark but already rated
                        already_marked.append(f'{movie_name}({imdb_id})')
                        print(f'已经在IMDB上打过分：{movie_name}({imdb_id})')  # "Already rated on IMDb" message
                else:
                    # If we reach here, we can proceed with the rating action
                    try:
                        # Find and click the rating button
                        rate_btn_xpath = '//div[@data-testid="hero-rating-bar__user-rating"]/button'
                        WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, rate_btn_xpath))
                        )
                        driver.find_element(By.XPATH, rate_btn_xpath).click()
                        time.sleep(1)  # Brief pause for UI to update

                        # Handle the unmark (delete rating) case
                        if is_unmark:
                            try:
                                # Find and click the delete button (second button after the star bar)
                                delete_btn = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, "//div[@class='ipc-starbar']/following-sibling::button[2]"))
                                )
                                delete_btn.click()
                                print(f'电影删除打分成功：{movie_name}({imdb_id})')  # "Successfully deleted rating" message
                                success_unmarked += 1
                            except Exception as e:
                                # Handle errors in the deletion process
                                print(f'删除评分失败: {movie_name}({imdb_id}) - {str(e)}')  # "Failed to delete rating" message
                                error_movies.append(f'{movie_name}({imdb_id}) - 删除失败')
                        else:
                            # Handle the mark (add rating) case
                            try:
                                # Import ActionChains for complex mouse interactions
                                from selenium.webdriver.common.action_chains import ActionChains
                                
                                # IMDb requires hovering over the star before clicking
                                # Find the specific star button for our rating (1-10)
                                star_ele_xpath = f'//button[@aria-label="Rate {movie_rate}"]'
                                star_ele = WebDriverWait(driver, 5).until(
                                    EC.visibility_of_element_located((By.XPATH, star_ele_xpath))
                                )
                                
                                # Create and perform the hover + click action
                                mark_action = ActionChains(driver).move_to_element(star_ele).click()
                                mark_action.perform()
                                time.sleep(1)  # Brief pause for UI to update
                                
                                # After selecting the rating, confirm it
                                confirm_rate_ele_xpath = "//div[@class='ipc-starbar']/following-sibling::button"
                                confirm_btn = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, confirm_rate_ele_xpath))
                                )
                                confirm_btn.click()
                                
                                print(f'电影打分成功：{movie_name}({imdb_id}) → {movie_rate}★')  # "Successfully rated" message
                                success_marked += 1
                            except Exception as e:
                                # Handle errors in the rating process
                                print(f'评分失败: {movie_name}({imdb_id}) - {str(e)}')  # "Failed to rate" message
                                error_movies.append(f'{movie_name}({imdb_id}) - 评分失败')
                    except Exception as e:
                        # Handle general errors in the rating interaction process
                        print(f'处理电影时出错: {movie_name}({imdb_id}) - {str(e)}')  # "Error processing movie" message
                        error_movies.append(f'{movie_name}({imdb_id}) - 处理错误')
                        
                # Pause between movies to avoid overloading the site
                time.sleep(2)  
            except Exception as e:
                # Handle general errors in processing a line from the CSV
                print(f'处理行时出错: {line} - {str(e)}')  # "Error processing line" message
                if len(line) >= 3 and line[0] and line[2]:
                    error_movies.append(f'{line[0]}({line[2]}) - 处理异常')
    
    # Properly close the browser
    try:
        driver.quit()  # quit() closes all browser windows and ends the driver session
    except:
        pass  # Ignore errors on cleanup

    # Print a summary of results
    print('***************************************************************************')
    
    if is_unmark:
        # Summary for unmarking (removing ratings) operation
        print(f'成功删除了 {success_unmarked} 部电影的打分')  # "Successfully deleted ratings for X movies"
        print(f'有 {len(can_not_found)} 部电影没能在IMDB上找到：', can_not_found)  # "X movies not found on IMDb"
        print(f'有 {len(never_marked)} 部电影并没有在IMDB上打过分：', never_marked)  # "X movies never rated on IMDb"
    else:
        # Summary for marking (adding ratings) operation
        print(f'成功标记了 {success_marked} 部电影')  # "Successfully rated X movies"
        print(f'有 {len(can_not_found)} 部电影没能在IMDB上找到：', can_not_found)  # "X movies not found on IMDb"
        print(f'有 {len(already_marked)} 部电影已经在IMDB上打过分：', already_marked)  # "X movies already rated on IMDb"
    
    # Print error summary if any errors occurred
    if error_movies:
        print(f'有 {len(error_movies)} 部电影处理失败：', error_movies)  # "X movies failed processing"
        
    print('***************************************************************************')


# Script entry point - execution begins here when run directly
if __name__ == '__main__':
    # Check if the CSV file exists
    if not os.path.exists(os.path.dirname(os.path.abspath(__file__)) + '/movie.csv'):
        print('未能找到CSV文件，请先导出豆瓣评分，请参照：',  # "CSV file not found" message
              'https://github.com/fisheepx/douban-to-imdb')
        sys.exit()
        
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == 'unmark':
        # If 'unmark' argument is provided, run in unmark mode
        mark(True)
    elif len(sys.argv) > 1:
        # If a rating adjustment argument is provided
        if sys.argv[1] not in ['-2', '-1', '0', '1', '2']:
            # Verify the adjustment is in the valid range
            print('分数调整范围不能超过±2分(默认 -1分)，请参照：',  # "Rating adjustment must be between -2 and +2" message
                  'https://github.com/fisheepx/douban-to-imdb')
            sys.exit()
        else:
            # Run with the specified rating adjustment
            mark(False, int(sys.argv[1]))
    else:
        # Run with default settings (mark mode, -1 rating adjustment)
        mark()
