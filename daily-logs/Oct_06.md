# Dnevnik Rada 
## 🎯 Fokus Dana 
Tranzicija sa privremenog Python batch konzumenta na stabilni ClickHouse Materialized View (MV). Potvrda end-to-end toka podataka (Kafka → MV → Tabela) i uspostavljanje ispravne logike parsiranja milisekundi i JSON objekata.

## 🛠 Izvršeni Zadaci
### 1. Batch upis 

Pomoću consumer servisa omogućen je batch upis pročitanih poruka sa kafke u *transaction_events* tabelu.
![SHOW TABLES](assets/oct06_insert_to_ch.png)

Pristupanjem Web SQL UI za ClickHouse (http://localhost:8123/, potrebno je uneti username i password - definisani u docker-compose fajlu) i pokretanje komande za prikaz svih redova potvrđen je upis.

![SHOW TABLES](assets/oct06_ch_input_confirmed.png)

### 2. Upis pomoću Kafka engine and Materialized views

Promenjen je kafka_format u *JSONAsString'* kako bi u *staging_transaction_events* tabeli bila zapamćena cela JSON poruka kao string, radi otpornosti na eventualnu promenu šeme. Za izdvajanje i konvertovanje podataka zadužen je *transaction_events_mv* materialized view, kojim se vrši unos u *transaction_events* tabelu.


