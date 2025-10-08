-- Staging tabela
CREATE TABLE IF NOT EXISTS staging_transaction_events (
    value String
)
ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:29092',           
    kafka_topic_list = 'transaction_events',          
    kafka_group_name = 'clickhouse_consumer_group',
    kafka_format = 'JSONAsString',                
    kafka_num_consumers = 1;

-- Target tabela
CREATE TABLE IF NOT EXISTS transaction_events (
    event_id    String,    
    user_id     String,   
    session_id  String,  
    product     LowCardinality(String),
    tx_type     LowCardinality(String),
    currency    LowCardinality(String),
    amount      Int32,
    event_time  DateTime64(3),  
    metadata    String,
    ingestion_time DateTime64(3),
    insertTimeByCH DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree() 
ORDER BY (event_id, event_time);

-- Materialized View
/*
CREATE MATERIALIZED VIEW IF NOT EXISTS transaction_events_mv TO transaction_events
AS SELECT
    JSONExtractString(value,'event_id') AS event_id,
    JSONExtractString(value, 'user_id') AS user_id,
    JSONExtractString(value, 'session_id') AS session_id,
    JSONExtractString(value, 'product') AS product,
    JSONExtractString(value, 'tx_type') AS tx_type,
    JSONExtractString(value, 'currency') AS currency,
    JSONExtractInt(value, 'amount') AS amount,
    toDateTime64(JSONExtractFloat(value, 'event_time'), 3) AS event_time, 
    JSONExtractString(value, 'metadata') AS metadata
FROM staging_transaction_events;
*/

--Tabela odbijenih transakcija
SET allow_experimental_full_text_index = true;
CREATE TABLE IF NOT EXISTS rejected_events (
    rejection_reason String,
    rej_reasons Array(String),
    event_id    String,    
    user_id     String,   
    session_id  String,  
    product     LowCardinality(String),
    tx_type     LowCardinality(String),
    currency    LowCardinality(String),
    amount      Int32,
    event_time  Nullable(DateTime64(3)),  
    metadata    String,
    INDEX rej_res_tokenized(rejection_reason) TYPE text(tokenizer = 'split', separators = ['\n'])
)
ENGINE = MergeTree() 
ORDER BY (event_id, user_id);