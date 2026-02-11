# Kehrwoche365 – Teams Recordings Cleanup

Automatisiertes Aufräumen von Microsoft Teams Aufzeichnungen aus SharePoint.

## Warum?

Microsoft 365 Lizenzen wie **Business Basic / Standard** bieten keine Retention Labels oder Auto-Labeling-Policies. Teams-Aufzeichnungen sammeln sich dadurch unbegrenzt auf SharePoint an und fressen Speicherplatz. Kehrwoche365 ist ein Workaround: Ein Container, der regelmäßig alte Aufzeichnungen findet und löscht – inklusive Papierkorb.

## Was macht er?

- Durchsucht alle SharePoint-Sites im Tenant nach `.mp4`-Dateien (Teams-Aufzeichnungen)
- Löscht Aufzeichnungen, die älter als die konfigurierte Aufbewahrungsfrist sind (Standard: 8 Tage)
- Leert den SharePoint-Papierkorb von `.mp4`-Dateien, die älter als die Aufbewahrungsfrist sind
- Läuft per Cron-Schedule als Docker-Container (Standard: täglich um 2 Uhr)
- Dry-Run-Modus zum gefahrlosen Testen

## Voraussetzungen

- Docker & Docker Compose
- Azure AD App Registration mit folgenden **Application Permissions** (Microsoft Graph):
  - `Sites.ReadWrite.All`
  - `Sites.FullControl.All`

## Quickstart

1. `.env.example` nach `.env` kopieren und ausfüllen:

   ```bash
   cp .env.example .env
   ```

2. Container starten:

   ```bash
   docker compose up -d
   ```

3. Logs prüfen:

   ```bash
   docker compose logs -f
   ```

## Konfiguration

| Variable | Beschreibung | Standard |
|---|---|---|
| `AZURE_TENANT_ID` | Azure AD Tenant-ID | *erforderlich* |
| `AZURE_CLIENT_ID` | App Registration Client-ID | *erforderlich* |
| `AZURE_CLIENT_SECRET` | App Registration Secret | *erforderlich* |
| `SHAREPOINT_DOMAIN` | SharePoint-Domain | `yourcompany.sharepoint.com` |
| `RETENTION_DAYS` | Aufbewahrungsfrist in Tagen | `8` |
| `CRON_SCHEDULE` | Cron-Ausdruck für Zeitplan | `0 2 * * *` |
| `DRY_RUN` | Testmodus ohne Löschung | `true` |
| `LOG_LEVEL` | Log-Level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

> **Wichtig:** `DRY_RUN` ist standardmäßig `true`. Erst auf `false` setzen, wenn die Ergebnisse im Log korrekt aussehen.
