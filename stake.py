#!/usr/bin/env python3

import argparse
import json
import time
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict
from src.config import Config
from src.tx import Transaction
from src.script import Script
from src.utils import Prompter, BitcoinRPC
from src.validation import Validator


class Staker:
    def __init__(self, verbose: bool = False, tx: Transaction = None, script: Script = None, validator: Validator = None, rpc: BitcoinRPC = None):
        self.verbose = verbose
        self.tx = tx
        self.script = script
        self.validator = validator
        self.rpc = rpc

    def create_stake(self, config: Config) -> Optional[str]:
        if not self.validator.validate_address(config.change_address):
            print("Error: Invalid change address")
            return None

        redeem_script = self.script.create_redeem_script(config.days, config.pubkey)
        if not redeem_script:
            print("Error: Failed to create redeem script")
            return None
        script_info = self.validator.validate_script(redeem_script)
        if not script_info:
            print("Error: Invalid redeem script")
            return None

        op_return_data = self.script.construct_op_return(config.bb_address, config.days, config.amount_btc)
        if not op_return_data:
            print("Error: Failed to construct OP_RETURN data")
            return None
        
        result = self.tx.build_stake_tx(
            config.utxos,
            config.amount_btc,
            config.change_address,
            op_return_data,
            script_info,
            config.use_p2sh
        )
        if not result:
            print("Error: Failed to build transaction")
            return None

        signed_tx = result['signed_tx']
        # privkey = result['privkey']

        # if not self.tx.verify_stake_signature(signed_tx, privkey, config.pubkey, redeem_script, script_info, config.use_p2sh):
        #     print("Error: Private key verification failed")
        #     return None

        if not self._confirm_transaction(config, op_return_data, redeem_script, script_info):
            return None

        txid = self.tx.broadcast(signed_tx)
        if not txid:
            print("Error: Failed to broadcast transaction")
            return None

        self._show_success_info(txid, redeem_script, config.days)
        return txid

    def _confirm_transaction(self, config: Config, op_return_data: str, redeem_script: str, script_info: Dict) -> bool:
        unlock_time = datetime.fromtimestamp(self.rpc.getcurrenttime() + config.days * 86400)
        
        print("\nTransaction details:")
        print(f"BB Chain Address: {config.bb_address}")
        print(f"Amount: {config.amount_btc} BTC")
        print(f"Lock Period: {config.days} days")
        print(f"Unlock Time: {unlock_time}")
        print(f"Change Address: {config.change_address}")
        print(f"UTXOs: {', '.join(config.utxos)}")
        print(f"Redeem Script: {redeem_script}")
        print(f"P2WSH: {script_info['segwit']['address']}")
        print(f"P2SH: {script_info['p2sh']}")
        print(f"OP_RETURN: {op_return_data}")
        
        # if self.verbose:
        #     print(f"Script Info: {json.dumps(script_info, indent=2)}")
            
        return Prompter.confirm_action("Confirm data?")

    def _show_success_info(self, txid: str, redeem_script: str, days: int) -> None:
        print(f"\nTransaction broadcast: {txid}")
        print("\nSave for unlocking:")
        print(f"UTXO: {txid}:0")
        print(f"Redeem Script: {redeem_script}")
        print(f"./spend.py --utxo={txid}:0 --redeem_script={redeem_script} --address=<destination>")

def parse_args():
    parser = argparse.ArgumentParser(description='BTC Staking Tool')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--config', default='stake_config.json', help='Config file path')
    parser.add_argument('--pubkey', help='Public key')
    parser.add_argument('--days', type=int, help='Timelock days')
    parser.add_argument('--amount_btc', help='Amount in BTC')
    parser.add_argument('--bb_address', help='BB chain address')
    parser.add_argument('--change_address', help='Change address')
    parser.add_argument('--use_p2sh', action='store_true', help='Use P2SH instead of P2WSH')
    parser.add_argument('--utxos', help='UTXOs to spend')
    parser.add_argument('-t', '--test', action='store_true', help='Test mode')
    return parser.parse_args()

def main():
    args = parse_args()
    config = Config(args)
    if args.verbose:
        print(f"Config: {config.__dict__}")
    
    rpc = BitcoinRPC(verbose=args.verbose, test=args.test)
    tx = Transaction(rpc, verbose=args.verbose, test=args.test)
    script = Script(rpc, verbose=args.verbose, test=args.test)
    validator = Validator(rpc, verbose=args.verbose, test=args.test)
    staker = Staker(verbose=args.verbose, tx=tx, script=script, validator=validator, rpc=rpc)
    staker.create_stake(config)

if __name__ == '__main__':
    main() 