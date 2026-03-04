# Plan działania: Nutrition Tracker API (Minimum Viable Product)

Pełen opis aplikacji w pliku "APP_DESCRIPTION.md"

Ten dokument opisuje kroki niezbędne do uruchomienia podstawowej wersji systemu Nutrition Tracker.

## Etap 1: Fundamenty i Baza Danych (SQLite)
- [ ] Inicjalizacja projektu Python (FastAPI).
- [ ] Stworzenie schematu bazy danych SQLite (SQLAlchemy/SQLModel):
    - Tabela `users` (id, name, token).
    - Tabela `foods` (słownik produktów: kcal/białko na 100g).
    - Tabela `meals` (nagłówek wpisu, powiązanie z użytkownikiem).
    - Tabela `meal_items` (poszczególne składniki posiłku).
- [ ] Skrypt do inicjalizacji bazy i dodania testowego użytkownika oraz kilku produktów (np. "skyr", "borówki").

## Etap 2: Autoryzacja i Middleware
- [ ] Implementacja mechanizmu sprawdzania tokena (8 znaków) w nagłówku `Authorization: Bearer`.
- [ ] Dependency Injection w FastAPI do pobierania `current_user` na podstawie tokena.

## Etap 3: Parser Tekstu (Core Logic)
- [x] Implementacja prostej logiki parsowania tekstu (regex):
    - Wyciąganie gramatury (np. "400g").
    - Wyciąganie nazwy produktu.
- [x] Logika dopasowania nazwy z tekstu do bazy `foods` (proste dopasowanie po nazwie/aliasach).
- [x] Przeliczanie wartości odżywczych (kcal, białko) na podstawie gramatury i danych ze słownika.

## Etap 4: Endpointy API (MVP)
- [x] `POST /eat`: Przyjmuje surowy tekst, filmuje go, parsuje i zapisuje jako `meal` + `meal_items`.
- [x] `GET /meals`: Lista posiłków zalogowanego użytkownika (filtrowanie po `user_id`).
- [x] `GET /stats/today`: Podsumowanie dzisiejszych kalorii i białka.

## Etap 5: Prosty Interfejs (Frontend)
- [x] Statyczny plik HTML/JS serwowany przez FastAPI lub Nginx.
- [x] Pole tekstowe do wpisywania posiłków.
- [x] Wyświetlanie prostego podsumowania dnia.

## Etap 6: Konteneryzacja i Wdrożenie
- [ ] Przygotowanie `Dockerfile` dla aplikacji FastAPI.
- [ ] Konfiguracja podstawowego `docker-compose.yml` (opcjonalnie z Nginx).
