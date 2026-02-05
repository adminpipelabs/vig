"""
Vig Token Approvals — Approve USDC and CTF tokens for Polymarket trading.
Run this once before starting the bot in live mode.
"""
import os
import time
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# Polygon RPC - use Alchemy if available, fallback to others
RPC_URLS = [
    os.getenv("POLYGON_RPC_URL", "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"),
    "https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm",
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
]

w3 = None
for rpc_url in RPC_URLS:
    if not rpc_url:
        continue
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        # Test connection
        w3.eth.block_number
        print(f"Connected to RPC: {rpc_url[:50]}...")
        break
    except Exception as e:
        print(f"Failed to connect to {rpc_url[:50]}: {e}")
        continue

if not w3:
    print("ERROR: Could not connect to any Polygon RPC endpoint")
    exit(1)

# Load config from .env
PRIVATE_KEY = os.getenv("POLYGON_PRIVATE_KEY", "")
FUNDER_ADDRESS = os.getenv("POLYGON_FUNDER_ADDRESS", "")

if not PRIVATE_KEY:
    print("ERROR: POLYGON_PRIVATE_KEY not set in .env")
    exit(1)

if not FUNDER_ADDRESS:
    print("ERROR: POLYGON_FUNDER_ADDRESS not set in .env")
    exit(1)

# Contract addresses
USDC = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Polygon USDC
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # Conditional Token Framework
EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Polymarket Exchange
NEG_RISK = "0xC5d563A36AE78145C45a50134d48A1215220f80a"  # NegRisk Exchange

# ABIs
ERC20_APPROVE_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

ERC1155_SET_APPROVAL_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_operator", "type": "address"},
            {"name": "_approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function"
    }
]

# Get account
account = w3.eth.account.from_key(PRIVATE_KEY)
address = account.address

print(f"Wallet: {address}")
print(f"Chain ID: {w3.eth.chain_id}")
print(f"Balance: {w3.eth.get_balance(address) / 1e18:.4f} MATIC")
print()

# Check current approvals first
print("Checking current approvals...")
ALLOWANCE_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
IS_APPROVED_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}]

usdc_check = w3.eth.contract(address=USDC, abi=ALLOWANCE_ABI)
ctf_check = w3.eth.contract(address=CTF, abi=IS_APPROVED_ABI)

