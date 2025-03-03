#!/usr/bin/env python3

import argparse
import json
from decimal import Decimal
from typing import Optional

BB_CHAIN_ID = "1771"  # BB chain ID (6001) in hex
BB_CONTRACT = "0000000000000000000000000000000000000800"  # Fixed LSD contract address

def construct_op_return(bb_addr: str, days: int, amount_btc: str, verbose: bool = False) -> Optional[str]:
    try:
        if not bb_addr.startswith('0x'):
            print("Error: BB address must start with 0x")
            return None
            
        bb_addr = bb_addr[2:].lower()
        if len(bb_addr) != 40:
            print("Error: Invalid BB address length")
            return None
            
        try:
            amount_mbtc = int(Decimal(amount_btc) * 1000)
        except:
            print("Error: Invalid amount format")
            return None
            
        if amount_mbtc <= 0:
            print("Error: Amount must be positive")
            return None
            
        if days <= 0:
            print("Error: Days must be positive")
            return None
            
        data = (
            "46535450"  # FSTP
            + BB_CHAIN_ID
            + BB_CONTRACT
            + bb_addr.zfill(40)
            + f"{amount_mbtc:08x}"
            + f"{days:04x}"
        )
        
        # if verbose:
        print(f"BB Address: 0x{bb_addr}")
        print(f"Amount BTC: {amount_btc}")
        print(f"Amount mBTC: {amount_mbtc}")
        print(f"Days: {days}")
        print(f"OP_RETURN: {data}")
            
        return data
        
    except Exception as e:
        print(f"Error: Failed to construct OP_RETURN data: {e}")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description='Generate OP_RETURN data for BTC staking')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--config', default='stake_config.json', help='Config file path')
    parser.add_argument('--bb_address', help='BB chain address')
    parser.add_argument('--days', type=int, help='Lock days')
    parser.add_argument('--amount_btc', help='Amount in BTC')
    return parser.parse_args()

def main():
    args = parse_args()
    
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
    bb_address = args.bb_address or config.get('bb_address')
    days = args.days or config.get('days')
    amount_btc = args.amount_btc or config.get('amount_btc')
    
    # Validate required fields
    if not all([bb_address, days, amount_btc]):
        print("Error: Missing required parameters")
        print("Use --config=<config.json> or provide parameters via command line")
        return
        
    data = construct_op_return(bb_address, days, amount_btc, args.verbose)
    if data:
        print(f"\nOP_RETURN data: {data}")

if __name__ == '__main__':
    main() 