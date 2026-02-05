"""
Vig v1 — Corrected Token Approval Script
Approves USDC.e (not native USDC) and CTF tokens for Polymarket Exchange.
Polymarket CLOB uses USDC.e (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174) as collateral.
"""
import os
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

ALCHEMY_RPC = "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("POLYGON_FUNDER_ADDRESS")

# Contract addresses
USDC_E = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")  # USDC.e (CLOB collateral)
CTF = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")
EXCHANGE = Web3.to_checksum_address("0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E")
NEG_RISK_EXCHANGE = Web3.to_checksum_address("0xC5d563A36AE78145C45a50134d48A1215220f80a")

MAX_UINT256 = 2**256 - 1

ERC20_ABI = [{
    "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
    "name": "approve",
    "outputs": [{"name": "", "type": "bool"}],
    "stateMutability": "nonpayable",
    "type": "function"
}]

ERC1155_ABI = [{
    "inputs": [{"name": "operator", "type": "address"}, {"name": "approved", "type": "bool"}],
    "name": "setApprovalForAll",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
account = w3.eth.account.from_key(PRIVATE_KEY)
address = account.address

print(f"Wallet: {address}")
print(f"Chain ID: {w3.eth.chain_id}")
print(f"Balance: {w3.eth.get_balance(address) / 1e18:.4f} MATIC")
print()

# Check current approvals
print("Checking current approvals...")
ALLOWANCE_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
IS_APPROVED_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}]

usdc_e_check = w3.eth.contract(address=USDC_E, abi=ALLOWANCE_ABI)
ctf_check = w3.eth.contract(address=CTF, abi=IS_APPROVED_ABI)

a1 = usdc_e_check.functions.allowance(address, EXCHANGE).call()
a2 = usdc_e_check.functions.allowance(address, NEG_RISK_EXCHANGE).call()
a3 = ctf_check.functions.isApprovedForAll(address, EXCHANGE).call()
a4 = ctf_check.functions.isApprovedForAll(address, NEG_RISK_EXCHANGE).call()

print(f"USDC.e -> Exchange: {'✓ Already approved' if a1 > 0 else '✗ Needs approval'}")
print(f"USDC.e -> NegRisk: {'✓ Already approved' if a2 > 0 else '✗ Needs approval'}")
print(f"CTF -> Exchange: {'✓ Already approved' if a3 else '✗ Needs approval'}")
print(f"CTF -> NegRisk: {'✓ Already approved' if a4 else '✗ Needs approval'}")
print()

if all([a1 > 0, a2 > 0, a3, a4]):
    print("All approvals already set!")
    exit(0)

print("Starting approvals...")
print()

total_gas = 0

# 1. USDC.e -> Exchange
if a1 == 0:
    print("1/4 — USDC.e → Exchange...")
    contract = w3.eth.contract(address=USDC_E, abi=ERC20_ABI)
    tx = contract.functions.approve(EXCHANGE, MAX_UINT256).build_transaction({
        "from": address,
        "nonce": w3.eth.get_transaction_count(address),
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 137,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status == 1:
        gas_used = receipt.gasUsed * receipt.effectiveGasPrice / 1e18
        total_gas += gas_used
        print(f"  ✓ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")
        print(f"  Gas: {gas_used:.6f} MATIC")
    time.sleep(3)
    print()

# 2. USDC.e -> NegRisk
if a2 == 0:
    print("2/4 — USDC.e → NegRisk Exchange...")
    contract = w3.eth.contract(address=USDC_E, abi=ERC20_ABI)
    tx = contract.functions.approve(NEG_RISK_EXCHANGE, MAX_UINT256).build_transaction({
        "from": address,
        "nonce": w3.eth.get_transaction_count(address),
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 137,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status == 1:
        gas_used = receipt.gasUsed * receipt.effectiveGasPrice / 1e18
        total_gas += gas_used
        print(f"  ✓ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")
        print(f"  Gas: {gas_used:.6f} MATIC")
    time.sleep(3)
    print()

# 3. CTF -> Exchange (ERC1155)
if not a3:
    print("3/4 — CTF → Exchange (ERC1155)...")
    contract = w3.eth.contract(address=CTF, abi=ERC1155_ABI)
    tx = contract.functions.setApprovalForAll(EXCHANGE, True).build_transaction({
        "from": address,
        "nonce": w3.eth.get_transaction_count(address),
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 137,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status == 1:
        gas_used = receipt.gasUsed * receipt.effectiveGasPrice / 1e18
        total_gas += gas_used
        print(f"  ✓ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")
        print(f"  Gas: {gas_used:.6f} MATIC")
    time.sleep(3)
    print()

# 4. CTF -> NegRisk Exchange (ERC1155)
if not a4:
    print("4/4 — CTF → NegRisk Exchange (ERC1155)...")
    contract = w3.eth.contract(address=CTF, abi=ERC1155_ABI)
    tx = contract.functions.setApprovalForAll(NEG_RISK_EXCHANGE, True).build_transaction({
        "from": address,
        "nonce": w3.eth.get_transaction_count(address),
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 137,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status == 1:
        gas_used = receipt.gasUsed * receipt.effectiveGasPrice / 1e18
        total_gas += gas_used
        print(f"  ✓ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")
        print(f"  Gas: {gas_used:.6f} MATIC")
    time.sleep(3)
    print()

print("=" * 60)
print(f"✓ All approvals complete!")
print(f"Total gas cost: ~{total_gas:.4f} MATIC")
print()
print("⚠️  IMPORTANT: You also need USDC.e in your wallet for trading!")
print("   Current USDC.e balance: Check with your wallet")
print()
print("You can now start the bot with: python3.11 main.py")
