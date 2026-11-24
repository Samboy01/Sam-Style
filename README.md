# Orderintegration webshop–affärssystem

Integration som automatiskt för över ordrar från en webshop (Shopify) till ett affärssystem och synkar lagersaldon tillbaka, för det fiktiva klädföretaget Sam Bolaget.

> 🚧 Projektet är under uppbyggnad.

## Problemet

Idag förs ordrar över för hand från webshoppen till affärssystemet. Det ger fel och förseningar. Integrationen gör överföringen automatiskt och ser till att ingen order försvinner eller skapas två gånger.

## Mappstruktur

| Mapp | Innehåll |
|------|----------|
| `docs/` | Kravspecifikation, integrationsspecifikation, mappning, testplan, runbook, ADR |
| `integration/` | Integrationstjänsten: webhook, kö-worker, lagersynk |
| `mini-erp/` | Ett enkelt affärssystem (REST-API + databas) att integrera mot |
| `tests/` | Enhets- och integrationstester |

## Kom igång

Kommer snart.
