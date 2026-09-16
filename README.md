# ClimaAperto

Un'API pubblica e documentata che raccoglie dati ufficiali su rischi climatici da fonti europee e internazionali, pensata per essere **usata da altri programmi** (sviluppatori, giornalisti, ONG) — non solo guardata su un sito.

> Nome di lavoro, cambialo pure: sostituisci "ClimaAperto" ovunque compaia nel repository con il nome che scegli.

## Perché esiste

Oggi i dati ufficiali su incendi, siccità e altri rischi climatici europei esistono, sono pubblici, ma sono sparsi su portali diversi, in formati diversi (CSV, WMS, NetCDF), spesso pensati per un ricercatore, non per uno sviluppatore che vuole interrogare un endpoint e ricevere JSON pulito. Questo progetto prova a fare da collante: un unico punto di accesso, aggiornato automaticamente, gratuito, con provenienza dei dati sempre dichiarata.

**Nota di trasparenza:** prima di iniziare ho verificato che esistono già progetti simili che aggregano dati meteo/incendi/qualità dell'aria in un'unica API (es. combinazioni di Open-Meteo, WAQI e NASA FIRMS). Questo progetto non pretende di essere il primo in assoluto: la differenza che vale la pena costruire è concentrarsi solo su fonti **ufficiali europee**, restare gratuito e ben documentato, e coprire nel tempo un dato — la siccità EDO — che oggi nessun servizio offre gratis in formato API pulito.

## Fonti dati

| Versione | Fonte | Cosa fornisce | Stato |
|---|---|---|---|
| v1 (questo scaffold) | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/) | Incendi attivi rilevati da satellite (quasi in tempo reale) | Implementato |
| v2 (roadmap) | [EFFIS](https://forest-fire.emergency.copernicus.eu/) (Copernicus) | Dato ufficiale UE su incendi boschivi e rischio | Da fare |
| v3 (roadmap) | [EDO](https://drought.emergency.copernicus.eu/) (Copernicus) | Indicatore di siccità ufficiale UE | Da fare |

Ogni fonte resta sempre dichiarata nel JSON prodotto (campo `fonte`), così chi consuma l'API sa sempre da dove viene ogni dato.

## Come funziona

Stessa architettura di [Allerta Meteo Toscana](https://github.com/emanuelc89/allerta-meteo-toscana): uno script Python, schedulato con GitHub Actions, scarica i dati dalla fonte ufficiale, li normalizza in un JSON pulito, e li salva nel repository come file statico versionato. Con GitHub Pages attivo, quel file diventa un URL stabile che chiunque può interrogare via HTTP — è la tua "API", senza bisogno di un server sempre acceso.

```
scripts/fetch_incendi.py  →  data/incendi.json  →  pubblicato via GitHub Pages
```

## Endpoint (una volta pubblicato)

```
https://<tuo-utente>.github.io/<nome-repo>/data/incendi.json
```

## Setup

1. Registrati gratuitamente su NASA FIRMS per ottenere una MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. Nel repository GitHub: Settings → Secrets and variables → Actions → New repository secret, nome `NASA_FIRMS_MAP_KEY`, valore la chiave ricevuta via email.
3. Attiva GitHub Pages (root o `/docs`, come preferisci).
4. Prima esecuzione manuale: Actions → "Aggiorna incendi" → Run workflow.

**Prova locale prima di tutto**, prima di fidarti del workflow: esegui `python scripts/fetch_incendi.py` con `NASA_FIRMS_MAP_KEY` impostata come variabile d'ambiente, e controlla `data/incendi.json`. Lo script è scritto seguendo la documentazione ufficiale dell'API ma non è mai stato eseguito con una chiave reale — è probabile che i nomi di qualche colonna del CSV richiedano un piccolo aggiustamento al primo giro.

## Licenza

Il codice è distribuito secondo i termini della **PolyForm Strict License 1.0.0** (testo completo in `LICENSE`): chiunque può leggerlo e usarlo per scopi non commerciali, ma non può ridistribuirlo né modificarlo/crearne derivati. Non è una licenza open source in senso tecnico (l'OSI non la classifica come tale) — è codice sorgente pubblico a scopo di trasparenza, portfolio e riuso non commerciale.

**Importante — codice vs. dati:** questa licenza copre il *codice*. Chi si limita a interrogare l'endpoint pubblico via HTTP sta usando un dato, non il software, e non è vincolato da questa licenza. Se vuoi che chiunque (comprese aziende) possa liberamente riusare i *dati* esposti da `data/incendi.json`, valuta di dichiarare esplicitamente qui una licenza dati separata (es. Creative Commons CC-BY 4.0) — codice e dati sono due cose diverse, con licenze indipendenti.

## Roadmap

- [x] v1: incendi attivi (NASA FIRMS) — bounding box Italia, aggiornamento automatico ogni 3 ore, JSON pubblico + pagina di visualizzazione
- [x] v2: rischio incendi ufficiale (EFFIS) — mostrato come livello mappa in tempo reale (WMS), non come dato nel JSON: il layer `mf010.fwi` di EFFIS non è configurato come interrogabile puntualmente sul loro server (`QUERY_LAYERS` restituisce `LayerNotDefined`), quindi non è possibile estrarne un valore numerico via GetFeatureInfo. Verificato anche il servizio WFS: non risulta attivo su questo endpoint.
- [ ] v3: indicatore di siccità (EDO)
- [ ] Pagina di documentazione stile "API docs" per sviluppatori terzi
