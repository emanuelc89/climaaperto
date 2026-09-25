#!/usr/bin/env python3
"""
ClimaAperto — fetch_incendi.py

Scarica gli incendi attivi rilevati da satellite (NASA FIRMS) per un'area
geografica e li normalizza in un JSON pulito, pensato per essere
consumato da altri programmi — non solo mostrato su una pagina web.

Fonte dati: NASA FIRMS (Fire Information for Resource Management System)
https://firms.modaps.eosdis.nasa.gov/api/

Richiede una MAP_KEY gratuita, ottenibile qui:
https://firms.modaps.eosdis.nasa.gov/api/map_key/

NOTA: questo script è scritto seguendo la documentazione ufficiale
dell'API, ma non è mai stato eseguito con una chiave reale (l'ambiente
in cui è stato scritto non ha accesso alla rete verso firms.modaps.eosdis.nasa.gov).
Al primo utilizzo controlla l'output di scarica_incendi() e, se necessario,
aggiusta i nomi delle colonne lette dal CSV in base alla risposta reale.
"""

import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

import requests

# --- Configurazione -----------------------------------------------------

# MAP_KEY gratuita di NASA FIRMS, letta da variabile d'ambiente.
MAP_KEY = os.environ.get("NASA_FIRMS_MAP_KEY")

# Sensore satellitare da interrogare. VIIRS_SNPP_NRT offre una buona
# risoluzione spaziale (375m) e aggiornamento quasi in tempo reale.
# Elenco completo dei sensori disponibili nella documentazione ufficiale:
# https://firms.modaps.eosdis.nasa.gov/api/area/
SENSORE = os.environ.get("SENSORE_FIRMS", "VIIRS_SNPP_NRT")

# Area geografica come "lon_min,lat_min,lon_max,lat_max".
# Di default: rettangolo che contiene l'Europa (dall'Islanda al Caucaso,
# da Creta alla Scandinavia). Essendo un rettangolo, include anche la costa
# del Nord Africa e parte della Turchia.
# Sovrascrivibile con la variabile d'ambiente AREA_BBOX per estendere
# ad altri paesi o a tutta Europa.
AREA_BBOX = os.environ.get("AREA_BBOX", "-25,34,45,72")

# Quanti giorni indietro interrogare (il piano gratuito standard
# copre tipicamente 1-10 giorni per richiesta).
GIORNI = int(os.environ.get("GIORNI", "1"))

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

OUTPUT_PATH = os.path.join("data", "incendi.json")


def scarica_incendi():
    """Interroga l'API NASA FIRMS e restituisce una lista di rilevamenti normalizzati."""
    if not MAP_KEY:
        print(
            "Errore: variabile d'ambiente NASA_FIRMS_MAP_KEY mancante. "
            "Registrati gratuitamente su "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key/",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"{URL_BASE}/{MAP_KEY}/{SENSORE}/{AREA_BBOX}/{GIORNI}"
    risposta = requests.get(url, timeout=30)
    risposta.raise_for_status()

    testo = risposta.text.strip()
    if not testo or testo.lower().startswith("invalid"):
        print(f"Risposta inattesa dall'API FIRMS: {testo[:200]}", file=sys.stderr)
        return []

    lettore = csv.DictReader(io.StringIO(testo))
    incendi = []
    for riga in lettore:
        try:
            incendi.append({
                "latitudine": float(riga["latitude"]),
                "longitudine": float(riga["longitude"]),
                "data_rilevamento": riga.get("acq_date"),
                "ora_rilevamento_utc": riga.get("acq_time"),
                "confidenza": riga.get("confidence"),
                "intensita_radiativa_mw": _float_o_none(riga.get("frp")),
                "satellite": riga.get("satellite"),
            })
        except (KeyError, ValueError):
            # Riga malformata o con colonne inattese: la saltiamo invece
            # di far fallire l'intero aggiornamento.
            continue

    return incendi


def _float_o_none(valore):
    try:
        return float(valore)
    except (TypeError, ValueError):
        return None


def salva_json(incendi):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    output = {
        "fonte": f"NASA FIRMS ({SENSORE})",
        "fonte_url": "https://firms.modaps.eosdis.nasa.gov/",
        "area_bbox": AREA_BBOX,
        "aggiornato_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "numero_rilevamenti": len(incendi),
        "incendi": incendi,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        # JSON compatto (senza spazi): con l'area europea i rilevamenti sono molti,
        # e ogni versione del file resta nella cronologia di Git.
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Salvati {len(incendi)} rilevamenti in {OUTPUT_PATH}")


if __name__ == "__main__":
    dati = scarica_incendi()
    salva_json(dati)
