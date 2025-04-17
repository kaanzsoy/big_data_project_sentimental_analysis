from flask import Flask, render_template, jsonify, request
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType
import joblib

app = Flask(__name__)

# Spark ve Kafka Konektörü için SparkSession
spark = SparkSession.builder \
    .appName("FlaskKafkaPrediction") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# Modeli yükleyip broadcast et
model = joblib.load("logreg_sentiment140_model.pkl")  # Model dosyanızı doğru dizine koyun
bmodel = spark.sparkContext.broadcast(model)

# UDF: metin üzerinden tahmin yapar
def predict_sentiment(text):
    try:
        pred = bmodel.value.predict([text])[0]
        return "Olumlu" if pred == 1 else "Olumsuz"
    except Exception:
        return "Hata"

predict_udf = udf(predict_sentiment, StringType())

# Tahmin sonuçlarını ve tweet listesini saklamak için global yapılar
tweets = []
predictions = {}

# Çekirdek tahmin fonksiyonu
def run_prediction():
    global tweets, predictions
    tweets = []
    predictions = {}

    # Kafka'dan batch oku
    kafka_df = (
        spark.read
             .format("kafka")
             .option("kafka.bootstrap.servers", "localhost:9092")
             .option("subscribe", "tweets")
             .option("startingOffsets", "earliest")
             .load()
    )

    # Mesajı string olarak al
    text_df = kafka_df.selectExpr("CAST(value AS STRING) AS tweet_text")

    # Paralel inference
    result_df = text_df.withColumn("prediction", predict_udf(col("tweet_text")))

    # Sonuçları toplu olarak al ve global dict'e yaz
    for row in result_df.collect():
        t = row["tweet_text"]
        p = row["prediction"]
        tweets.append(t)
        predictions[t] = p

    print(f"Prediction yapıldı: {len(predictions)} tweet işlendi.")

# Flask endpoint'leri
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/start_prediction', methods=['POST'])
def start_prediction():
    run_prediction()
    return jsonify({"status": "Prediction yapıldı.", "tweet_count": len(tweets)})

@app.route('/get_tweets')
def get_tweets():
    return jsonify([{"tweet": t, "prediction": predictions.get(t, "")} for t in tweets])

if __name__ == '__main__':
    app.run(debug=True)