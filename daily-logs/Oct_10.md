# Dnevnik Rada 
## 🎯 Fokus Dana 
Poboljšanje simulacije transakcionih podataka

## 🛠 Izvršeni Zadaci
### 1. Poboljšanje mockup podataka
#### Recurring user_ids
Definisana je grupa od 1000 user_id-eva.

#### Amount
Za simulaciju vrednosti *amount* korisničkih transakcija napravljena je funkcija koja generiše vrednosti tako da odgovaraju Pareto distribuciji(grupe: minnow 80% user-a, dolphins 15%, whales 5%).

#### Sesija
Simulacija je unapredjena tako da postoje transakcije koje se dešavaju u okviru iste sesije.

Funkcija u *producer* servisu je zamenjena novom verzijom.


### 2. Ispravka tokena kod invertovanih indeksa
Razlozi za odbijanje su zamenjeni šiframa:
"Missing event_id." - miss_evnt_id
"Misssing user_id." - miss_usr_id
"Currency value not valid." - curr_not_valid
"Transaction type is not valid." - tx_type_not_valid
"Amount<0 for invalid type of transaction." - amnt_not_valid
"Timestamp is in the future." - ts_not_valid



