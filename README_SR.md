# AIJobRadar

FastAPI servis produkcijskog kvaliteta koji prikuplja oglase za AI/ML poslove sa vise remote job sajtova, normalizuje ih u jedinstvenu shemu, kesira rezultate sa TTL mehanizmom i sluzi sve kroz REST API.

## Glavne funkcionalnosti

- **Prikupljanje iz vise izvora** — Agregira poslove sa RemoteOK, WeWorkRemotely i Hacker News "Who is hiring?" tema
- **Fokus na AI/ML** — Filtrira oglase koristeci 25+ AI kljucnih reci (LLM, PyTorch, MLOps, computer vision, itd.)
- **Jedinstvena shema** — Svaki posao se normalizuje u isti Pydantic model bez obzira na izvor
- **Pametno kesiranje** — JSON fajl kes sa podesivim TTL-om da se ne preopterecuju sajt izvori
- **API sa filterima** — Pretraga po kljucnoj reci, kompaniji, lokaciji ili izvoru sa paginacijom
- **Swagger dokumentacija** — Interaktivna API dokumentacija na `/docs`
- **Potpuno testiran** — 66 testova sa 89% pokrivenosti koda

## Tehnoloski stek

| Komponenta     | Tehnologija                     |
|----------------|---------------------------------|
| Jezik          | Python 3.11+                    |
| Web framework  | FastAPI                         |
| HTTP klijent   | httpx (asinhroni)               |
| HTML parsiranje| BeautifulSoup4 + lxml           |
| Validacija     | Pydantic v2                     |
| Konfiguracija  | pydantic-settings + .env        |
| Testiranje     | pytest + pytest-asyncio + respx |
| Server         | uvicorn                         |
| Linting        | ruff                            |
| Formatiranje   | black                           |

## Brzi pocetak

```bash
# Kloniraj repozitorijum
git clone https://github.com/YOUR_USERNAME/aijobradar.git
cd aijobradar

# Napravi i aktiviraj virtualno okruzenje (Python 3.11+)
python3 -m venv venv
source venv/bin/activate

# Instaliraj zavisnosti
pip install -r requirements.txt

# (Opciono) Kopiraj i podesi environment varijable
cp .env.example .env

# Pokreni server
python run.py
```

API ce biti dostupan na **http://localhost:8000**.

## Kako sistem funkcionise

### Tok podataka

1. **Zahtev stize** na API endpoint u `app/routes/jobs.py`
2. **ScraperManager** proverava da li je kes svez (u okviru TTL-a)
3. **Kes pogodak**: Vraca kesirane poslove odmah
4. **Kes promasaj**: Pokrece sve skrejpere istovremeno koristeci `asyncio.gather()`
5. **Skrejperi** prikupljaju podatke sa sva tri izvora paralelno
6. **Filtriranje**: Svaki skrejper filtrira rezultate po AI kljucnim recima
7. **Normalizacija**: Svi rezultati se normalizuju u jedinstveni `Job` Pydantic model
8. **Upis u kes**: Rezultati se upisuju u `data/jobs_cache.json` sa vremenskim pecatom
9. **API odgovor**: Filtrirani, paginirani rezultati se vracaju klijentu

### Kljucne komponente

**Konfiguracija (`app/config.py`)**:
- 25+ AI kljucnih reci: ai, llm, machine learning, pytorch, nlp, mlops, rag, computer vision, agent, itd.
- Podesiv TTL kesa (podrazumevano: 60 minuta)
- Tajmaut zahteva (podrazumevano: 15 sekundi)
- Maksimalan broj poslova po izvoru (podrazumevano: 100)

**Kes sloj (`app/cache.py`)**:
- Kesiranje bazirano na JSON fajlu (`data/jobs_cache.json`)
- Struktura: `{"updated_at": "ISO_TIMESTAMP", "jobs": [...]}`
- Provera svezine na osnovu vremenskog pecata
- Graciozan oporavak od ostecenih ili nestalih fajlova

