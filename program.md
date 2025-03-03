# BTC Staking Program

## Script Structure

```
<locktime> OP_CHECKLOCKTIMEVERIFY OP_DROP <pubkey> OP_CHECKSIG
```

- `locktime`: Unix timestamp (4 bytes)
- `pubkey`: Compressed public key (33 bytes)

## Transaction Types

### 1. Lock Transaction

- Input: Simple UTXO (P2PKH/P2WPKH)
- Outputs:
  - P2WSH/P2SH: Locked amount
  - Change (optional)
  - OP_RETURN: BB chain data

### 2. Unlock Transaction

- Input: P2WSH/P2SH UTXO
- Output: Destination address

## OP_RETURN Format

```
FSTP|ChainID|Contract|Address|Amount|Days
```

- FSTP: Fixed prefix (4 bytes)
- ChainID: BB chain ID (2 bytes)
- Contract: LSD contract address (20 bytes)
- Address: BB chain address (20 bytes)
- Amount: mBTC amount (4 bytes)
- Days: Lock days (2 bytes)

## Validation

1. Lock:
   - Valid BB address
   - Valid pubkey
   - Future locktime
   - Sufficient funds

2. Unlock:
   - Valid redeem script
   - Expired locktime
   - Correct signature

## Overview
A Python-based tool for staking BTC on BB chain. The tool supports creating time-locked transactions with OP_RETURN data for BB chain staking, and unlocking these transactions after the timelock expires.

## Features
1. Create time-locked staking transactions
2. Support both P2WSH and P2SH scripts
3. Automatic fee calculation
4. Transaction validation
5. Unlock staked funds

## Components

### 1. Configuration (src/config.py)
- Load settings from JSON file or command line
- Validate configuration parameters
- Handle BB chain constants

### 2. Script Building (src/script.py)
- Construct OP_RETURN data
- Create time-locked redeem scripts
- Validate script parameters

### 3. Transaction Handling (src/tx.py)
- Build raw transactions
- Calculate fees
- Sign transactions
- Broadcast transactions

### 4. Bitcoin RPC (src/utils.py)
- Wrapper for bitcoin-cli commands
- Handle RPC responses
- Error handling

## Usage

### Staking
```bash
# Using config file
./stake.py --config stake_config.json

# Using command line
./stake.py \
  --pubkey=034d956c1091a1498c58393b391c18bd4a9fb7880ccbd33a521bd22fc263f7e1a1 \
  --days=30 \
  --amount_btc=0.00100000 \
  --bb_address=0xfD24B690f81d85390fFAC82FA9930De1629C14f6 \
  --change_address=1EYWEKTtUmM7Q2tarTBdyiWvNbpfm8sfkp \
  --utxos=2d54637694d03fbe954002a83f51fb58bf86fc3e538efcd4c2a301dc1403d467:0
```

### Unlocking
```bash
./spend.py \
  --utxo=<txid:vout> \
  --redeem-script=<script> \
  --address=<destination>
```

## Implementation Details

### 1. Staking Process
1. Load and validate configuration
2. Construct OP_RETURN data
3. Create time-locked redeem script
4. Build and sign transaction
5. Broadcast transaction

### 2. Unlocking Process
1. Validate redeem script and locktime
2. Build unlock transaction
3. Sign with private key
4. Broadcast transaction

### 3. Script Types
- P2WSH (Native SegWit)
- P2SH (Legacy)

### 4. Fee Calculation
- Based on transaction size
- Uses estimatesmartfee RPC
- Different sizes for P2WSH/P2SH

## Security Considerations
1. Private keys never stored in files
2. Transaction validation before signing
3. Locktime verification
4. User confirmation for broadcasts

## Dependencies
- Python 3.7+
- bitcoin-cli
- Standard Python libraries 