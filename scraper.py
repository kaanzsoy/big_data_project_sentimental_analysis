from kafka import KafkaProducer
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

# Kafka producer config
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: v.encode('utf-8')
)

search_url = "https://x.com/search?q=from%3Acnni&src=typed_query"
# TechCrunch
# BBCWorld
# cnni


options = webdriver.ChromeOptions()
options.add_argument("user-data-dir=/home/kaan/.config/selenium-profile")
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

service = Service(ChromeDriverManager().install())
browser = webdriver.Chrome(service=service, options=options)

browser.get(search_url)
time.sleep(3)

body = browser.find_element(By.TAG_NAME, "body")
seen = set()

print("Tweet cekimi baslatildi. Durdurmak icin Ctrl + C")

with open("tweets.txt", "w", encoding="utf-8") as file:
    try:
        while True:
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(1.2 if random.random() < 0.1 else 0.6)

            tweets = browser.find_elements(By.CSS_SELECTOR, "article")
            for tweet in tweets:
                try:
                    text = tweet.find_element(
                        By.XPATH, './/div[@data-testid="tweetText"]'
                    ).text.strip()
                    if text and text not in seen:
                        seen.add(text)

                        file.write(text + "\n\n")
                        file.flush()

                        # kafka'ya yaz
                        message = text + "\n\n"
                        producer.send('tweets', message)
                        producer.flush()
                except:
                    continue
    except KeyboardInterrupt:
        print("\nTweet cekimi manuel olarak durduruldu.")
        print(f"Toplam tweet sayisi: {len(seen)}")

browser.quit()
producer.flush()
producer.close()
