# Integrationstjänst

Tar emot ordrar från webshoppen via webhook, lägger dem på en kö och skickar dem vidare till affärssystemet.

Består av två processer som byggs från samma kod:

| Process | Start | Uppgift |
|---|---|---|
| **integration** | `uvicorn app.main:app` | Tar emot webhooks på `POST /webhooks/shopify/orders`, verifierar signaturen och lägger ordern på kön `orders.incoming`. |
| **worker** | `python -m app.worker` | Hämtar ordrar från kön, mappar dem enligt [mappningstabellen](../docs/mappning.md) och anropar `POST /orders` i mini-ERP:t. Misslyckade ordrar läggs i felkön `orders.dead` med orsak. |

## Starta

Från projektroten:

```
docker compose up -d --build
```

- Webhook: http://localhost:8000/webhooks/shopify/orders (nås från Shopify via tunnel)
- Orderstatus: http://localhost:8000/admin/orders och `/admin/orders/{shopify_order_id}`, kräver headern `X-Admin-Key` med värdet av `INTEGRATION_ADMIN_KEY` i `.env`. Testsida på http://localhost:8000/docs.
- RabbitMQ:s webbgränssnitt: http://localhost:15672 (användare och lösenord: `RABBITMQ_USER` och `RABBITMQ_PASSWORD` i `.env`)

## Filer

| Fil | Innehåll |
|---|---|
| `app/main.py` | Webhook-endpointen |
| `app/shopify.py` | Verifiering av Shopifys HMAC-signatur |
| `app/broker.py` | Köer och publicering till RabbitMQ |
| `app/worker.py` | Workern |
| `app/mapping.py` | Shopify-order → ERP-order |
| `app/erp.py` | Anrop till mini-ERP:t |
| `app/models.py`, `app/status.py` | Statustabellen `order_status`: mottagen → skickad → klar / fel |
| `app/db.py` | Databasanslutning |
| `app/config.py` | Inställningar från miljövariabler |

## Tester

```
pip install -r requirements-dev.txt
pytest
```
