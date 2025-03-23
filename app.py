import os
import time
import random
import logging
import datetime
import shutil
import chromedriver_binary  # Automatically adds chromedriver to PATH

from flask import Flask, jsonify
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

# Initialize Flask app
app = Flask(__name__)

def setup_drive():
    """Initialize Google Drive authentication with service account."""
    try:
        credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'abc.json')
        gauth = GoogleAuth()
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_path,
            ['https://www.googleapis.com/auth/drive']
        )
        gauth.credentials = credentials
        return GoogleDrive(gauth)
    except Exception as e:
        logger.error(f"Drive initialization failed: {str(e)}")
        raise

def browser_setup():
    """Configure headless Chrome browser for Render.com."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--disable-gpu")
        return webdriver.Chrome(options=chrome_options)
    except WebDriverException as e:
        logger.error(f"Browser setup failed: {str(e)}")
        raise

def process_video(driver, idx, video_url):
    """Process an individual video and capture screenshots."""
    errors = []
    try:
        logger.info(f"Processing video {idx}: {video_url}")
        driver.get(video_url)
        time.sleep(5)  # Allow page to load
        logger.info(f"Loaded video page for video {idx}")

        try:
            video = driver.find_element(By.TAG_NAME, "video")
            driver.execute_script("arguments[0].controls = false;", video)
            logger.info(f"Found video element for video {idx}")

            # Attempt to set HD quality
            try:
                driver.execute_script("arguments[0].setPlaybackQuality('hd1080');", video)
                current_quality = driver.execute_script("return arguments[0].getPlaybackQuality()", video)
                logger.info(f"Set video quality to {current_quality} for video {idx}")
            except Exception as quality_ex:
                logger.warning(f"Failed to set quality for video {idx}: {quality_ex}")

            # Wait for duration to be available
            duration = None
            for _ in range(10):
                try:
                    duration = driver.execute_script("return arguments[0].duration", video)
                    if duration:
                        break
                except:
                    pass
                time.sleep(1)
            if not duration:
                error_msg = f"Could not retrieve duration for video {idx}"
                logger.warning(error_msg)
                return False, [error_msg]
            logger.info(f"Duration for video {idx}: {duration}s")

            if duration < 10:
                error_msg = f"Skipping short video {idx} (duration: {duration}s)"
                logger.info(error_msg)
                return False, [error_msg]

            os.makedirs(TEMP_DIR, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            for shot_num in range(1, 5):
                try:
                    target_time = random.uniform(duration * 0.1, duration * 0.9)
                    driver.execute_script("arguments[0].currentTime = arguments[1];", video, target_time)
                    time.sleep(2)  # Allow frame to update
                    logger.info(f"Capturing shot {shot_num} for video {idx} at time {target_time}")

                    filename = f"video_{idx}_shot_{shot_num}_{timestamp}.png"
                    local_path = os.path.join(TEMP_DIR, filename)

                    # Capture and save screenshot
                    driver.save_screenshot(local_path)
                    logger.info(f"Saved screenshot for shot {shot_num} of video {idx}")

                    # Upload to Google Drive
                    upload_to_drive(local_path, filename)
                    logger.info(f"Uploaded screenshot for shot {shot_num} of video {idx}")

                    # Remove local file
                    os.remove(local_path)

                except Exception as shot_ex:
                    shot_error = f"Error in shot {shot_num} of video {idx}: {str(shot_ex)}"
                    logger.error(shot_error)
                    errors.append(shot_error)

            if errors:
                return False, errors
            return True, None

        except NoSuchElementException:
            error_msg = f"No video element found in video {idx}"
            logger.warning(error_msg)
            return False, [error_msg]

    except Exception as e:
        error_msg = f"Error processing video {idx}: {str(e)}"
        logger.error(error_msg)
        return False, [error_msg]

def upload_to_drive(local_path, filename):
    """Upload a file to Google Drive."""
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

def main_process():
    """Main flow to process videos from the playlist."""
    driver = None
    try:
        driver = browser_setup()
        driver.get(PLAYLIST_URL)
        time.sleep(5)  # Allow playlist to load

        video_elements = driver.find_elements(By.ID, "video-title")
        video_links = [elem.get_attribute("href") for elem in video_elements]
        logger.info(f"Found {len(video_links)} videos in playlist")

        all_errors = []
        processed_count = 0

        for idx, video_url in enumerate(video_links[:5], 1):
            if video_url:
                success, errors = process_video(driver, idx, video_url)
                if success:
                    processed_count += 1
                else:
                    all_errors.extend(errors)

        if not all_errors:
            return {"status": "success", "processed_videos": processed_count}
        return {"status": "partial_success", "processed_videos": processed_count, "errors": all_errors}

    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
        return {"status": "error", "error": str(e)}
    finally:
        if driver:
            driver.quit()
            logger.info("Browser instance closed")
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
            logger.info("Cleaned up temporary directory")

# Initialize Google Drive connection
try:
    drive = setup_drive()
    logger.info("Successfully authenticated with Google Drive")
except Exception as e:
    logger.error("Failed to initialize Google Drive connection")
    raise

# Ensure TEMP_DIR exists
os.makedirs(TEMP_DIR, exist_ok=True)

@app.route("/")
def index():
    """Endpoint to trigger video processing."""
    result = main_process()
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
