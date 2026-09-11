#!/usr/bin/env python3

import argparse
import bisect
import json
import os
import re
import sys
import subprocess
import time
import urllib.request
from pathlib import Path


ORD_URL = "http://127.0.0.1:8080"

# ANSI colors for the compact result display
RED = "\033[31m"
GREEN = "\033[32m"
ORANGE = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

def colorize(text, color):
    """Color terminal output."""
    return f"{color}{text}{RESET}"


CACHE_FILE = Path("/home/bte/.local/share/ord/historical_satributes.json")


# Historical Satributes from the known Sating ranges.
HISTORICAL_CATEGORIES = [
    "FIRST_TX",
    "BLOCK_9",
    "BLOCK_78",
    "VINTAGE",
    "NAKAMOTO",
    "PIZZA",
    "HITMAN",
]

NUMERIC_CATEGORIES = [
    "PALINDROME",
    "ALPHA",
    "OMEGA",
]

# Fixed historical Satributes from the known Sating definitions.
BLOCK_SUBSIDY_50_BTC = 5_000_000_000

FIRST_TX_RANGES = [
    (45_000_000_000, 46_000_000_000),
]

NAKAMOTO_BLOCKS = [
    9,
    286,
    688,
    877,
    1760,
    2459,
    2485,
    3479,
    5326,
    9443,
    9925,
    10645,
    14450,
    15625,
    15817,
    19093,
    23014,
    28593,
    29097,
]

STATIC_RANGES = {
    "FIRST_TX": FIRST_TX_RANGES,
    "BLOCK_9": [
        (
            9 * BLOCK_SUBSIDY_50_BTC,
            10 * BLOCK_SUBSIDY_50_BTC,
        ),
    ],
    "BLOCK_78": [
        (
            78 * BLOCK_SUBSIDY_50_BTC,
            79 * BLOCK_SUBSIDY_50_BTC,
        ),
    ],
    "VINTAGE": [
        (
            0,
            1000 * BLOCK_SUBSIDY_50_BTC,
        ),
    ],
    "NAKAMOTO": [
        (
            block * BLOCK_SUBSIDY_50_BTC,
            (block + 1) * BLOCK_SUBSIDY_50_BTC,
        )
        for block in NAKAMOTO_BLOCKS
    ],
}


def format_sat(value):
    return f"{value:,}".replace(",", "'")


class ProgressBar:
    def __init__(self, label, total, width=32):
        self.label = label
        self.total = max(total, 1)
        self.width = width
        self.last_length = 0
        self.enabled = sys.stdout.isatty()

    def update(self, current):
        current = min(max(current, 0), self.total)
        ratio = current / self.total
        filled = int(self.width * ratio)
        bar = "█" * filled + "░" * (self.width - filled)
        line = (
            f"  {self.label:<10} [{bar}] "
            f"{ratio * 100:6.1f}% {current}/{self.total}"
        )

        if self.enabled:
            padding = max(self.last_length - len(line), 0)
            print("\r" + line + (" " * padding), end="", flush=True)
            self.last_length = len(line)
        else:
            if current == self.total:
                print(line)

    def finish(self):
        self.update(self.total)
        if self.enabled:
            print()


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_output(outpoint):
    url = f"{ORD_URL}/output/{outpoint}"
    return get_json(url)


def get_inscription(inscription_id):
    url = f"{ORD_URL}/inscription/{inscription_id}"
    return get_json(url)


def is_inscription_id(value):
    return bool(
        re.fullmatch(
            r"[0-9a-fA-F]{64}i\d+",
            value,
        )
    )


def is_inscription_number(value):
    return value.isdigit()


def is_bitcoin_address(value):
    return bool(
        re.fullmatch(
            r"(?:bc1[ac-hj-np-z02-9]{8,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})",
            value,
        )
    )


