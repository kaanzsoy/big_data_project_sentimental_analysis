# Tweet Sentiment Prediction

A real-time web application that scrapes tweets via Selenium, streams them into Kafka, processes them with Apache Spark, and performs sentiment prediction using a pre-trained logistic regression model.

## Project Structure

> **Note:** The `sentiment_BERT/` directory contains large model files (≈420 MB) and is **not** included in this repository.  
> Please download it manually before running the app. (https://drive.google.com/drive/folders/1RqGCpUjVUT0-F05LE1pulAeueogXflrS)

```
kafka_2.12-3.5.0/               # Kafka distribution
├── bin/                        # Kafka CLI scripts
├── config/
├── libs/
├── ...
static/
  └── style.css                 # CSS for the web UI
templates/
  └── index.html                # HTML template
app.py                          # Flask + Spark + Kafka integration
scraper.py                      # Selenium scraper & Kafka producer
sentiment_BERT/                 
├── config.json                        
├── model.safetensors
├── special_tokens_map.json
├── tokenizer_config.json
├── training_args.bin
└── vocab.txt
logreg_sentiment140_model.pkl   # Pre-trained sentiment model
README.md                       # This file
```

## Prerequisites

- Java 8+ (for Spark & Kafka)
- Kafka & Zookeeper
- Python 3.8+ and pip
- Google Chrome (for Selenium)

### Python Dependencies

```bash
pip install flask pyspark kafka-python selenium webdriver-manager joblib
```

## Setup & Run

1. **Start Zookeeper & Kafka**

   ```bash
   # In one terminal
   bin/zookeeper-server-start.sh config/zookeeper.properties

   # In another
   bin/kafka-server-start.sh config/server.properties
   ```

2. **Delete & Recreate Topic** (optional, to purge old data)

   ```bash
   # Delete existing topic
   bin/kafka-topics.sh \
     --bootstrap-server localhost:9092 \
     --delete --topic tweets

   # Recreate with 4 partitions
   bin/kafka-topics.sh \
     --bootstrap-server localhost:9092 \
     --create \
     --topic tweets \
     --partitions 4 \
     --replication-factor 1
   ```

3. **(Optional) View Topic Contents**

   ```bash
   bin/kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic tweets \
     --from-beginning
   ```

4. **Run the App**

   ```bash
   python app.py
   ```

   - The Flask server will launch on `http://127.0.0.1:5000`.
   - Use the **Fetch Tweets** button to start the scraper (opens headless Chrome, scrapes and pushes tweets to Kafka).
   - **Stop Fetching Tweets** stops the scraper process.
   - **Start Prediction** stops scraping, consumes all tweets from the topic, runs sentiment prediction, and displays results.

## How It Works

- `scraper.py`: Uses Selenium to scroll through Twitter search results (`x.com`) and produces tweet text messages into Kafka topic `tweets`.
- `app.py`:
  - Spins up a SparkSession with the Kafka SQL connector.
  - Broadcasts a pre-trained logistic regression model for inference.
  - Provides Flask endpoints:
    - `/fetch_tweets` &rarr; spawns `scraper.py` as a subprocess
    - `/stop_fetch` &rarr; terminates the scraper and fetches any remaining tweets
    - `/start_prediction` &rarr; reads entire topic from `earliest` offset, applies the model via a Spark UDF, and stores predictions
    - `/get_tweets` &rarr; returns a JSON list of `{ tweet, prediction }`
- `index.html` + `style.css`: A simple UI with controls and a live table that polls `/get_tweets` every 2 seconds, animates new rows, and color‑codes predictions.

## UI Flow

1. **Fetch Tweets** &rarr; begins scraping & streaming to Kafka, table updates live.
2. **Stop Fetching Tweets** &rarr; stops scraper but table continues polling Kafka for completeness.
3. **Start Prediction** &rarr; stops polling (optionally), runs batch prediction over all messages, updates table cells with sentiment. 

