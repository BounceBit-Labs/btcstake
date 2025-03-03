# BTC Staking Tool

Lock BTC with CLTV and create BB chain staking record.

## Requirements

- Bitcoin Core (with RPC enabled)
- Python 3.7+

## Installation

```bash
git clone https://github.com/user/btcstake.git
cd btcstake
pip install -r requirements.txt
```

## Usage

### 1. Lock BTC

```bash
./stake.py \
  --pubkey=<public_key> \
  --days=<lock_days> \
  --amount_btc=<amount> \
  --bb_address=<bb_chain_address> \
  --change_address=<btc_address> \
  --utxos=<txid:vout,...>
```

### 2. Unlock BTC

```bash
./spend.py \
  --utxo=<txid:vout> \
  --redeem_script=<script> \
  --address=<destination>
```

## Options

- `-v, --verbose`: Show detailed output
- `-t, --test`: Test mode
- `--config`: Load config from JSON file
- `--fee`: Set custom fee (in BTC)

## Transaction Structure

- Inputs: Simple UTXOs (pubkeyhash/pubkey)
- Outputs: P2SH/P2WSH + Change + OP_RETURN
- Signing: Only requires scriptPubKey for inputs 