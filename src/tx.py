#!/usr/bin/env python3

import json
from decimal import Decimal
from typing import List, Optional, Dict
from .utils import BitcoinRPC, Prompter
from .validation import Validator
from .config import MIN_FEE, MAX_FEE, CONF_TARGET
class Transaction:
    def __init__(self, rpc: BitcoinRPC, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.test = test
        self.rpc = rpc
        self.validator = Validator(rpc, verbose=verbose, test=test)

    def calculate_fees(self, use_p2sh: bool = False, n_utxo: int = 1) -> Decimal:
        fee_rate = Decimal(self.rpc.estimatesmartfee(CONF_TARGET)['feerate'])

        tx_size = 300 if use_p2sh else 222
        tx_size += n_utxo * 148

        fee = (fee_rate * tx_size / 1000).quantize(Decimal('0.00000001'))
        fee = max(MIN_FEE, fee)
        fee = min(MAX_FEE, fee)

        if self.verbose:
            print(f"Fee: {fee} BTC")
            print(f"Fee rate: {fee_rate} sat/vB")
            print(f"Tx size: {tx_size} bytes")

        return fee

    def build_stake_tx(self, utxos: List[str], amount_btc: str, change_address: str, 
                         op_return_data: str, script_info: Dict, use_p2sh: bool = False) -> Optional[Dict]:
        amount = Decimal(amount_btc).quantize(Decimal('0.00000001'))
        total_input = Decimal('0')
        inputs = [] 
        for utxo in utxos:
            txid, vout = utxo.split(':')
            vout = int(vout)
            utxo_info = self.rpc.gettxout(txid, vout, True)
            if not utxo_info:
                print(f"UTXO {txid}:{vout} not found or spent")
                return None
            utxo_amount = Decimal(str(utxo_info['value'])).quantize(Decimal('0.00000001'))
            total_input += utxo_amount
            inputs.append({
                'txid': txid,
                'vout': vout,
                'scriptPubKey': utxo_info['scriptPubKey']['hex'],
                'amount': str(utxo_info['value'])
            })
            
        fee = self.calculate_fees(use_p2sh, len(utxos))
        change = (total_input - amount - fee).quantize(Decimal('0.00000001'))
        if change < 0:
            print(f"Insufficient funds: total_input: {total_input} BTC, amount: {amount} BTC, fee: {fee} BTC")
            return None
            
        outputs = {}
        address = script_info['p2sh']
        if not use_p2sh:
            address = script_info['segwit']['address']
        outputs[address] = f"{amount:.8f}"
        if change > Decimal('0.00000546'):
            outputs[change_address] = f"{change:.8f}"
        outputs['data'] = op_return_data
        
        if self.verbose:
            print(f"Total input: {total_input} BTC")
            print(f"Amount: {amount} BTC")
            print(f"Fee: {fee} BTC") 
            print(f"Change: {change} BTC")
            
        raw_tx = self.rpc.createrawtransaction(
            inputs=inputs,
            outputs=outputs,
            locktime=0 # Must be 0 for broadcast immediately
        )
        if not raw_tx:
            return None
        if self.verbose:
            self.rpc.decoderawtransaction(raw_tx)
        
        print("\nPaste or type your private key (input will not be shown)")
        privkey = Prompter.get_hidden_input("Enter private key for signing: ")
        print("Private key received")

        privkeys = [privkey for _ in range(len(inputs))]
        signed_result = self.sign_transaction(raw_tx, privkeys, inputs)
        if not signed_result:
            return None
        
        # signed_result['privkey'] = privkey
        return signed_result

    def sign_transaction(self, raw_tx: str, privkeys: List[str], signing_inputs: List[Dict]) -> Optional[Dict]:
        if self.verbose:
            print("\nSigning inputs:")
            print(json.dumps(signing_inputs, indent=2))
        
        signed_result = self.rpc.signrawtransactionwithkey(raw_tx, privkeys, signing_inputs)
        if signed_result['complete']:
            return {
                'signed_tx': signed_result['hex'],
            }
        else:
            print(f"\nError: {signed_result['errors'][0]['error']}")
            print("Error: Transaction signing failed!")
            
            return None

    def broadcast(self, signed_tx: str) -> Optional[str]:
        try:
            if self.verbose:
                self.rpc.decoderawtransaction(signed_tx)
            if not Prompter.confirm_action("Confirm broadcast the transaction?"):
                return None
            if self.test:
                return "test_txid"
            return self.rpc.sendrawtransaction(signed_tx)
        except Exception as e:
            print(f"Error: {e}")
            return None

    def build_spend_tx(
        self,
        utxo: str,
        address: str,
        redeem_script: str,
        script_info: Dict
    ) -> Optional[str]:
        """Build and sign unlock transaction"""
        try:
            # Parse UTXO string
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
            
            # Get locktime from script
            locktime = int(script_info['asm'].split()[0])
            
            # Determine if it's P2SH or P2WSH
            script_type = utxo_info['scriptPubKey']['type']
            use_p2sh = script_type == 'scripthash'
            
            # Get amount and calculate fee
            amount = Decimal(utxo_info['value'])

            fee = self.calculate_fees(use_p2sh)
            
            # Calculate final amount
            spend_amount = amount - fee
            if spend_amount <= 0:
                print(f"Error: Fee ({fee} BTC) is larger than UTXO amount ({amount} BTC)")
                return None
            
            # Create inputs with nSequence for CLTV
            inputs = [{
                'txid': txid,
                'vout': vout,
                'sequence': 0xfffffffe  # Enable CLTV
            }]
            
            # Create outputs
            outputs = {address: f"{spend_amount:.8f}"}
            
            if self.verbose:
                print("\nTransaction details:")
                print(f"  Input UTXO: {txid}:{vout}")
                print(f"  Amount: {amount} BTC")
                print(f"  Fee: {fee} BTC")
                print(f"  Output: {spend_amount} BTC")
                print(f"  Address: {address}")
                print(f"  Locktime: {locktime}")
                print(f"  Type: {'P2SH' if use_p2sh else 'P2WSH'}")
            
            # Create raw transaction with locktime
            raw_tx = self.rpc.createrawtransaction(
                inputs=inputs,
                outputs=outputs,
                locktime=locktime
            )
            
            if not raw_tx:
                print("Error: Failed to create raw transaction")
                return None
            
            # Get private key from user
            print("\nPaste or type your private key (input will not be shown)")
            privkey = Prompter.get_hidden_input("Enter private key for signing: ")
            if not privkey:
                print("Error: No private key provided")
                return None
            
            # Prepare signing input
            signing_input = {
                'txid': txid,
                'vout': vout,
                'scriptPubKey': utxo_info['scriptPubKey']['hex'],
                'amount': amount
            }
            
            # Add script info based on type
            if use_p2sh:
                signing_input['redeemScript'] = redeem_script
            else:  # P2WSH
                signing_input.update({
                    'witnessScript': redeem_script,
                    'amount': amount,  # Need to set amount again for P2WSH
                    'witnessVersion': 0
                })
            
            if self.verbose:
                print("\nSigning input:")
                print(json.dumps(signing_input, indent=2))
            
            # Sign transaction
            signed = self.rpc.signrawtransactionwithkey(raw_tx, [privkey], [signing_input])
            
            if not signed or not signed.get('complete'):
                print("Error: Failed to sign transaction")
                if self.verbose and signed:
                    print(json.dumps(signed, indent=2))
                return None
            
            return signed['hex']
            
        except Exception as e:
            print(f"Error: Failed to build spend transaction: {e}")
            return None
