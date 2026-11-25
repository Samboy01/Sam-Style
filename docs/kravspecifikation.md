# Kravspecifikation – Orderintegration webshop–affärssystem

| | |
|---|---|
| **Version** | 0.1 (utkast) |
| **Datum** | 2026-11-25 |
| **Författare** | Sam Airey |
| **Status** | Under arbete |

## 1. Bakgrund

Sam Bolaget är ett fiktivt klädföretag som säljer kläder via en webshop (Shopify). Lager och ekonomi hanteras i ett separat affärssystem (ERP). Systemen är inte kopplade till varandra.

När en kund lägger en order i webshoppen dyker den inte upp i affärssystemet av sig själv. Idag måste någon på kontoret eller lagret öppna webshoppens admin, läsa ordern och skriva in den för hand i affärssystemet. Det leder till:

- **Förseningar:** ordrar plockas först när någon hunnit föra över dem.
- **Fel:** felskrivna artikelnummer eller antal ger fel leverans och fel lagersaldo.
- **Översäljning:** lagersaldot i webshoppen uppdateras inte när lagret ändras, så kunder kan köpa varor som är slut.

## 2. Syfte och mål

Integrationen ska automatiskt föra över ordrar från webshoppen till affärssystemet och skicka lagersaldon tillbaka, så att:

1. ingen manuell överföring av ordrar behövs,
2. lagersaldot i webshoppen stämmer med affärssystemet,
3. fel upptäcks och kan åtgärdas utan att data försvinner eller dubbleras.

## 3. Omfattning

**Ingår (MVP):**

- Nya betalda ordrar i webshoppen skapas automatiskt som ordrar i affärssystemet.
- Lagersaldon i affärssystemet synkas tillbaka till webshoppen.
- Misslyckade överföringar sparas, försöks igen och syns i en översikt.

**Ingår inte (MVP):**

- Ändrade eller makulerade ordrar efter att de skapats
- Returer och återbetalningar
- Synk av produkter, priser eller kunder
- Flera lager (webshoppen har ett lager)
- Andra valutor än SEK

## 4. Aktörer och system

| Aktör / system | Roll |
|---|---|
| **Kund** | Lägger order i webshoppen. Påverkas av integrationen indirekt (rätt saldo, snabbare leverans). |
| **Lagerpersonal** | Plockar och packar ordrar från affärssystemet. Behöver veta vad som händer om en order inte kommer fram. |
| **Ekonomi** | Använder ordrarna i affärssystemet för fakturering och bokföring. |
| **Förvaltare / IT** | Övervakar integrationen, åtgärdar fel och kör om misslyckade överföringar. |
| **Webshop (Shopify)** | Källsystem för ordrar, målsystem för lagersaldo. |
| **Affärssystem (mini-ERP)** | Målsystem för ordrar, källsystem för lagersaldo. |
| **Integrationstjänst** | Tar emot, översätter och för över data mellan systemen. |

## 5. Funktionella krav

| ID | Krav | Prioritet |
|---|---|---|
| **FK1** | En betald order i webshoppen ska finnas i affärssystemet inom 5 minuter. | Måste |
| **FK2** | Lagersaldo i webshoppen ska uppdateras från affärssystemet minst var 15:e minut. | Måste |
| **FK3** | En order som inte kan föras över ska sparas med orsak och visas i en översikt. | Måste |
| **FK4** | Förvaltaren ska kunna köra om en misslyckad överföring när felet är åtgärdat. | Måste |
| **FK5** | En order med ett artikelnummer (SKU) som inte finns i affärssystemet ska inte försökas igen automatiskt, utan direkt markeras som fel med tydlig orsak. | Måste |
| **FK6** | Förvaltaren ska få ett larm när det finns misslyckade överföringar. | Bör |
| **FK7** | Det ska gå att se status för varje order i integrationen: mottagen, skickad, klar eller fel. | Bör |
| **FK8** | En artikel som finns i affärssystemet men saknas i webshoppen ska loggas som varning utan att stoppa lagersynken. | Bör |

## 6. Icke-funktionella krav

| ID | Krav | Kategori |
|---|---|---|
| **IFK1** | Ingen order får försvinna om affärssystemet är nere eller svarar långsamt. | Tillgänglighet |
| **IFK2** | Samma order får aldrig skapas två gånger i affärssystemet, även om webshoppen skickar den flera gånger. | Riktighet |
| **IFK3** | Loggar får inte innehålla kunders personuppgifter (e-post, namn, adress) i klartext. | Konfidentialitet / GDPR |
| **IFK4** | Integrationen ska bara ta emot ordrar som bevisligen kommer från webshoppen (verifierad signatur). | Säkerhet |
| **IFK5** | Lösenord, API-nycklar och andra hemligheter får inte finnas i koden eller i repot. | Säkerhet |
| **IFK6** | Bara de personuppgifter som affärssystemet behöver får föras över (dataminimering). | GDPR |
| **IFK7** | Integrationens egna data och loggar ska rensas automatiskt efter 30 dagar. | GDPR |
| **IFK8** | Varje order ska gå att följa genom hela flödet i loggarna med ett gemensamt ID (korrelations-ID). | Förvaltningsbarhet |
| **IFK9** | Hela lösningen ska gå att starta lokalt med ett kommando (`docker compose up`). | Förvaltningsbarhet |

## 7. Antaganden

- Endast **betalda** ordrar förs över. Obetalda eller avbrutna ordrar ignoreras.
- **Artikelnumret (SKU)** är samma i webshoppen och affärssystemet och används för att matcha artiklar.
- **Affärssystemet** är källan till sanningen för lagersaldo. Webshoppens saldo skrivs över vid synk.
- Alla belopp är i **SEK** inklusive moms.

## 8. Öppna frågor

- Hur länge kan affärssystemet vara nere innan verksamheten måste börja föra över ordrar manuellt igen?
- Vem i verksamheten tar emot larm utanför kontorstid?
- Behövs kundens adress i affärssystemet för leverans, eller räcker ett kundnummer?

## 9. Spårbarhet

Varje krav ska ha minst ett testfall i [testplan.md](testplan.md) som hänvisar till kravets ID.
