import os
import json
import time, datetime
from threading import Thread
import uuid
from kafka import KafkaConsumer
from clickhouse_driver import Client
from iso4217 import Currency
from flask import Flask, jsonify 
import joblib 
import pandas as pd
import numpy as np


KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'transaction_events')
KAFKA_BROKER_URL = os.environ.get('KAFKA_BROKER_URL')

CH_HOST = os.environ.get('CH_HOST')
CH_USER = os.environ.get('CH_USER')
CH_PASSWORD = os.environ.get('CH_PASSWORD')
CH_DB = os.environ.get('CH_DB', 'default')

BATCH_SIZE = 10000
COMMIT_INTERVAL = 0.01 

GLOBAL_METRICS = {
    'status': 'healthy',
    'last_update': datetime.datetime.now(),
    'total' :0,
    'rejected_total': 0,
    'last_batch_size': 0,
    'last_insert_duration_s': 0.0,
}
try:
    ai_model = joblib.load("model_reg.pkl")
    print("AI model loaded.")
except Exception as e:
    print(f"FATAL:Greška pri učitavanju modela: {e}")
    

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
    
    #if code == 'XXX':  #ISO 4217 validan ali nekoristan za transakcionu analizu
        #return False
    try:
        Currency(code)
        return True
    except ValueError:
        return False

def apply_cyclical_encoding(df, col, max_val):
    df[col + '_sin'] = np.sin(2 * np.pi * df[col] / max_val)
    df[col + '_cos'] = np.cos(2 * np.pi * df[col] / max_val)
    return df

def insert_rejected_rows(rows, client):
    column_names = [ 'rejection_reason','rej_reasons','event_id', 'user_id', 'session_id', 'product','tx_type', 'currency', 'amount', 'event_time', 'metadata']
    try:
        client.execute(
            f'INSERT INTO rejected_events ({", ".join(column_names)}) VALUES',
            rows
        )
        print(f"INFO:Uspešno upisano {len(rows)} redova u ClickHouse tabelu *rejected_events*.")

        
    except Exception as e:
        print(f"ERROR:Greška pri batch upisu u ClickHouse tabelu *rejected_events*: {e}")

def insert_rows(rows,client):
    column_names = ['event_id', 'user_id', 'session_id', 'product','tx_type', 'currency', 'amount', 'event_time', 'event_time_send','metadata', 'anomaly_score']
    try:
        client.execute(
            f'INSERT INTO transaction_events_anomaly ({", ".join(column_names)}) VALUES',
            rows
        )
        print(f"INFO:Uspešno upisano {len(rows)} redova u ClickHouse tabelu *transaction_events_anomaly*.")
    except Exception as e:
        print(f"ERROR:Greška pri batch upisu u ClickHouse tabelu *transaction_events_anomaly*: {e}")

