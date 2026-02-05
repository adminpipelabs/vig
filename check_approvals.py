from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://polygon-mainnet.g.alchemy.com/v2/7LOy-ke3YzoCRr1qimCRm"))

lines = open('.env').readlines()
env = {}
for l in lines:
    if '=' in l and not l.strip().startswith('#'):
        k,v = l.strip().split('=',1)
        env[k] = v

addr = env['POLYGON_FUNDER_ADDRESS']

USDC = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

ALLOWANCE_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
IS_APPROVED_ABI = [{"inputs":[{"name":"owner","type":"address"},{"name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}]

usdc = w3.eth.contract(address=USDC, abi=ALLOWANCE_ABI)
ctf = w3.eth.contract(address=CTF, abi=IS_APPROVED_ABI)

a1 = usdc.functions.allowance(addr, EXCHANGE).call()
a2 = usdc.functions.allowance(addr, NEG_RISK).call()
a3 = ctf.functions.isApprovedForAll(addr, EXCHANGE).call()
a4 = ctf.functions.isApprovedForAll(addr, NEG_RISK).call()

print("USDC -> Exchange:", "OK" if a1 > 0 else "NOT SET")
print("USDC -> NegRisk:", "OK" if a2 > 0 else "NOT SET")
print("CTF -> Exchange:", "OK" if a3 else "NOT SET")
print("CTF -> NegRisk:", "OK" if a4 else "NOT SET")
