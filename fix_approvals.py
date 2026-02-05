"""
Fix: Add missing Neg Risk Adapter approvals
Run once — adds the 2 missing approvals we skipped
"""
import os
import time
from web3 import Web3
from web3.constants import MAX_INT
from dotenv import load_dotenv

load_dotenv()

ALCHEMY_RPC = "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY")

w3 = Web3(Web3.HTTPProvider(ALCHEMY_RPC))
wallet = w3.eth.account.from_key(PRIVATE_KEY).address
print(f"Wallet: {wallet}")

# Contracts
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

erc20_abi = [{"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}]
erc1155_abi = [{"inputs": [{"name": "operator", "type": "address"}, {"name": "approved", "type": "bool"}], "name": "setApprovalForAll", "outputs": [], "stateMutability": "nonpayable", "type": "function"}]

usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=erc20_abi)
ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF), abi=erc1155_abi)

# Approval 1: USDC.e -> Neg Risk Adapter
print("5/6 — USDC.e → Neg Risk Adapter")
nonce = w3.eth.get_transaction_count(wallet)
tx = usdc.functions.approve(
    Web3.to_checksum_address(NEG_RISK_ADAPTER), int(MAX_INT, 0)
).build_transaction({"chainId": 137, "from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price})
signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120)
print(f"   ✅ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")

time.sleep(2)

# Approval 2: CTF -> Neg Risk Adapter
print("6/6 — CTF → Neg Risk Adapter")
nonce = w3.eth.get_transaction_count(wallet)
tx = ctf.functions.setApprovalForAll(
    Web3.to_checksum_address(NEG_RISK_ADAPTER), True
).build_transaction({"chainId": 137, "from": wallet, "nonce": nonce, "gasPrice": w3.eth.gas_price})
signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120)
print(f"   ✅ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")

print("\n🎉 All 6 approvals now complete!")
