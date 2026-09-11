# Ordinals Satribute Check

Ein lokales Python-Script zur Suche nach interessanten Satoshis
(Satributes) in aktuellen Bitcoin-UTXOs.

Das Script verbindet **Bitcoin Core** und einen lokalen **ord-Server**.
Es kann ein einzelnes UTXO, eine Inscription, eine Inscription-Nummer
oder eine Bitcoin-Adresse prüfen.

## Voraussetzungen

### 1. Synchronisierter Bitcoin-Core-Fullnode

Der Bitcoin-Core-Node muss vollständig synchronisiert sein und den
Transaktionsindex aktiviert haben:

``` ini
txindex=1
```

`ord` benötigt diesen Index, um die Satoshi-Lokationen korrekt
aufzubauen.

### 2. Synchronisierter ord-Index

Für die Satribute-Suche wird ein synchronisierter `ord`-Index mit
`--index-sats` benötigt:

``` bash
ord --index-sats server
```

`--index-sats` ist entscheidend, weil damit die Sat-Ranges der UTXOs
bestimmt werden können.

Damit sind für dieses Projekt die beiden relevanten Indexe:

-   **Bitcoin Core:** `txindex=1`
-   **ord:** `--index-sats`

Ein Beispiel für den verwendeten `ord`-Server:

``` bash
ord --index-sats server --http-port 8080
```

Weitere `ord`-Indexe wie `--index-addresses` oder `--index-runes` sind
für die eigentliche Satribute-Suche nicht erforderlich.

## Was das Script macht

Nach dem Start kann das Script vier verschiedene Eingaben verarbeiten:

1.  **TXID:VOUT**

    ``` text
    20c44a48...649d0:0
    ```

    Prüft ein bestimmtes UTXO direkt.

2.  **Inscription-ID**

    ``` text
    20c44a48...649d0i0
    ```

    `ord` liefert den Satpoint und das zugehörige UTXO.

3.  **Inscription-Nummer**

    ``` text
    127289216
    ```

    `ord` löst die Nummer zur Inscription-ID auf und ermittelt daraus
    Satpoint und UTXO.

4.  **Bitcoin-Adresse**

    ``` text
    bc1q...
    ```

    Bitcoin Core führt mit `scantxoutset` eine Suche im aktuellen
    UTXO-Set durch. Dadurch können auch Adressen geprüft werden, die
    nicht zu einer Bitcoin-Core-Wallet gehören.

## Ablauf der Prüfung

Für jedes gefundene UTXO:

1.  `ord` liefert die Output-Daten.
2.  Das Script prüft, ob bereits eine Inscription auf dem Output liegt.
3.  Die vom `ord`-Index gelieferten Sat-Ranges werden ermittelt.
4.  Diese Ranges werden gegen bekannte historische Satributes geprüft.
5.  Optional kann zusätzlich die numerische Suche ausgeführt werden.
6.  Das Ergebnis wird farblich im Terminal dargestellt.

## Geprüfte Satributes

Die historische Suche umfasst unter anderem:

-   `FIRST_TX`
-   `BLOCK_9`
-   `BLOCK_78`
-   `VINTAGE`
-   `NAKAMOTO`
-   `PIZZA`
-   `HITMAN`

Zusätzlich können numerische Satributes geprüft werden:

-   `PALINDROME`
-   `ALPHA`
-   `OMEGA`

Die historische Suche verwendet dafür einen lokalen Cache:

``` text
/home/bte/.local/share/ord/historical_satributes.json
```

## Verwendung

``` bash
python3 check_utxo_satributes_v6.py
```

Danach kann die Eingabe interaktiv erfolgen.

Alternativ kann die Eingabe direkt als Argument übergeben werden:

``` bash
python3 check_utxo_satributes_v6.py <INPUT>
```

Beispiele:

``` bash
python3 check_utxo_satributes_v6.py 20c44a48...649d0:0
python3 check_utxo_satributes_v6.py 20c44a48...649d0i0
python3 check_utxo_satributes_v6.py 127289216
python3 check_utxo_satributes_v6.py bc1q...
```

## Referenztests

Die integrierten Referenztests können separat ausgeführt werden:

``` bash
python3 check_utxo_satributes_v6.py --test
```

Der Test überprüft bekannte Referenz-Sats für unter anderem PIZZA,
BLOCK_9, BLOCK_78 und HITMAN.

Der Status des Historical-Satribute-Caches kann angezeigt werden:

``` bash
python3 check_utxo_satributes_v6.py --refresh-historical
```

## Wichtige Hinweise

-   Die Adresssuche untersucht den **aktuellen UTXO-Stand** von Bitcoin
    Core.
-   `scantxoutset` erstellt keinen dauerhaften Adressindex.
-   Eine Adresse muss nicht zu einer Bitcoin-Core-Wallet gehören.
-   Der `ord`-Index muss synchronisiert und auf dem aktuellen Chain-Tip
    sein.
-   `--index-sats` verfolgt die aktuellen Sat-Lokationen. Bereits
    ausgegebene historische Outputs sind damit nicht als aktuelle UTXOs
    vorhanden.
-   Die numerische Suche ist optional und kann bei größeren Sat-Ranges
    deutlich länger dauern.

## Benötigte lokale Dienste

Das Script erwartet standardmäßig:

``` text
Bitcoin Core RPC: lokal über bitcoin-cli
ord API:          http://127.0.0.1:8080
```

Der `ord`-Server muss während der Prüfung laufen.

## Hintergrund

Das Projekt ist für die lokale Suche nach seltenen bzw. interessanten
Satoshis gedacht, ohne dafür einen externen Ordinals-Explorer als
primäre Datenquelle zu benötigen.

Weitere Informationen:

-   [Ordinal Theory Handbook -- Sat
    Hunting](https://docs.ordinals.com/guides/sat-hunting.html)
-   [Ordinal Theory Handbook --
    API](https://docs.ordinals.com/guides/api.html)
