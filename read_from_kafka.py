from pyspark.sql import SparkSession
from pyspark.sql.functions import col
import pickle
import joblib

# 🔹 Tek model dosyasını yükle (TF-IDF + Logistic Regression pipeline)
with open('logreg_sentiment140_model.pkl', 'rb') as f:
    model = joblib.load(f)

# 🔹 Tahmin fonksiyonu
def predict_batch(df, epoch_id):
    pandas_df = df.select("value").toPandas()

    if not pandas_df.empty:
        texts = pandas_df["value"].tolist()
        preds = model.predict(texts)

        for text, pred in zip(texts, preds):
            print(f"TWEET: {text} | PREDICTION: {pred}")

# 🔹 Spark başlat
spark = SparkSession.builder \
    .appName("KafkaTweetReader") \
    .getOrCreate()

# 🔹 Kafka'dan veri oku
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "tweets") \
    .load()

# 🔹 Veriyi string'e çevir
df_text = df.selectExpr("CAST(value AS STRING)")

# 🔹 Inference işlemini başlat
query = df_text.writeStream \
    .outputMode("append") \
    .foreachBatch(predict_batch) \
    .start()

query.awaitTermination()