**Modeli podataka (`app/models.py`)**:
- `Job` — Glavni model sa poljima: id, title, company, location, salary, tags, url, source, posted_at, scraped_at
- `JobsResponse` — Paginiran odgovor sa total, page, limit i listom poslova
- `SourceStatus` — Status izvora sa imenom, vremenom poslednjeg skrejpovanja, brojem poslova i greskom

**Skrejperi (`app/scrapers/`)**:
- `base.py` — Apstraktna `BaseScraper` klasa koju svi skrejperi nasledjuju
- `manager.py` — `ScraperManager` koji orkestira sve skrejpere
- `remoteok.py` — Koristi JSON API, sa HTML fallback-om ako API zakaze
- `weworkremotely.py` — HTML skrejping sa pretragom, fallback na stranicu kategorije ako Cloudflare blokira
- `hackernews.py` — Algolia API za pronalazenje poslednje "Who is hiring?" teme i parsiranje komentara

## API Endpointi

### `GET /` — Dobrodoslica

Vraca navigacione linkove ka svim endpointima.

### `GET /jobs` — Lista AI/ML poslova

Vraca paginirane oglase sa mogucnoscu filtriranja.

**Parametri upita:**

| Parametar  | Tip    | Podrazumevano | Opis                                       |
|------------|--------|---------------|---------------------------------------------|
| `keyword`  | string | —             | Filter po kljucnoj reci (naslov/kompanija/tagovi) |
| `company`  | string | —             | Filter po imenu kompanije                   |
| `location` | string | —             | Filter po lokaciji                          |
| `source`   | string | —             | Filter po izvoru (remoteok/weworkremotely/hackernews) |
| `page`     | int    | 1             | Broj stranice                               |
| `limit`    | int    | 20            | Rezultata po stranici (maksimum 100)        |

Svi filteri su case-insensitive pretrage podstringova.

**Primeri:**

```bash
# Svi poslovi sa paginacijom
curl "http://localhost:8000/jobs?page=1&limit=20"

# Filter po kljucnoj reci
curl "http://localhost:8000/jobs?keyword=llm"

# Filter po kompaniji i izvoru
curl "http://localhost:8000/jobs?company=OpenAI&source=remoteok"

# Kombinacija filtera
curl "http://localhost:8000/jobs?keyword=pytorch&location=remote&limit=5"
```

### `GET /sources` — Status izvora

Vraca vreme skrejpovanja, broj poslova i status greske za svaki izvor.

```bash
curl http://localhost:8000/sources
```

### `POST /refresh` — Prisilno osvezavanje

Ponistava kes i ponovo skrejpuje sve izvore. Vraca statistiku i trajanje.

```bash
curl -X POST http://localhost:8000/refresh
```

### `GET /health` — Provera zdravlja servisa

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "1.0.0"}
```

### Swagger UI

Interaktivna dokumentacija je dostupna na **http://localhost:8000/docs**.

## Struktura projekta

```
aijobradar/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI aplikacija — ulazna tacka
│   ├── config.py            # Podesavanja preko pydantic-settings
│   ├── models.py            # Pydantic modeli podataka
│   ├── cache.py             # JSON fajl kes sa TTL-om
│   ├── routes/
│   │   ├── __init__.py
│   │   └── jobs.py          # API rute i handleri
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py           # Apstraktni bazni skrejper
│       ├── manager.py        # Orkestracija skrejpera
│       ├── remoteok.py       # RemoteOK (JSON API + HTML fallback)
│       ├── weworkremotely.py # WeWorkRemotely (HTML skrejper)
│       └── hackernews.py     # HN "Who is hiring?" (Algolia API)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Deljeni fiksturi
│   ├── test_api.py           # Testovi API endpointa
│   ├── test_cache.py         # Testovi kes sloja
│   ├── test_scrapers.py      # Testovi skrejpera sa mokovanim HTTP-om
│   └── fixtures/             # Uzorci HTML/JSON za testove
│       ├── remoteok_sample.json
│       ├── remoteok_sample.html
│       ├── weworkremotely_sample.html
│       ├── hackernews_story.json
│       ├── hackernews_comments.json
│       └── hackernews_sample.html
├── data/                     # Direktorijum za kes
│   └── jobs_cache.json       # Kes fajl (generise se u runtime-u)
├── .env.example              # Primer environment konfiguracije
├── .gitignore
├── requirements.txt          # Python zavisnosti
├── pyproject.toml            # Metapodaci projekta i konfiguracija alata
├── run.py                    # Ulazna tacka — pokrece uvicorn server
├── LICENSE                   # MIT licenca
└── README.md                 # Dokumentacija (engleski)
```

## Testiranje

```bash
# Pokreni kompletan test suite
pytest

