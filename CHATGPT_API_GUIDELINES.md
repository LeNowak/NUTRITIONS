# Wytyczne dla ChatGPT: korzystanie z Nutrition Tracker API

Ten dokument opisuje, jak ChatGPT powinien komunikować się z API projektu `NUTRITIONS`.

## 1) Założenia
- API działa lokalnie pod adresem bazowym: `http://127.0.0.1:8082`
- Wszystkie endpointy użytkownika wymagają tokena w nagłówku:
  - `Authorization: Bearer TOKEN8`
- Token musi mieć dokładnie 8 znaków z zakresu `A-Z0-9`.
- Domyślny token testowy: `TEST1234`

## 2) Endpointy używane przez ChatGPT

### `GET /health`
- Cel: szybkie sprawdzenie, czy API odpowiada.
- Nie wymaga autoryzacji.

### `GET /me`
- Cel: walidacja tokena i pobranie danych aktualnego użytkownika.
- Wymaga `Authorization: Bearer ...`

### `POST /eat`
- Cel: zapisanie posiłku z tekstu.
- Body JSON:
```json
{
  "text": "400g skyr, 100g borowki"
}
```
- Zwraca zapisany posiłek wraz z wyliczonymi pozycjami i sumami.

### `GET /meals`
- Cel: lista posiłków aktualnego użytkownika (od najnowszych).
- Wymaga `Authorization: Bearer ...`

### `GET /stats/today`
- Cel: podsumowanie dnia (`kcal`, `protein`) dla aktualnego użytkownika.
- Wymaga `Authorization: Bearer ...`

## 3) Zalecana sekwencja działań ChatGPT
1. Sprawdź `GET /health`.
2. Sprawdź `GET /me` z tokenem użytkownika.
3. Gdy użytkownik podaje posiłek, wywołaj `POST /eat`.
4. Po zapisie odśwież `GET /stats/today`.
5. Gdy użytkownik prosi o historię, wywołaj `GET /meals`.

## 4) Przykładowe żądania (cURL)

### Health
```bash
curl http://127.0.0.1:8082/health
```

### Walidacja użytkownika
```bash
curl -H "Authorization: Bearer TEST1234" http://127.0.0.1:8082/me
```

### Zapis posiłku
```bash
curl -X POST http://127.0.0.1:8082/eat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TEST1234" \
  -d '{"text":"400g skyr, 100g borowki"}'
```

### Lista posiłków
```bash
curl -H "Authorization: Bearer TEST1234" http://127.0.0.1:8082/meals
```

### Statystyki dnia
```bash
curl -H "Authorization: Bearer TEST1234" http://127.0.0.1:8082/stats/today
```

## 5) Obsługa błędów (ważne)

### `401 Unauthorized`
Najczęściej:
- brak nagłówka `Authorization`,
- zły format (`Bearer ...`),
- niepoprawny token (nie 8 znaków `A-Z0-9`),
- token nie istnieje w bazie.

Reakcja ChatGPT:
- poproś użytkownika o poprawny token,
- wyjaśnij wymagany format: `Authorization: Bearer TOKEN8`.

### `422 Unprocessable Entity`
Najczęściej:
- parser nie wykrył pozycji jedzenia,
- API nie dopasowało produktu do słownika `foods`.

Reakcja ChatGPT:
- poproś o doprecyzowanie wpisu (np. `200g skyr, 100g banan`),
- zaproponuj poprawny format z gramaturą i nazwą produktu.

## 6) Format odpowiedzi ChatGPT do użytkownika
Po zapisaniu posiłku:
- podaj krótkie podsumowanie sumy posiłku (`kcal`, `protein`),
- opcjonalnie wypisz pozycje (nazwa + gramy),
- zaproponuj od razu aktualizację statystyk dnia.

Przykład odpowiedzi:
- „Zapisano posiłek: 309.0 kcal i 44.7 g białka. Chcesz, żebym dodał kolejny wpis?”

## 7) Dobre praktyki promptowania ChatGPT (dla operatora)
- Podawaj token na początku rozmowy.
- Podawaj posiłki w formacie: `ilość + jednostka + produkt`, np.:
  - `400g skyr`
  - `100g borowki`
  - `0.2kg platki owsiane`
- Przy wielu składnikach rozdzielaj przecinkiem lub nową linią.

## 8) Ograniczenia aktualnego API
- `POST /eat` zapisuje posiłek na bieżącą datę serwera.
- Brak endpointu do edycji wpisu.
- Brak endpointu do usuwania wpisu.
- Brak endpointów administracyjnych do zarządzania słownikiem `foods`.