def resolve_inscription_number(number):
    """Resolve an inscription by its number through ord."""
    try:
        inscription = get_inscription(number)
    except Exception as exc:
        raise RuntimeError(
            f"Inscription-Nummer konnte nicht über ord abgerufen werden: {exc}"
        ) from exc

    satpoint = inscription.get("satpoint")
    if not isinstance(satpoint, str) or satpoint.count(":") != 2:
        raise RuntimeError(
            "ord hat für diese Inscription keinen gültigen Satpoint geliefert."
        )

    txid, vout, offset = satpoint.split(":")

    if not re.fullmatch(r"[0-9a-fA-F]{64}", txid):
        raise RuntimeError("Ungültige TXID im Satpoint der Inscription.")

    if not vout.isdigit():
        raise RuntimeError("Ungültiger VOUT im Satpoint der Inscription.")

    return {
        "id": inscription.get("id"),
        "outpoint": f"{txid}:{int(vout)}",
        "sat": inscription.get("sat"),
        "satpoint": satpoint,
        "address": inscription.get("address"),
        "value": inscription.get("value"),
    }


def resolve_inscription(inscription_id):
    try:
        inscription = get_inscription(inscription_id)
    except Exception as exc:
        raise RuntimeError(
            f"Inscription konnte nicht über ord abgerufen werden: {exc}"
        ) from exc

    satpoint = inscription.get("satpoint")

    if not isinstance(satpoint, str) or satpoint.count(":") != 2:
        raise RuntimeError(
            "ord hat für diese Inscription keinen gültigen Satpoint geliefert."
        )

    txid, vout, offset = satpoint.split(":")

    if not re.fullmatch(r"[0-9a-fA-F]{64}", txid):
        raise RuntimeError("Ungültige TXID im Satpoint der Inscription.")

    if not vout.isdigit():
        raise RuntimeError("Ungültiger VOUT im Satpoint der Inscription.")

    return {
        "outpoint": f"{txid}:{int(vout)}",
        "sat": inscription.get("sat"),
        "satpoint": satpoint,
        "address": inscription.get("address"),
        "value": inscription.get("value"),
    }


