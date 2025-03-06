#!/bin/bash
set -e
set -u

chain=regtest

privkey=cNeZbvYbvFBuVUeZenfFPNBG3RfXs2hXeSQujAQax4qjJwGMnqyh
addr=mmSpz7FsRX2L4k8DY4oHNWHq5qSoij921z
pubkey=020ed9e628e3d032efa667b3cd325d502bed94658c3d012d41c2ab1b1339092320
fee=0.00002000

function bcc() {
    #/Volumes/newver/code/bitcoin-28.1/src/bitcoin-cli --conf=/Volumes/newver/code/bitcoin-28.1/src/bitcoin.conf "$@"
    bitcoin-cli -chain=$chain "$@"
}

function mine_and_transfer() {
    local addr=$1
    local privkey=$2
    local blocks=${3:-102}

    bcc generatetoaddress "$blocks" "$addr" >&2

    local height=$(bcc getblockcount)
    height=$((height - blocks + 1))
    local hash=$(bcc getblockhash "$height")
    local txid=$(bcc getblock "$hash" | jq -r '.tx[0]')

    local amount=$(bcc gettxout "$txid" 0 | jq '.value')
    amount=$(echo "scale=8; $amount - $fee" | bc | awk '{printf "%.8f", $0}')

    local rawtx=$(bcc createrawtransaction \
        '[{"txid":"'$txid'","vout":0}]' \
        '{"'$addr'":'$amount'}')

    local signedtx=$(bcc signrawtransactionwithkey "$rawtx" '["'$privkey'"]' | jq -r '.hex')
    local txid2=$(bcc sendrawtransaction "$signedtx")

    bcc generatetoaddress 1 "$addr" >&2

    echo "$txid2"
}

function build_bitcoin_script_hex() {
  local lockts="$1"
  local pubkey="$2"

  local OP_CHECKLOCKTIMEVERIFY="b1"
  local OP_DROP="75"
  local OP_CHECKSIG="ac"

  local time_le=$(printf "%x" "$lockts" | sed -E 's/([0-9a-f]{2})/\1 /g' | awk '{for (i=4; i>=1; i--) printf $i} END {print ""}')

  local script="04${time_le}${OP_CHECKLOCKTIMEVERIFY}${OP_DROP}21${pubkey}${OP_CHECKSIG}"

  echo "$script"
}

function create_cltv_tx() {
    local txid="$1"
    local vout="$2"
    local segwit_addr="$3"
    local change_addr="$4"
    local op_return="$5"
    local lockts="${6:-0}"

    local input_amount=$(bcc gettxout $txid $vout |jq '.value')
    
    local lock_amount=0.00100000
    local change_amount=$(echo "scale=8; $input_amount - $lock_amount - $fee" | bc | awk '{printf "%.8f", $0}')

    local rawtx=$(bcc createrawtransaction \
        '[{"txid": "'$txid'", "vout": '$vout'}]' \
        '{"'$segwit_addr'": "'$lock_amount'", "'$change_addr'": "'$change_amount'", "data": "'$op_return'"}' \
        $lockts)

    echo "$rawtx"
}

function sign_cltv_tx() {
    local rawtx="$1"
    local txid="$2" 
    local vout="$3"
    local privkey="$4"
    
    local utxo_info=$(bcc gettxout $txid $vout)
    local scriptPubKey=$(echo "$utxo_info" | jq -r '.scriptPubKey.hex')
    local amount=$(echo "$utxo_info" | jq -r '.value')

    local prevtx='[{
        "txid": "'$txid'",
        "vout": '$vout',
        "scriptPubKey": "'$scriptPubKey'",
        "amount": "'$amount'"
    }]'

    local signedtx=$(bcc signrawtransactionwithkey "$rawtx" '["'$privkey'"]' "$prevtx" | jq -r '.hex')
    
    echo "$signedtx"
}

function create_p2wsh_cltv_tx() {
    local privkey=$1
    local addr=$2
    local redeem_script=$3
    local op_return=$4
    local txid=$5
    local vout=${6:-0}

    local segwit_addr=$(bcc decodescript "$redeem_script" | jq -r '.segwit.address')
    
    local rawtx=$(create_cltv_tx "$txid" "$vout" "$segwit_addr" "$addr" "$op_return")
    
    local signedtx=$(sign_cltv_tx "$rawtx" "$txid" "$vout" "$privkey")
    
    local txid=$(bcc sendrawtransaction "$signedtx")
    
    echo "$txid"
}

function spend_p2wsh_cltv_tx() {
    local txid=$1          
    local redeem_script=$2  
    local privkey=$3        
    local addr=$4      
    local lockts=$5
    local vout=${6:-0}      

    local utxo_info=$(bcc gettxout $txid $vout)
    local input_amount=$(echo "$utxo_info" | jq -r '.value')

    local send_amount=$(echo "scale=8; $input_amount - $fee" | bc | awk '{printf "%.8f", $0}')

    local rawtx=$(bcc createrawtransaction '[{"txid":"'$txid'","vout":'$vout',"sequence":4294967294}]' '[{"'$addr'":'$send_amount'}]' $lockts)
    
    local prevtx='[{
        "txid": "'$txid'",
        "vout": '$vout',
        "scriptPubKey": "'$(echo "$utxo_info" | jq -r '.scriptPubKey.hex')'",
        "witnessScript": "'$redeem_script'",
        "amount": "'$input_amount'"
    }]'

    # can't sign with this method
    # local signedtx=$(bcc signrawtransactionwithkey "$rawtx" '["'$privkey'"]' "$prevtx" | jq -r '.hex')
    
    # python spend_p2wsh.py \
    # --private-key cNeZbvYbvFBuVUeZenfFPNBG3RfXs2hXeSQujAQax4qjJwGMnqyh \
    # --utxo 29722452aa38204350f944db8a6a82eda46c85cba742e900c8a122ea9c4269da:0 \
    # --amount 0.001 \
    # --redeem-script 045b37c967b17521020ed9e628e3d032efa667b3cd325d502bed94658c3d012d41c2ab1b1339092320ac
    local signedtx=$(python3 spend_p2wsh.py \
        --private-key $privkey \
        --utxo $txid:$vout \
        --amount $input_amount \
        --redeem-script $redeem_script \
        --network $chain \
        --payto-address $addr \
        --fee $fee)
    
    local new_txid=$(bcc sendrawtransaction "$signedtx")
    
    bcc generatetoaddress 1 "$addr" >&2
    
    echo "$new_txid"
}

locksecs=10
nowts=$(date +%s)
lockts=$((nowts + locksecs))
redeem_script=$(build_bitcoin_script_hex "$lockts" "$pubkey")
op_return="4653545017710000000000000000000000000000000000000800fd24b690f81d85390ffac82fa9930de1629c14f600000001001e"

txid2=$(mine_and_transfer "$addr" "$privkey" 120)

txid3=$(create_p2wsh_cltv_tx  "$privkey" "$addr" "$redeem_script" "$op_return" "$txid2" )

echo "waiting $locksecs seconds"
sleep $locksecs
txid4=$(spend_p2wsh_cltv_tx "$txid3" "$redeem_script" "$privkey" "$addr" $lockts)

echo "lockts: $lockts" 
echo "redeem_script: $redeem_script"
echo "txid2: $txid2"
echo "txid3: $txid3"
echo "txid4: $txid4"

exit 0
