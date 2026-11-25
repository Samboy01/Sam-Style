# Mappningstabell – Shopify-order → ERP-order

| | |
|---|---|
| **Version** | 0.1 (utkast) |
| **Datum** | 2026-11-25 |
| **Författare** | Sam Airey |
| **Relaterat** | [Kravspecifikation](kravspecifikation.md), [Integrationsspecifikation](integrationsspecifikation.md) |

Tabellen beskriver hur en order från webshoppens webhook (`orders/paid`) översätts till en order i affärssystemets `POST /orders`. Den är underlaget för enhetstesterna av mappningen.

## 1. Orderhuvud

| Shopify (källa) | ERP (mål) | Typ i ERP | Transformation och regler |
|---|---|---|---|
| `id` | `external_order_id` | text | Heltal → text. Används för dubblettkontroll (IFK2). Obligatoriskt. |
| `name` | `external_order_no` | text | T.ex. `#1001`. Ordernumret som kunden och personalen ser. |
| `created_at` | `order_date` | datum och tid | ISO 8601 → svensk tid (Europe/Stockholm), t.ex. `2026-11-25T14:03:00+01:00`. |
| `currency` | `currency` | text | Måste vara `SEK`, annars permanent fel. |
| `customer.id` | `customer_ref` | text | Pseudonym referens: `SHOP-<customer.id>`. Saknas kund blir värdet `GUEST`. E-post förs inte över (IFK6). |
| `shipping_lines[].price` | `shipping_amount` | decimal | Summa av alla fraktrader. Text → decimal med 2 decimaler. Saknas frakt blir värdet `0.00`. |
| `total_discounts` | `discount_amount` | decimal | Text → decimal med 2 decimaler. |
| `total_price` | `total_amount` | decimal | Text → decimal med 2 decimaler. Belopp inklusive moms, i SEK. |

## 2. Orderrader

En rad i `line_items[]` blir en rad i `rows[]`.

| Shopify (källa) | ERP (mål) | Typ i ERP | Transformation och regler |
|---|---|---|---|
| `line_items[].sku` | `rows[].article_no` | text | Tomma mellanslag tas bort. Måste finnas i ERP, annars permanent fel (FK5). Tom SKU är också ett permanent fel. |
| `line_items[].title` | `rows[].description` | text | Kopieras rakt av. Endast för läsbarhet; ERP:t använder artikelnumret. |
| `line_items[].quantity` | `rows[].qty` | heltal | Måste vara större än 0. |
| `line_items[].price` | `rows[].unit_price` | decimal | Text → decimal med 2 decimaler. Styckpris inklusive moms. |

## 3. Fält som inte förs över

Dataminimering (IFK6): affärssystemet behöver inte dessa uppgifter för att plocka och bokföra ordern i MVP:n.

| Shopify-fält | Varför det inte förs över |
|---|---|
| `email`, `customer.email` | Personuppgift. Ersätts av `customer_ref`. |
| `customer.first_name`, `customer.last_name` | Personuppgift. |
| `shipping_address`, `billing_address` | Personuppgift. Hanteras av webshoppens fraktflöde i MVP:n. |
| `phone` | Personuppgift. |
| `note` | Fritext som kan innehålla personuppgifter. |

> Om lagret senare behöver leveransadress i affärssystemet måste det beslutas och dokumenteras som ett nytt krav (se öppna frågor i kravspecifikationen).

## 4. Valideringsregler

Kontrolleras av integrationen *innan* ordern skickas till affärssystemet. Ett fel här är alltid permanent: ordern går direkt till felkön med orsak och försöks inte igen.

| Regel | Felorsak i felkön |
|---|---|
| `id` saknas | `Order-ID saknas` |
| `currency` är inte `SEK` | `Valuta stöds inte: <valuta>` |
| Ordern har inga rader | `Ordern saknar rader` |
| En rad saknar SKU | `Rad <n> saknar artikelnummer` |
| `quantity` är 0 eller mindre | `Rad <n> har ogiltigt antal` |
| Ett belopp går inte att tolka som tal | `Ogiltigt belopp i fält <fält>` |

Kontrollen av att artikelnumret finns görs av affärssystemet, som svarar `422` med orsaken `Okänt artikelnummer: <SKU>`.

## 5. Exempel

**In: förenklad webhook från Shopify**

```json
{
  "id": 5123456789012,
  "name": "#1001",
  "created_at": "2026-11-25T13:03:00Z",
  "currency": "SEK",
  "email": "anna@example.com",
  "customer": { "id": 7012345678901, "email": "anna@example.com", "first_name": "Anna" },
  "total_discounts": "0.00",
  "total_price": "745.00",
  "shipping_lines": [ { "price": "49.00" } ],
  "line_items": [
    { "sku": "SB-TSH-001", "title": "Basic t-shirt vit", "quantity": 2, "price": "199.00" },
    { "sku": "SB-ACC-001", "title": "Mössa svart",       "quantity": 1, "price": "149.00" },
    { "sku": "SB-ACC-001", "title": "Mössa svart",       "quantity": 1, "price": "149.00" }
  ],
  "shipping_address": { "address1": "Storgatan 1", "city": "Borås" }
}
```

**Ut: anrop till `POST /orders` i affärssystemet**

```json
{
  "external_order_id": "5123456789012",
  "external_order_no": "#1001",
  "order_date": "2026-11-25T14:03:00+01:00",
  "currency": "SEK",
  "customer_ref": "SHOP-7012345678901",
  "shipping_amount": "49.00",
  "discount_amount": "0.00",
  "total_amount": "745.00",
  "rows": [
    { "article_no": "SB-TSH-001", "description": "Basic t-shirt vit", "qty": 2, "unit_price": "199.00" },
    { "article_no": "SB-ACC-001", "description": "Mössa svart",       "qty": 1, "unit_price": "149.00" },
    { "article_no": "SB-ACC-001", "description": "Mössa svart",       "qty": 1, "unit_price": "149.00" }
  ]
}
```

Notera i exemplet:

- `created_at` i UTC (`13:03Z`) blir `14:03` svensk vintertid.
- E-post, förnamn och adress finns inte med i utdata.
- Samma artikel kan förekomma på flera rader. Raderna slås inte ihop, utan förs över som de är.
- Beloppen skickas som text med två decimaler för att undvika avrundningsfel.
