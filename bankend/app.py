import os
import json
import time
import requests
from flask import Flask, render_template, request, redirect, session, jsonify
from web3 import Web3
from eth_account.messages import encode_defunct
from dotenv import load_dotenv
from backend.wallet_interact import prepare_nft_metadata, get_nfts_for_user, get_balance, get_nfts_for_sale

# Load environment first
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret123")
app.config['UPLOAD_FOLDER'] = 'uploads'

# Web3 setup
ZKSYNC_RPC = os.getenv("ZKSYNC_RPC", "https://sepolia.era.zksync.dev")
w3 = Web3(Web3.HTTPProvider(ZKSYNC_RPC))
CONTRACT_ADDRESS = Web3.to_checksum_address(os.getenv("CONTRACT_ADDRESS"))

# Load contract ABI
try:
    ABI_PATH = os.getenv("ABI_PATH", "artifacts-zk/contracts/ImageNFT.sol/ImageNFT.json")
    with open(ABI_PATH) as f:
        contract_data = json.load(f)
        abi = contract_data["abi"]
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
    print("Contract initialized successfully")
except Exception as e:
    print(f"Contract initialization error: {e}")
    abi = []
    contract = None

@app.before_request
def check_contract():
    if request.endpoint in ['create', 'mint', 'listings'] and not contract:
        return jsonify({"error": "Contract not initialized"}), 500

@app.route("/")
def index():
    user_address = session.get('wallet_address')
    return render_template("index.html", 
                           user_address=user_address,
                           contract_address=CONTRACT_ADDRESS)

# FIXED CONNECT WALLET ROUTE
@app.route("/connect", methods=["POST"])
def connect_wallet():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Missing JSON data"}), 400

    signature = data.get("signature")
    message = data.get("message")
    address = data.get("address")
    
    if not all([signature, message, address]):
        return jsonify({"success": False, "error": "Missing parameters"}), 400
    
    # Verify signature
    verified = verify_signature(message, signature, address)
    if verified:
        try:
            checksum_address = Web3.to_checksum_address(address)
            session['wallet_address'] = checksum_address
            return jsonify({"success": True})
        except ValueError as e:
            return jsonify({"success": False, "error": f"Invalid address: {str(e)}"}), 400
    return jsonify({"success": False, "error": "Signature verification failed"}), 401

@app.route("/disconnect", methods=["POST"])
def disconnect_wallet():
    session.pop('wallet_address', None)
    return redirect("/")

@app.route("/create", methods=["POST"])
def create_nft():
    if not session.get('wallet_address'):
        return jsonify({"success": False, "error": "Wallet not connected"}), 401
    
    wallet_address = session['wallet_address']
    name = request.form.get("name")
    description = request.form.get("description")
    file_type = request.form.get("file_type", "image")
    file = request.files.get("file")
    thumbnail = request.files.get("thumbnail")
    
    if not all([name, description, file]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    
    try:
        # Check file size (100MB)
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_length > 100 * 1024 * 1024:  # 100MB
            return jsonify({"success": False, "error": "File size exceeds 100MB limit"}), 400
        
        # Check thumbnail for video/audio
        if file_type in ['video', 'audio']:
            if not thumbnail:
                return jsonify({
                    "success": False, 
                    "error": "Thumbnail required for video/audio files"
                }), 400
            
            # Check thumbnail size
            thumbnail.seek(0, os.SEEK_END)
            thumb_size = thumbnail.tell()
            thumbnail.seek(0)
            
            if thumb_size > 10 * 1024 * 1024:  # 10MB for thumbnails
                return jsonify({
                    "success": False, 
                    "error": "Thumbnail size exceeds 10MB limit"
                }), 400
        
        # Prepare metadata and upload to IPFS
        token_uri = prepare_nft_metadata(
            file=file,
            name=name,
            description=description,
            wallet_address=wallet_address,
            file_type=file_type,
            thumbnail=thumbnail
        )
        
        # Return token URI for frontend minting
        return jsonify({
            "success": True,
            "token_uri": token_uri
        })
    
    except Exception as e:
        app.logger.error(f"Create NFT error: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "NFT creation failed. See logs for details."
        }), 500
    
@app.route("/listings")
def listings():
    try:
        nfts_for_sale = get_nfts_for_sale()  # Uses the fixed function
        return jsonify({"success": True, "nfts": nfts_for_sale})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/tx/<tx_hash>")
def check_tx(tx_hash):
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        return jsonify(dict(receipt))
    except:
        return jsonify({"status": "not found"}), 404

# FIXED PROFILE ROUTE (SAFER ADDRESS HANDLING)
@app.route("/profile")
def profile():
    raw_address = session.get('wallet_address')
    if not raw_address:
        return redirect("/")
    
    try:
        wallet_address = Web3.to_checksum_address(raw_address)
    except ValueError as e:
        print(f"Invalid address in session: {raw_address} - {str(e)}")
        session.pop('wallet_address', None)
        return redirect("/")
    
    try:
        balance = get_balance(wallet_address)
        user_nfts = get_nfts_for_user(wallet_address)
        return render_template("profile.html", 
                               user_address=wallet_address,
                               balance=balance,
                               nfts=user_nfts)
    except Exception as e:
        print(f"Error loading profile: {e}")
        return render_template("profile.html", 
                               user_address=wallet_address,
                               balance=0,
                               nfts=[])