# Pokreni sa izvestajem o pokrivenosti
pytest --cov=app --cov-report=term-missing

# Pokreni specifican test fajl
pytest tests/test_api.py -v

# Pokreni samo testove skrejpera
pytest tests/test_scrapers.py -v
```

**Sta se testira:**
- `test_api.py` — 30+ testova za API endpointe (paginacija, filtriranje, validacija odgovora)
- `test_cache.py` — Testovi kes sloja (TTL, serijalizacija, svezina)
- `test_scrapers.py` — Testovi skrejpera sa mokovanim HTTP odgovorima (respx biblioteka)
- `conftest.py` — Deljeni fiksturi (uzorci poslova, mokovani manager, test klijent)

## Linting i formatiranje

```bash
# Proveri lint greske
ruff check app/ tests/

# Proveri formatiranje
black --check app/ tests/

# Automatsko formatiranje
black app/ tests/
```

## Konfiguracija

Sva podesavanja se mogu pregaziti preko environment varijabli ili `.env` fajla. Pogledaj `.env.example` za kompletnu listu.

| Varijabla                | Podrazumevano          | Opis                             |
|--------------------------|------------------------|----------------------------------|
| `CACHE_TTL_MINUTES`      | `60`                   | Trajanje svezine kesa (minuti)   |
| `REQUEST_TIMEOUT_SECONDS` | `15`                  | Tajmaut HTTP zahteva (sekunde)   |
| `MAX_JOBS_PER_SOURCE`    | `100`                  | Maks. poslova po skrejperu       |
| `LOG_LEVEL`              | `INFO`                 | Nivo logovanja                   |
| `CACHE_FILE_PATH`        | `data/jobs_cache.json` | Putanja do kes fajla             |
| `USER_AGENT`             | `Mozilla/5.0 (AIJobRadar/1.0; ...)` | HTTP User-Agent zaglavlje |

## Izvori podataka

| Izvor            | Metod                     | Napomene                                          |
|------------------|---------------------------|---------------------------------------------------|
| RemoteOK         | JSON API (`/api`)         | Fallback na HTML parsiranje ako API zakaze         |
| WeWorkRemotely   | HTML skrejping            | Fallback na stranicu kategorije ako pretraga bude blokirana |
| Hacker News      | Algolia API               | Parsira komentare iz poslednje "Who is hiring?" teme |

## Vazne napomene

- **Nema baze podataka** — Projekat koristi fajl-bazirano JSON kesiranje umesto tradicionalne baze
- **Asinhroni dizajn** — Svi skrejperi rade paralelno zahvaljujuci async/await patternu
- **Otpornost na greske** — Ako jedan skrejper zakaze, ostali nastavljaju normalno (graceful degradation)
- **Rate limiting** — TTL kes mehanizam sprecava prekomerno opterecivanje izvora
- **Cloudflare zastita** — WeWorkRemotely skrejper ima fallback strategiju za slucaj blokiranja

## Licenca

MIT
