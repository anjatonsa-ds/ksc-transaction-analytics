# Dnevnik Rada 
## 🎯 Fokus Dana 
Sredjivanje producer, consumer servisa kako bi izveštaji prikazivali realnije podatke.

### 1. Ponovno pokretanje Clickhouse kontejnera
```bash
    docker compose down clickhouse -v
    docker compose up clickhouse --build
```
Izbačena je tabela *casino_transactions*.
Promenjeno je da se *ingestion_lag* u tabelama *hourly_metrics* i *daily_metrics* računa u milisekundama.
Materijalizovani prikazi i table su ponovo kreirane i sada su prazne.

### 2. Brisanje zaostalih poruka u Kafka brokerku
```bash
    docker exec -it kafka bash
    kafka-topics --bootstrap-server kafka:29092 --topic transaction_events --delete
    kafka-topics --bootstrap-server kafka:29092 --topic transaction_events --create
```

### 3. Promena načina slanja poruka u *producer* servisu
Trenutne funkcionalnosti: Slanje poruka radi sa 100 random unapred definisanih korisnika. Postoji simuliranje sesije u okviru koje može da se desi random broj transakcija izmedju 1 i 10. Do 20% poruka koje se šalju nemaju sve validne podatke. Za transakcije gde je *product* tipa "casino" generišu se metapodaci.

Promenjeno je da vreme poruke za slanje bude trenutno vreme za prvu transakciju iz sesije. Kako bi moglo jos uvek da se simulira i trajanje sesije za neki period od 5 do 10min, uvedena je nova kolona za vreme *event_time_send* kako bi mogao da se prati realni *ingestion lag*. *Event_time_send* predstavlja realno vreme slanja poruke u sistemu i poklapa se sa vremenom početka sesije u tačnosti minuta.

### 4. Promene u *consumer* servisu
Uklonjena je funkcija za pamćenje posebno transakcija gde je *product* tipa "casino", sve transakcije idu ili u *transaction_events_anomaly* ili *rejected_events* tabelu. Ispravka koda za insert transakcija zbog novouvedene kolone.

Isključena je provera vremena da li je transakcija u budućnosti kako bi se ispratila prethodna logika oko vremena transakcija iz sesije.

### 5. Testiranje
Servisi su pušteni da rade 3 dana kako bi se posle kreirali izveštaji koji daju približno realnu sliku stvarnog sistema.


