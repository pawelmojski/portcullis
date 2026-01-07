# 🚪 Inside - Brama z Kontrolą Dostępu Czasowego

**Przezroczysta brama bezpieczeństwa, która kontroluje kto może być wewnątrz Twojej infrastruktury, kiedy i jak długo.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Version](https://img.shields.io/badge/version-1.8-blue)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()

---

## 🎯 Model Mentalny: Nie "Dostęp", ale "Bycie Wewnątrz"

**Inside nie zarządza tożsamościami. Inside zarządza tym, kiedy prawdziwi ludzie mogą być wewnątrz Twojej infrastruktury.**

To jest różnica, która:
- ✅ Odróżnia Inside od Teleport, PAM-ów i ZTNA
- ✅ Tłumaczy, czemu wdrożenie zajmuje 1 godzinę, a nie miesiące
- ✅ Sprawia, że system jest natychmiast zrozumiały dla każdego

### Natychmiastowa Jasność

Nie "dostęp", nie "tożsamość", nie "kontrola".

Każdy od razu rozumie:
- 👤 **Kto jest wewnątrz** w tej chwili
- 🎫 **Kto może być wewnątrz** (i kiedy)
- 🎬 **Co robi będąc wewnątrz**
- ⏰ **Kiedy przestaje być wewnątrz**

Nie trzeba tłumaczyć architektury.

### Idealny Język Operacyjny

To jest mega ważne.

*"Kto jest wewnątrz produkcji teraz?"*

*"Był wewnątrz przez 30 minut."*

*"Ta obecność trwa do 14:30."*

*"Nikt nie może być wewnątrz bez grantu."*

Brzmi jak rzeczywistość, nie jak system.

---

## 💡 Czym jest Inside?

Wyobraź sobie, że masz 50 serwerów i 20 pracowników. Każda osoba potrzebuje dostępu do różnych serwerów w różnym czasie. Tradycyjne podejście: tworzenie kont na każdym serwerze, zarządzanie kluczami SSH, pamiętanie kto ma dostęp gdzie, ręczne odwoływanie gdy ktoś odchodzi.

**Inside siedzi pośrodku** i rozwiązuje to:

```
Komputer Osoby → Brama Inside → Serwer Backendowy
   (gdziekolwiek)   (jedno miejsce)    (10.0.x.x)
```

Z perspektywy osoby: `ssh serwer.firma.pl` - działa jak normalny SSH/RDP.
Za kulisami: Inside sprawdza "czy ta osoba ma ważny grant W TEJ CHWILI?" i albo pozwala, albo odmawia.

### Kluczowa Koncepcja: Granty Czasowe

Zamiast stałych kont, **przyznaj esz czasowy dostęp**:

```bash
# Daj Alice 8 godzin na bycie wewnątrz produkcyjnej bazy danych
inside grant alice --server prod-db-01 --duration 8h

# Alice może teraz: ssh alice@prod-db-01
# Po 8 godzinach: Dostęp automatycznie wygasa, brak sprzątania
```

Wszystko jest:
- ✅ **Scentralizowane** - jedno miejsce do zarządzania dostępem
- ✅ **Tymczasowe** - granty wygasają automatycznie
- ✅ **Audytowane** - każda obecność wewnątrz jest nagrana
- ✅ **Elastyczne** - przyznaj dostęp do grup, pojedynczych serwerów lub konkretnych protokołów

---

## 🏗️ Podstawowe Koncepcje

### 👤 Person (Osoba)

Prawdziwy człowiek.
- Ma imię i nazwisko (np. "Paweł Mojski")
- Ma konto w AAD / LDAP / czymkolwiek
- **NIE loguje się do systemów** - osoby wchodzą do środowisk

### 🎫 Grant

Pozwolenie na bycie wewnątrz.
- Definiuje **gdzie** (które serwery/grupy)
- Definiuje **jak długo** (8 godzin, tydzień, na stałe)
- Definiuje **pod jakimi warunkami** (okna czasowe, protokoły, dozwolone loginy SSH)

**Grant pozwala osobie być wewnątrz.**

Nie:
- ❌ rola
- ❌ grupa
- ❌ dokument polityki

Tylko konkretne pozwolenie.

### 🏃 Stay (Obecność)

Fakt bycia wewnątrz.
- **Stay zaczyna się** gdy osoba wchodzi (pierwsze połączenie)
- **Stay kończy się** gdy grant wygasa lub zostaje odwołany
- **Stay jest zawsze powiązany** z osobą i grantem
- **Stay może mieć wiele sesji** (disconnect/reconnect)

Osoba **pozostaje wewnątrz** nawet między połączeniami.

Nie:
- ❌ sesja
- ❌ połączenie
- ❌ logowanie

### 🔌 Session (Sesja)

Pojedyncze połączenie TCP w ramach stay.
- Połączenie SSH (terminal)
- Połączenie RDP (pulpit)
- Połączenie HTTP (GUI web)

Szczegół techniczny. Stay jest tym, co się liczy.

### 🚪 Entry (Wejście)

Sposób dostania się do środka.
- **ssh_proxy** - Entry przez SSH (port 22)
- **rdp_proxy** - Entry przez RDP (port 3389)
- **http_proxy** - Entry przez HTTP/HTTPS (przyszłość)

Entry sprawdza grant, rozpoczyna lub dołącza do stay.

### 🧾 Username

Techniczny identyfikator w systemach backendowych.
- Istnieje na hostach (konta Linux, użytkownicy DB, etc.)
- Istnieje w legacy (Cisco, routery, appliance)
- **NIE reprezentuje osoby**

**Username to szczegół implementacyjny.**

Inside mapuje `username → person`, ale:
- ❌ Nie zmienia hosta
- ❌ Nie zmienia klienta
- ❌ Nie informuje AAD
- ❌ Nie informuje targetu

To jest kluczowy punkt architektury.

### 📜 Record (Zapis)

Ślad audytowy.
- **Kto był wewnątrz** (osoba)
- **Kiedy** (znaczniki czasu)
- **Na podstawie jakiego grantu**
- **Co robił** (nagrania sesji)

Audyt bez audytu.

---

## 🎯 Jak To Działa

### 1. Brama (Inside)

Inside działa na jednym serwerze (np. `gateway.firma.pl`):
- **Port 22** - punkt wejścia SSH
- **Port 3389** - punkt wejścia RDP
- **Port 5000** - interfejs web do zarządzania

### 2. Osoba Wchodzi przez Entry

Osoba próbuje się połączyć:
```bash
ssh alice@prod-db-01.firma.pl
```

Inside (ssh_proxy):
1. Identyfikuje osobę po IP źródłowym
2. Sprawdza czy osoba ma ważny grant do celu
3. Jeśli tak: Tworzy lub dołącza do stay, przekazuje połączenie
4. Jeśli nie: Odmawia, zapisuje powód odmowy

### 3. Bycie Wewnątrz (Stay)

Alice jest teraz **wewnątrz prod-db-01**:
- Może disconnect/reconnect swobodnie (ten sam stay)
- Wszystkie sesje nagrane (logi terminala)
- Widoczne w dashboardzie: "Alice jest wewnątrz prod-db-01"

### 4. Koniec Stay

Stay kończy się gdy:
- Grant wygasa (osiągnięty limit czasu)
- Admin odwołuje grant
- Okno harmonogramu się zamyka (np. poza godzinami pracy)

Aktywne sesje przerwane, osoba nie może już wejść.

---

## 🌟 Przykład z Prawdziwego Świata

**Problem:** Problem z produkcyjną bazą danych o 9 rano. DBA potrzebuje natychmiastowego dostępu.

**Tradycyjne podejście:**
1. Utwórz konto VPN (15 minut)
2. Utwórz klucz SSH (5 minut)
3. Dodaj klucz do prod-db (10 minut + ticket zmian)
4. DBA się łączy (w końcu!)
5. Pamiętaj żeby odwołać później (zazwyczaj zapominane)

**Z Inside:**
```bash
# Admin (30 sekund):
inside grant dba-john --server prod-db-01 --duration 4h

# DBA (natychmiast):
ssh dba-john@prod-db-01.firma.pl
```

- ✅ Dostęp przyznany w 30 sekund
- ✅ Automatycznie wygasa za 4 godziny
- ✅ Pełne nagranie sesji
- ✅ Ślad audytowy: "John był wewnątrz prod-db-01 od 09:00 do 13:00"

---

## 🎨 Interfejs Web do Zarządzania

### Dashboard

Widok w czasie rzeczywistym:
- **Kto jest wewnątrz teraz** (aktywne stay)
- **Ostatnie wejścia** (ostatnie 100 prób)
- **Granty wygasające wkrótce**
- **Statystyki** (obecności dzisiaj, dostępne nagrania)

Auto-odświeżanie co 5 sekund.

### Kreator Tworzenia Grantów

Prosty proces 4-etapowy:
1. **Kto** - Wybierz osobę (lub grupę użytkowników)
2. **Gdzie** - Wybierz serwery (lub grupę serwerów)
3. **Jak** - Protokół (SSH/RDP), czas trwania, harmonogram
4. **Przegląd** - Potwierdź i utwórz

### Uniwersalne Wyszukiwanie (Mega-Wyszukiwarka)

Znajdź cokolwiek z 11+ filtrami:
- Imię osoby, username
- Serwer, grupa, IP
- Protokół, status
- Zakres dat
- Grant ID, session ID
- Powód odmowy

Eksport wyników do CSV. Auto-odświeżanie co 2 sekundy.

### Podgląd Sesji Na Żywo

Oglądaj aktywne sesje SSH w czasie rzeczywistym:
- Wyjście terminala (odświeżanie co 2 sekundy)
- Co osoba pisze w tej chwili
- Idealne do szkoleń, wsparcia, audytów

### Nagrania Sesji

Odtwarzaj przeszłe sesje:
- **SSH** - Odtwarzacz terminala (jak asciinema)
- **RDP** - Odtwarzacz wideo MP4
- Pełna historia, przeszukiwalna, eksportowalna

---

## 💎 Funkcje

### Kontrola Dostępu
- ✅ **Wiele IP źródłowych na osobę** - Dom, biuro, VPN, mobile
- ✅ **Grupy serwerów** - Przyznaj dostęp do całych grup ("Wszystkie serwery produkcyjne")
- ✅ **Szczegółowy zakres** - Poziom grupy, serwera lub protokołu
- ✅ **Filtrowanie protokołów** - Tylko SSH, tylko RDP lub oba
- ✅ **Ograniczenia loginów SSH** - Zezwalaj tylko na konkretne konta systemowe (usernames)
- ✅ **Granty czasowe** - Ograniczone czasowo z automatycznym wygaśnięciem
- ✅ **Okna harmonogramu** - Dostęp tylko Pon-Pt 9-17, cyklicznie co tydzień
- ✅ **Rekurencyjne grupy** - Grupy użytkowników z dziedziczeniem

### Zarządzanie Obecnościami (Stay)
- ✅ **Monitoring na żywo** - Zobacz kto jest wewnątrz w czasie rzeczywistym
- ✅ **Podgląd SSH na żywo** - Oglądaj sesję terminala w trakcie
- ✅ **Nagrywanie** - SSH (terminal) i RDP (wideo)
- ✅ **Odtwarzanie** - Przeglądaj przeszłe obecności
- ✅ **Wyszukiwanie** - Znajdź obecności po osobie, serwerze, czasie, statusie
- ✅ **Auto-odświeżanie** - Dashboard co 5s, wyszukiwarka co 2s
- ✅ **Wygaśnięcie grantu** - Sesje przerywane gdy grant się kończy (osoby dostają wcześniejsze ostrzeżenie)

### Audytowanie
- ✅ **Próby wejścia** - Zarówno udane jak i odmówione
- ✅ **Zmiany grantów** - Pełny ślad audytowy z historią
- ✅ **Powody odmowy** - Jasne logowanie dlaczego wejście zostało odmówione
- ✅ **Eksport** - Eksport CSV do raportowania/zgodności

### Doświadczenie Użytkownika
- ✅ **Przezroczyste** - Działa ze standardowymi klientami SSH/RDP
- ✅ **Bez agentów** - Zero oprogramowania na kliencie lub backendzie
- ✅ **Natywne narzędzia** - Używaj ssh, mstsc, PuTTY - cokolwiek wolisz
- ✅ **Port forwarding** - SSH -L, -R, -D działają (jeśli grant pozwala)
- ✅ **Transfer plików** - scp, sftp działają normalnie

---

## 🚀 Dlaczego Inside Jest Inny

### 1️⃣ Natychmiastowy Model Mentalny

Nie "dostęp", nie "tożsamość", nie "kontrola".

Każdy natychmiast rozumie:
- Kto jest wewnątrz
- Kto może być wewnątrz
- Co robi będąc wewnątrz
- Kiedy przestaje być wewnątrz

Nie trzeba tłumaczyć architektury.

### 2️⃣ Praktyczna Rzeczywistość vs. Teoretyczny Ideał

To pokazuje praktyczną różnicę między teorią a realnym IT:

| Aspekt | Inside | Tradycyjne IAM/PAM |
|--------|--------|---------------------|
| **Czas wdrożenia** | 1 godzina | Miesiące |
| **Inwazyjność** | Zero zmian w klientach/serwerach | Agenty, konfiguracje wszędzie |
| **Akceptacja użytkowników** | Użytkownicy niczego nie zauważają | Programiści protestują |
| **Kontrola i audyt** | Pełna odpowiedzialność per stay | Słabe śledzenie sesji |
| **Skalowalność** | Każdy nowy VM/serwer auto-chroniony | Konfiguracja per-host |

💡 **Puenta dla CTO/CISO:**

*"Nie zmieniamy świata - dajemy Ci pełną odpowiedzialność i audyt w realnym IT w godzinę, nie w miesiące."*

### 3️⃣ Tożsamość to NIE username

- ✅ **Tożsamość = osoba**, nie konto systemowe
- Konta systemowe mogą być: współdzielone, sklonowane, tymczasowe
- Każdy stay jest powiązany z **konkretną osobą**

> 💡 **Dla audytora/CTO:** Konto techniczne ≠ odpowiedzialność użytkownika

### 4️⃣ Dostęp skoncentrowany na Stay

- ⏱ **Granty czasowe** - dostęp tylko w wyznaczonym czasie
- 🔒 **Brak aktywnego grantu → brak wejścia**
- ❌ **Stay kończy się automatycznie gdy grant wygasa**

> 🔑 Kontrola obecności zamiast walki z systemowym IAM

### 5️⃣ Pełna audytowalność

- 🎥 **Nagrywanie każdej sesji**
- 📝 Sesje powiązane z osobą, nie kontem
- 🔍 Możliwość przeglądu działań każdej osoby

> 📜 **ISO 27001:** audytowalność i odpowiedzialność spełnione

### 6️⃣ Projekt nieinwazyjny

- ⚡ Nie wymaga agentów, PAM, ani zmian w firewallu
- 🖥 Działa z natywnymi narzędziami (SSH, vendor CLI)
- ♻️ Idealny dla systemów legacy i appliance'ów

> 🛡 Minimalne ryzyko operacyjne i łatwe wdrożenie

### 7️⃣ Praktyczna rzeczywistość

- 🖥 VM sklonowane → automatycznie podlega zasadom Inside
- 👥 Współdzielone konta → audytowalne obecności
- ⏳ Maszyny "tymczasowe" → nagrane i kontrolowane, nawet po latach

> 🚀 System dopasowany do **realnego IT**, nie teoretycznego ideału

### 8️⃣ Zgodność z ISO 27001

- ✅ Kontrolowany dostęp
- ✅ Least privilege (czasowo)
- ✅ Odpowiedzialność i audytowalność
- ✅ Nieinwazyjne wdrożenie

> 📌 Spełnia **rzeczywiste wymagania audytu** bez rewolucji w IAM

### 9️⃣ Kluczowy wniosek

> **"Nie naprawiamy świata. Naprawiamy odpowiedzialność.**
> **Liczy się kto działa, kiedy i co robi - nie konto."**

---

## 🏗️ Architektura

### Obecna Architektura (v1.8)

```
Osoba (gdziekolwiek)
    ↓
Brama Inside (jeden serwer)
    ├── ssh_proxy (Entry przez SSH :22)
    ├── rdp_proxy (Entry przez RDP :3389)
    └── web_ui (:5000)
    ↓
Serwery Backendowe (10.0.x.x)
```

### Jak Działa Entry

```
1. Osoba łączy się: ssh alice@prod-db-01
2. Entry (ssh_proxy) wyciąga:
   - IP źródłowe (identyfikuje osobę)
   - Hostname docelowy (identyfikuje serwer)
3. Zapytanie do bazy:
   - Osoba ma ważny grant?
   - Grant zezwala na SSH?
   - Grant zezwala na ten serwer?
   - Grant zezwala na tego SSH username?
4. Jeśli tak:
   - Utwórz lub dołącz do stay
   - Utwórz sesję w ramach stay
   - Przekaż do backendu
   - Nagraj wszystko
5. Jeśli nie:
   - Odmów wejścia
   - Zapisz powód odmowy
```

### Przyszła Architektura (v1.9+)

**Rozproszona:** Tower (płaszczyzna kontroli) + Gates (płaszczyzny danych)

```
Tower (Płaszczyzna Kontroli)
├── Web UI
├── REST API (/api/v1/)
└── PostgreSQL (granty, obecności, osoby)

Gates (Płaszczyzna Danych - rozproszone)
├── Gate 1 (DMZ) - ssh/rdp/http entry
├── Gate 2 (Cloud) - ssh/rdp entry
└── Gate 3 (Biuro) - tylko ssh entry

Komunikacja: REST API + lokalny cache
```

Korzyści:
- Skalowanie horyzontalne (dodaj więcej Gates)
- Dystrybucja geograficzna
- Tryb offline (Gates cache'ują granty)
- Redukcja promienia rażenia

---

## 📋 Przypadki Użycia

### 1. Dostęp Kontraktora

**Problem:** Zewnętrzny kontraktor potrzebuje 2 tygodnie dostępu do środowiska stagingowego.

**Rozwiązanie:**
```bash
inside grant kontraktor-bob --group staging-servers --duration 14d
```

Po 14 dniach: automatyczne wygaśnięcie, brak sprzątania.

### 2. Rotacja Dyżurów

**Problem:** Tygodniowy dyżurny inżynier potrzebuje awaryjnego dostępu do produkcji.

**Rozwiązanie:**
```bash
# Każdy poniedziałek, przyznaj obecnemu dyżurnemu
inside grant oncall-engineer --group production \
  --schedule "Mon-Sun 00:00-23:59" \
  --duration 7d
```

Grant automatycznie wygasa, nowy dyżurny dostaje nowy grant.

### 3. Tymczasowa Eskalacja Uprawnień

**Problem:** Junior admin potrzebuje sudo na konkretne 1-godzinne okno maintenance.

**Rozwiązanie:**
```bash
inside grant junior-admin --server app-01 \
  --ssh-login root \
  --duration 1h
```

Po 1 godzinie: dostęp root automatycznie odwołany, stay kończy się.

### 4. Audyt Zgodności

**Problem:** "Pokaż mi wszystkich, którzy byli wewnątrz produkcji w zeszłym miesiącu."

**Rozwiązanie:**
- Web UI → Wyszukiwanie
- Filtr: server_group="Production", date_from="2025-12-01"
- Eksport → CSV
- Gotowe. Pełny ślad audytowy z nagraniami sesji.

---

## 🔐 Bezpieczeństwo

### Autentykacja

- **Identyfikacja osoby** - Po IP źródłowym (mapowane na osobę w bazie)
- **Bez haseł** - Inside nigdy nie obsługuje haseł
- **Autentykacja backendowa** - Klucze SSH, dane RDP przechowywane per osoba

### Autoryzacja

- **Oparta na grantach** - Każde wejście sprawdzane względem aktywnych grantów
- **Czasowa** - Granty wygasają automatycznie
- **Szczegółowa** - Per-osoba, per-serwer, per-protokół, per-username

### Ślad Audytowy

- **Niezmienne zapisy** - Wszystkie wejścia logowane (sukces + odmowa)
- **Nagrania sesji** - Logi terminala (SSH), wideo (RDP)
- **Historia zmian** - Tworzenie/modyfikacja/usuwanie grantów śledzone

### Kontrola Sesji

- **Monitoring na żywo** - Zobacz kto jest wewnątrz teraz
- **Wymuszone przerwanie** - Admin może zabić aktywne stay
- **Auto-przerwanie** - Stay kończy się gdy grant wygasa (z ostrzeżeniami)

---

## 🛠️ Zaawansowane Funkcje

### Kontrola Port Forwardingu

Kontroluj kto może robić SSH port forwarding:

```bash
# Grant z dozwolonym port forwardingiem
inside grant alice --server bastion \
  --allow-port-forwarding local,remote,dynamic

# Grant bez port forwardingu
inside grant bob --server app-server \
  --no-port-forwarding
```

### Dostęp Oparty na Harmonogramie

Dostęp tylko w godzinach pracy:

```bash
inside grant alice --server prod-db \
  --schedule "Mon-Fri 09:00-17:00" \
  --timezone "Europe/Warsaw"
```

Cyklicznie co tydzień - osoba może wejść kiedykolwiek w harmonogramie, automatycznie blokowana poza nim.

### Tryb TPROXY (v1.9)

Transparentne proxy dla routerów Linux:

```bash
# Osoba łączy się bezpośrednio z IP serwera
ssh 10.50.1.100

# iptables przekierowuje do Inside
iptables -t mangle -A PREROUTING -p tcp --dport 22 \
  -j TPROXY --on-port 2222

# Inside wyciąga prawdziwy cel (SO_ORIGINAL_DST)
# Osoba nie wie, że Inside istnieje
```

Idealne dla Tailscale exit nodes, koncentratorów VPN.

### HTTP/HTTPS Proxy (v2.1 - Przyszłość)

Dla starych urządzeń sieciowych (stare switche, routery, appliance):

```bash
# Przyznaj dostęp do GUI web switcha
inside grant network-admin --server old-cisco-switch \
  --protocol http --duration 2h

# Osoba używa przeglądarki z proxy
https_proxy=gateway:8080 firefox
```

MITM dla pełnej kontroli HTTPS, nagrywanie sesji dla GUI web.

---

## 📊 Monitoring i Operacje

### Zdrowie Systemu

- Status PostgreSQL
- Procesy proxy (ssh_proxy, rdp_proxy)
- Wykorzystanie miejsca na nagrania
- Liczba aktywnych obecności

### Metryki

- Wejścia na godzinę (udane / odmówione)
- Średni czas trwania stay
- Najczęściej dostępne serwery
- Kolejka konwersji nagrań

### Alerty

- Grant wygasa wkrótce (< 1 godzina)
- Miejsce na nagrania > 80%
- Skok odmówionych wejść
- Serwer backendowy nieosiągalny

---

## 🗓️ Plan Rozwoju

### Obecnie: v1.8 (Mega-Wyszukiwarka) ✅

- Uniwersalne wyszukiwanie z 11+ filtrami
- Auto-odświeżanie dashboardu
- Eksport CSV
- Pełny ślad audytowy

### Następnie: v1.9 (Rozproszone + TPROXY) 🎯

- Architektura Tower/Gate (rozproszona)
- TPROXY transparentne proxy
- Warstwa API (REST)
- Ulepszenia GUI

### Przyszłość: v2.0 (Narzędzia CLI) 💡

- CLI oparte na curl (`inside grant`, `inside stays`)
- Autentykacja tokenami
- Bash completion

### Przyszłość: v2.1 (HTTP Proxy) 🔮

- HTTP/HTTPS proxy dla urządzeń legacy
- MITM dla GUI web (stare switche, routery)
- Kontrola dostępu web oparta na politykach

---

## 📚 Szybki Start

### Wymagania

- Serwer Linux (zalecany Debian 12)
- PostgreSQL 15+
- Python 3.13+
- Publiczne IP lub dostęp VPN dla klientów

### Instalacja

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/pawelmojski/inside.git
cd inside

# 2. Zainstaluj zależności
pip install -r requirements.txt

# 3. Skonfiguruj bazę danych
sudo -u postgres createdb inside
alembic upgrade head

# 4. Konfiguracja
cp config/inside.conf.example config/inside.conf
vim config/inside.conf

# 5. Uruchom usługi
sudo systemctl start inside-ssh-proxy
sudo systemctl start inside-rdp-proxy
sudo systemctl start inside-flask
```

### Pierwszy Grant

```bash
# 1. Dodaj osobę
inside person add "Jan Kowalski" --ip 100.64.0.50

# 2. Dodaj serwer backendowy
inside server add prod-db-01 --ip 10.0.1.100

# 3. Utwórz grant
inside grant create jan.kowalski --server prod-db-01 --duration 8h

# 4. Osoba może teraz wejść
ssh jan.kowalski@gateway.firma.pl
```

---

## 🎓 Dokumentacja

- **[ROADMAP.md](ROADMAP.md)** - Plan rozwoju i historia wersji
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Dokumentacja techniczna
- **[README.md](README.md)** - Wersja angielska

---

## 💬 TL;DR

**Inside w jednym zdaniu:**

*Czasowe granty dla prawdziwych ludzi na bycie wewnątrz infrastruktury, z pełnym audytem i nagrywaniem sesji, wdrożone w godzinę.*

**Kluczowe różnice:**

- 👤 **Osoba ≠ username** - Odpowiedzialność dla ludzi, nie kont
- ⏱ **Skoncentrowane na Stay** - Kto jest wewnątrz teraz, jak długo
- 🎫 **Oparte na Grantach** - Konkretne pozwolenie, nie rola/grupa
- 🚀 **Nieinwazyjne** - Bez agentów, bez zmian, wdrożenie w godzinę
- 📜 **Pełny audyt** - Każde wejście, każdy stay, każda sesja nagrana

**Jedna komenda żeby przyznać dostęp:**
```bash
inside grant alice --server prod-db --duration 8h
```

**Jedno miejsce żeby zobaczyć wszystko:**
```
Dashboard → Kto jest wewnątrz teraz
```

---

**Projekt:** Inside
**Repozytorium:** https://github.com/pawelmojski/inside
**Status:** Produkcja (v1.8)
**Licencja:** Komercyjna (opcje monetyzacji otwarte)
