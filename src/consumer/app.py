import os
import json
import time, datetime
from kafka import KafkaConsumer
from clickhouse_driver import Client
from iso4217 import Currency

KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'transaction_events')
KAFKA_BROKER_URL = os.environ.get('KAFKA_BROKER_URL')

CH_HOST = os.environ.get('CH_HOST')
CH_USER = os.environ.get('CH_USER')
CH_PASSWORD = os.environ.get('CH_PASSWORD')
CH_DB = os.environ.get('CH_DB', 'default')

BATCH_SIZE = 500
COMMIT_INTERVAL = 5 

if not all([KAFKA_BROKER_URL, CH_HOST, CH_USER, CH_PASSWORD]):
    print("FATAL: Critical environment variables (Kafka/ClickHouse) are missing.")
    exit(1)

def get_kafka_consumer():
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER_URL],
            group_id='clickhouse-batch-consumer',
            auto_offset_reset='earliest',
            enable_auto_commit=False, 
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        print(f"Uspešno povezan na Kafka temu: {KAFKA_TOPIC}")
        return consumer
    except Exception as e:
        print(f"Greška pri povezivanju na Kafku: {e}")
        exit(1)

def get_clickhouse_client():
    try:
        client = Client(
            host=CH_HOST,
            user=CH_USER,
            password=CH_PASSWORD,
            database=CH_DB,
            port=9000 
        )
        client.execute('SELECT 1') 
        print(f"Uspešno povezan na ClickHouse bazu na {CH_HOST}")
        return client
    except Exception as e:
        print(f"Greška pri povezivanju na ClickHouse: {e}")
        exit(1)

def is_iso4217_currency_code(code):
    try:
        Currency(code)
        return True
    except ValueError:
        return False
    
def validate_and_transform_row(data):
    if not data['event_id'] or not data['user_id']:
        print("WARNING: Nedostajući ID.")
        return None
    
    data['is_valid'] = True

    #validacija valuta
    if not is_iso4217_currency_code(data['currency']):
        data['currency'] = 'RSD'

    #provera negativnih iznosa
    if data['amount'] < 0 and not data['tx_type']=='deposit':
        data['is_valid'] = False

    #timestamp konverzija
    event_time_dt = datetime.datetime.fromtimestamp(data['event_time'], tz=datetime.timezone.utc)
    
    row = (
        data['event_id'],
        data['user_id'],
        data['session_id'],
        data['product'],
        data['tx_type'],
        data['currency'],
        data['amount'],
        event_time_dt,
        data['metadata'],
        data['is_valid']

    )
    return row

def parse_and_insert_batch(consumer, client, batch):
    print("Parse and insert function")
    rows_to_insert = []
    
    column_names = ['event_id', 'user_id', 'session_id', 'product','tx_type', 'currency', 'amount', 'event_time', 'metadata', 'is_valid']
    
    for message in batch:
        try:
            data = message.value 
            row = validate_and_transform_row(data)
            if row:
                rows_to_insert.append(row)  
            
        except Exception as e:
            print(f"Greška pri parsiranju poruke: {e}. Poruka: {message.value}")
            
    if rows_to_insert:
        try:
            client.execute(
                f'INSERT INTO transaction_events ({", ".join(column_names)}) VALUES',
                rows_to_insert
            )
            print(f"Uspešno upisano {len(rows_to_insert)} redova u ClickHouse.")
            
        except Exception as e:
            print(f"Greška pri batch upisu u ClickHouse: {e}")
    
    consumer.commit()

def start_consuming(consumer, client):
    print("Pokrećem Batch Consumer...")
    
    message_batch = []
    last_commit_time = time.time()
    
    try:
        while True:
            messages = consumer.poll(timeout_ms=1000, max_records=BATCH_SIZE) 
            
            for topic_partition, raw_messages in messages.items():
                message_batch.extend(raw_messages)

            time_elapsed = time.time() - last_commit_time

            # Provera da li je batch pun ili je prošlo vreme za commit
            if message_batch and (len(message_batch) >= BATCH_SIZE or time_elapsed >= COMMIT_INTERVAL):   
                print("Time elapsed-", time_elapsed, "Number of messages-", len(message_batch))
                parse_and_insert_batch(consumer, client, message_batch)                
                message_batch = []
                last_commit_time = time.time()
                
            elif not message_batch:
                time.sleep(1)
            
        
    except KeyboardInterrupt:
        print("\nZaustavljam Consumer...")
    except Exception as e:
        print(f"Kritična greška u glavnoj petlji: {e}")
    finally:
        if consumer:
            consumer.close()
            print("Kafka Consumer zatvoren.")

if __name__ == '__main__':
    time.sleep(5) 
    
    kafka_consumer = get_kafka_consumer()
    clickhouse_client = get_clickhouse_client()
    time.sleep(5) 
    start_consuming(kafka_consumer, clickhouse_client)
