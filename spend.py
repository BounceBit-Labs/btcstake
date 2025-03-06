#!/usr/bin/env python3

import argparse
from decimal import Decimal
from typing import Optional
from src.tx import Transaction
from src.utils import BitcoinRPC
from src.validation import Validator
from src.spend_p2wsh import sign_p2wsh_cltv_with_script
from src.spend_p2sh import sign_p2sh_cltv_with_script
from src.utils import Prompter
from src.config import NETWORK

class Spender:
    def __init__(self, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.rpc = BitcoinRPC(NETWORK, verbose=verbose, test=test)
        self.validator = Validator(rpc=self.rpc, verbose=verbose, test=test)
        self.tx = Transaction(rpc=self.rpc, verbose=verbose, test=test)
        
    def spend_stake(self, utxo: str, address: str, redeem_script: str) -> Optional[str]:
        if not self.validator.validate_address(address):
            print("Error: Invalid destination address")
            return None

        script_info = self.validator.validate_script(redeem_script, spend=True)
        if not script_info:
            print("Error: Invalid redeem script")
            return None

        try:
            txid, vout = utxo.split(':')
            vout = int(vout)
        except ValueError:
            print(f"Error: Invalid UTXO format: {utxo}")
            return None
        
        # Get UTXO details
        utxo_info = self.rpc.gettxout(txid, vout, True)
        if not utxo_info:
            print(f"Error: UTXO {txid}:{vout} not found or already spent")
            return None
        
        amount = Decimal(utxo_info['value'])
        script_type = utxo_info['scriptPubKey']['type']
        use_p2sh = script_type == 'scripthash'
        
        fee = self.tx.calculate_fees(use_p2sh)
    
        print("\nPaste or type your private key (input will not be shown)")
        privkey = Prompter.get_hidden_input("Enter private key for signing: ")
        if not privkey:
            print("Error: No private key provided")
            return None
        
        COIN = int(100000000)
        signed_tx = None
        if use_p2sh:
            signed_tx = sign_p2sh_cltv_with_script(
                network=NETWORK,
                private_key=privkey,
                redeem_script=redeem_script,
                utxo_txid=txid,
                utxo_vout=vout,
                payto_address=address,
                amount=int(amount*COIN),
                fee=int(fee*COIN)
            )
        else:
            signed_tx = sign_p2wsh_cltv_with_script(
                network=NETWORK,
                private_key=privkey,
                redeem_script=redeem_script,
                utxo_txid=txid,
                utxo_vout=vout,
                payto_address=address,
                amount=int(amount*COIN),
                fee=int(fee*COIN),
            )

        if not signed_tx:
            print("Error: Failed to build unlock transaction")
            return None
        print("signed_tx: ", signed_tx)

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
    # parser.add_argument('--config', default='spend_config.json', help='Config file path')
    parser.add_argument('--utxo', help='UTXO to spend (txid:vout)')
    parser.add_argument('--redeem-script', help='Redeem script')
    parser.add_argument('--address', help='Destination address')
    # parser.add_argument('--fee', type=Optional[str], help='Transaction fee in BTC')
    return parser.parse_args()

def main():
    args = parse_args()
    spender = Spender(verbose=args.verbose, test=args.test)
    spender.spend_stake(args.utxo, args.address, args.redeem_script)

if __name__ == '__main__':
    main() 