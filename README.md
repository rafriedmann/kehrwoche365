# Kehrwoche365 – Teams Recordings Cleanup

Automatisiertes Aufräumen von Microsoft Teams Aufzeichnungen aus SharePoint.

## Warum?

Microsoft 365 Lizenzen wie **Business Basic / Standard** bieten keine Retention Labels oder Auto-Labeling-Policies. Teams-Aufzeichnungen sammeln sich dadurch unbegrenzt auf SharePoint an und fressen Speicherplatz. Kehrwoche365 ist ein Workaround: Ein Container, der regelmäßig alte Aufzeichnungen findet und löscht – inklusive Papierkorb.

## Was macht er?

- Durchsucht alle SharePoint-Sites nach `.mp4`-Dateien im `Recordings`-Ordner
- Löscht Aufzeichnungen, die älter als die konfigurierte Aufbewahrungsfrist sind (Standard: 8 Tage)
- Optional: Leert den 1st Stage Papierkorb (permanent delete, überspringt 2nd Stage)
- Optional: Leert den 2nd Stage Papierkorb von `.mp4`-Dateien (benötigt Zertifikat-Auth)
- Läuft per Cron-Schedule als Docker-Container (Standard: täglich um 2 Uhr)
- Dry-Run-Modus zum gefahrlosen Testen

## Voraussetzungen

- Docker & Docker Compose
- Azure AD App Registration mit folgenden **Application Permissions** (Microsoft Graph):
  - `Sites.ReadWrite.All`
  - `Sites.FullControl.All`

### Zertifikat-Auth (optional, für 2nd Stage Papierkorb)

Die SharePoint REST API akzeptiert keine Client-Secret-Tokens. Für den Zugriff auf den 2nd Stage Papierkorb wird ein Zertifikat benötigt:

1. Zertifikat erstellen:

   ```bash
   openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=kehrwoche365"
   ```

2. SHA1-Thumbprint auslesen:

   ```bash
   openssl x509 -in certs/cert.pem -noout -fingerprint -sha1 | sed 's/://g' | cut -d= -f2
   ```

3. `certs/cert.pem` in Azure AD hochladen (App Registration > Certificates & secrets)

4. `CERT_KEY_PATH` und `CERT_THUMBPRINT` in `.env` setzen

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
| `PURGE_FIRST_STAGE` | 1st Stage Papierkorb leeren | `false` |
| `CERT_KEY_PATH` | Pfad zum privaten Schlüssel (PEM) | *leer* |
| `CERT_THUMBPRINT` | SHA1-Thumbprint des Zertifikats | *leer* |
| `LOG_LEVEL` | Log-Level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

> **Wichtig:** `DRY_RUN` ist standardmäßig `true`. Erst auf `false` setzen, wenn die Ergebnisse im Log korrekt aussehen.
