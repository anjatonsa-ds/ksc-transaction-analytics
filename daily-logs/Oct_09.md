# Dnevnik Rada 
## 🎯 Fokus Dana 
 Uporedna analiza brzine izvršavanja SQL upita nad tokenizovanim poljima i postavljanje finalnog modela za izveštavanje o kašnjenju (ingestion lag) i stopi odbijanja poruka. Finalizacija metrika kvaliteta podataka (DQ) i performansi sistema.

## 🛠 Izvršeni Zadaci
### 1. Tokenizacija polja u *rejected_events* tabeli - poredjenje brzine izvršavanja 

#### Testiranje brzine izvršavanja upita sa inverted index-om
- Test 1: Pronalazak broja transakcija koje su odbačene iz razloga definisanog upitom.
```sql
SELECT count()
FROM rejected_events
WHERE searchAll(rejection_reason, ['Currency value not valid.'])
SETTINGS allow_experimental_full_text_index=1
```

- Test 2: Odredjivanje procentualne zastupljenosti odredjenog razloga odbijanja.
```sql
WITH(
        SELECT count()
        FROM rejected_events
    ) AS total_rejected_events
SELECT 
    arrayJoin(splitByChar('\n', rejection_reason)) AS unique_rejection_reason, 
    count() AS rejection_count,
    toFloat64(rejection_count) / total_rejected_events * 100 AS percentage_of_total_rejected
FROM rejected_events
WHERE unique_rejection_reason != ''
GROUP BY unique_rejection_reason
ORDER BY rejection_count DESC
SETTINGS allow_experimental_full_text_index=1
```

#### Poredjenje bzina izvršavanja
Upit koji se koristi za proveravanje dužine trajanja upita radi poredjenja brzine.
```sql
SELECT
    query_duration_ms / 1000 AS duration_seconds,
    query,
    event_time
FROM
    system.query_log
WHERE
    query_kind = 'Select'
    AND type = 'QueryFinish'
    -- bez upita koji prate sam query_log
    AND query NOT LIKE '%system.query_log%'
ORDER BY
    event_time DESC
```
Stanje tabele prilikom testiranja - 1080 redova.
Zaključak
- Test 1:
![Test 1](assets/oct_09_test1.png)
Upit koji koristi Array(String) se izvršava neznatno brže.

- Test 2:
![Test 2](assets/oct_09_test2.png)
Upit koji koristi invertovani indeks se izvršava neznatno brže.


Stanje tabele prilikom testiranja - 7491 redova.
Zaključak
- Test 1:
![Test 1](assets/oct_09_test1_2.png)
Upit koji koristi invertovani indeks se izvršava neznatno brže.

- Test 2:
![Test 2](assets/oct_09_test2_2.png)
Upit koji koristi Array(String) se izvršava duplo brže.



### 2. DQ report
Kreiranje upita koji prikazuje broj ukupnih poruka, broj validnih, broj odbijenih, procenat odbijenih i prosečan ingest lag u poslednjih 24h.
Za potrebe efikasnog izveštavanja na dnevnom nivou, izabran je engine SummingMergeTree kojim se omogućava automatsko sabiranje svih brojača (poruke, lag) koje se unose za isti dan (report_date). Time se drastično smanjuje prostor na disku i ubrzava analiza. Izbor ključa za sortiranje (ORDER BY (report_date)) je odluka kako bi se da se svaki kalendarski dan tretirao kao jedinstvena grupa za sabiranje. Ovo osigurava da se svi mali batch unosi spoje u jedan red sa konačnim zbirom poruka i prosekom lag-a.

```sql
WITH
    valid_data AS (
        SELECT
            count() AS valid_count,
            avg(ingestion_time - event_time) AS avg_lag
        FROM transaction_events
        WHERE event_time > now() - INTERVAL 24 HOUR
    ),
    rejected_data AS (
        SELECT count() AS rejected_count
        FROM rejected_events
        WHERE event_time > now() - INTERVAL 24 HOUR
    )

SELECT
    valid_data.valid_count + rejected_data.rejected_count AS total_messages,
    valid_data.valid_count AS valid_messages,
    rejected_data.rejected_count AS rejected_messages,
    toFloat64(rejected_data.rejected_count) / (valid_data.valid_count + rejected_data.rejected_count) * 100 AS rejected_percentage,
    valid_data.avg_lag AS average_ingestion_lag_seconds
FROM valid_data, rejected_data;
```
Kreiranje tabele za dnevne metrike u koju se pomoću 2 MV-a upisuje broj ukupnih poruka, broj validnih, broj odbijenih, procenat odbijenih i prosečan ingest lag u na dnevnom nivou.

Upit koji služi ta dobijanje metrika na dnevnom nivou.
```sql 
SELECT 
    report_date, 
    total_messages,
    valid_messages,
    rejected_messages,
    (toFloat64(rejected_messages) / total_messages) * 100 AS rejected_percentage,
    average_lag_seconds
FROM daily_metrics
FINAL
ORDER BY report_date DESC;
```

Upit koji služi ta dobijanje metrika po satima.
```sql
SELECT
    report_hour,
    total_messages,
    valid_messages,
    rejected_messages,
    (toFloat64(rejected_messages) / total_messages) * 100 AS rejected_percentage
FROM hourly_metrics
FINAL
ORDER BY report_hour DESC;
```
### 3. Povezivanje Superset-a sa ClickHouse-om

Potrebno je instalirati clickhouse-connect biblioteku.
```bash
docker exec -it superset bash
pip install clickhouse-connect
```
Kredencijali za konektovanje na SuperSet UI-u su admin, admin. Prilikom konekcije potrebno je dodati SQLAlchemy uri("clickhousedb://ch_user:ch_password@clickhouse:9000/default").

Napravljeni su sledeći grafikoni.
Broj dogadjaja kroz vreme.
![Broj dogadjaja kroz vreme](assets/oct_09_br_po_min.jpg)

Distribucija amount vrednosti.
![Distribucija amount vrednosti](assets/oct_09_distribucija_amount.jpg)


Pregled transakcija po tipu transakcije.
![Pregled transakcija po tipu transakcije](assets/oct_09_po_tipu_transakcije.jpg)
