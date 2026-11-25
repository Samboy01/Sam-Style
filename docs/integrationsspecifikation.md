# Integrationsspecifikation – Orderintegration webshop–affärssystem

| | |
|---|---|
| **Version** | 0.1 (utkast) |
| **Datum** | 2026-11-25 |
| **Författare** | Sam Airey |
| **Relaterat** | [Kravspecifikation](kravspecifikation.md), [Mappningstabell](mappning.md) |

## 1. Översikt

Integrationen har två flöden:

| Flöde | Riktning | Trigger | Krav |
|---|---|---|---|
| **1. Order** | Webshop → affärssystem | Händelsestyrd (webhook) | FK1, FK3–FK7, IFK1–IFK4 |
| **2. Lagersaldo** | Affärssystem → webshop | Schemalagd (var 10:e minut) | FK2, FK8 |

```
Webshop ──order──▶ Webhook ──▶ Kö ──▶ Worker ──order──▶ Mini-ERP
   ▲                                    │
   │                                    └─fel─▶ Felkö ──▶ Översikt
   └────nytt saldo──── Lagersynk ◀──ändrade saldon──── Mini-ERP
```

## 2. System och gränssnitt

| System | Gränssnitt | Autentisering | Ägare |
|---|---|---|---|
| **Webshop** (Shopify, butik `sam-bolaget-dev`) | Skickar webhooks. Tar emot anrop via Admin API (GraphQL). | Webhooks: HMAC-signatur. Admin API: åtkomsttoken i header. | E-handel |
| **Integrationstjänst** (Python, FastAPI) | `POST /webhooks/shopify/orders`, översiktssida, omkörning | Webhook: HMAC. Översikt: intern åtkomst. | IT / förvaltare |
| **Kö** (RabbitMQ) | AMQP, internt i Docker-nätverket | Användarnamn och lösenord | IT / förvaltare |
| **Affärssystem** (mini-ERP, FastAPI) | REST/JSON: `POST /orders`, `GET /orders/{id}`, `GET /articles`, `GET /articles/changed?since=` | API-nyckel i header `X-API-Key` | Lager / ekonomi |

Alla hemligheter (HMAC-nyckel, åtkomsttoken, API-nyckel, lösenord) läses från miljövariabler och finns aldrig i koden (IFK5).

## 3. Flöde 1: Order (webshop → affärssystem)

### 3.1 Trigger

Webshoppen skickar en webhook med ämnet **`orders/paid`** när en order är betald. Vi använder inte `orders/create`, eftersom den även skickas för obetalda ordrar (se antagandet i kravspecifikationen).

### 3.2 Steg

1. **Ta emot:** integrationstjänsten tar emot webhooken på `POST /webhooks/shopify/orders`.
2. **Verifiera:** signaturen i headern `X-Shopify-Hmac-Sha256` räknas om på den *råa* request-bodyn med den delade hemligheten. Om den inte stämmer avvisas anropet med `401` och ingenting sparas (IFK4).
3. **Spara och köa:** ordern får status `mottagen` och ett korrelations-ID. Meddelandet läggs på kön `orders.incoming`.
4. **Svara:** tjänsten svarar `200 OK` direkt. Själva överföringen görs *inte* i webhook-anropet, eftersom webshoppen bara väntar några sekunder på svar och annars skickar webhooken igen.
5. **Bearbeta:** en worker läser meddelandet, mappar det enligt [mappningstabellen](mappning.md) och anropar `POST /orders` i affärssystemet. Status blir `skickad`.
6. **Bekräfta:** när affärssystemet svarar `201 Created` (eller `409`, se 3.4) blir status `klar`. Först då tas meddelandet bort från kön.

### 3.3 Format

JSON i båda riktningar. Bara de fält som affärssystemet behöver förs över (IFK6). Kundens e-post ersätts med en pseudonym referens (`customer_ref`). Se [mappningstabellen](mappning.md).

### 3.4 Dubbletter (idempotens)

Webshoppen kan skicka samma webhook flera gånger. Skydd i två lager (IFK2):

- **Integrationen** sparar webshoppens order-ID och lägger inte en order på kön igen om den redan är mottagen.
- **Affärssystemet** har en unik nyckel på `external_order_id`. Om ordern redan finns svarar det `409 Conflict`, vilket workern behandlar som lyckat.

## 4. Flöde 2: Lagersaldo (affärssystem → webshop)

### 4.1 Trigger

Ett schemalagt jobb körs **var 10:e minut**. Det ger marginal till kravet på max 15 minuter (FK2).

### 4.2 Steg

1. Läs tidpunkten för senaste *lyckade* körning.
2. Hämta ändrade artiklar: `GET /articles/changed?since=<tidpunkt>` (deltasynk).
3. För varje artikel: slå upp varianten i webshoppen via SKU och sätt nytt saldo via Admin API.
4. Om SKU:n saknas i webshoppen: logga en varning och fortsätt med nästa artikel (FK8).
5. Spara starttiden för körningen som ny "senaste lyckade körning", men bara om hela körningen gick igenom. Annars görs samma hämtning om vid nästa körning.

### 4.3 Regler

- Affärssystemet är källan till sanningen. Webshoppens saldo skrivs över.
- Webshoppen har ett lager, så alla saldon sätts på det lagret.

## 5. Felhantering

| Feltyp | Exempel | Hantering | Krav |
|---|---|---|---|
| **Tillfälligt** | Affärssystemet är nere (`503`), timeout, nätverksfel | Nytt försök efter 1, 5 och 15 minuter. Därefter till felkön. | IFK1 |
| **Permanent** | Okänd SKU, valideringsfel (`400`, `422`) | Inget nytt försök. Direkt till felkön med orsak. | FK5 |
| **Dubblett** | Affärssystemet svarar `409` | Behandlas som lyckat. | IFK2 |
| **Ogiltig webhook** | Fel signatur | Avvisas med `401`, loggas utan innehåll. | IFK4 |
| **Lagersynk misslyckas** | Webshoppens API svarar inte | Körningen avbryts och görs om vid nästa schemalagda tillfälle. | FK2 |

**Felkön** (`orders.dead`) visas i översikten med orsak (FK3). Förvaltaren kan köra om ett meddelande när felet är åtgärdat (FK4). Ett larm skickas när felkön inte är tom (FK6).

## 6. Status per order

```
mottagen ──▶ skickad ──▶ klar
                │
                └──▶ fel ──(omkörning)──▶ skickad
```

Status, antal försök och senaste felorsak sparas i integrationens egen databas (FK7). Raderna rensas efter 30 dagar (IFK7).

## 7. Loggning

- Strukturerade loggar i JSON.
- Varje rad har korrelations-ID och webshoppens order-ID, så att en order kan följas genom hela flödet (IFK8).
- E-post, namn och adress loggas aldrig i klartext (IFK3).

## 8. Volymer och antaganden

- Uppskattad volym: upp till några hundra ordrar per dag, med toppar vid kampanjer.
- Om affärssystemet är nere längre än omförsöken räcker (cirka 20 minuter) hamnar ordrarna i felkön. De går inte förlorade, men måste köras om från översikten när systemet är uppe igen.
