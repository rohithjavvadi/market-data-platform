FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir confluent-kafka==2.16.1 websocket-client==1.8.0 python-dotenv==1.1.0
COPY producer/ producer/
CMD ["python", "-u", "producer/finnhub_producer.py", "--bootstrap", "redpanda-0:9092", "--seconds", "0"]
