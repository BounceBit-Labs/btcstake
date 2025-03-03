#!/usr/bin/env python3

import json
from decimal import Decimal
from typing import List, Optional, Dict
from .utils import BitcoinRPC, Prompter
from .validation import Validator

class Transaction:
    def __init__(self, rpc: BitcoinRPC, verbose: bool = False, test: bool = False):
        self.verbose = verbose
        self.test = test
        self.rpc = rpc
        self.validator = Validator(rpc, verbose=verbose, test=test)

    def calculate_fees(self, use_p2sh: bool = False, conf_target: int = 6) -> Decimal:
        fee_rate = Decimal(self.rpc.estimatesmartfee(conf_target)['feerate'])
        tx_size = 300
        fee = (fee_rate * tx_size / 1000).quantize(Decimal('0.00000001'))
        min_fee = Decimal('0.00001001')
        if fee < min_fee:
            fee = min_fee
        if self.verbose:
            print(f"Fee: {fee:.8f} BTC")
        return fee

    def build_transaction(self, utxos: List[str], amount_btc: str, change_address: str, 
                         op_return_data: str, redeem_script: str, use_p2sh: bool = False) -> Optional[Dict]:
        amount = Decimal(amount_btc).quantize(Decimal('0.00000001'))
        if not self.validator.validate_address(change_address) or \
           not self.validator.validate_utxos(utxos, amount) or \
           not self.validator.validate_script(redeem_script):
            return None
            
        total_input = Decimal('0')
        inputs = []
        script_info = self.rpc.decodescript(redeem_script)
        if not script_info:
            return None
            
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
                'scriptPubKey': utxo_info['scriptPubKey']['hex']
            })
            
        fee = self.calculate_fees(use_p2sh)
        change = (total_input - amount - fee).quantize(Decimal('0.00000001'))
        if change < 0:
            print("Insufficient funds")
            return None
            
        outputs = {}
        outputs[script_info['p2sh' if use_p2sh else 'segwit']['address']] = f"{amount:.8f}"
        if change > Decimal('0.00000546'):
            outputs[change_address] = f"{change:.8f}"
        outputs['data'] = op_return_data
        
        if self.verbose:
            print(f"Total input: {total_input} BTC")
            print(f"Amount: {amount} BTC")
            print(f"Fee: {fee} BTC") 
            print(f"Change: {change} BTC")
            
        raw_tx = self.create_raw_tx(inputs, outputs, redeem_script, use_p2sh)
        if not raw_tx:
            return None
        return self.sign_transaction(raw_tx, inputs, redeem_script, use_p2sh)

    def create_raw_tx(self, inputs: List[Dict], outputs: Dict, redeem_script: str, use_p2sh: bool = False) -> Optional[str]:
        try:
            script_info = self.rpc.decodescript(redeem_script)
            if not script_info:
                return None
            locktime = int(script_info['asm'].split()[0])
            for inp in inputs:
                inp['sequence'] = 0xfffffffe
            raw_tx = self.rpc.createrawtransaction(
                inputs=inputs,
                outputs=outputs,
                replaceable=not use_p2sh,
                locktime=locktime
            )
            if self.verbose:
                print(self.rpc.decoderawtransaction(raw_tx))
            return raw_tx
        except Exception as e:
            print(f"Error: {e}")
            return None

    def sign_transaction(self, raw_tx: str, inputs: List[Dict], redeem_script: str, use_p2sh: bool = False) -> Optional[Dict]:
        try:
            print("\nPaste or type your private key (input will not be shown)")
            privkey = Prompter.get_hidden_input("Enter private key for signing: ")
            print("Private key received")
            
            signing_inputs = []
            for inp in inputs:
                signing_inputs.append({
                    'txid': inp['txid'],
                    'vout': inp['vout'],
                    'scriptPubKey': inp['scriptPubKey']
                })
            
            if self.verbose:
                print("\nSigning inputs:")
                print(json.dumps(signing_inputs, indent=2))
            
            signed_result = self.rpc.signrawtransactionwithkey(raw_tx, [privkey], signing_inputs)
            if signed_result['complete']:
                return {
                    'signed_tx': signed_result['hex'],
                    'privkey': privkey
                }
            else:
                print("Error: Transaction signing failed!")
                if self.verbose:
                    print(json.dumps(signed_result, indent=2))
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def broadcast(self, signed_tx: str) -> Optional[str]:
        try:
            if self.verbose:
                print(self.rpc.decoderawtransaction(signed_tx))
            if not Prompter.confirm_action("Broadcast?"):
                return None
            if self.test:
                return "test_txid"
            return self.rpc.sendrawtransaction(signed_tx)
        except Exception as e:
            print(f"Error: {e}")
            return None

    def _confirm_action(self, warning_msg: str) -> bool:
        return Prompter.confirm_action(
            "Do you want to proceed anyway?",
            warning_msg + "\nPlease verify that you are using the correct private key!"
        )

    def verify_spend_signature(self, raw_tx: str, privkey: str, pubkey: str, redeem_script: str, use_p2sh: bool = False) -> bool:
        """Verify if the private key matches pubkey and can spend the first output"""
        try:
            # Get first output info
            decoded = self.rpc.decoderawtransaction(raw_tx)
            if not decoded or 'vout' not in decoded or not decoded['vout']:
                warning = "Error: Failed to decode transaction"
                return self._confirm_action(warning)
            
            vout = decoded['vout'][0]
            
            # Verify scriptPubKey is P2WSH
            script_info = self.rpc.decodescript(redeem_script)
            expected_script_hash = script_info['segwit']['hex'][4:]  # Remove '0020' prefix
            actual_script_hash = vout['scriptPubKey']['hex'][4:]  # Remove '0020' prefix
            
            if expected_script_hash != actual_script_hash:
                if self.verbose:
                    print(f"Expected script hash: {expected_script_hash}")
                    print(f"Actual script hash: {actual_script_hash}")
                warning = "Error: Script hash mismatch"
                return self._confirm_action(warning)
            
            # Get locktime from redeem script
            locktime = int(script_info['asm'].split()[0])  # First number in ASM is locktime
            
            # Create a dummy transaction spending the first output
            dummy_inputs = [{
                'txid': decoded['txid'],
                'vout': 0,  # First output (the locked one)
                'sequence': 0xfffffffe  # Enable CLTV
            }]
            dummy_outputs = {
                "1111111111111111111114oLvT2": "0.00000001"  # Burn address
            }
            
            # Create dummy transaction with locktime
            dummy_tx = self.rpc.createrawtransaction(
                inputs=dummy_inputs,
                outputs=dummy_outputs,
                locktime=locktime  # Set locktime from script
            )
            
            if dummy_tx is None:
                warning = "Error: Failed to create test transaction"
                return self._confirm_action(warning)
            
            # Prepare signing input
            signing_input = {
                'txid': decoded['txid'],
                'vout': 0,
                'scriptPubKey': vout['scriptPubKey']['hex'],
                'amount': vout['value']
            }
            
            # Add script info based on type
            if use_p2sh:
                signing_input['redeemScript'] = redeem_script
            else:  # P2WSH
                signing_input.update({
                    'witnessScript': redeem_script,
                    'amount': vout['value'],
                    'witnessVersion': 0
                })
            
            if self.verbose:
                print("\nVerifying signature with input:")
                print(json.dumps(signing_input, indent=2))
            
            # Try to sign with the private key
            signed = self.rpc.signrawtransactionwithkey(dummy_tx, [privkey], [signing_input])
            
            if signed and signed.get('complete'):
                print("✓ Private key can spend the locked output")
                return True
            else:
                warning = "\nWarning: Could not verify that the private key can spend the locked output.\n" \
                         "This could mean:\n" \
                         "1. The private key does not match the configured public key\n" \
                         "2. The private key cannot spend the locked output"
                return self._confirm_action(warning)
                
        except Exception as e:
            warning = f"\nWarning: Failed to verify private key.\nError: {e}"
            return self._confirm_action(warning) 
        
    def build_spend_tx(
        self,
        utxo: str,
        address: str,
        redeem_script: str
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
            utxo_info = self.rpc.gettxout(txid, vout)
            if not utxo_info:
                print(f"Error: UTXO {txid}:{vout} not found or already spent")
                return None
            
            # Get script info and locktime
            script_info = self.rpc.decodescript(redeem_script)
            if not script_info:
                print("Error: Failed to decode redeem script")
                return None
            
            # Get locktime from script
            locktime = int(script_info['asm'].split()[0])
            
            # Determine if it's P2SH or P2WSH
            script_type = utxo_info['scriptPubKey']['type']
            use_p2sh = script_type == 'scripthash'
            
            # Get amount and calculate fee
            amount = Decimal(utxo_info['value'])
            
            fee_rate = self.rpc.estimatesmartfee(6)['feerate']
            tx_size = 300 if use_p2sh else 200  # P2SH is larger than P2WSH
            fee = Decimal(fee_rate) * tx_size / 1000000
            
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