def find_address_utxos(address):
    request = json.dumps(
        [f"addr({address})"],
        separators=(",", ":"),
    )

    command = [
        "bitcoin-cli",
        "scantxoutset",
        "start",
        request,
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Bitcoin-Core UTXO-Abfrage fehlgeschlagen: {exc}"
        ) from exc

    print("SCAN DES BITCOIN-CORE UTXO-SETS")
    print("------------------------------------------------------------------------")
    print("Bitcoin Core durchsucht die komplette aktuelle UTXO-Datenbank.")
    print("Das kann mehrere Minuten dauern.")
    print()

    start_time = time.monotonic()
    last_progress = -1
    timeout_seconds = 1800

    while process.poll() is None:
        elapsed = time.monotonic() - start_time

        if elapsed > timeout_seconds:
            process.kill()
            process.wait()
            raise RuntimeError(
                "Der Bitcoin-Core UTXO-Scan hat das Zeitlimit von "
                f"{timeout_seconds // 60} Minuten überschritten."
            )

        try:
            status = subprocess.run(
                ["bitcoin-cli", "scantxoutset", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            status = None

        progress = None

        if status is not None and status.returncode == 0:
            try:
                status_data = json.loads(status.stdout)
                progress = status_data.get("progress")
            except json.JSONDecodeError:
                progress = None

        if isinstance(progress, (int, float)):
            progress = max(0.0, min(100.0, float(progress)))
            progress_int = int(progress)

            if progress_int != last_progress:
                width = 32
                filled = int(width * progress / 100.0)
                bar = "#" * filled + "." * (width - filled)
                elapsed_text = time.strftime(
                    "%H:%M:%S",
                    time.gmtime(elapsed),
                )
                print(
                    f"\r[{bar}] {progress:6.2f}% | Laufzeit {elapsed_text}",
                    end="",
                    flush=True,
                )
                last_progress = progress_int
        else:
            if last_progress == -1:
                print(
                    "\r[................................]   --.--% | "
                    "Bitcoin Core startet den UTXO-Scan ...",
                    end="",
                    flush=True,
                )

        time.sleep(0.5)

    stdout, stderr = process.communicate()

    if last_progress >= 0:
        print()
    else:
        print()

    if process.returncode != 0:
        message = stderr.strip() or stdout.strip()
        raise RuntimeError(
            f"bitcoin-cli scantxoutset fehlgeschlagen: {message}"
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Bitcoin Core hat keine gültige JSON-Antwort geliefert."
        ) from exc

    if not data.get("success"):
        raise RuntimeError(
            "Bitcoin Core konnte den UTXO-Scan nicht erfolgreich abschließen."
        )

    utxos = []

    for item in data.get("unspents", []):
        txid = item.get("txid")
        vout = item.get("vout")

        if not isinstance(txid, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}",
            txid,
        ):
            continue

        if not isinstance(vout, int) or vout < 0:
            continue

        utxos.append(
            {
                "outpoint": f"{txid}:{vout}",
                "amount": item.get("amount"),
                "height": item.get("height"),
            }
        )

    return utxos


def resolve_input(value):
    if is_inscription_id(value):
        resolved = resolve_inscription(value)
        print("INPUT-TYP: INSCRIPTION")
        print(f"INSCRIPTION: {value}")
        print(f"SAT: {format_sat(resolved['sat'])}" if isinstance(resolved["sat"], int) else "SAT: unbekannt")
        print(f"SATPOINT: {resolved['satpoint']}")
        print(f"OUTPOINT: {resolved['outpoint']}")
        if resolved.get("address"):
            print(f"ADDRESS: {resolved['address']}")
        print()
        return [resolved["outpoint"]]

    if is_inscription_number(value):
        resolved = resolve_inscription_number(value)
        if not resolved.get("id"):
            raise RuntimeError(
                f"Inscription-Nummer {value} konnte nicht aufgelöst werden."
            )

        print("INPUT-TYP: INSCRIPTION-NUMMER")
        print(f"NUMMER: {value}")
        print(f"INSCRIPTION: {resolved['id']}")
        print(
            f"SAT: {format_sat(resolved['sat'])}"
            if isinstance(resolved["sat"], int)
            else "SAT: unbekannt"
        )
        print(f"SATPOINT: {resolved['satpoint']}")
        print(f"OUTPOINT: {resolved['outpoint']}")
        if resolved.get("address"):
            print(f"ADDRESS: {resolved['address']}")
        print()
        return [resolved["outpoint"]]

    if is_bitcoin_address(value):
        print("INPUT-TYP: BITCOIN-ADRESSE")
        print(f"ADDRESS: {value}")
        print()
        print("BITCOIN-CORE UTXO-SUCHE")
        print("-" * 72)

        utxos = find_address_utxos(value)

        if not utxos:
            print("Keine aktuell unspent Outputs für diese Adresse gefunden.")
            return []

        print(colorize(f"GEFUNDENE UTXOS: {len(utxos)}", GREEN if utxos else RED))
        print()

        return [item["outpoint"] for item in utxos]

    if re.fullmatch(
        r"[0-9a-fA-F]{64}:\d+",
        value,
    ):
        return [value]

    raise ValueError(
        "Ungültige Eingabe. Erlaubt sind TXID:VOUT, eine Inscription-ID "
        "(...i0), eine Inscription-Nummer oder eine Bitcoin-Adresse."
    )


def get_sat_ranges(output):
    """
    Liefert die Sat-Ranges eines Outputs.

    During indexing, ord may:
      - return a list
      - return null
      - omit the field entirely

    null does not mean that the UTXO contains no Sats.
    It only means that ord does not currently provide the Sat ranges
    for this output.
    """

    ranges = output.get("sat_ranges")

    if ranges is None:
        return None

    if not isinstance(ranges, list):
        return None

    parsed = []

    for item in ranges:
        if not isinstance(item, list) or len(item) != 2:
            continue

        start, end = item

        if not isinstance(start, int) or not isinstance(end, int):
            continue

        if end <= start:
            continue

        parsed.append((start, end))

    return parsed


def load_cache():
    if not CACHE_FILE.exists():
        return None

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(data):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    temporary = CACHE_FILE.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)

    temporary.replace(CACHE_FILE)


