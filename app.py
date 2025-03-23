import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# Initialize once at startup
def setup_drive():
    try:
        gauth = GoogleAuth()
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.environ.get('GDRIVE_CREDENTIALS', 'abc.json'),
            ['https://www.googleapis.com/auth/drive']
        )
        gauth.credentials = credentials
        return GoogleDrive(gauth)
    except Exception as e:
        print(f"Drive initialization failed: {str(e)}")
        raise

drive = setup_drive()

def browser_setup():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    return webdriver.Chrome(options=chrome_options)

def main():
    driver = browser_setup()
    try:
        driver.get("https://www.youtube.com/playlist?list=PL9Zg64loGCGCFo5VXVb0KJrbiPhmOnGkK")
        time.sleep(5)
        
        video_links = [elem.get_attribute("href") for elem in driver.find_elements(By.ID, "video-title")]
        print(f"Processing {len(video_links)} videos")

        for idx, video_url in enumerate(video_links, 1):
            process_video(driver, idx, video_url)

    finally:
        driver.quit()

def process_video(driver, idx, video_url):
    try:
        driver.get(video_url)
        time.sleep(5)
        
        video = driver.find_element(By.TAG_NAME, "video")
        driver.execute_script("arguments[0].controls = false;", video)
        
        duration = driver.execute_script("return arguments[0].duration", video)
        if duration < 10:
            return

        save_folder = "/tmp/youtube_screenshots"
        os.makedirs(save_folder, exist_ok=True)

        for shot_num in range(1, 5):
            target_time = random.uniform(duration*0.1, duration*0.9)
            driver.execute_script("arguments[0].currentTime = arguments[1];", video, target_time)
            time.sleep(2)
            
            filename = f"video_{idx}_shot_{shot_num}.png"
            local_path = os.path.join(save_folder, filename)
            driver.save_screenshot(local_path)
            
            upload_to_drive(local_path, filename)
            os.remove(local_path)

    except Exception as e:
        print(f"Video {idx} error: {str(e)}")

def upload_to_drive(local_path, filename):
    try:
        gfile = drive.CreateFile({
            'title': filename,
            'parents': [{'id': '1gEtuIBff3DiRfcTUHLZchQDyCw90QBp3'}]
        })
        gfile.SetContentFile(local_path)
        gfile.Upload()
        print(f"Uploaded {filename} successfully")
    except Exception as e:
        print(f"Upload failed for {filename}: {str(e)}")

if __name__ == "__main__":
    main()