def validate_and_transform_row(data, client):
    to_reject = False
    rejection_reason = ""
    rej_reasons=[]
    event_time_dt = None

    if not data['event_id']:
        #print("WARNING: Nedostaje event_id.")
        rejection_reason+="miss_evnt_id "
        rej_reasons.append("Missing event_id.")
        to_reject=True
    
    if not data['user_id']:
        #print("WARNING: Nedostaje user_id.")
        rejection_reason+="miss_usr_id "
        rej_reasons.append("Missing user_id.")
        to_reject=True
    
    if not data['session_id']:
        #print("WARNING: Nedostaje session_id.")
        rejection_reason+="miss_ses_id "
        rej_reasons.append("Missing session_id.")
        to_reject=True

    #validacija valuta
    if not is_iso4217_currency_code(data['currency']):
        #print("WARNING: Currency vrednost nije validna.")
        rejection_reason+="curr_not_valid "
        rej_reasons.append("Currency value not valid.")
        to_reject=True

    #provera tipa transakcije
    if not data['tx_type'] in ['bet', 'win', 'deposit', 'withdraw']:
        #print("WARNING: Tip transakcije nije validan.")
        rejection_reason+="tx_type_not_valid "
        rej_reasons.append("Transaction type is not valid.")
        to_reject=True
    
    #provera tipa product
    if not data['product'] in ['sportsbook', 'casino', 'virtual']:
        #print("WARNING: Tip producta nije validan.")
        rejection_reason+='product_not_valid '
        rej_reasons.append("Product type is not valid.")
        to_reject=True

    #provera negativnih iznosa
    if data['amount'] < 0 and not (data['tx_type']=='bet' or data['tx_type']=='withdraw'):
        #print("WARNING: Amount<0 za nevalidan tip transakcije.")
        rejection_reason+="amnt_not_valid "
        rej_reasons.append("Amount<0 for invalid type of transaction.")
        to_reject=True

    #timestamp konverzija
    ''' 
    if data['event_time'] > time.time():
        #print("WARNING: Timestamp transakcije je u buducnosti.")
        rejection_reason+="ts_not_valid"
        rej_reasons.append("Timestamp is in the future.")
        to_reject=True
        event_time_dt=None
    else:    
        event_time_dt = datetime.datetime.fromtimestamp(data['event_time'], tz=datetime.timezone.utc)
    '''
    event_time_dt = datetime.datetime.fromtimestamp(data['event_time'], tz=datetime.timezone.utc)


    print("WARNING:", rej_reasons)
    if to_reject:
        row = (
            rejection_reason,
            rej_reasons,
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
        return row, True
    else:
        anomaly_score = prepare_row_for_model(data)
        send_event_time_dt = datetime.datetime.fromtimestamp(data['event_time_send'], tz=datetime.timezone.utc)

        row = (
            data['event_id'],
            data['user_id'],
            data['session_id'],
            data['product'],
            data['tx_type'],
            data['currency'],
            data['amount'],
            event_time_dt,
            send_event_time_dt,
            data['metadata'],
            anomaly_score
        )
        return row, False
        
def prepare_row_for_model(data):
    user_mod = 0
    try:
        user_uuid = uuid.UUID(data['user_id'])
        user_mod = user_uuid.int % 10
    except (ValueError, TypeError):
        user_mod = 9

    event_time_dt = datetime.datetime.fromtimestamp(data['event_time'], tz=datetime.timezone.utc)
    hour_of_day = event_time_dt.hour if event_time_dt else 0 
    print(hour_of_day, 'hour')

    row_df = pd.DataFrame({
        'amount': [data['amount']],
        'hour_of_day': [hour_of_day],
        'currency': [data['currency']],
        'user_id_mod': [user_mod],
        'tx_type':[data['tx_type']]
    })
    
    row_df['abs_amount'] = np.abs(row_df['amount'])
    row_df = apply_cyclical_encoding(row_df, 'hour_of_day', 24)
    row_df = row_df.drop('hour_of_day', axis=1)
    raw_features_for_pipeline = ['amount', 'abs_amount', 'hour_of_day_sin', 'hour_of_day_cos', 'tx_type', 'currency', 'user_id_mod']
    X_predict = row_df[raw_features_for_pipeline]
    anomaly_prediction = ai_model.predict(X_predict)[0]
    anomaly_score_db = int(anomaly_prediction)

    return anomaly_score_db

def insert_pipeline_metrics(client, metric_data):
    column_names = ['batch_size','failed_insert_size', 'num_rejected']
    try:
        client.execute(
            f"INSERT INTO pipeline_metrics ({', '.join(column_names)}) VALUES",
            [metric_data]
        )
        print(f"INFO: Upisano u pipeline_metrics tabelu.")
    except Exception as e:
        print(f"ERROR: Neuspeli upis metrika u pipeline_metrics: {e}")

def parse_and_insert_batch(consumer, client, batch):

    print(f"INFO - Batch insert, size {len(batch)}")
    rows_to_insert = []    
    rejected_rows_to_insert = []    
    rejected_count = 0 

    for message in batch:
        try:
            data = message.value 
            row, rejceted = validate_and_transform_row(data, client)
            if rejceted:
                rejected_count += 1
                rejected_rows_to_insert.append(row)
            else: 
                rows_to_insert.append(row)  
        except Exception as e:
            print(f"ERROR: Greška pri parsiranju poruke: {e}. Poruka: {message.value}")
    
    GLOBAL_METRICS['total'] += len(batch)
    GLOBAL_METRICS['rejected_total'] += rejected_count
    GLOBAL_METRICS['last_batch_size'] = len(batch)
    GLOBAL_METRICS['last_update'] = datetime.datetime.now()

    insert_start_time = time.time()
    failed_count = 0
    if rows_to_insert:
        MAX_RETRIES = 3
        PAUSE_SECONDS = 5
        for attempt in range(MAX_RETRIES):
            try:
                insert_rows(rows_to_insert,client)
                break 
            except Exception as e:
                print(f"WARNING: Neuspeli batch upis u transaction_events_anomaly tabelu (Pokušaj {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt == MAX_RETRIES - 1:
                    print(f"FATAL: Svi pokušaji upisa ({MAX_RETRIES}) su propali. Odbacivanje batcha zbog perzistentne greške.")
                    failed_count = failed_count + len(rows_to_insert)
                else:
                    print(f"INFO: Pauziranje na {PAUSE_SECONDS} sekundi pre sledećeg pokušaja...")
                    time.sleep(PAUSE_SECONDS)
    
    if rows_to_insert:
        MAX_RETRIES = 3
        PAUSE_SECONDS = 5
        for attempt in range(MAX_RETRIES):
            try:
                insert_rejected_rows(rejected_rows_to_insert,client)
                break 
            except Exception as e:
                print(f"WARNING: Neuspeli batch upis u rejected_evnets tabelu (Pokušaj {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt == MAX_RETRIES - 1:
                    print(f"FATAL: Svi pokušaji upisa ({MAX_RETRIES}) su propali. Odbacivanje batcha zbog perzistentne greške.")
                    failed_count = failed_count + len(rows_to_insert)
                else:
                    print(f"INFO: Pauziranje na {PAUSE_SECONDS} sekundi pre sledećeg pokušaja...")
                    time.sleep(PAUSE_SECONDS)
    
    insert_duration_s = time.time() - insert_start_time
    GLOBAL_METRICS['last_insert_duration_s'] = insert_duration_s

    print(f"INFO: Uspešno upisano {len(batch)-failed_count} redova u ClickHouse za {insert_duration_s}s.")
    print(f"INFO: Neuspešno upisano {failed_count} redova u ClickHouse. Broj odbijenih poruka u batch-u {rejected_count}")

    
    metric_data = (
        len(batch),
        failed_count,
        rejected_count
    )
    
    insert_pipeline_metrics(client, metric_data)
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
                time.sleep(0.1)

    except Exception as e:
        print(f"ERROR: {e}")
        GLOBAL_METRICS['status'] = f'FATAL ERROR: {e}'
    finally:
        if consumer:
            consumer.close()
            print("INFO:Kafka Consumer zatvoren.")

app = Flask(__name__)

@app.route('/status', methods=['GET'])
def status_endpoint():
    GLOBAL_METRICS['last_update'] = datetime.datetime.now()
    return jsonify(GLOBAL_METRICS)

def run_flask_app():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False) 

if __name__ == '__main__':
    time.sleep(5) 
    
    kafka_consumer = get_kafka_consumer()
    clickhouse_client = get_clickhouse_client()
    time.sleep(5) 
    flask_thread = Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    start_consuming(kafka_consumer, clickhouse_client)