def get_nfts_for_sale():
    if not contract:
        return []
        
    try:
        total = contract.functions.totalSupply().call()
        nfts = []
        for token_id in range(1, total + 1):
            try:
                owner, creator, price, uri, is_listed = contract.functions.getTokenDetails(token_id).call()
                
                if is_listed and price > 0:
                    resp = requests.get(uri, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        nfts.append({
                            "token_id": token_id,
                            "image": data.get("image", ""),
                            "name": data.get("name", f"Token {token_id}"),
                            "description": data.get("description", ""),
                            "price": w3.from_wei(price, 'ether'),
                            "owner": owner
                        })
            except Exception as e:
                print(f"Skipping token {token_id}: {str(e)}")
                continue
        return nfts
    except Exception as e:
        print(f"Error getting listings: {str(e)}")
        return []
    
@app.route("/mint", methods=["POST"])
def mint_nft():
    if not session.get('wallet_address'):
        return jsonify({"success": False, "error": "Wallet not connected"}), 401

    data = request.get_json()
    token_uri = data.get("token_uri")
    if not token_uri:
        return jsonify({"success": False, "error": "Missing token URI"}), 400

    try:
        wallet_address = Web3.to_checksum_address(session['wallet_address'])
        
        gas_price = w3.eth.gas_price
        nonce = w3.eth.get_transaction_count(wallet_address)
        
        tx = contract.functions.mint(wallet_address, token_uri).build_transaction({
            'chainId': 300,
            'gas': 500000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': wallet_address
        })
        
        return jsonify({
            "success": True,
            "tx": tx
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    

@app.route("/list", methods=["POST"])
def list_nft():
    if not session.get('wallet_address'):
        return jsonify({"success": False, "error": "Wallet not connected"}), 401

    data = request.get_json()
    token_id = data.get("token_id")
    price_eth = data.get("price")
    
    if not token_id or not price_eth:
        return jsonify({"success": False, "error": "Missing token ID or price"}), 400

    try:
        # Convert token ID to integer
        token_id = int(token_id)
        wallet_address = Web3.to_checksum_address(session['wallet_address'])
        price_wei = w3.to_wei(price_eth, 'ether')
        
        # Verify ownership
        owner = contract.functions.ownerOf(token_id).call()
        if owner.lower() != wallet_address.lower():
            return jsonify({"success": False, "error": "Not the owner"}), 403

        gas_price = w3.eth.gas_price
        nonce = w3.eth.get_transaction_count(wallet_address)
        
        tx = contract.functions.listForSale(
            token_id, 
            price_wei
        ).build_transaction({
            'chainId': 300,
            'gas': 500000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': wallet_address
        })
        
        return jsonify({
            "success": True,
            "tx": tx
        })
    except ValueError:
        return jsonify({"success": False, "error": "Invalid token ID format"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/unlist", methods=["POST"])
def unlist_nft():
    if not session.get('wallet_address'):
        return jsonify({"success": False, "error": "Wallet not connected"}), 401

    data = request.get_json()
    token_id = data.get("token_id")
    
    if not token_id:
        return jsonify({"success": False, "error": "Missing token ID"}), 400

    try:
        # Convert token ID to integer
        token_id = int(token_id)
        wallet_address = Web3.to_checksum_address(session['wallet_address'])
        
        # Verify ownership
        owner = contract.functions.ownerOf(token_id).call()
        if owner.lower() != wallet_address.lower():
            return jsonify({"success": False, "error": "Not the owner"}), 403

        gas_price = w3.eth.gas_price
        nonce = w3.eth.get_transaction_count(wallet_address)
        
        tx = contract.functions.unlist(token_id).build_transaction({
            'chainId': 300,
            'gas': 500000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': wallet_address
        })
        
        return jsonify({
            "success": True,
            "tx": tx
        })
    except ValueError:
        return jsonify({"success": False, "error": "Invalid token ID format"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Add this new route for ABI access
@app.route("/get-abi")
def get_abi():
    try:
        ABI_PATH = os.getenv("ABI_PATH", "artifacts-zk/contracts/ImageNFT.sol/ImageNFT.json")
        with open(ABI_PATH) as f:
            contract_data = json.load(f)
            abi = contract_data["abi"]
        return jsonify({"success": True, "abi": abi})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def verify_signature(message, signature, address):
    try:
        message_hash = encode_defunct(text=message)
        signer = w3.eth.account.recover_message(message_hash, signature=signature)
        return signer.lower() == address.lower()
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False
@app.route('/view_metadata')
def view_metadata():
    url = request.args.get('url')
    if not url:
        return "No metadata URL provided."

    try:
        response = requests.get(url)
        metadata = response.json()
        return render_template("view_metadata.html", metadata=metadata)
    except Exception as e:
        return f"Error loading metadata: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)