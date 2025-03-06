#!/usr/bin/env python3

import re
import json
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime
from .utils import BitcoinRPC

class Validator:
    def __init__(self, rpc, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.test = test
        self.rpc = rpc
        
    def validate_address(self, address: str) -> bool:
        # if not re.match(r'^([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[qp][a-zA-HJ-NP-Z0-9]{38,58}|tb1[qp][a-zA-HJ-NP-Z0-9]{38,58})$', address):
        #     print(f"Invalid Bitcoin address: {address}")
        #     return False
        return True
    
    def validate_pubkey(self, pubkey: str) -> bool:
        if not re.match(r'^[0-9a-fA-F]{66}$', pubkey):
            print("Invalid public key format")
            return False
        if pubkey[:2] not in ['02', '03']:
            print("Invalid public key prefix")
            return False
        return True
        
    def validate_script(self, script: str, spend: bool = False) -> Optional[Dict]:
        try:
            script_info = self.rpc.decodescript(script)
            if script_info['type'] != 'nonstandard':
                print(f"Unexpected script type: {script_info['type']}")
                return None
                
            asm = script_info['asm'].split()
            if len(asm) != 5:
                print("Invalid script format")
                return None
                
            locktime = int(asm[0])
            current_time = self.rpc.getcurrenttime()
            
            if not spend:
                if locktime < current_time:
                    print("Script locktime is in the past")
                    return None
                if locktime > current_time + 365 * 86400:
                    print("Script locktime too far in future")
                    return None
            elif spend and locktime > current_time:
                print("Script locktime is in the future")
                return None

            if self.verbose:
                print(f"Locktime verified (until {datetime.fromtimestamp(locktime)})")

            return script_info
            
        except Exception as e:
            print(f"Error: {e}")
            return None 