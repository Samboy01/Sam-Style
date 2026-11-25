# Mini-ERP

Ett enkelt affärssystem med REST-API och databas (artiklar, ordrar, orderrader). Det är målsystemet för integrationen och kan simulera fel, till exempel att det är nere.

Byggt med Python, FastAPI, SQLAlchemy och PostgreSQL.

## Starta

Från projektroten (Docker Desktop måste vara igång):

```
docker compose up -d --build mini-erp
```

API:et finns på http://localhost:8001. Öppna **http://localhost:8001/docs** för en testsida där du kan prova alla anrop. Klicka på **Authorize** och klistra in värdet av `ERP_API_KEY` från `.env`.

Vid första start skapas tabellerna, och de 8 artiklarna från webshoppen läggs in med samma saldon.

## Endpoints

Alla utom `/health` kräver API-nyckel i headern `X-API-Key`.

| Metod | Sökväg | Beskrivning | Svar |
|---|---|---|---|
| `GET` | `/health` | Hälsokontroll | `200` |
| `POST` | `/orders` | Skapa order. Drar av antalet från lagersaldot. | `201` skapad, `409` finns redan, `422` ogiltig eller okänt artikelnummer |
| `GET` | `/orders/{id}` | Hämta order med rader | `200`, `404` |
| `GET` | `/articles` | Lista alla artiklar med saldo | `200` |
| `GET` | `/articles/changed?since=<tid>` | Artiklar vars saldo ändrats efter `since` (ISO 8601). Används av lagersynken. | `200` |
| `PUT` | `/articles/{article_no}/stock` | Sätt nytt saldo, t.ex. efter inleverans | `200`, `404` |

Fältens format beskrivs i [mappningstabellen](../docs/mappning.md).

## Felbrytare

Används för att visa integrationens felhantering. Ändra i `.env` och starta om tjänsten:

| `ERP_FAILURE_MODE` | Beteende |
|---|---|
| `none` | Normal drift |
| `down` | Alla API-anrop svarar `503 Service Unavailable` |
| `slow` | Alla API-anrop väntar `ERP_SLOW_SECONDS` sekunder innan de svarar |

```
docker compose up -d mini-erp
```

`/health` och `/docs` påverkas inte av felbrytaren.

## Filer

| Fil | Innehåll |
|---|---|
| `app/main.py` | API:et, API-nyckel och felbrytare |
| `app/models.py` | Databastabeller |
| `app/schemas.py` | Validering av data in och ut |
| `app/seed.py` | Startdata (artiklar) |
| `app/config.py` | Inställningar från miljövariabler |
| `app/database.py` | Databasanslutning |
