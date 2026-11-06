FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir confluent-kafka==2.16.1 boto3 pyarrow
COPY consumer/ consumer/
CMD ["python", "-u", "consumer/bronze_writer.py", "--bootstrap", "redpanda-0:9092", "--idle-exit", "0"]