def safe_call(func, default=False):
    """Safely call contract function with retry"""
    for attempt in range(3):
        try:
            return func()
        except Exception as e:
            if "rate limit" in str(e).lower() or "too many requests" in str(e).lower():
                if attempt < 2:
                    wait = (attempt + 1) * 10
                    print(f"  Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
            print(f"  Warning: {e}")
            return default
    return default

a1 = safe_call(lambda: usdc_check.functions.allowance(address, EXCHANGE).call(), 0)
time.sleep(2)
a2 = safe_call(lambda: usdc_check.functions.allowance(address, NEG_RISK).call(), 0)
time.sleep(2)
a3 = safe_call(lambda: ctf_check.functions.isApprovedForAll(address, EXCHANGE).call(), False)
time.sleep(2)
a4 = safe_call(lambda: ctf_check.functions.isApprovedForAll(address, NEG_RISK).call(), False)

print(f"USDC -> Exchange: {'✓ Already approved' if a1 > 0 else '✗ Needs approval'}")
print(f"USDC -> NegRisk: {'✓ Already approved' if a2 > 0 else '✗ Needs approval'}")
print(f"CTF -> Exchange: {'✓ Already approved' if a3 else '✗ Needs approval'}")
print(f"CTF -> NegRisk: {'✓ Already approved' if a4 else '✗ Needs approval'}")
print()

if all([a1 > 0, a2 > 0, a3, a4]):
    print("All approvals already set! You're good to go.")
    exit(0)

print("Starting approvals...")
print()

def send_tx_with_retry(w3, signed_tx, max_retries=5):
    """Send transaction with retry logic for rate limits"""
    for attempt in range(max_retries):
        try:
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return tx_hash
        except Exception as e:
            error_str = str(e).lower()
            if "replacement transaction underpriced" in error_str:
                # Transaction was already sent, extract hash
                try:
                    tx_hash = w3.to_hex(signed_tx.hash)
                    print(f"  Transaction already sent: {tx_hash}")
                    return tx_hash
                except:
                    return None
            if "rate limit" in error_str or "too many requests" in error_str:
                wait_time = min(20, (attempt + 1) * 10)
                print(f"  Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise e
    raise Exception("Failed to send transaction after retries")

def wait_for_receipt_with_retry(w3, tx_hash, max_retries=10, timeout=120):
    """Wait for transaction receipt with retry logic"""
    start_time = time.time()
    for attempt in range(max_retries):
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            return receipt
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise Exception(f"Timeout waiting for receipt after {elapsed:.0f}s")
            
            error_str = str(e).lower()
            if "rate limit" in error_str or "too many requests" in error_str:
                if attempt < max_retries - 1:
                    wait = 10
                    print(f"  Rate limited waiting for receipt, waiting {wait}s...")
                    time.sleep(wait)
                    continue
            # Try checking if tx is already mined
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                return receipt
            except:
                pass
            raise e
    return None

def approve_token(token_address, spender_address, token_name, spender_name, is_erc1155=False):
    """Approve a token to a spender"""
    try:
        if is_erc1155:
            contract = w3.eth.contract(address=token_address, abi=ERC1155_SET_APPROVAL_ABI)
            tx = contract.functions.setApprovalForAll(
                Web3.to_checksum_address(spender_address),
                True
            ).build_transaction({
                "from": address,
                "nonce": w3.eth.get_transaction_count(address),
                "gas": 100000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            })
        else:
            contract = w3.eth.contract(address=token_address, abi=ERC20_APPROVE_ABI)
            max_uint256 = 2**256 - 1
            tx = contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                max_uint256
            ).build_transaction({
                "from": address,
                "nonce": w3.eth.get_transaction_count(address),
                "gas": 100000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            })
        
        signed = account.sign_transaction(tx)
        tx_hash = send_tx_with_retry(w3, signed)
        if not tx_hash:
            print(f"  ⚠ Could not get tx hash")
            return None
        
        print(f"  Transaction sent: {tx_hash.hex()}")
        receipt = wait_for_receipt_with_retry(w3, tx_hash)
        if not receipt:
            print(f"  ⚠ Could not get receipt, check: https://polygonscan.com/tx/{tx_hash.hex()}")
            return None
        
        if receipt.status == 1:
            gas_used = receipt.gasUsed * receipt.effectiveGasPrice / 1e18
            print(f"  ✓ Confirmed: https://polygonscan.com/tx/{tx_hash.hex()}")
            print(f"  Gas: {gas_used:.6f} MATIC")
            return gas_used
        else:
            print(f"  ✗ Transaction failed: {tx_hash.hex()}")
            return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

total_gas = 0

# 1. USDC -> Exchange
if a1 == 0:
    print("1/4 — USDC → Exchange...")
    time.sleep(2)
    gas = approve_token(USDC, EXCHANGE, "USDC", "Exchange")
    if gas:
        total_gas += gas
    time.sleep(3)
    print()

# 2. USDC -> NegRisk
if a2 == 0:
    print("2/4 — USDC → NegRisk Exchange...")
    time.sleep(2)
    gas = approve_token(USDC, NEG_RISK, "USDC", "NegRisk Exchange")
    if gas:
        total_gas += gas
    time.sleep(3)
    print()

# 3. CTF -> Exchange (ERC1155)
if not a3:
    print("3/4 — CTF → Exchange (ERC1155)...")
    time.sleep(2)
    gas = approve_token(CTF, EXCHANGE, "CTF", "Exchange", is_erc1155=True)
    if gas:
        total_gas += gas
    time.sleep(3)
    print()

# 4. CTF -> NegRisk Exchange (ERC1155)
if not a4:
    print("4/4 — CTF → NegRisk Exchange (ERC1155)...")
    time.sleep(2)
    gas = approve_token(CTF, NEG_RISK, "CTF", "NegRisk Exchange", is_erc1155=True)
    if gas:
        total_gas += gas
    time.sleep(3)
    print()

print("=" * 60)
print(f"✓ All approvals complete!")
print(f"Total gas cost: ~{total_gas:.4f} MATIC")
print()
print("You can now start the bot with: python3.11 main.py")
