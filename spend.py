#!/usr/bin/env python3

import argparse
from decimal import Decimal
from typing import Optional
from src.tx import Transaction
from src.utils import BitcoinRPC
from src.validation import Validator

class Spender:
    def __init__(self, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.rpc = BitcoinRPC(verbose=verbose, test=test)
        self.validator = Validator(rpc=self.rpc, verbose=verbose, test=test)
        self.tx = Transaction(rpc=self.rpc, verbose=verbose, test=test)
        
    def spend_stake(self, utxo: str, address: str, redeem_script: str, fee: Optional[str] = None) -> Optional[str]:
        if not self.validator.validate_address(address):
            print("Error: Invalid destination address")
            return None

        script_info = self.validator.validate_script(redeem_script, spend=True)
        if not script_info:
            print("Error: Invalid redeem script")
            return None

        signed_tx = self.tx.build_spend_tx(utxo, address, redeem_script, fee)
        if not signed_tx:
            print("Error: Failed to build unlock transaction")
            return None

        txid = self.tx.broadcast(signed_tx)
        if not txid:
            print("Error: Failed to broadcast transaction")
            return None

        print(f"\nTransaction broadcast: {txid}")
        return txid

def parse_args():
    parser = argparse.ArgumentParser(description='BTC Unlock Tool')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-t', '--test', action='store_true', help='Test mode')
    parser.add_argument('--config', default='spend_config.json', help='Config file path')
    parser.add_argument('--utxo', help='UTXO to spend (txid:vout)')
    parser.add_argument('--redeem_script', help='Redeem script')
    parser.add_argument('--address', help='Destination address')
    parser.add_argument('--fee', help='Transaction fee in BTC')
    return parser.parse_args()

def main():
    args = parse_args()
    spender = Spender(verbose=args.verbose, test=args.test)
    spender.spend_stake(args.utxo, args.address, args.redeem_script, args.fee)

if __name__ == '__main__':
    main() 