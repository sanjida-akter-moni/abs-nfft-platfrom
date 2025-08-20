# ABS Decentralized NFT Marketplace

A decentralized NFT Marketplace built on **ZKSync Era**, allowing users to **mint**, **list**, **buy**, and **view** unique NFTs. The project uses Solidity smart contracts, a Flask backend, and a responsive HTML/CSS/JavaScript frontend, leveraging **Web3.py** and **Filebase (S3 → IPFS)** for asset storage.

---

## Demo

* Video demo: [https://youtu.be/XQYFUFkpM48](https://youtu.be/XQYFUFkpM48)

---

## Features

* **Mint NFTs** — Upload an image, metadata is pushed to IPFS via Filebase, and a new ERC-721 token is minted on ZKSync Era.
* **List & Unlist** — Set a sale price for owned NFTs and list/unlist them on the marketplace.
* **Buy NFTs** — Purchase listed NFTs from the marketplace UI.
* **Profile Dashboard** — View wallet address, balance, owned NFTs, and listing controls.
* **Marketplace View** — Browse all NFTs currently listed for sale.

---

## Tech Stack

* **Smart Contracts:** Solidity (`ERC721URIStorage`) deployed to **ZKSync Era**
* **Backend:** Python, Flask, Web3.py
* **Frontend:** HTML5, CSS3, JavaScript (responsive)
* **Storage:** Filebase (S3-compatible) → IPFS
* **Environment/Tools:** Hardhat, dotenv, Node.js

---

## Prerequisites

* Node.js & npm
* Python 3.8+
* Hardhat (`npm install --save-dev hardhat`)
* Filebase account with S3 credentials (Access Key, Secret Key, Bucket)
* ZKSync Era RPC endpoint & wallet private key

---

## Quick Start

> Clone, install, configure environment variables, deploy contracts, run backend and frontend.

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd nft-marketplace-zksync

# 2. Install frontend & hardhat deps
npm install

# 3. Install backend deps (recommended: virtualenv)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Add environment variables
# .env (example)
# ZKSYNC_RPC_URL=https://your-zksync-era-rpc
# PRIVATE_KEY=0x...
# FILEBASE_KEY=your-filebase-access-key
# FILEBASE_SECRET=your-filebase-secret
# FILEBASE_BUCKET=your-bucket

# 5. Compile & deploy contracts (Hardhat)
npx hardhat compile
npx hardhat run scripts/deploy.js --network zksync

# 6. Run backend
export FLASK_APP=app.py
flask run --port 5000

# 7. Serve frontend (or open index.html)
npm run dev
```

---

## Project Structure (example)

```
/contracts         # Solidity contracts (ERC721URIStorage)
/scripts           # Hardhat deploy scripts
/backend           # Flask backend, Web3.py, Filebase upload helpers
/frontend          # HTML/CSS/JS frontend
/tests             # smart contract & integration tests
.env.example       # example env variables
README.md
```

---

## Smart Contract Notes

* Contract is based on `ERC721URIStorage` to store tokenURIs pointing to Filebase/IPFS.

* Marketplace listing logic can be implemented either on-chain (marketplace contract) or off-chain via backend escrow and contract `safeTransferFrom` flows. This repo provides an on-chain marketplace contract with:

  * `listItem(tokenId, price)`
  * `cancelListing(tokenId)`
  * `buyItem(tokenId)`
  * owner-only `withdraw` for accumulated sales (if applicable)

* Use `hardhat` + `ethers` for deployment scripts. Make sure to fund your deployer on the chosen ZKSync testnet/mainnet.

---

## Storage (Filebase → IPFS)

* Images and metadata JSON are uploaded to Filebase using S3-compatible API.
* Metadata schema example:

```json
{
  "name": "Cool NFT",
  "description": "Description of the NFT",
  "image": "ipfs://<CID>/image.png",
  "attributes": [{ "trait_type": "Rarity", "value": "Legendary" }]
}
```

---

## Environment & Security

* Never commit private keys or Filebase secrets. Use `.env` and keep secrets out of the repo.
* For production, consider a secure secret manager and revoke keys if leaked.

---

## Testing

* Unit tests for smart contracts using Hardhat & Mocha/Chai.
* Integration tests (optional) that exercise backend upload → mint → list → buy flows against a ZKSync testnet.

---

## Roadmap / Ideas

* On-chain auction support (Dutch / English auctions)
* Royalties (ERC-2981 or custom royalty split)
* Better indexing & search (TheGraph or backend indexing)
* Gas-optimizations and meta-transactions

---

## Contributing

* Tahmid Hasan Rafi (writing smart contract, working on backend, frontend )
* Alvi Hasan Emon ( writing report)
* Sanjida Akter moni (working on frontend)
---

## License

MIT

---

## Contact

Your Name — Tahmid Rafi
Project video demo: [https://youtu.be/XQYFUFkpM48](https://youtu.be/XQYFUFkpM48)
