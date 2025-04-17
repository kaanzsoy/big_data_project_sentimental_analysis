from flask import Flask, render_template, jsonify
import subprocess, sys, os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType
import joblib
import time

app = Flask(__name__)

# Spark ve Kafka configuration
spark = SparkSession.builder \
    .appName("FlaskKafkaPrediction") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# Model yuklenir, broadcast edilir
model = joblib.load("logreg_sentiment140_model.pkl")
bmodel = spark.sparkContext.broadcast(model)

# Prediction UDF'i
def predict_sentiment(text):
    try:
        p = bmodel.value.predict([text])[0]
        return "Positive" if p == 1 else "Negative"
    except:
        return ""
predict_udf = udf(predict_sentiment, StringType())

# Global state
predictions = {}
scraper_proc = None

def stop_scraper():
    # scraper.py'nin calismasi durdurulur, yeni tweetler cekilmez.
    global scraper_proc
    if scraper_proc and scraper_proc.poll() is None:
        scraper_proc.terminate()
        try:
            scraper_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            scraper_proc.kill()
        scraper_proc = None

def read_all_tweets():
    # Kafka topici en bastan okunarak unique tweet listesi elde edilir.
    df = (
        spark.read
             .format("kafka")
             .option("kafka.bootstrap.servers", "localhost:9092")
             .option("subscribe", "tweets")
             .option("startingOffsets", "earliest")
             .load()
    )
    tweets_df = df.selectExpr("CAST(value AS STRING) AS tweet_text")
    
    # Duplicate'lari kaldir
    rows = tweets_df.dropDuplicates(['tweet_text']).collect()
    return [row['tweet_text'] for row in rows]

# scraper.py sayesinde twitter'dan anlik olarak tweet cekme islemi gerceklesir
# bu kod dosyasinda, elde edilen tweetler Kafka topic'ine yazilir.
@app.route('/fetch_tweets', methods=['POST'])
def fetch_tweets():
    global scraper_proc
    if scraper_proc is None or scraper_proc.poll() is not None:
        script = os.path.join(os.path.dirname(__file__), "scraper.py")
        scraper_proc = subprocess.Popen([sys.executable, script])
        return jsonify({"status": "Tweet cekme islemi baslatildi."})
    else:
        return jsonify({"status": "Tweet cekme zaten calisiyor."})

# scraper.py calismasini durdur
@app.route('/stop_fetch', methods=['POST'])
def stop_fetch():
    stop_scraper()
    time.sleep(2)
    # Geride kalan tweetleri al
    all_tweets = read_all_tweets()
    result = [{"tweet": t, "prediction": predictions.get(t, "")} for t in all_tweets]
    return jsonify({"status": "Tweet cekme islemi durduruldu.", "tweets": result})

# her bir tweet icin prediction baslat
# Kafka topic'inden okuma islemi gerceklestirilir.
@app.route('/start_prediction', methods=['POST'])
def start_prediction():
    # stop_scraper()
    stop_fetch()
    
    global predictions
    predictions = {}

    # Kafka’dan batch olarak okur
    df = (
        spark.read
             .format("kafka")
             .option("kafka.bootstrap.servers", "localhost:9092")
             .option("subscribe", "tweets")
             .option("startingOffsets", "earliest")
             .load()
    )
    tweets_df = df.selectExpr("CAST(value AS STRING) AS tweet_text")
    res_df = tweets_df.withColumn("prediction", predict_udf(col("tweet_text")))

    # sonuclar kaydedilir
    for row in res_df.dropDuplicates(['tweet_text']).collect():
        predictions[row['tweet_text']] = row['prediction']

    return jsonify({"status": "Prediction tamamlandi.", "tweet_count": len(predictions)})

# tweet listesi ve prediction sonuclarinin arayuzde gorunmesi saglanir
@app.route('/get_tweets')
def get_tweets():
    all_tweets = read_all_tweets()
    out = []
    for t in all_tweets:
        out.append({
            "tweet": t,
            "prediction": predictions.get(t, "")
        })
    return jsonify(out)

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)
