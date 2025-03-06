import hashlib
import argparse

from bitcoin import SelectParams
from bitcoin.core import b2x, lx, COIN, COutPoint, CMutableTxOut, CMutableTxIn, CMutableTransaction, CTxInWitness, CTxWitness
from bitcoin.core.script import CScript, CScriptWitness, OP_0, OP_CHECKSIG, SignatureHash, SIGHASH_ALL, SIGVERSION_WITNESS_V0, OP_CHECKLOCKTIMEVERIFY, OP_DROP
from bitcoin.wallet import CBitcoinSecret, CBitcoinAddress, P2WSHBitcoinAddress

def _create_and_sign_p2wsh_tx(txin_redeemScript:CScript, network:str, private_key:str, utxo_txid:str, utxo_vout:int, payto_address:str, amount:int, fee:int, lockts:int=None):
    # print("All params: ", txin_redeemScript, network, private_key, utxo_txid, utxo_vout, payto_address, amount, fee, lockts)
    SelectParams(network)
    seckey = CBitcoinSecret(private_key)
    
    # txin_scriptHash = hashlib.sha256(txin_redeemScript).digest()
    # txin_scriptPubKey = CScript([OP_0, txin_scriptHash])
    # txin_p2wsh_address = P2WSHBitcoinAddress.from_scriptPubKey(txin_scriptPubKey)

    # print("lockts: ", lockts)
    # print("redeemScript", b2x(txin_redeemScript))
    # print("scriptPubKey", b2x(txin_scriptPubKey))
    # print('Pay to:', str(txin_p2wsh_address))

    txid = lx(utxo_txid)
    vout = utxo_vout
    amount_less_fee = amount - fee

    txin = CMutableTxIn(COutPoint(txid, vout))
    txin.nSequence = 0xFFFFFFFE

    destination_address = CBitcoinAddress(payto_address).to_scriptPubKey()
    txout = CMutableTxOut(amount_less_fee, destination_address)

    tx = CMutableTransaction([txin], [txout])
    if lockts is not None:
        tx.nLockTime = lockts

    sighash = SignatureHash(script=txin_redeemScript, txTo=tx, inIdx=0,
                           hashtype=SIGHASH_ALL, amount=amount, 
                           sigversion=SIGVERSION_WITNESS_V0)

    sig = seckey.sign(sighash) + bytes([SIGHASH_ALL])

    witness = CScriptWitness([sig, txin_redeemScript])
    tx.wit = CTxWitness([CTxInWitness(witness)])

    return b2x(tx.serialize())

def sign_p2wsh_cltv_with_lockts(network, private_key, lockts:int, utxo_txid, utxo_vout, payto_address, amount, fee):
    """
    Sign P2WSH transaction with CLTV
    """
    SelectParams(network)  # Move network selection here
    seckey = CBitcoinSecret(private_key)
    pubkey = seckey.pub.hex()
    # print("your pubkey: ", pubkey)

    locktime = lockts.to_bytes(4, byteorder='little')
    txin_redeemScript = CScript([
        locktime, 
        OP_CHECKLOCKTIMEVERIFY, 
        OP_DROP,
        bytes.fromhex(pubkey), 
        OP_CHECKSIG
    ])

    return _create_and_sign_p2wsh_tx(
        txin_redeemScript, network, private_key, utxo_txid, 
        utxo_vout, payto_address, amount, fee, lockts
    )

def sign_p2wsh_cltv_with_script(network, private_key, redeem_script, utxo_txid, utxo_vout, payto_address, amount, fee):
    """
    Sign P2WSH transaction with a custom redeem script
    """
    SelectParams(network)  # Move network selection here
    script_bytes = bytes.fromhex(redeem_script)
    txin_redeemScript = CScript(script_bytes)
    script_elements = list(txin_redeemScript)
    
    # print("script_elements: ", script_elements)
    # print("len(script_elements): ", len(script_elements), "len(script_elements[0]): ", len(script_elements[0]), "script_elements[1]: ", script_elements[1])

    lockts = None
    if len(script_elements) >= 2 and len(script_elements[0]) == 4 and script_elements[1] == OP_CHECKLOCKTIMEVERIFY:
        lockts = int.from_bytes(script_elements[0], byteorder='little')
        # print(f"Parsed locktime from script: {lockts}")

    return _create_and_sign_p2wsh_tx(
        txin_redeemScript, network, private_key, utxo_txid, 
        utxo_vout, payto_address, amount, fee, lockts
    )

def parse_args(default_params):
    parser = argparse.ArgumentParser(description='Create and sign P2WSH transaction')
    
    parser.add_argument('--private-key', required=True, help='Private key in WIF format')
    parser.add_argument('--utxo', required=True, help='UTXO in format txid:vout')
    parser.add_argument('--amount', required=True, type=float, help='Amount in BTC')
    parser.add_argument('--redeem-script', required=True, help='Hex encoded redeem script')
    
    parser.add_argument('--network', default=default_params['network'], 
                        help=f'Bitcoin network (default: {default_params["network"]})')
    parser.add_argument('--payto-address', default=default_params['payto_address'], 
                        help=f'Destination address (default: {default_params["payto_address"]})')
    parser.add_argument('--fee', type=float, default=default_params['fee']/COIN, 
                        help=f'Fee in BTC (default: {default_params["fee"]/COIN})')
    
    args = parser.parse_args()
    
    try:
        utxo_txid, utxo_vout = args.utxo.split(':')
        utxo_vout = int(utxo_vout)
    except ValueError:
        parser.error("--utxo must be in format txid:vout")

    return {
        'network': args.network,
        'private_key': args.private_key,
        'utxo_txid': utxo_txid,
        'utxo_vout': utxo_vout,
        'payto_address': args.payto_address,
        'amount': int(args.amount * COIN),
        'fee': int(args.fee * COIN),
        'redeem_script': args.redeem_script
    }

if __name__ == "__main__":
    default_params = {
        'network': 'regtest',
        'private_key': 'cNeZbvYbvFBuVUeZenfFPNBG3RfXs2hXeSQujAQax4qjJwGMnqyh',
        'utxo_txid': '29722452aa38204350f944db8a6a82eda46c85cba742e900c8a122ea9c4269da',
        'utxo_vout': 0,
        'payto_address': 'mmSpz7FsRX2L4k8DY4oHNWHq5qSoij921z',
        'amount': int(0.0010 * COIN),
        'fee': int(0.00002 * COIN),
        'redeem_script': '045b37c967b17521020ed9e628e3d032efa667b3cd325d502bed94658c3d012d41c2ab1b1339092320ac'
    }

    params = parse_args(default_params)
    
    tx_hex = sign_p2wsh_cltv_with_script(**params)
    print(tx_hex)

