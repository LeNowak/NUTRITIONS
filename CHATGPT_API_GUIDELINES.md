# Wytyczne dla ChatGPT: korzystanie z Nutrition Tracker API

Ten dokument opisuje, jak ChatGPT powinien komunikować się z API projektu `NUTRITIONS`.

## 1) Założenia
- API działa pod adresem bazowym: `https://mdtest.gembito.net`
- Wszystkie endpointy użytkownika wymagają tokena w nagłówku:
  - `Authorization: Bearer TOKEN8`
- Token musi mieć dokładnie 8 znaków z zakresu `A-Z0-9`.
- Domyślny token testowy: `TEST1234`
- Używaj wyłącznie HTTPS (HTTP może zwracać `301/308`).
- Endpoint `POST /eat` obsługuje zarówno `/eat`, jak i `/eat/`.

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
- Pozycje i sumy obejmują `kcal`, `protein`, `carbs`, `fiber`.
- Jeśli produkt nie istnieje jeszcze w słowniku i skonfigurowano `GEMINI_API_KEY`, backend spróbuje oszacować wartości przez Gemini, zapisać produkt do `foods` i od razu policzyć wpis.
- Jeśli AI nie uzupełni produktu, wpis nadal zostanie zapisany, ale ta pozycja dostanie `0` dla wszystkich wartości odżywczych do czasu uzupełnienia słownika.
- Jeśli parser nie wyciągnie żadnych pozycji, surowy wpis nadal zostanie zapisany w historii z pustą listą pozycji i zerowymi sumami.

### `GET /meals`
- Cel: lista posiłków aktualnego użytkownika (od najnowszych).
- Wymaga `Authorization: Bearer ...`

### `GET /stats/today`
- Cel: podsumowanie dnia (`kcal`, `protein`, `carbs`, `fiber`) dla aktualnego użytkownika.
- Wymaga `Authorization: Bearer ...`

### `GET /foods`
- Cel: pobranie słownika gotowych produktów i potraw.
- Wymaga `Authorization: Bearer ...`

### `POST /foods`
- Cel: dodanie nowego produktu do słownika.
- Wymaga `Authorization: Bearer ...`
- Body JSON:
```json
{
  "name": "jajko",
  "aliases": "egg|jajka",
  "kcal_per_100g": 143,
  "protein_per_100g": 12.6,
  "carbs_per_100g": 0.7,
  "fiber_per_100g": 0
}
```

### `PUT /foods/{id}`
- Cel: edycja istniejącego produktu w słowniku.
- Wymaga `Authorization: Bearer ...`

### `DELETE /foods/{id}`
- Cel: usunięcie produktu ze słownika, jeśli nie jest użyty w historii posiłków.
- Wymaga `Authorization: Bearer ...`

### `GET /oauth/authorize`
- Cel: rozpoczęcie OAuth (`response_type=code`).
- Wymagane parametry: `redirect_uri`, `state`.
- Opcjonalne: `client_id`.
- Endpoint wyświetla prostą stronę logowania z polem `TOKEN8`.
- Po poprawnym logowaniu robi redirect na `redirect_uri` z `code` i `state`.

### `POST /oauth/token`
- Cel: wymiana `code` na `access_token`.
- Wymagane pola: `grant_type=authorization_code`, `code`, `redirect_uri`.
- Zwraca JSON z `access_token` (tu: TOKEN8), `token_type`, `expires_in`.

## 3) Zalecana sekwencja działań ChatGPT
1. Sprawdź `GET /health`.
2. Sprawdź `GET /me` z tokenem użytkownika.
3. Gdy użytkownik podaje posiłek, wywołaj `POST /eat`.
4. Po zapisie odśwież `GET /stats/today`.
5. Gdy użytkownik prosi o historię, wywołaj `GET /meals`.

## 3a) OAuth dla GPT Actions
1. GPT otwiera: `GET /oauth/authorize?response_type=code&client_id=...&redirect_uri=...&state=...`
2. Użytkownik wpisuje `TOKEN8` na stronie logowania.
3. Backend przekierowuje na callback z parametrami `code` i `state`.
4. GPT wykonuje `POST /oauth/token` i dostaje `access_token`.
5. GPT używa `Authorization: Bearer <access_token>` przy wywołaniach API.

Wymagania bezpieczeństwa:
- Parametr `state` jest obowiązkowy.
- `redirect_uri` musi być HTTPS.
- Dopuszczone callbacki OpenAI obejmują domeny:
  - `https://chat.openai.com/.../oauth/callback`
  - `https://chatgpt.com/.../oauth/callback`
- Możesz też doprecyzować whitelistę przez env: `OAUTH_ALLOWED_REDIRECT_URIS` (lista URI rozdzielona przecinkami).

## 4) Przykładowe żądania (cURL)

### Health
```bash
curl https://mdtest.gembito.net/health
```

### Walidacja użytkownika
```bash
curl -H "Authorization: Bearer TEST1234" https://mdtest.gembito.net/me
```

### Zapis posiłku
```bash
curl -X POST https://mdtest.gembito.net/eat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TEST1234" \
  -d '{"text":"400g skyr, 100g borowki"}'
```

### Lista posiłków
```bash
curl -H "Authorization: Bearer TEST1234" https://mdtest.gembito.net/meals
```

### Statystyki dnia
```bash
curl -H "Authorization: Bearer TEST1234" https://mdtest.gembito.net/stats/today
```

### Dodanie produktu do słownika
```bash
curl -X POST https://mdtest.gembito.net/foods \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TEST1234" \
  -d '{"name":"jajko","aliases":"egg|jajka","kcal_per_100g":143,"protein_per_100g":12.6,"carbs_per_100g":0.7,"fiber_per_100g":0}'
```

### OAuth authorize
```bash
curl "https://mdtest.gembito.net/oauth/authorize?response_type=code&client_id=test-client&redirect_uri=https%3A%2F%2Fchat.openai.com%2Faip%2Foauth%2Fcallback&state=abc123"
```

### OAuth token exchange
```bash
curl -X POST https://mdtest.gembito.net/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=AUTH_CODE&redirect_uri=https%3A%2F%2Fchat.openai.com%2Faip%2Foauth%2Fcallback&client_id=test-client"
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
- payload jest błędny lub pusty.

Reakcja ChatGPT:
- poproś o doprecyzowanie wpisu,
- zaproponuj format z gramaturą i nazwą produktu, jeśli użytkownik chce też liczyć makro.

## 6) Format odpowiedzi ChatGPT do użytkownika
Po zapisaniu posiłku:
- podaj krótkie podsumowanie sumy posiłku (`kcal`, `protein`, opcjonalnie `carbs`, `fiber`),
- opcjonalnie wypisz pozycje (nazwa + gramy),
- zaproponuj od razu aktualizację statystyk dnia.

Przykład odpowiedzi:
- „Zapisano posiłek: 309.0 kcal, 44.7 g białka, 18.2 g węglowodanów i 3.1 g błonnika. Chcesz, żebym dodał kolejny wpis?”

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
- AI enrichment wymaga skonfigurowanego `GEMINI_API_KEY` i poprawnego modelu Gemini.
- OAuth korzysta z tymczasowych kodów zapisanych w SQLite (TTL 5 minut, jednorazowe użycie).
- Endpoint `/oauth/authorize` akceptuje standardowe `response_type=code` oraz tymczasowo także starsze `authorization_code` dla kompatybilności wstecznej.
