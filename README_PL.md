# 🏰 Portcullis - Brama SSH/RDP z Kontrolą Dostępu Opartą na Politykach

**Transparentna brama bezpieczeństwa, która stoi między użytkownikami a serwerami backend, egzekwując polityki dostępu, nagrywając sesje i zapewniając scentralizowane zarządzanie.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Wersja](https://img.shields.io/badge/version-1.8-blue)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()

---

## 💡 Czym jest Portcullis?

Wyobraź sobie, że masz 50 serwerów i 20 pracowników. Każdy pracownik potrzebuje dostępu do różnych serwerów w różnym czasie. Tradycyjne podejście: tworzysz konta na każdym serwerze, zarządzasz kluczami SSH, pamiętasz kto ma dostęp gdzie, ręcznie odwołujesz gdy ktoś odchodzi.

**Portcullis stoi pośrodku** i rozwiązuje ten problem:

```
Komputer Użytkownika → Brama Portcullis → Serwer Backend
    (skądkolwiek)          (jedno miejsce)      (10.0.x.x)
```

Z perspektywy użytkownika: `ssh server.firma.pl` - działa jak normalny SSH/RDP.
Za kulisami: Portcullis sprawdza "czy ten użytkownik ma uprawnienia WŁAŚNIE TERAZ?" i albo zezwala, albo odmawia.

### Kluczowy Koncept: Czasowe Granty Dostępu

Zamiast stałych kont, **przydzielasz tymczasowy dostęp**:

```bash
# Daj Alicji 8 godzin dostępu do produkcyjnej bazy danych
portcullis grant alice --server prod-db-01 --duration 8h

# Alicja może teraz: ssh alice@prod-db-01
# Po 8 godzinach: Dostęp automatycznie wygasa, bez sprzątania
```

Wszystko jest:
- ✅ **Scentralizowane** - jedno miejsce do zarządzania wszystkimi dostępami
- ✅ **Tymczasowe** - dostęp wygasa automatycznie
- ✅ **Audytowane** - każde połączenie zapisane
- ✅ **Elastyczne** - przydzielaj dostęp do grup, pojedynczych serwerów lub konkretnych protokołów

---

## 🎯 Jak to Działa

### 1. Brama (Portcullis)

Portcullis działa na jednym serwerze (np. `gateway.firma.pl`):
- **Port 22** - Ruch SSH przechodzi tutaj
- **Port 3389** - Ruch RDP przechodzi tutaj
- **Port 5000** - Interfejs webowy zarządzania

### 2. Granty Dostępu (Polityki)

Zarządzasz dostępem przez **polityki** (granty):

**Przykład: Grant dostępu do grupy**
```
Użytkownik: jan
Cel: Wszystkie serwery w grupie "Bazy Produkcyjne"
Protokół: Tylko SSH
Czas trwania: 24 godziny
Loginy SSH: postgres, readonly
```

Gdy Jan próbuje się połączyć:
```bash
jan@laptop:~$ ssh postgres@prod-db-01.firma.pl
# ↓ Połączenie trafia do Portcullis
# ↓ Portcullis sprawdza: Czy jan ma aktywny grant do prod-db-01?
# ✅ TAK - proxy połączenie do prawdziwego serwera prod-db-01
# ❌ NIE - pokaż przyjazną wiadomość "dostęp zabroniony"
```

### 3. Co Widzi Użytkownik

**Z GRANTEM DOSTĘPU:**
```bash
$ ssh moj-user@serwer-docelowy
# Działa dokładnie jak normalny SSH
# Użytkownik nawet nie wie, że Portcullis jest pośrodku
```

**BEZ GRANTU DOSTĘPU:**
```
+====================================================================+
|                        DOSTĘP ZABRONIONY                           |
+====================================================================+

  Szanowny użytkowniku,

  Brak aktywnego grantu dostępu dla Twojego adresu IP: 100.64.0.20

  Powód: Brak pasującej polityki dostępu

  Skontaktuj się z administratorem aby poprosić o dostęp.
```

### 4. Nagrywanie Sesji

Każde połączenie jest nagrywane:
- **Sesje SSH** - Pełne nagranie terminala (jak asciinema)
- **Sesje RDP** - Nagranie wideo z możliwością odtworzenia
- **Log audytu** - Kto połączył się kiedy, skąd, do którego serwera

Interfejs webowy pokazuje:
- Aktywne sesje (kto jest teraz połączony)
- Historia sesji (szukaj po użytkowniku, serwerze, dacie)
- Podgląd na żywo (oglądaj sesję SSH w czasie rzeczywistym)
- Odtwarzanie nagrań

---

## 🚀 Przykład ze Świata Rzeczywistego

### Scenariusz: Awaryjny Dostęp do Bazy Danych

**9:00** - Zgłoszono problem z bazą danych

**Team Lead:**
```bash
# Przyznaj DBA dostęp na 4 godziny
portcullis grant alice --server prod-db-01 --duration 4h --protocol ssh
```

**Alicja (z domu, VPN, albo biura):**
```bash
alice@laptop:~$ ssh postgres@prod-db-01
# Działa natychmiast, nie trzeba kopiować kluczy, tworzyć kont na serwerze
```

**13:00** - Problem rozwiązany, dostęp wygasa automatycznie

**Później** - Team lead sprawdza:
- Panel webowy pokazuje że Alicja była połączona 9:15-10:30
- Można obejrzeć nagranie terminala aby zobaczyć jakie komendy zostały wykonane
- Log audytu pokazuje połączenie z IP 100.64.0.25

---

## 🎨 Interfejs Webowy Zarządzania

Dostęp pod `http://gateway.firma.pl:5000`

### Dashboard
- 🟢 Status usług (SSH Proxy, RDP Proxy działają)
- 📊 Szybkie statystyki (15 użytkowników, 42 serwery, 8 aktywnych sesji)
- 📅 Dzisiejsza aktywność (23 połączenia, 2 odmowy, 91% sukces)
- 🔄 Auto-odświeżanie co 5 sekund

### Kreator Przydzielania Dostępu

**Prosty proces 3 kroków:**

1. **Kto?** Wybierz użytkownika (lub utwórz nowego)
2. **Gdzie?** Wybierz:
   - Grupa serwerów (np. "Wszystkie produkcyjne bazy")
   - Pojedynczy serwer (np. "app-server-01")
   - Konkretna usługa (np. "db-01 tylko SSH")
3. **Jak długo?** Wpisz czas: `2h`, `3d`, `1w`, lub `permanent`

**Opcje zaawansowane:**
- Filtrowanie protokołu (tylko SSH, tylko RDP, lub oba)
- Ograniczenia loginów SSH (tylko konta `postgres` i `readonly`)
- Okna harmonogramu (Poniedziałek-Piątek 9-17)

### Wyszukaj Wszystko (Mega-Wyszukiwarka) 🔍

Zunifikowane wyszukiwanie po wszystkich danych:
- Szukaj po nazwie użytkownika, nazwie serwera, adresie IP
- Filtruj po protokole, statusie (aktywne/odmowa), zakresie dat
- Auto-odświeżanie co 2 sekundy (zobacz nowe sesje na żywo)
- Eksport do CSV dla raportowania

**Przykłady:**
```
Szukaj: "alice"          → Wszystkie sesje użytkownika alice
Szukaj: "10.0.1.50"      → Wszystkie połączenia do/z tego IP
Szukaj: "#42"            → Szczegóły polityki #42
Szukaj: "denied"         → Wszystkie odmówione próby połączenia
```

---

## 🏗️ Architektura

### Proste Wdrożenie (Obecne)

```
┌─────────────────────────────────────────┐
│         Brama Portcullis                │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │  SSH Proxy  │  │   RDP Proxy      │ │
│  │   (port 22) │  │   (port 3389)    │ │
│  └─────────────┘  └──────────────────┘ │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │  Flask Web  │  │   PostgreSQL     │ │
│  │ (port 5000) │  │  (polityki, logi)│ │
│  └─────────────┘  └──────────────────┘ │
└─────────────────────────────────────────┘
           │
           │ Kieruje do serwerów backend
           ↓
    ┌──────────────┐  ┌──────────────┐
    │  Serwer      │  │  Serwer      │
    │  Backend 1   │  │  Backend 2   │
    └──────────────┘  └──────────────┘
```

### Architektura Rozproszona (v1.9 - Wkrótce)

```
         ┌──────────────────────────┐
         │    Tower (Kontrola)      │
         │  - Interfejs Web         │
         │  - Baza Polityk          │
         │  - Serwer API            │
         └────────────┬─────────────┘
                      │
        ┬─────────────┼─────────────┬
        │             │             │
   ┌────▼───┐    ┌───▼────┐    ┌───▼────┐
   │ Gate 1 │    │ Gate 2 │    │ Gate 3 │
   │  DMZ   │    │ Chmura │    │ Biuro  │
   └────────┘    └────────┘    └────────┘
```

**Zastosowanie:** Zainstaluj bramę Portcullis w różnych segmentach sieci (DMZ, chmura, biuro) - wszystko zarządzane z jednej Wieży.

---

## 💎 Funkcje

### Kontrola Dostępu
- ✅ **Wiele źródłowych IP per użytkownik** - Dom, biuro, VPN, mobile
- ✅ **Grupy serwerów** - Przyznaj dostęp do całych grup ("Wszystkie serwery produkcyjne")
- ✅ **Granularny zakres** - Poziom grupy, poziom serwera, lub poziom protokołu
- ✅ **Filtrowanie protokołu** - Tylko SSH, tylko RDP, lub oba
- ✅ **Ograniczenia loginów SSH** - Zezwalaj tylko na konkretne konta systemowe
- ✅ **Czasowy dostęp** - Ograniczony czasowo z automatycznym wygaśnięciem
- ✅ **Okna harmonogramu** - Dostęp tylko Pon-Pt 9-17, cyklicznie co tydzień
- ✅ **Rekurencyjne grupy** - Grupy użytkowników z dziedziczeniem

### Zarządzanie Sesjami
- ✅ **Monitoring na żywo** - Zobacz aktywne sesje w czasie rzeczywistym
- ✅ **Podgląd SSH na żywo** - Oglądaj sesję terminala w trakcie
- ✅ **Nagrywanie** - SSH (terminal) i RDP (wideo)
- ✅ **Odtwarzanie** - Przeglądaj przeszłe sesje
- ✅ **Wyszukiwanie** - Znajdź sesje po użytkowniku, serwerze, czasie, statusie
- ✅ **Auto-odświeżanie** - Dashboard co 5s, wyszukiwanie co 2s

### Audytowanie
- ✅ **Próby połączeń** - Zarówno udane jak i odmówione
- ✅ **Zmiany polityk** - Pełna ścieżka audytu z historią
- ✅ **Powody odmowy** - Jasne logowanie czemu dostęp został odmówiony
- ✅ **Eksport** - Eksport CSV dla raportowania/zgodności

### Doświadczenie Użytkownika
- ✅ **Transparentny** - Działa ze standardowymi klientami SSH/RDP
- ✅ **Przyjazne błędy** - Jasne komunikaty gdy dostęp odmówiony
- ✅ **Bez konfiguracji** - Użytkownicy po prostu `ssh serwer`, bez specjalnej konfiguracji
- ✅ **Agent forwarding** - Klucze SSH działają naturalnie

---

## 🔧 Szybki Start

### Instalacja

```bash
# Zainstaluj zależności systemowe
sudo apt install postgresql python3.13 python3-pip python3-venv

# Sklonuj repozytorium
git clone https://github.com/pawelmojski/portcullis
cd portcullis

# Skonfiguruj środowisko wirtualne
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Zainicjuj bazę danych
sudo -u postgres createdb portcullis
alembic upgrade head

# Uruchom usługi
sudo systemctl enable --now portcullis-ssh-proxy
sudo systemctl enable --now portcullis-rdp-proxy
sudo systemctl enable --now portcullis-flask
```

### Pierwsze Użycie

1. **Wejdź na interfejs webowy:** http://twoj-serwer:5000
2. **Dodaj siebie jako użytkownika:**
   - Użytkownicy → Dodaj Użytkownika
   - Wprowadź swoje imię, email
   - Dodaj swoje źródłowe IP (zobacz "Mój IP: X.X.X.X" w prawym górnym rogu)
3. **Dodaj serwer backend:**
   - Serwery → Dodaj Serwer
   - Nazwa: `test-serwer`, IP: `10.0.1.100`
4. **Przyznaj sobie dostęp:**
   - Polityki → Przyznaj Dostęp
   - Wybierz siebie, wybierz serwer, czas trwania `1h`
5. **Przetestuj połączenie:**
   ```bash
   ssh twoj-login@test-serwer
   ```

---

## 📖 Typowe Przypadki Użycia

### 1. Dostęp dla Kontrahenta

**Problem:** Trzeba dać kontrahencie tymczasowy dostęp do konkretnych serwerów.

**Rozwiązanie:**
```bash
# Dodaj kontrahenta
portcullis user add kontrahent-jan --email jan@zewnetrzna.pl
portcullis user add-ip kontrahent-jan 203.0.113.50 --label "VPN Kontrahenta"

# Przyznaj 2-tygodniowy dostęp tylko do serwerów dev
portcullis grant kontrahent-jan --group "Serwery Deweloperskie" --duration 14d

# Dostęp automatycznie wygasa, nie trzeba sprzątać
```

### 2. Rotacja Dyżurów

**Problem:** Co tydzień inna osoba ma dostęp do produkcji.

**Rozwiązanie:**
```bash
# Tydzień 1: Alicja dyżuruje
portcullis grant alice --group "Produkcja" --duration 7d

# Tydzień 2: Bartek dyżuruje (grant Alicji już wygasł)
portcullis grant bartek --group "Produkcja" --duration 7d
```

### 3. Dostęp Awaryjny

**Problem:** Baza padła o 2 w nocy, potrzebny dostęp DBA TERAZ.

**Rozwiązanie:**
```bash
# Z telefonu przez curl:
curl -X POST https://gateway/api/v1/grant \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user":"dba-alice","server":"prod-db","duration":"4h"}'

# DBA może się połączyć natychmiast z dowolnego miejsca
```

### 4. Audyt Zgodności

**Problem:** "Pokaż mi wszystkich którzy mieli dostęp do produkcji w zeszłym miesiącu."

**Rozwiązanie:**
- Interfejs Web → Wyszukiwanie
- Filtr: server_group="Produkcja", date_from="2025-12-01"
- Eksport → CSV
- Gotowe. Pełna ścieżka audytu z nagraniami sesji.

---

## 🎓 Kluczowe Pojęcia

### Polityki (Granty)

Polityka to: "Użytkownik X może mieć dostęp do Celu Y przez Protokół Z przez Czas D"

**Komponenty:**
- **Użytkownik** - Kto dostaje dostęp
- **Cel** - Grupa serwerów, pojedynczy serwer, lub konkretna usługa
- **Protokół** - SSH, RDP, lub oba
- **Czas trwania** - Jak długo (lub permanentnie)
- **Harmonogram** (opcjonalnie) - Okna czasowe (np. tylko w godzinach pracy)
- **Loginy SSH** (opcjonalnie) - Ogranicz które konta systemowe

### Źródłowe IP Użytkowników

Użytkownicy mogą mieć wiele źródłowych IP:
- Dom: `192.168.1.100`
- Biuro: `10.0.50.25`
- VPN: `100.64.0.10`
- Mobile: `203.0.113.5`

Gdy użytkownik łączy się z KTÓREGOKOLWIEK z tych IP, Portcullis go rozpoznaje.

### Grupy Serwerów

Organizuj serwery logicznie:
- "Bazy Produkcyjne"
- "Serwery Deweloperskie"
- "Serwery Web w DMZ"

Przyznaj dostęp do całej grupy zamiast pojedynczych serwerów.

### Stany Sesji

- **Aktywna** - Użytkownik obecnie połączony
- **Zamknięta** - Sesja zakończona normalnie
- **Odmowa** - Próba połączenia zablokowana (brak polityki)

---

## 🔒 Funkcje Bezpieczeństwa

### Obrona Warstwowa

1. **Poziom Sieciowy** - Tylko Portcullis dostępny z internetu
2. **Poziom Polityk** - Szczegółowa kontrola dostępu
3. **Poziom Protokołu** - Filtruj SSH vs RDP
4. **Poziom Kont** - Ogranicz konta systemowe SSH
5. **Poziom Czasowy** - Automatyczne wygasanie
6. **Poziom Audytu** - Wszystko logowane

### Co Jest Nagrywane

- Próby połączeń (udane i odmówione)
- Źródłowe IP, serwer docelowy, protokół
- Czas trwania, przesłane bajty
- Pełne nagranie sesji (terminal lub wideo)
- Polityka która przyznała/odmówiła dostępu
- Powód odmowy jeśli zablokowane

### Odmowa Dostępu

Gdy dostęp odmówiony, użytkownik widzi:
- Przyjazną wiadomość (nie kryptyczny błąd)
- Powód odmowy
- Jak poprosić o dostęp

Portcullis loguje:
- Próbowany użytkownik, serwer, źródłowe IP
- Powód odmowy (brak polityki, wygasł, zły protokół, etc.)
- Timestamp

---

## 🛠️ Zaawansowane Funkcje

### Kontrola Port Forwardingu

Kontroluj kto może robić SSH port forwarding:

```bash
# Grant z dozwolonym port forwarding
portcullis grant alice --server bastion \
  --allow-port-forwarding local,remote,dynamic

# Grant bez port forwarding
portcullis grant bartek --server app-server \
  --no-port-forwarding
```

### Dostęp Oparty na Harmonogramie

Dostęp tylko w godzinach pracy:

```bash
portcullis grant alice --server prod-db \
  --schedule "Pon-Pt 09:00-17:00" \
  --timezone "Europe/Warsaw"
```

Cyklicznie co tydzień - użytkownik może się łączyć w dowolnym momencie w harmonogramie, automatycznie blokowany poza nim.

### Tryb TPROXY (v1.9)

Transparentny proxy dla routerów (Tailscale, bramy VPN):

```bash
# Użytkownik myśli że łączy się bezpośrednio
ssh user@10.50.1.100

# Iptables kieruje przez Portcullis transparentnie
iptables -t mangle -A PREROUTING -p tcp --dport 22 \
  -j TPROXY --on-port 2222

# Portcullis widzi oryginalne docelowe IP, sprawdza politykę
```

---

## 🚧 Plan Rozwoju

### v1.9 - Architektura Rozproszona & TPROXY
- Wdrożenie wielu bram (DMZ, chmura, biuro)
- Separacja Tower (płaszczyzna kontroli) + Gate (płaszczyzna danych)
- Tryb transparentnego proxy TPROXY
- Lokalne cache'owanie dla odporności offline

### v2.0 - CLI & Automatyzacja
- Pełne narzędzie CLI oparte na curl
- Uwierzytelnianie API przez tokeny
- Bash completion
- Powiadomienia webhook (Slack, Teams)
- Integracja FreeIPA/LDAP

---

## 📊 Monitoring & Operacje

### Sprawdzenie Zdrowia

```bash
# Sprawdź wszystkie usługi
systemctl status portcullis-*

# Zobacz logi
journalctl -u portcullis-ssh-proxy -f
tail -f /var/log/portcullis/ssh_proxy.log
```

### Metryki

Dashboard webowy pokazuje:
- Liczba aktywnych sesji
- Połączenia na godzinę (wykres)
- Top użytkownicy według aktywności
- Odmówione próby
- Ostrzeżenia o wygasających politykach

### Konserwacja

```bash
# Backup bazy danych
pg_dump portcullis > backup.sql

# Zobacz nagrania sesji
ls /var/recordings/portcullis/ssh/
ls /var/recordings/portcullis/rdp/

# Wyczyść stare nagrania (>90 dni)
find /var/recordings/ -mtime +90 -delete
```

---

## 🤝 Współpraca

Wkład mile widziany! Obszary w których chętnie przyjmiemy pomoc:
- Integracja FreeIPA/LDAP
- Playbooki Ansible do wdrożenia
- Moduły Terraform
- Charty Kubernetes Helm
- Dodatkowe metody uwierzytelniania

---

## 🎯 TL;DR

**Portcullis = Brama bezpieczeństwa która:**
- Stoi między użytkownikami a serwerami
- Egzekwuje czasowe polityki dostępu
- Nagrywa każdą sesję
- Pokazuje wszystko w interfejsie web
- Działa ze standardowymi klientami SSH/RDP

**Jedna komenda aby przyznać dostęp:**
```bash
portcullis grant alice --server prod-db --duration 8h
```

**Jedno miejsce aby zobaczyć wszystko:**
```
http://gateway:5000
```

To tyle. Prosty koncept, potężna implementacja. 🏰

---

*Zbudowane dla zespołów bezpieczeństwa, które cenią prostotę i audytowalność.*
