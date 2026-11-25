# Sekvensdiagram – Orderflödet

| | |
|---|---|
| **Version** | 0.1 (utkast) |
| **Datum** | 2026-11-25 |
| **Författare** | Sam Airey |
| **Relaterat** | [Integrationsspecifikation](integrationsspecifikation.md), [Mappningstabell](mappning.md) |

Diagrammen visar i vilken ordning systemen anropar varandra. Läs uppifrån och ned. Heldragna pilar är anrop och streckade pilar är svar.

## 1. Lyckat fall

En betald order förs över till affärssystemet (FK1).

```mermaid
sequenceDiagram
    autonumber
    participant S as Webshop (Shopify)
    participant W as Webhook
    participant DB as Integrationens databas
    participant Q as Kö (RabbitMQ)
    participant K as Worker
    participant E as Mini-ERP

    S->>W: POST /webhooks/shopify/orders (orders/paid)
    W->>W: Verifiera HMAC-signatur
    W->>DB: Spara order, status = mottagen
    W->>Q: Lägg meddelande på orders.incoming
    W-->>S: 200 OK
    Q->>K: Leverera meddelande
    K->>K: Mappa enligt mappningstabellen
    K->>DB: Status = skickad
    K->>E: POST /orders (X-API-Key)
    E-->>K: 201 Created
    K->>DB: Status = klar
    K->>Q: Bekräfta (ack), meddelandet tas bort
```

## 2. Affärssystemet är tillfälligt nere

Ordern försöks igen med växande väntetid och försvinner inte (IFK1).

```mermaid
sequenceDiagram
    autonumber
    participant Q as Kö (RabbitMQ)
    participant K as Worker
    participant DB as Integrationens databas
    participant E as Mini-ERP
    participant F as Felkö (orders.dead)
    participant O as Översikt och larm

    Q->>K: Leverera meddelande
    K->>E: POST /orders
    E-->>K: 503 Service Unavailable
    K->>DB: Försök 1 misslyckades, orsak sparas
    K->>Q: Lägg på väntekö (1 min)

    alt ERP är uppe igen vid nästa försök
        Q->>K: Leverera meddelande igen
        K->>E: POST /orders
        E-->>K: 201 Created
        K->>DB: Status = klar
    else Alla försök (1, 5, 15 min) misslyckas
        K->>F: Flytta meddelandet till felkön
        K->>DB: Status = fel, orsak = ERP svarar inte
        F->>O: Visa i översikten och skicka larm
    end
```

## 3. Samma webhook skickas två gånger

Ordern skapas bara en gång (IFK2).

```mermaid
sequenceDiagram
    autonumber
    participant S as Webshop (Shopify)
    participant W as Webhook
    participant DB as Integrationens databas
    participant K as Worker
    participant E as Mini-ERP

    S->>W: POST webhook (order 5123456789012)
    W->>DB: Finns ordern redan?
    DB-->>W: Nej
    W->>DB: Spara order, status = mottagen
    W-->>S: 200 OK

    Note over S,W: Svaret kom inte fram, Shopify skickar igen

    S->>W: POST webhook (samma order)
    W->>DB: Finns ordern redan?
    DB-->>W: Ja
    W-->>S: 200 OK (läggs inte på kön igen)

    Note over K,E: Andra skyddet om dubbletten ändå skulle nå ERP:t
    K->>E: POST /orders (samma external_order_id)
    E-->>K: 409 Conflict
    K->>DB: Behandlas som lyckat, status = klar
```

## 4. Order med okänt artikelnummer

Ett permanent fel försöks inte igen (FK5).

```mermaid
sequenceDiagram
    autonumber
    participant Q as Kö (RabbitMQ)
    participant K as Worker
    participant E as Mini-ERP
    participant DB as Integrationens databas
    participant F as Felkö (orders.dead)
    participant O as Översikt och larm
    actor P as Förvaltare

    Q->>K: Leverera meddelande
    K->>E: POST /orders (SKU = SB-XXX-999)
    E-->>K: 422 Okänt artikelnummer
    K->>F: Flytta direkt till felkön (inga omförsök)
    K->>DB: Status = fel, orsak = Okänt artikelnummer SB-XXX-999
    F->>O: Visa i översikten och skicka larm
    P->>E: Lägger upp artikeln i affärssystemet
    P->>O: Klickar på Kör om
    O->>Q: Lägg meddelandet på orders.incoming igen
    Note over Q,E: Flödet fortsätter som i diagram 1
```

## 5. Lagersynk

Schemalagd deltasynk från affärssystemet till webshoppen (FK2, FK8).

```mermaid
sequenceDiagram
    autonumber
    participant J as Lagersynk (var 10:e min)
    participant DB as Integrationens databas
    participant E as Mini-ERP
    participant S as Webshop (Shopify)

    J->>DB: Hämta tid för senaste lyckade körning
    DB-->>J: 2026-11-25 14:00
    J->>E: GET /articles/changed?since=2026-11-25T14:00
    E-->>J: Lista med ändrade artiklar och saldon

    loop För varje artikel
        J->>S: Slå upp variant via SKU
        alt SKU finns i webshoppen
            J->>S: Sätt nytt saldo (Admin API)
            S-->>J: OK
        else SKU saknas
            J->>J: Logga varning och fortsätt
        end
    end

    J->>DB: Spara körningens starttid som senaste lyckade körning
```
