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
    print("FATAL: Nedostaju parametri za povezivanje sa Kafka/ClickHouse.")
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
        print(f"INFO:Uspešno povezan na Kafka topic: {KAFKA_TOPIC}")
        return consumer
    except Exception as e:
        print(f"FATAL:Greška pri povezivanju na Kafku: {e}")
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
    
    if code == 'XXX':  #ISO 4217 validan ali nekoristna za transakcionu analizu
        return False
    try:
        Currency(code)
        return True
    except ValueError:
        return False
    
def insert_rejected(row, client):
    column_names = [ 'rejection_reason','event_id', 'user_id', 'session_id', 'product','tx_type', 'currency', 'amount', 'event_time', 'metadata']
    try:
        client.execute(
            f'INSERT INTO rejected_events ({", ".join(column_names)}) VALUES',
            [row]
        )
        print(f"INFO:Uspešno upisan u ClickHouse tabelu *rejected_events*.")
        
    except Exception as e:
        print(f"ERROR:Greška pri batch upisu u ClickHouse tabelu *rejected_events*: {e}", row)

def validate_and_transform_row(data, client):
    to_reject = False
    rejection_reason = ""

    if not data['event_id']:
        print("WARNING: Nedostaje event_id.")
        rejection_reason+=" Misssing event_id."
        to_reject=True
    
    if not data['user_id']:
        print("WARNING: Nedostaje user_id.")
        rejection_reason+=" Misssing user_id."
        to_reject=True

    #validacija valuta
    if not is_iso4217_currency_code(data['currency']):
        print("WARNING: Currency vrednost nije validna.")
        rejection_reason+=" Currency value not valid."
        to_reject=True

    #provera tipa transakcije
    if not data['tx_type'] in ['bet', 'win', 'deposit', 'withdraw']:
        print("WARNING: Tip transakcije nije validan.")
        rejection_reason+=" Transaction type is not valid."
        to_reject=True

    #provera negativnih iznosa
    if data['amount'] < 0 and not (data['tx_type']=='deposit' or data['tx_type']=='withdraw'):
        print("WARNING: Amount<0 za nevalidan tip transakcije.")
        rejection_reason+=" Amount<0 for invalid type of transaction."
        to_reject=True

    #timestamp konverzija
    if data['event_time'] > time.time():
        print("WARNING: Timestamp transakcije je u buducnosti.")
        rejection_reason+=" Timestamp is in the future."
        to_reject=True
        event_time_dt=None
    else:    
        event_time_dt = datetime.datetime.fromtimestamp(data['event_time'], tz=datetime.timezone.utc)


    if to_reject:
        row = (
            rejection_reason,
            data['event_id'],
            data['user_id'],
            data['session_id'],
            data['product'],
            data['tx_type'],
            data['currency'],
            data['amount'],
            event_time_dt,
            data['metadata']
        )
        insert_rejected(row, client)
        return None
    else:
        row = (
            data['event_id'],
            data['user_id'],
            data['session_id'],
            data['product'],
            data['tx_type'],
            data['currency'],
            data['amount'],
            event_time_dt,
            data['metadata']
        )
        return row



def parse_and_insert_batch(consumer, client, batch):
    rows_to_insert = []    
    column_names = ['event_id', 'user_id', 'session_id', 'product','tx_type', 'currency', 'amount', 'event_time', 'metadata']
    
    for message in batch:
        try:
            data = message.value 
            row = validate_and_transform_row(data, client)
            if row:
                rows_to_insert.append(row)  
            
        except Exception as e:
            print(f"ERROR: Greška pri parsiranju poruke: {e}. Poruka: {message.value}")
            
    if rows_to_insert:
        try:
            client.execute(
                f'INSERT INTO transaction_events ({", ".join(column_names)}) VALUES',
                rows_to_insert
            )
            print(f"INFO:Uspešno upisano {len(rows_to_insert)} redova u ClickHouse tabelu *transaction_events*.")
            
        except Exception as e:
            print(f"ERROR:Greška pri batch upisu u ClickHouse tabelu *transaction_events*: {e}")
    
    consumer.commit()

def start_consuming(consumer, client):
    print("INFO:Pokrećem Batch Consumer...")
    
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
                parse_and_insert_batch(consumer, client, message_batch)                
                message_batch = []
                last_commit_time = time.time()
                
            elif not message_batch:
                time.sleep(1)

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if consumer:
            consumer.close()
            print("INFO:Kafka Consumer zatvoren.")

if __name__ == '__main__':
    time.sleep(5) 
    
    kafka_consumer = get_kafka_consumer()
    clickhouse_client = get_clickhouse_client()
    time.sleep(5) 
    start_consuming(kafka_consumer, clickhouse_client)
