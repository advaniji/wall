import os
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DRIVE_FOLDER_ID = '1gEtuIBff3DiRfcTUHLZchQDyCw90QBp3'
PLAYLIST_URL = 'https://www.youtube.com/playlist?list=PL9Zg64loGCGCFo5VXVb0KJrbiPhmOnGkK'
TEMP_DIR = '/tmp/youtube_screenshots'

def setup_drive():
    """Initialize Google Drive authentication with service account"""
    try:
        gauth = GoogleAuth()
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.environ.get('GDRIVE_CREDENTIALS', 'abc.json'),
            ['https://www.googleapis.com/auth/drive']
        )
        gauth.credentials = credentials
        return GoogleDrive(gauth)
    except Exception as e:
        logger.error(f"Drive initialization failed: {str(e)}")
        raise

def browser_setup():
    """Configure headless Chrome browser for Render.com using older Selenium parameters"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")

        # Use executable_path and chrome_options for Selenium versions below 4.x
        return webdriver.Chrome(executable_path='/usr/bin/chromedriver', chrome_options=chrome_options)
    except WebDriverException as e:
        logger.error(f"Browser setup failed: {str(e)}")
        raise

def process_video(driver, idx, video_url):
    """Process individual video and capture screenshots"""
    try:
        logger.info(f"Processing video {idx}: {video_url}")
        driver.get(video_url)
        time.sleep(5)  # Allow page to load

        try:
            video = driver.find_element(By.TAG_NAME, "video")
            driver.execute_script("arguments[0].controls = false;", video)
            # Attempt to force HD quality via JavaScript
            try:
                driver.execute_script("arguments[0].setPlaybackQuality('hd1080');", video)
                logger.info("Attempted to set video quality to hd1080 via JS.")
            except Exception as quality_ex:
                logger.warning(f"Failed to set quality via JS: {quality_ex}")

            duration = driver.execute_script("return arguments[0].duration", video)
        except NoSuchElementException:
            logger.warning(f"No video element found in video {idx}")
            return

        if duration < 10:
            logger.info(f"Skipping short video {idx} (duration: {duration}s)")
            return

        os.makedirs(TEMP_DIR, exist_ok=True)

        for shot_num in range(1, 5):
            try:
                target_time = random.uniform(duration * 0.1, duration * 0.9)
                driver.execute_script("arguments[0].currentTime = arguments[1];", video, target_time)
                time.sleep(2)  # Allow frame to update

                filename = f"video_{idx}_shot_{shot_num}.png"
                local_path = os.path.join(TEMP_DIR, filename)
                
                # Capture and save screenshot
                driver.save_screenshot(local_path)
                logger.info(f"Saved screenshot: {local_path}")

                # Upload to Google Drive
                upload_to_drive(local_path, filename)
                
                # Cleanup local file
                os.remove(local_path)

            except Exception as e:
                logger.error(f"Error processing shot {shot_num} of video {idx}: {str(e)}")

    except Exception as e:
        logger.error(f"General error processing video {idx}: {str(e)}")

def upload_to_drive(local_path, filename):
    """Upload file to Google Drive"""
    try:
        gfile = drive.CreateFile({
            'title': filename,
            'parents': [{'id': DRIVE_FOLDER_ID}]
        })
        gfile.SetContentFile(local_path)
        gfile.Upload()
        logger.info(f"Successfully uploaded {filename} to Drive")
    except Exception as e:
        logger.error(f"Drive upload failed for {filename}: {str(e)}")
        raise

def main():
    """Main execution flow"""
    driver = None
    try:
        driver = browser_setup()
        driver.get(PLAYLIST_URL)
        time.sleep(5)  # Allow playlist to load

        video_elements = driver.find_elements(By.ID, "video-title")
        video_links = [elem.get_attribute("href") for elem in video_elements]
        logger.info(f"Found {len(video_links)} videos in playlist")

        for idx, video_url in enumerate(video_links[:5], 1):  # Process first 5 for testing
            if video_url:  # Skip None values
                process_video(driver, idx, video_url)

    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logger.info("Browser instance closed")

if __name__ == "__main__":
    # Initialize Google Drive connection
    try:
        drive = setup_drive()
        logger.info("Successfully authenticated with Google Drive")
    except Exception as e:
        logger.error("Failed to initialize Google Drive connection")
        raise

    # Create temp directory if not exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Start main process
    main()
