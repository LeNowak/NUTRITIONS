# Specyfikacja: Nutrition Tracker API + Dashboard
*(SQLite, multi-user token, parser tekstu)*

## Cel projektu
Zbudować mały serwis HTTP (API) z bazą danych SQLite, który pozwala kilku osobom prowadzić dziennik jedzenia. Użytkownicy logują się 8-znakowym tokenem dołączanym do każdego zapytania.

**Kluczowe funkcjonalności:**
- Przyjmowanie posiłków w formie tekstowej.
- Parsowanie składników i wag (gramatury).
- Dopasowywanie składników do słownika produktów (`foods`).
- Automatyczne wyliczanie kalorii (kcal) i białka.
- Zapisywanie wpisów do bazy danych.
- Udostępnianie kalendarza wpisów oraz dashboardu statystyk.

---

## Architektura wdrożenia
Najprostsza konfiguracja na serwerze z otwartym portem.

### Topologia
`Internet` → `Nginx (Reverse Proxy)` → `FastAPI (Port 8090)` → `SQLite (nutrition.db)`

### Komponenty:
1.  **Nginx**: Serwuje statyczną stronę (frontend) i przekierowuje zapytania do API (np. pod ścieżką `/nutrition/`).
2.  **API**: Działa jako proces systemowy (`systemd`), automatycznie wstaje po restarcie serwera.
3.  **SQLite**: Pojedynczy plik bazy danych; backup wykonywany regularnie przez `cron`.

---

## Uwierzytelnianie i multi-user

### Token dostępu
- Każdy użytkownik posiada unikalny token: 8 znaków (`A–Z`, `0–9`).
- Przesyłany w każdym zapytaniu:
    - **Rekomendowane**: Nagłówek `Authorization: Bearer TOKEN8`
    - **Alternatywnie**: Query param `?token=TOKEN8`

### Zasady bezpieczeństwa
- Wszystkie dane w API są filtrowane po `user_id` wynikającym z tokena.
- Token jest stałym kluczem dostępu (brak sesji w tradycyjnym sensie).
- Zarządzanie użytkownikami i słownikiem produktów dostępne wyłącznie dla administratora.

---

## Model danych (SQLite)

### Relacje (schemat logiczny)
`users (1)` ─── `(N) meals (1)` ─── `(N) meal_items (N)` ─── `(1) foods`

### Tabele:
1.  **`users`**
    - `id` (PK)
    - `name`
    - `token` (UNIQUE, 8 znaków)

2.  **`foods`** (Słownik produktów)
    - `id` (PK)
    - `name` (Kanoniczna nazwa, np. "skyr")
    - `aliases` (Opcjonalnie: synonimy rozdzielone pionową kreską, np. "skyr|jogurt islandzki")
    - `kcal_per_100g`
    - `protein_per_100g`
    - *Wspólne dla wszystkich użytkowników.*

3.  **`meals`** (Nagłówek posiłku)
    - `id` (PK)
    - `user_id` (FK → `users`)
    - `date` (`YYYY-MM-DD`)
    - `time` (Opcjonalnie: `HH:MM`)
    - `raw_text` (Oryginalny wpis użytkownika)
    - `total_kcal` (Wyliczone automatycznie)
    - `total_protein` (Wyliczone automatycznie)
    - `created_at` (Timestamp)

4.  **`meal_items`** (Pozycje posiłku)
    - `id` (PK)
    - `meal_id` (FK → `meals`)
    - `food_id` (FK → `foods`)
    - `grams`
    - `kcal` (Wyliczone dla pozycji)
    - `protein` (Wyliczone dla pozycji)
    - `matched_name` (Co dopasowano z tekstu)

---

## Parser posiłków (Automatyczny)

### Wejście
Użytkownik wysyła wieloliniowy tekst do endpointu `/eat`:
```text
400g skyr
150g borówki
10g bcaa
```

### Zasady parsowania:
- **Linia**: Każda linia to jedna pozycja.
- **Detekcja**:
    - Gramatura: `(\d+)(g|gram|grams)` lub `kg` (konwersja na `g`).
    - Nazwa produktu: Reszta linii.
- **Normalizacja**: Lower-case, usunięcie spacji, uproszczenie polskich znaków.
- **Dopasowanie**:
    1. Exact match do `foods.name`.
    2. Match do `foods.aliases`.
    3. Wybór najlepszego dopasowania (score/długość).
- **Obsługa błędów**: Rekomendowany "wariant twardy" – zwróć błąd przy braku dopasowania linii, aby utrzymać porządek.

### Obliczenia:
- `kcal_item = grams * kcal_per_100g / 100`
- `protein_item = grams * protein_per_100g / 100`

---

## Endpointy API

### Użytkownik (Wymaga tokena)
1.  **`GET /me`**: Walidacja tokena, zwraca dane profilu.
2.  **`POST /eat`**: Dodanie posiłku z tekstu.
    - Body: `{ "date": "YYYY-MM-DD", "time": "HH:MM", "text": "..." }`
3.  **`GET /day/{date}`**: Lista wpisów i sumy dla konkretnego dnia.
4.  **`GET /calendar?month=YYYY-MM`**: Heatmapa miesięczna (dni z wpisami + badge kcal).
5.  **`GET /stats`**: Szybkie statystyki (dziś, tydzień, miesiąc).
6.  **`DELETE /meal/{id}`**: Usunięcie wpisu (tylko właściciel).

### Administrator
1.  **`POST /admin/users`**: Tworzenie nowego użytkownika.
2.  **`POST/PUT/GET /admin/foods`**: Zarządzanie słownikiem produktów.

---

## Frontend (Dashboard)
Minimalistyczna strona HTML+JS serwowana przez Nginx.

- **Login**: Zapis tokena w `localStorage`.
- **Dashboard**: Widok statystyk dziennych/tygodniowych.
- **Kalendarz**: Interaktywna mapa dni (kliknięcie pokazuje detale dnia).
- **Input**: Pole tekstowe do szybkiego wpisywania posiłków.

---

## Plan wdrożenia
1.  Konfiguracja katalogu aplikacji i środowiska.
2.  Implementacja API (FastAPI + SQLAlchemy/SQLModel).
3.  Konfiguracja `systemd` dla procesu API.
4.  Ustawienie Nginx jako Reverse Proxy + HTTPS (Let's Encrypt).
5.  Automatyzacja backupu bazy `nutrition.db`.

---

## Rozwój w przyszłości
- Obsługa "porcji" (sztuka, łyżka).
- Personalizowane słowniki produktów per-user.
- Eksport danych do CSV/JSON.
- Integracja z wagą i modelowanie zapotrzebowania (TDEE).
