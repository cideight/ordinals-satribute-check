# ordinals-satribute-check

A local Python script for finding interesting Satoshis (Satributes)
inside current Bitcoin UTXOs.

The script combines **Bitcoin Core** with a local **ord** server. It can
check a single UTXO, an inscription, an inscription number, or all
current UTXOs belonging to a Bitcoin address.

## Requirements

### Bitcoin Core Full Node

Bitcoin Core must be a fully synchronized **full node**.

The transaction index must be enabled:

``` ini
txindex=1
```

The script relies on the Bitcoin Core node for current UTXO discovery,
transaction data and address-based UTXO scans.

### ord

A synchronized `ord` index with the Satoshi index enabled is required:

``` bash
ord --index-sats server
```

The important ord parameter is:

``` text
--index-sats
```

This index is required because the script uses ord to determine the
Satoshi ranges contained in each UTXO.

Example:

``` bash
ord --index-sats server --http-port 8080
```

The two required indexes for the complete setup are therefore:

``` text
Bitcoin Core: txindex=1
ord:          --index-sats
```

Additional ord indexes such as `--index-addresses` or `--index-runes`
are not required for the Satribute search itself.

## Database and Index Architecture

The script does not maintain its own Bitcoin blockchain database. It
uses the databases and indexes provided by Bitcoin Core and ord.

### Bitcoin Core databases

Bitcoin Core maintains the blockchain data and the current UTXO set.

The relevant components are:

``` text
blocks/
chainstate/
```

`chainstate` contains the current UTXO set. Address searches are
performed against this current UTXO set using:

``` bash
scantxoutset
```

`txindex=1` creates and maintains Bitcoin Core's transaction index,
allowing transactions to be retrieved by TXID.

The script does not create a separate permanent address database when
using `scantxoutset`.

### ord database

ord maintains its own index database. In the local setup this is stored
as:

``` text
/home/bte/.local/share/ord/index.redb
```

The `--index-sats` index is what allows ord to map UTXOs and satpoints
to individual Satoshis and their ranges.

The ord database is therefore the primary source used by the script for
Satoshi-level location data.

### Historical Satribute database

The script additionally uses a local JSON cache for historical Satribute
ranges:

``` text
/home/bte/.local/share/ord/historical_satributes.json
```

This data is separate from the Bitcoin Core and ord databases.

It contains the known historical ranges used by the script, including:

``` text
FIRST_TX
BLOCK_9
BLOCK_78
VINTAGE
NAKAMOTO
PIZZA
HITMAN
```

Static historical ranges such as `FIRST_TX`, `BLOCK_9`, `BLOCK_78`,
`VINTAGE` and `NAKAMOTO` are defined by the script. Cached range data is
used for the larger historical categories such as `PIZZA` and `HITMAN`.

## How the Databases Work Together

The general data flow is:

``` text
Bitcoin Core Full Node
        |
        | txindex=1
        | current UTXO set
        v
     UTXO / TX
        |
        +----------------------+
        |                      |
        v                      v
   Bitcoin Core              ord
   scantxoutset          --index-sats
        |                      |
        |                      v
        |                 Sat Ranges
        |                 / Satpoints
        |                      |
        +----------+-----------+
                   |
                   v
          Ordinals Satribute Check
                   |
                   v
       Historical Satribute Cache
                   |
                   v
              Result
```

For an address search, Bitcoin Core first finds the currently unspent
outputs for that address. The script then asks ord for the corresponding
output and Satoshi-range information.

For an inscription ID or inscription number, ord is used first to
resolve the inscription to its satpoint and UTXO.

## Input Types

The script accepts four different input types:

1.  **TXID:VOUT**

    ``` text
    20c44a48...649d0:0
    ```

    Directly checks a specific Bitcoin UTXO.

2.  **Inscription ID**

    ``` text
    20c44a48...649d0i0
    ```

    Uses ord to resolve the inscription's satpoint and corresponding
    UTXO.

3.  **Inscription number**

    ``` text
    127289216
    ```

    Uses ord to resolve the number to the corresponding inscription,
    satpoint and UTXO.

4.  **Bitcoin address**

    ``` text
    bc1q...
    ```

    Bitcoin Core uses `scantxoutset` to find all currently unspent
    outputs belonging to the address.

The address does not need to belong to a Bitcoin Core wallet.

## Scan Process

For every UTXO found:

1.  The script retrieves the output data from ord.
2.  It checks whether an inscription already exists on the output.
3.  It obtains the Satoshi ranges contained in the UTXO.
4.  The ranges are checked against known historical Satributes.
5.  An optional numerical Satribute search can be performed.
6.  The results are displayed in the terminal with color-coded output.

## Satributes Checked

The historical search includes:

-   `FIRST_TX`
-   `BLOCK_9`
-   `BLOCK_78`
-   `VINTAGE`
-   `NAKAMOTO`
-   `PIZZA`
-   `HITMAN`

The optional numerical search includes:

-   `PALINDROME`
-   `ALPHA`
-   `OMEGA`

## Test Mode

The script contains a dedicated reference test mode:

``` bash
python3 check_utxo_satributes_v6.py --test
```

The test mode does not scan an address or UTXO. It verifies the internal
Satribute definitions against known reference Sats.

The reference tests include known examples for:

-   PIZZA
-   BLOCK_9
-   BLOCK_78
-   HITMAN

It also checks expected overlaps between historical Satribute
categories.

This makes `--test` useful after changes to the Satribute definitions,
cache handling or scan logic.

## Historical Satribute Cache

The historical data cache can be inspected with:

``` bash
python3 check_utxo_satributes_v6.py --refresh-historical
```

The cache is stored separately from the Bitcoin Core and ord databases:

``` text
/home/bte/.local/share/ord/historical_satributes.json
```

The cache contains precomputed historical Satribute ranges so the script
does not have to reconstruct those large range sets during every UTXO
scan.

## Usage

Start the script interactively:

``` bash
python3 check_utxo_satributes_v6.py
```

Or provide the input directly:

``` bash
python3 check_utxo_satributes_v6.py <INPUT>
```

Examples:

``` bash
python3 check_utxo_satributes_v6.py 20c44a48...649d0:0
python3 check_utxo_satributes_v6.py 20c44a48...649d0i0
python3 check_utxo_satributes_v6.py 127289216
python3 check_utxo_satributes_v6.py bc1q...
```

## Important Notes

-   Address searches operate on the **current UTXO set**.
-   `scantxoutset` does not create a permanent address index.
-   An address does not need to belong to a Bitcoin Core wallet.
-   The ord index must be synchronized and close to the current chain
    tip.
-   `--index-sats` is required for determining Satoshi locations.
-   Spent historical outputs are not returned by a current UTXO-set
    scan.
-   The numerical search is optional and can take considerably longer
    for large Satoshi ranges.
-   The script itself does not replace Bitcoin Core or ord as a
    blockchain or Satoshi index.

## Local Services

By default, the script expects:

``` text
Bitcoin Core RPC: available through bitcoin-cli
ord API:          http://127.0.0.1:8080
```

The ord server must be running while the script performs a scan.

## Purpose

The project is designed for local discovery of rare or otherwise
interesting Satoshis without relying on an external Ordinals explorer as
the primary data source.
