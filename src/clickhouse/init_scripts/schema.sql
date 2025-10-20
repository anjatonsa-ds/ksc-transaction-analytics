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
    amount      Float32,
    event_time  DateTime64(3),  
    metadata    String,
    ingestion_time DateTime64(3) DEFAULT now()
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
    JSONExtractFloat32(value, 'amount') AS amount,
    toDateTime64(JSONExtractFloat(value, 'event_time'), 3) AS event_time, 
    JSONExtractString(value, 'metadata') AS metadata
FROM staging_transaction_events;
*/

--Tabela odbijenih transakcija
SET allow_experimental_full_text_index = 1;
CREATE TABLE IF NOT EXISTS rejected_events (
    rejection_reason String,
    rej_reasons Array(String),
    event_id    String,    
    user_id     String,   
    session_id  String,  
    product     LowCardinality(String),
    tx_type     LowCardinality(String),
    currency    LowCardinality(String),
    amount      Float32,
    event_time  Nullable(DateTime64(3)),  
    metadata    String,
    ingestion_time DateTime64(3) DEFAULT now(),
    INDEX rej_res_tokenized(rejection_reason) TYPE text(tokenizer = 'split', separators = ['\n'])
)
ENGINE = MergeTree() 
ORDER BY (event_id, user_id);

--Za DQ report dnevne metrike
CREATE TABLE IF NOT EXISTS daily_metrics (
    report_date Date,
    total_messages UInt64,
    valid_messages UInt64,
    rejected_messages UInt64,
    average_lag_seconds Float32
)
ENGINE = SummingMergeTree()
ORDER BY (report_date);

--Za DQ report dnevne metrike
CREATE TABLE IF NOT EXISTS hourly_metrics (
    report_hour DateTime,
    total_messages UInt64,
    valid_messages UInt64,
    rejected_messages UInt64,
    average_lag_seconds Float32 
)
ENGINE = SummingMergeTree()
ORDER BY (report_hour);

-- MV za validne transakcije
CREATE MATERIALIZED VIEW valid_metrics_mv TO daily_metrics AS
SELECT
    toDate(event_time) AS report_date,
    count() AS valid_messages,
    0 AS rejected_messages,
    count() AS total_messages,
    avg(ingestion_time - event_time) AS average_lag_seconds
FROM transaction_events
GROUP BY report_date;

-- MV za odbijene transakcije
CREATE MATERIALIZED VIEW rejected_metrics_mv TO daily_metrics AS
SELECT
    toDate(ingestion_time) AS report_date,
    0 AS valid_messages, 
    count() AS rejected_messages,
    count() AS total_messages,
    0 AS average_lag_seconds
FROM rejected_events
GROUP BY report_date;



CREATE MATERIALIZED VIEW valid_hourly_mv TO hourly_metrics AS
SELECT
    toStartOfHour(event_time) AS report_hour,
    count() AS valid_messages,
    0 AS rejected_messages,
    count() AS total_messages,
    avg(ingestion_time - event_time) AS average_lag_seconds
FROM transaction_events
GROUP BY report_hour;

CREATE MATERIALIZED VIEW rejected_hourly_mv TO hourly_metrics AS
SELECT
    toStartOfHour(ingestion_time) AS report_hour,
    0 AS valid_messages,
    count() AS rejected_messages,
    count() AS total_messages,
    toFloat32(0.0) AS average_lag_seconds
FROM rejected_events
GROUP BY report_hour;

--Pipeline metrics
CREATE TABLE IF NOT EXISTS pipeline_metrics (
    ingestion_time DateTime64(3) DEFAULT now(),
    batch_size UInt64,
    failed_insert_size UInt64,
    num_rejected UInt64
)
ENGINE = MergeTree()
ORDER BY (failed_insert_size );

CREATE TABLE IF NOT EXISTS casino_transactions (
    event_id    String,    
    user_id     String,   
    session_id  String,  
    product     LowCardinality(String),
    tx_type     LowCardinality(String),
    currency    LowCardinality(String),
    amount      Float32,
    event_time  DateTime64(3),  
    metadata    String,
    ingestion_time DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree() 
ORDER BY (event_id, event_time);

SELECT
    avg(JSONExtractFloat(raw_metadata_json, 'TotalBetAmount'))
FROM
    transaction_events;