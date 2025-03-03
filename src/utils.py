#!/usr/bin/env python3

import time
import subprocess
import json
import getpass
from typing import Any, Dict, List, Optional

class BitcoinRPC:
    """Bitcoin RPC wrapper using bitcoin-cli"""
    
    def __init__(self, test: bool = False, verbose: bool = False):
        self.cli = 'bitcoin-cli'
        self.test = test
        self.verbose = verbose

    def _call(self, *args) -> Any:
        """Execute bitcoin-cli command and return parsed JSON result"""
        try:
            str_args = [str(arg) if not isinstance(arg, (dict, list)) else json.dumps(arg) for arg in args]
            cmd = [self.cli]
            cmd.extend(str_args)
            
            print(f"\nExecuting: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                shell=False
            )
            
            output = result.stdout.strip()
            if not output:
                return None
            
            if self.verbose:
                print(f"Output: {output}")
                
            try:
                data = json.loads(output)
                if isinstance(data, dict) and 'feerate' in data:
                    data['feerate'] = format(float(data['feerate']), '.8f')
                return data
            except json.JSONDecodeError:
                return output
            
        except subprocess.CalledProcessError as e:
            error = e.stderr.strip() if e.stderr else str(e)
            raise RuntimeError(f"Bitcoin RPC error: {error}")

    def gettxout(self, txid: str, vout: int, include_mempool: bool = True) -> Optional[Dict]:
        """Get transaction output info"""
        result = self._call('gettxout', txid, vout, str(include_mempool).lower())
        
        if not result and self.test:
            try:
                tx = self.getrawtransaction(txid, True)
                if tx and 'vout' in tx and len(tx['vout']) > vout:
                    vout_info = tx['vout'][vout]
                    script_info = vout_info['scriptPubKey']
                    
                    return {
                        'bestblock': tx.get('blockhash', ''),
                        'confirmations': tx.get('confirmations', 0),
                        'value': vout_info['value'],
                        'scriptPubKey': {
                            'asm': script_info.get('asm', ''),
                            'desc': script_info.get('desc', ''),
                            'hex': script_info.get('hex', ''),
                            'address': script_info.get('address', ''),
                            'type': script_info.get('type', '')
                        },
                        'coinbase': tx.get('coinbase', False)
                    }
            except Exception as e:
                print(f"Error retrieving historical UTXO info: {e}")
            
        return result

    def createrawtransaction(
        self,
        inputs: List[Dict],
        outputs: Dict,
        locktime: Optional[int] = None
    ) -> Optional[str]:
        """Create raw transaction"""
        args = ['createrawtransaction', json.dumps(inputs), json.dumps(outputs)]
        if locktime is not None:
            args.append(str(locktime))
        return self._call(*args)

    def signrawtransactionwithkey(
        self,
        hex_tx: str,
        privkeys: List[str],
        prevtxs: Optional[List[Dict]] = None
    ) -> Dict:
        """Sign raw transaction with private keys"""
        args = ['signrawtransactionwithkey', hex_tx, json.dumps(privkeys)]
        if prevtxs:
            args.append(json.dumps(prevtxs))
        return self._call(*args)

    def sendrawtransaction(self, hex_tx: str) -> str:
        """Submit raw transaction to network"""
        return self._call('sendrawtransaction', hex_tx)

    def decodescript(self, hex_script: str) -> Dict:
        """Decode script"""
        return self._call('decodescript', hex_script)

    def estimatesmartfee(self, conf_target: int) -> Dict[str, float]:
        """Estimate fee rate for target confirmation blocks"""
        return self._call('estimatesmartfee', conf_target)

    def decoderawtransaction(self, hex_tx: str) -> Dict:
        """Decode raw transaction"""
        return self._call('decoderawtransaction', hex_tx)

    def getrawtransaction(self, txid: str, verbose: bool = False) -> Dict:
        """Get raw transaction info"""
        args = ['getrawtransaction', txid]
        if verbose:
            args.append('1')
        return self._call(*args)
    
    def getcurrenttime(self) -> int:
        current_time = int(time.time())
        if self.test:
            current_time = 1711944215 - 30 * 86400
        return current_time
    
    def getblockchaininfo(self) -> Dict:
        """Get blockchain info"""
        return self._call('getblockchaininfo')

    
class Prompter:
    @staticmethod
    def confirm_action(prompt: str, warning_msg: str = None) -> bool:
        """Ask user to confirm an action"""
        if warning_msg:
            print(warning_msg)
            
        while True:
            confirm = input(f"\n{prompt} [y/N]: ").lower()
            if confirm in ['y', 'yes']:
                return True
            if confirm in ['n', 'no', '']:
                print("\nAction cancelled by user")
                return False
            print("Please enter 'y' or 'n'")

    @staticmethod
    def get_hidden_input(prompt: str) -> str:
        return getpass.getpass(prompt)
