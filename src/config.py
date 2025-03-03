#!/usr/bin/env python3

import json
import re
from typing import List, Optional
from dataclasses import dataclass
from decimal import Decimal

# BB chain constants
BB_CHAIN_ID = "1771"  # BB chain ID (6001) in hex
BB_CONTRACT = "0000000000000000000000000000000000000800"  # Fixed LSD contract address
CONF_TARGET = 6  # Target number of blocks for confirmation

# Staking constants
MIN_STAKE_AMOUNT = Decimal('0.00100000')  # Minimum stake amount in BTC (1 mBTC)
MAX_STAKE_DAYS = 365  # Maximum stake period in days

@dataclass
class Config:
    pubkey: str
    days: int
    amount_btc: str
    bb_address: str
    change_address: str
    utxos: List[str]
    use_p2sh: bool = False
    verbose: bool = False
    test: bool = False

    def __init__(self, args):
        """Initialize config from command line args or config file"""
        # Load config file if provided
        if args.config:
            try:
                with open(args.config) as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error loading config file: {e}")
                # return
        else:
            config = {}
            
        # Command line args override config file
        self.pubkey = args.pubkey or config.get('pubkey')
        self.days = args.days or config.get('days')
        self.amount_btc = args.amount_btc or config.get('amount_btc')
        self.bb_address = args.bb_address or config.get('bb_address')
        self.change_address = args.change_address or config.get('change_address')
        self.utxos = args.utxos.split(',') if args.utxos else config.get('utxos', [])
        self.use_p2sh = config.get('use_p2sh', False)
        self.test = args.test
        self.verbose = args.verbose
        
        # Validate all fields
        self.validate()
        
    def validate(self):
        """Validate all configuration fields"""
        missing = []
        
        # Check required fields
        if not self.bb_address:
            missing.append("bb_address")
        if not self.pubkey:
            missing.append("pubkey")
        if not self.days:
            missing.append("days")
        if not self.amount_btc:
            missing.append("amount_btc")
        if not self.change_address:
            missing.append("change_address")
        if not self.utxos:
            missing.append("utxos")
            
        if missing:
            raise ValueError(
                "Missing required parameters: " + ", ".join(missing) + "\n"
                "Use --config=<config.json> or provide parameters via command line"
            )

        # Validate BB address
        if not re.match(r'^0x[0-9a-fA-F]{40}$', self.bb_address):
            raise ValueError("Invalid BB chain address format")

        # Validate amount
        try:
            amount = Decimal(self.amount_btc)
        except:
            raise ValueError("Invalid amount format")
            
        # Validate days
        try:
            int(self.days)
        except:
            raise ValueError("Invalid days format")
        if self.days > MAX_STAKE_DAYS:
            raise ValueError(f"Stake period cannot exceed {MAX_STAKE_DAYS} days")

        # Validate change address format
        # Support all address types:
        # 1. Legacy (P2PKH): 1...
        # 2. P2SH: 3...
        # 3. Bech32 (P2WPKH/P2WSH): bc1q...
        # 4. Taproot (P2TR): bc1p...
        if not re.match(
            r'^('
            r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}|'  # Legacy and P2SH
            r'bc1[qp][a-zA-HJ-NP-Z0-9]{38,58}|'  # Bech32 and Taproot
            r'tb1[qp][a-zA-HJ-NP-Z0-9]{38,58}'   # Testnet Bech32 and Taproot
            r')$',
            self.change_address
        ):
            raise ValueError(
                "Invalid change address format\n"
                "Supported formats:\n"
                "- Legacy addresses (starting with 1)\n"
                "- P2SH addresses (starting with 3)\n" 
                "- Bech32 addresses (starting with bc1q)\n"
                "- Taproot addresses (starting with bc1p)\n"
                "- Testnet addresses (starting with tb1)"
            )

        # Validate UTXOs
        for utxo in self.utxos:
            if not re.match(r'^[0-9a-fA-F]{64}:[0-9]+$', utxo):
                raise ValueError(f"Invalid UTXO format: {utxo}")
