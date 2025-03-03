#!/usr/bin/env python3

import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from .config import BB_CHAIN_ID, BB_CONTRACT
from .utils import BitcoinRPC
from .validation import Validator

class Script:
    def __init__(self, rpc: BitcoinRPC, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.rpc = rpc
        self.validator = Validator(verbose)
        self.test = test

    def construct_op_return(self, bb_addr: str, days: int, amount_btc: str) -> str:
        """Construct OP_RETURN data for BB chain staking"""
        # Convert amount from BTC to mBTC
        amount_mbtc = int(Decimal(amount_btc) * 1000)
        
        if self.verbose:
            print("Constructing OP_RETURN data:")
            print(f"  BB Address: {bb_addr}")
            print(f"  Days: {days}")
            print(f"  Amount BTC: {amount_btc}")
            print(f"  Amount mBTC: {amount_mbtc}")
            print(f"  Amount hex: {amount_mbtc:08x}")
        
        # Construct data
        data = (
            "46535450"  # FSTP
            + BB_CHAIN_ID  # BB chain ID (6001) in hex
            + BB_CONTRACT  # Fixed LSD contract address
            + bb_addr[2:].lower().zfill(40)  # Remove 0x and pad to 40 chars
            + f"{amount_mbtc:08x}"  # 4 bytes for amount in mBTC
            + f"{days:04x}"  # 2 bytes for days
        )
        
        if self.verbose:
            print(f"Constructed data: {data}")
            print(f"Length: {len(data)} chars ({len(data) // 2} bytes)")
            
        return data

    def create_redeem_script(self, days: int, pubkey: str) -> str:
        """Create redeem script with timelock and pubkey"""
        # Validate pubkey first
        if not self.validator.validate_pubkey(pubkey):
            return None
            
        # Calculate lock time
        current_time = self.rpc.getcurrenttime()
        
        lock_time = current_time + days * 86400
        
        
        try:
            # Convert to hex and validate
            lock_time_hex = format(lock_time, '08x')
            self._validate_lock_time(lock_time, current_time)
            self._validate_lock_time_hex(lock_time_hex)
            
            # Convert hex timestamp to little-endian for script
            time_le = ''.join(reversed([lock_time_hex[i:i+2] for i in range(0, len(lock_time_hex), 2)]))
            
            # Construct script
            script = (
                f"04{time_le}"  # Push 4 bytes locktime
                "b175"          # OP_CHECKLOCKTIMEVERIFY OP_DROP
                f"21{pubkey}"   # Push 33 bytes pubkey
                "ac"           # OP_CHECKSIG
            )
            
            # Get script info from bitcoin-cli
            script_info = self.rpc.decodescript(script)
            if self.verbose:
                print(f"Script hex: {script}")
                print(f"Script Info: {json.dumps(script_info, indent=2)}")
                
            return script
            
        except Exception as e:
            print(f"Error creating redeem script: {e}")
            if self.verbose:
                print(f"Script hex: {script}")
            return None

    def _validate_lock_time(self, lock_time: int, current_time: int):
        """Validate timelock value"""
        if lock_time < current_time:
            raise ValueError(f"Generated locktime ({lock_time}) is in the past")
            
        if lock_time < 500000000:
            raise ValueError(f"Generated locktime ({lock_time}) is too small")
            
        if lock_time > 0x7fffffff:  # 2147483647
            raise ValueError(f"Generated locktime ({lock_time}) is too large")

    def _validate_lock_time_hex(self, lock_time_hex: str):
        """Validate timelock hex representation"""
        # Check if locktime would be interpreted as negative
        if int(lock_time_hex, 16) & 0x80000000:
            raise ValueError(
                "Locktime would be interpreted as negative value\n"
                f"Hex: {lock_time_hex}\n"
                "Please choose a different timelock period"
            ) 