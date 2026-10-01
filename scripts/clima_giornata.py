#!/usr/bin/env python3
"""
ClimaAperto - clima_giornata.py

La giornata di ieri confrontata con il normale 1991-2020, citta' per citta'.

Per un giorno (UTC) scarica il passo 0 delle analisi ECMWF delle 00, 06, 12 e 18 UTC,
calcola la temperatura media giornaliera nel punto di griglia di ogni citta' (media dei
4 valori) e la confronta con il normale calcolato allo stesso modo da ERA5.

Legge:   clima/citta.json, clima/normali/<slug>.json
Scrive:  data/clima/ultimo.json             (solo se la giornata e' completa)
         data/clima/giorni/AAAA-MM-GG.json   (sempre)
GRIB temporanei in tmp_ecmwf/ (esclusa dal repository).

Uso:  python scripts/clima_giornata.py [--data AAAA-MM-GG] [--oggi]

Regole di prudenza, decise dopo i collaudi (vedi README):
  - media di 4 orari, mai il singolo orario; gradi arrotondati all'intero;
  - sotto 2 gradi di scostamento: "nella norma";
  - collocazione storica con i percentili della finestra ±7 giorni (1991-2020);
  - se manca un orario: nessuna frase, solo "dato incompleto";
  - si scrive "area di <citta>": il valore e' la media di una cella di ~28 km.
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FILE_CITTA = RADICE / "clima" / "citta.json"
CARTELLA_NORMALI = RADICE / "clima" / "normali"
CARTELLA_USCITA = RADICE / "data" / "clima"
CARTELLA_GRIB = RADICE / "tmp_ecmwf"

ORE = (0, 6, 12, 18)
SORGENTI = ["aws", "google", "azure", "ecmwf"]
if os.environ.get("SORGENTE_ECMWF") in SORGENTI:
    SORGENTI.remove(os.environ["SORGENTE_ECMWF"])
    SORGENTI.insert(0, os.environ["SORGENTE_ECMWF"])
TENTATIVI, ATTESA, PAUSA = 2, 30, 3
SOGLIA_NORMA = 2.0

ATTRIBUZIONE = ("Dati: ClimaAperto di Emanuel Ciuro (https://emanuelc89.github.io/climaaperto/), "
                "elaborazione di analisi ECMWF Open Data e di dati ERA5 Copernicus C3S (CC BY 4.0)")
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def carica_citta():
    with open(FILE_CITTA, encoding="utf-8") as f:
        return json.load(f)["citta"]


# ----------------------------------------------------------------- download e lettura

def scarica_orario(giorno, ora):
    from ecmwf.opendata import Client

    CARTELLA_GRIB.mkdir(exist_ok=True)
    target = CARTELLA_GRIB / f"{giorno:%Y%m%d}_{ora:02d}.grib2"
    if target.exists():
        return target
    for sorgente in SORGENTI:
        try:
            Client(source=sorgente, maximum_retries=TENTATIVI, retry_after=ATTESA,
                   use_server_retry_after=False).retrieve(
                date=giorno.strftime("%Y%m%d"), time=ora, type="fc", stream="oper",
                step=0, param="2t", target=str(target))
            time.sleep(PAUSA)
            return target
        except Exception as errore:  # noqa: BLE001
            print(f"  {giorno} {ora:02d} UTC da {sorgente}: non disponibile ({str(errore)[:80]})")
            if target.exists():
                target.unlink()
    return None


def leggi_valori(percorso, citta):
    import eccodes

    with open(percorso, "rb") as f:
        gid = eccodes.codes_grib_new_from_file(f)
        if gid is None:
            raise ValueError(f"file GRIB vuoto: {percorso}")
        try:
            risultato = {}
            for slug, info in citta.items():
                vicino = eccodes.codes_grib_find_nearest(gid, info["lat"], info["lon"])[0]
                risultato[slug] = (vicino.value - 273.15, vicino.lat, vicino.lon)
            return risultato
        finally:
            eccodes.codes_release(gid)


# ----------------------------------------------------------------- frasi

def collocazione(media, d):
    if media > d["max"]:
        return "un valore oltre ogni giornata di questo periodo nei 30 anni di riferimento"
    if media >= d["p95"]:
        return "tra il 5% dei giorni più caldi di questo periodo negli ultimi 30 anni"
    if media >= d["p90"]:
        return "tra il 10% dei giorni più caldi di questo periodo negli ultimi 30 anni"
    if media < d["min"]:
        return "un valore sotto ogni giornata di questo periodo nei 30 anni di riferimento"
    if media <= d["p05"]:
        return "tra il 5% dei giorni più freddi di questo periodo negli ultimi 30 anni"
    if media <= d["p10"]:
        return "tra il 10% dei giorni più freddi di questo periodo negli ultimi 30 anni"
    return None


def classe(anomalia, media, d):
    if media > d["max"] or media < d["min"]:
        return "eccezionale"
    if abs(anomalia) < SOGLIA_NORMA:
        return "nella_norma"
    if round(anomalia) >= 5:
        return "molto_caldo"
    if round(anomalia) <= -5:
        return "molto_freddo"
    return "caldo" if anomalia > 0 else "freddo"


def frase(info, giorno, media, normale, d):
    anomalia = media - normale
    gradi = round(abs(anomalia))
    quando = f"Il {giorno.day} {MESI[giorno.month - 1]}"
    dove = f"nell'area di {info['nome']}"
    testo_media = (f"la temperatura media è stata di {round(media)} °C, "
                   if info.get("mostra_assoluto", True) else "la temperatura è stata ")
    if abs(anomalia) < SOGLIA_NORMA:
        base = f"{quando} {dove} {testo_media}nella norma per questo periodo dell'anno."
    else:
        verso = "sopra" if anomalia > 0 else "sotto"
        base = (f"{quando} {dove} {testo_media}circa {gradi} grad{'o' if gradi == 1 else 'i'} "
                f"{verso} il normale per questo periodo dell'anno (riferimento 1991-2020).")
    coll = collocazione(media, d)
    if coll:
        base += f" È {coll}."
    return base


# ----------------------------------------------------------------- elaborazione

def elabora(giorno):
    citta = carica_citta()
    orari = {}
    for ora in ORE:
        percorso = scarica_orario(giorno, ora)
        if percorso:
            try:
                orari[ora] = leggi_valori(percorso, citta)
            except Exception as errore:  # noqa: BLE001
                print(f"  Lettura fallita per le {ora:02d} UTC: {errore}")
    completo = len(orari) == len(ORE)

    risultati = []
    for slug, info in citta.items():
        with open(CARTELLA_NORMALI / f"{slug}.json", encoding="utf-8") as f:
            d = json.load(f)["giorni"][giorno.strftime("%m-%d")]
        voce = {
            "slug": slug, "nome": info["nome"],
            "punto_griglia": {"lat": info["lat"], "lon": info["lon"]},
            "orari_disponibili": sorted(orari),
            "valori_orari": {f"{ora:02d}": round(orari[ora][slug][0], 2) for ora in orari},
            "normale": d["normale"], "media_giornaliera": None, "anomalia": None,
            "classe": None, "frase": None,
        }
        if completo:
            media = sum(orari[ora][slug][0] for ora in ORE) / len(ORE)
            voce["media_giornaliera"] = round(media, 2)
            voce["anomalia"] = round(media - d["normale"], 2)
            voce["classe"] = classe(media - d["normale"], media, d)
            voce["frase"] = frase(info, giorno, media, d["normale"], d)
        else:
            voce["classe"] = "dato_incompleto"
            voce["frase"] = (f"Dato incompleto per il {giorno.day} {MESI[giorno.month - 1]}: "
                             f"disponibili {len(orari)} orari su {len(ORE)}.")
        risultati.append(voce)

    uscita = {
        "giorno": giorno.isoformat(),
        "generato_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "completo": completo,
        "metodo": "media delle analisi ECMWF (IFS, passo 0) delle ore 00/06/12/18 UTC, "
                  "confrontata con il normale 1991-2020 da ERA5 calcolato allo stesso modo",
        "fonte_presente": "ECMWF Open Data, analisi IFS, licenza CC BY 4.0",
        "fonte_normale": "ERA5, Copernicus Climate Change Service (C3S), licenza CC BY 4.0",
        "licenza": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
        "attribuzione_obbligatoria": ATTRIBUZIONE,
        "citta": risultati,
    }
    (CARTELLA_USCITA / "giorni").mkdir(parents=True, exist_ok=True)
    with open(CARTELLA_USCITA / "giorni" / f"{giorno.isoformat()}.json", "w", encoding="utf-8") as f:
        json.dump(uscita, f, ensure_ascii=False, indent=1)
    if completo:
        with open(CARTELLA_USCITA / "ultimo.json", "w", encoding="utf-8") as f:
            json.dump(uscita, f, ensure_ascii=False, indent=1)
    return uscita


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="giorno UTC da elaborare, AAAA-MM-GG (default: ieri)")
    parser.add_argument("--oggi", action="store_true", help="elabora oggi invece di ieri")
    args = parser.parse_args()
    oggi_utc = datetime.now(timezone.utc).date()
    giorno = date.fromisoformat(args.data) if args.data else (oggi_utc if args.oggi else oggi_utc - timedelta(days=1))

    print(f"Giornata del {giorno} (UTC)")
    uscita = elabora(giorno)
    print()
    for v in uscita["citta"]:
        if uscita["completo"]:
            print(f"{v['nome']}: media {v['media_giornaliera']:.1f} °C, normale {v['normale']:.1f}, "
                  f"anomalia {v['anomalia']:+.1f}  [{v['classe']}]")
        print(f"  {v['frase']}")
    if not uscita["completo"]:
        print("\nGiornata incompleta: data/clima/ultimo.json NON aggiornato.", file=sys.stderr)


if __name__ == "__main__":
    main()