def merge_ranges(ranges):
    """
    Vereinigt überlappende oder direkt angrenzende Bereiche.
    """

    if not ranges:
        return []

    sorted_ranges = sorted(ranges)
    merged = [list(sorted_ranges[0])]

    for start, end in sorted_ranges[1:]:
        previous = merged[-1]

        if start <= previous[1]:
            if end > previous[1]:
                previous[1] = end
        else:
            merged.append([start, end])

    return [(start, end) for start, end in merged]


def parse_range_string(value):
    """
    Unterstützt typische Schreibweisen:
      123-456
      [123,456)
      123,456
    """

    if isinstance(value, list) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    numbers = re.findall(r"\d+", value)

    if len(numbers) < 2:
        return None

    start = int(numbers[0])
    end = int(numbers[1])

    if end <= start:
        return None

    return start, end


def normalize_historical_data(data):
    """
    Vereinheitlicht statische historische Bereiche und den
    vorhandenen Sating.io-Cache.

    Der Cache verwendet die Keys "pizza" und "hitman".
    Die Scanner-Kategorien werden dagegen in Großschreibung geführt.
    """

    normalized = {}

    if not isinstance(data, dict):
        data = {}

    for category in HISTORICAL_CATEGORIES:
        ranges = list(STATIC_RANGES.get(category, []))

        if category == "PIZZA":
            values = data.get("PIZZA", data.get("pizza", []))
        elif category == "HITMAN":
            values = data.get("HITMAN", data.get("hitman", []))
        else:
            values = data.get(category, [])

        if isinstance(values, list):
            for value in values:
                parsed = parse_range_string(value)

                if parsed:
                    ranges.append(parsed)

        normalized[category] = merge_ranges(ranges)

    return normalized


def range_contains(ranges, sat):
    """
    Prüft, ob ein Sat in einem Bereich [start,end) liegt.
    """

    if not ranges:
        return False

    starts = [item[0] for item in ranges]
    index = bisect.bisect_right(starts, sat) - 1

    if index < 0:
        return False

    start, end = ranges[index]
    return start <= sat < end


def scan_historical(sat_ranges, historical):
    matches = {}

    for category, ranges in historical.items():
        found = []
        progress = ProgressBar(category, len(ranges))

        if not ranges:
            progress.finish()
            continue

        for index, (category_start, category_end) in enumerate(ranges, start=1):
            for start, end in sat_ranges:
                overlap_start = max(start, category_start)
                overlap_end = min(end, category_end)

                if overlap_start < overlap_end:
                    found.append((overlap_start, overlap_end))

            progress.update(index)

        progress.finish()

        if found:
            matches[category] = merge_ranges(found)

    return matches


def is_palindrome(value):
    text = str(value)
    return text == text[::-1]


def is_alpha(value):
    """
    Alpha:
    Eine Sat-Zahl, deren Ziffernfolge aus einer gültigen
    Alpha-Ordinals-Darstellung entsteht.

    Für den Scanner wird die numerische Alpha-Prüfung
    über die bekannte Ordinal-Systematik umgesetzt.
    """

    text = str(value)

    if len(text) < 2:
        return False

    return text[0] == "1" and text[1:] == text[1:][::-1]


def is_omega(value):
    """
    Omega:
    Letzter Sat eines Blocks.
    """

    return (value + 1) % 5_000_000_000 == 0


def scan_numeric(sat_ranges):
    matches = {
        "PALINDROME": [],
        "ALPHA": [],
        "OMEGA": [],
    }

    progress = ProgressBar("NUMERIC", len(sat_ranges))

    for index, (start, end) in enumerate(sat_ranges, start=1):
        for sat in find_palindromes_in_range(start, end):
            matches["PALINDROME"].append((sat, sat + 1))

        for sat in find_alpha_in_range(start, end):
            matches["ALPHA"].append((sat, sat + 1))

        first_omega = (
            ((start + 4_999_999_999) // 5_000_000_000)
            * 5_000_000_000
            - 1
        )

        if first_omega < start:
            first_omega += 5_000_000_000

        if first_omega < end:
            matches["OMEGA"].append((first_omega, first_omega + 1))

        progress.update(index)

    progress.finish()

    return {
        category: ranges
        for category, ranges in matches.items()
        if ranges
    }


def find_palindromes_in_range(start, end):
    """
    Findet Palindrome innerhalb [start,end), ohne jeden Sat
    einzeln durchlaufen zu müssen.
    """

    results = []

    max_value = end - 1

    if max_value < 0:
        return results

    max_digits = len(str(max_value))

    for digits in range(1, max_digits + 1):
        half_length = (digits + 1) // 2
        half_start = 0 if digits == 1 else 10 ** (half_length - 1)
        half_end = 10 ** half_length

        for half in range(half_start, half_end):
            left = str(half)

            if digits % 2 == 0:
                candidate = int(left + left[::-1])
            else:
                candidate = int(left + left[-2::-1])

            if candidate >= end:
                break

            if candidate >= start:
                results.append(candidate)

    return results


def find_alpha_in_range(start, end):
    """
    Erzeugt die kleine Menge numerischer Alpha-Kandidaten,
    statt den gesamten Sat-Bereich zu durchlaufen.
    """

    results = []

    max_digits = len(str(end - 1))

    for digits in range(1, max_digits + 1):
        half_length = (digits + 1) // 2

        minimum = 0 if digits == 1 else 10 ** (half_length - 1)
        maximum = 10 ** half_length

        for half in range(minimum, maximum):
            text = str(half)

            if digits % 2 == 0:
                candidate_text = text + text[::-1]
            else:
                candidate_text = text + text[-2::-1]

            candidate = int(candidate_text)

            if candidate >= end:
                break

            if candidate >= start and is_alpha(candidate):
                results.append(candidate)

    return results


def print_ranges(title, ranges):
    print(colorize(title, ORANGE))
    for start, end in ranges:
        print(colorize(
            f"  [{format_sat(start)}, {format_sat(end)})",
            ORANGE,
        ))


def print_matches(title, matches):
    print(title)

    for category, ranges in matches.items():
        print()
        print(colorize(category, GREEN))
        for start, end in ranges:
            print(colorize(
                f"  [{format_sat(start)}, {format_sat(end)})",
                GREEN,
            ))


def run_reference_tests(historical):
    print("REFERENCE TESTS")
    print("-" * 72)

    expected = {
        "PIZZA": 283_888_216_396_236,
        "BLOCK_9": 45_000_000_000,
        "BLOCK_78": 390_000_000_000,
        "HITMAN": 4_045_240_644_369,
    }

    all_ok = True

    for category, sat in expected.items():
        ranges = historical.get(category, [])

        if range_contains(ranges, sat):
            print(
                f"[ OK ] {category} Sat {format_sat(sat)}"
            )
        else:
            print(
                f"[FAIL] {category} Sat {format_sat(sat)}"
            )
            all_ok = False

    print()

    overlap_tests = [
        45_000_000_000,
        390_000_000_000,
    ]

    print("overlaps:")

    for sat in overlap_tests:
        categories = []

        for category, ranges in historical.items():
            if range_contains(ranges, sat):
                categories.append(category)

        print(
            f"  {format_sat(sat)}: "
            + ", ".join(categories)
        )

    print()

    if all_ok:
        print("RESULT all reference tests passed")
        return 0

    print("RESULT reference tests FAILED")
    return 1


def show_startup_help():
    print("ORDINALS SATRIBUTE CHECK")
    print("=" * 72)
    print()
    print("EINGABEMÖGLICHKEITEN")
    print("-" * 72)
    print("Du kannst dem Script vier verschiedene Eingabetypen geben:")
    print()
    print("  1. TXID:VOUT")
    print("     Beispiel: 20c44a48...649d0:0")
    print("     Ein einzelnes Bitcoin-UTXO wird direkt geprüft.")
    print()
    print("  2. INSCRIPTION-ID")
    print("     Beispiel: 20c44a48...649d0i0")
    print("     Das Script ermittelt über ord den Satpoint und das UTXO.")
    print()
    print("  3. INSCRIPTION-NUMMER")
    print("     Beispiel: 127289216")
    print("     Das Script ermittelt über ord die zugehörige Inscription-ID,")
    print("     den Satpoint und das UTXO.")
    print()
    print("  4. BITCOIN-ADRESSE")
    print("     Beispiel: bc1p6mqtknuxcf0ksffz5glv34vx5kl082hdz6q56n69wxx6f5ys8y5qeyc0xr")
    print("     Bitcoin Core sucht alle aktuell nicht ausgegebenen UTXOs")
    print("     dieser Adresse und prüft anschließend jedes gefundene UTXO.")
    print()
    print("ZUSÄTZLICHE FUNKTIONEN")
    print("-" * 72)
    print("  --test")
    print("     Führt nur die kurzen Referenztests für bekannte Satributes aus.")
    print()
    print("  --refresh-historical")
    print("     Zeigt den Status des Historical-Satribute-Caches.")
    print()
    print("Die numerische Satribute-Suche wird später separat abgefragt, da")
    print("sie je nach Sat-Range deutlich länger dauern kann.")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Check Bitcoin UTXO satributes using ord."
    )

    parser.add_argument(
        "input_value",
        nargs="?",
        help="TXID:VOUT, Inscription-ID, Inscription-Nummer oder Bitcoin-Adresse",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run reference tests",
    )

    parser.add_argument(
        "--refresh-historical",
        action="store_true",
        help="Refresh the historical satribute cache",
    )

    args = parser.parse_args()

    show_startup_help()

    if args.input_value:
        print(f"EINGABE: {args.input_value}")
    elif not args.test and not args.refresh_historical:
        args.input_value = input("Eingabe (TXID:VOUT, Inscription-ID, Inscription-Nummer oder Bitcoin-Adresse): ").strip()

    print()
    input("Drücke ENTER, um die Prüfung zu starten ...")
    print()

    historical_raw = load_cache()

    if historical_raw is None:
        print(
            "FEHLER: Historical-Satribute-Cache nicht gefunden."
        )
        print(
            f"Erwartet: {CACHE_FILE}"
        )
        print()
        print(
            "Falls der Cache neu erstellt werden soll:"
        )
        print(
            "  ./check_utxo_satributes.py --refresh-historical"
        )
        return 1

    historical = normalize_historical_data(historical_raw)

    if args.test:
        return run_reference_tests(historical)

    if args.refresh_historical:
        print(
            "Der vorhandene Historical-Cache wird aktuell "
            "nicht automatisch aus dem Internet neu aufgebaut."
        )
        print(
            "Der vorhandene Cache wird für PIZZA und HITMAN "
            "weiterverwendet."
        )
        print()
        print(
            f"PIZZA RANGES:  {len(historical.get('PIZZA', []))}"
        )
        print(
            f"HITMAN RANGES: {len(historical.get('HITMAN', []))}"
        )
        print()
        print(
            "Für einen vollständigen Neuaufbau bitte die bisherige "
            "Cache-Erstellung verwenden."
        )
        return 0

    if not args.input_value:
        parser.error(
            "EINGABE fehlt. Erwartet werden TXID:VOUT, Inscription-ID oder Bitcoin-Adresse."
        )

    try:
        outpoints = resolve_input(args.input_value)
    except (RuntimeError, ValueError) as exc:
        print(f"FEHLER: {exc}")
        return 1

    if not outpoints:
        return 0

    all_historical_matches = {}
    all_numeric_matches = {}

    for outpoint_index, outpoint in enumerate(outpoints, start=1):
        print("ORDINALS SATRIBUTE CHECK")
        print("=" * 72)
        print()
        try:
            output = get_output(outpoint)
        except Exception as exc:
            print("FEHLER beim Abrufen des Outputs:")
            print(f"  {exc}")
            print()
            continue

        value = output.get("value")

        print(colorize(f"OUTPOINT: {outpoint}", BLUE))
        print(colorize(
            f"VALUE: {format_sat(value)} sats"
            if isinstance(value, int)
            else "VALUE: unbekannt",
            BLUE,
        ))

        if len(outpoints) > 1:
            print(colorize(
                f"UTXO: {outpoint_index}/{len(outpoints)}",
                BLUE,
            ))

        print()
        print("INSCRIPTION-PRÜFUNG")
        print("-" * 72)

        # ord returns existing inscriptions directly on the output.
        inscriptions = output.get("inscriptions", [])

        if isinstance(inscriptions, list) and inscriptions:
            print(colorize("Inscription vorhanden: JA", GREEN))

            for inscription_id in inscriptions:
                if isinstance(inscription_id, str):
                    print(f"  INSCRIPTION: {inscription_id}")
        else:
            print(colorize("Inscription vorhanden: NEIN", RED))
            print("Keine Inscription auf diesem Output gefunden.")

        print()

        sat_ranges = get_sat_ranges(output)

        # Important:
        # During Sat indexing, ord may temporarily return
        # sat_ranges=null. This indicates an indexing state, not
        # a negative Satribute result.
        if sat_ranges is None:
            print("SAT RANGES: nicht verfügbar")
            print()
            print("STATUS: UTXO wird momentan nicht klassifiziert.")
            print()
            continue

        if not sat_ranges:
            print("SAT RANGES: leer")
            print()
            print("STATUS: Keine Sat-Ranges für diesen Output.")
            print()
            continue

        print(colorize("SAT RANGES:", ORANGE))
        for start, end in sat_ranges:
            print(colorize(
                f"  [{format_sat(start)}, {format_sat(end)})",
                ORANGE,
            ))
        print()

        print("SCAN FORTSCHRITT:")
        print("-" * 72)

        historical_matches = scan_historical(
            sat_ranges,
            historical,
        )

        for category, ranges in historical_matches.items():
            all_historical_matches.setdefault(category, []).extend(ranges)

        print()
        print("NUMERISCHE SATRIBUTES")
        print("-" * 72)
        print(
            "Die numerische Suche kann je nach Sat-Range deutlich "
            "länger dauern."
        )

        while True:
            answer = input(
                "Numerische Satributes prüfen? [ja/no]: "
            ).strip().lower()

            if answer in {"ja", "j", "yes", "y"}:
                print(colorize("Numerische Satributes: JA", GREEN))
                numeric_matches = scan_numeric(sat_ranges)
                break

            if answer in {"no", "n", "nein"}:
                print(colorize("Numerische Satributes: NEIN", RED))
                print(colorize("Numerische Suche übersprungen.", RED))
                numeric_matches = {}
                break

            print("Bitte 'ja' oder 'no' eingeben (auch 'n' oder 'nein' möglich).")

        for category, ranges in numeric_matches.items():
            all_numeric_matches.setdefault(category, []).extend(ranges)

        if historical_matches:
            print_matches(
                "HISTORICAL SATRIBUTES:",
                historical_matches,
            )
            print()

        if numeric_matches:
            print_matches(
                "NUMERIC SATRIBUTES:",
                numeric_matches,
            )
            print()

        if not historical_matches and not numeric_matches:
            print(colorize(
                "KEINE INTERESSANTEN SATRIBUTES GEFUNDEN",
                RED,
            ))

        print()

    for category, ranges in list(all_historical_matches.items()):
        all_historical_matches[category] = merge_ranges(ranges)

    for category, ranges in list(all_numeric_matches.items()):
        all_numeric_matches[category] = merge_ranges(ranges)

    if all_historical_matches or all_numeric_matches:
        print("=" * 72)
        print(colorize(
            "GESAMTERGEBNIS: INTERESSANTE SATRIBUTES GEFUNDEN",
            GREEN,
        ))
    else:
        print("=" * 72)
        print(colorize(
            "GESAMTERGEBNIS: KEINE INTERESSANTEN SATRIBUTES GEFUNDEN",
            RED,
        ))

    return 0


if __name__ == "__main__":
    sys.exit(main())
