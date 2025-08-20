import os
import json
import requests
import logging
import io
import time
import mimetypes
from web3 import Web3
from dotenv import load_dotenv
from .filebase_utils import upload_file_to_filebase

# Load environment first
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blockchain setup
ZKSYNC_RPC = os.getenv("ZKSYNC_RPC", "https://sepolia.era.zksync.dev")
w3 = Web3(Web3.HTTPProvider(ZKSYNC_RPC))
contract_address = os.getenv("CONTRACT_ADDRESS")

# Load ABI
try:
    ABI_PATH = os.getenv("ABI_PATH", "artifacts-zk/contracts/ImageNFT.sol/ImageNFT.json")
    with open(ABI_PATH) as f:
        contract_data = json.load(f)
        abi = contract_data["abi"]
    contract = w3.eth.contract(address=contract_address, abi=abi)
    logger.info("Contract initialized successfully")
except Exception as e:
    logger.error(f"Contract initialization failed: {e}")
    abi = []
    contract = None

def prepare_nft_metadata(file, name, description, wallet_address, file_type="image", thumbnail=None):
    try:
        prefix = wallet_address.lower()
        
        # Determine content type
        content_type = mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
        
        # Upload main file to IPFS
        main_url, _ = upload_file_to_filebase(
            file_obj=file,
            key_prefix=prefix,
            filename=file.filename,
            content_type=content_type
        )

        # Upload thumbnail if exists
        thumbnail_url = None
        if thumbnail:
            # Reset thumbnail stream position
            thumbnail.stream.seek(0)
            
            # Determine thumbnail content type
            thumb_content_type = mimetypes.guess_type(thumbnail.filename)[0] or 'image/jpeg'
            
            thumbnail_url, _ = upload_file_to_filebase(
                file_obj=thumbnail,
                key_prefix=f"{prefix}/thumbnails",
                filename=f"thumb_{int(time.time())}_{file.filename}",
                content_type=thumb_content_type
            )
        
        # Build metadata with backward compatibility
        metadata = {
            "name": name,
            "description": description,
            "creator": wallet_address,
            "created_at": int(time.time()),
            "file_type": file_type,
            "main_url": main_url,
            "thumbnail_url": thumbnail_url,
            "image": thumbnail_url if (file_type in ['video', 'audio'] and thumbnail_url) else main_url,
            "network": "zksync-sepolia",
            "chainId": 300
        }
        
        # Create metadata file
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        metadata_file = io.BytesIO(metadata_bytes)
        metadata_file.filename = f"metadata_{int(time.time())}.json"
        
        # Upload metadata to IPFS
        metadata_url, _ = upload_file_to_filebase(
            file_obj=metadata_file,
            key_prefix=f"{prefix}/metadata",
            filename=metadata_file.filename,
            content_type='application/json'
        )
        
        return metadata_url
    except Exception as e:
        logger.error(f"Metadata preparation failed: {e}", exc_info=True)
        raise RuntimeError(f"Could not create NFT metadata: {str(e)}")

def get_nfts_for_user(wallet_address):
    wallet_address = Web3.to_checksum_address(wallet_address)
    """Retrieve user's NFTs from blockchain"""
    if not contract:
        return []
        
    try:
        total = contract.functions.totalSupply().call()
        nfts = []
        for token_id in range(1, total + 1):
            try:
                # Get token details in one call
                owner, creator, price, uri, is_listed = contract.functions.getTokenDetails(token_id).call()
                
                if owner.lower() == wallet_address.lower():
                    # Fetch metadata
                    resp = requests.get(uri, timeout=5)
                    if resp.status_code == 200:
                        metadata = resp.json()
                        # Backward compatibility for old NFTs
                        if 'file_type' not in metadata:
                            metadata['file_type'] = 'image'
                        if 'main_url' not in metadata:
                            metadata['main_url'] = metadata.get('image', '')
                        if 'thumbnail_url' not in metadata:
                            metadata['thumbnail_url'] = metadata.get('image', '')
                        
                        nfts.append({
                            "token_id": token_id,
                            "image": metadata.get("image", ""),
                            "name": metadata.get("name", f"Token #{token_id}"),
                            "description": metadata.get("description", ""),
                            "price": w3.from_wei(price, 'ether') if price > 0 else None,
                            "is_listed": is_listed,
                            "metadata_url": uri,
                            "file_type": metadata.get("file_type", "image"),
                            "main_url": metadata.get("main_url", metadata.get("image", "")),
                            "thumbnail_url": metadata.get("thumbnail_url", metadata.get("image", ""))
                        })
            except Exception as e:
                logger.warning(f"Skipping token {token_id}: {str(e)}")
                continue
        return nfts
    except Exception as e:
        logger.error(f"Failed to get NFTs: {e}")
        return []

def get_balance(wallet_address):
    try:
        checksum_address = Web3.to_checksum_address(wallet_address)
        balance_wei = w3.eth.get_balance(checksum_address)
        return w3.from_wei(balance_wei, 'ether')
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        return 0
    
# FIXED: Renamed to get_nfts_for_sale and added is_listed check
def get_nfts_for_sale():
    """Retrieve all NFTs listed for sale"""
    if not contract:
        return []
    
    try:
        total = contract.functions.totalSupply().call()
        nfts_for_sale = []
        for token_id in range(1, total + 1):
            try:
                # Explicitly convert token ID to int
                token_id_int = int(token_id)
                owner, creator, price, uri, is_listed = contract.functions.getTokenDetails(token_id_int).call()
                
                if is_listed and price > 0:
                    resp = requests.get(uri, timeout=5)
                    metadata = resp.json() if resp.status_code == 200 else {}
                    
                    nfts_for_sale.append({
                        "token_id": token_id_int,
                        "image": metadata.get("image", ""),
                        "name": metadata.get("name", f"Token #{token_id_int}"),
                        "description": metadata.get("description", ""),
                        "price": w3.from_wei(price, 'ether'),
                        "owner": owner,
                        "creator": creator,
                        "metadata_url": uri
                    })
            except Exception as e:
                logger.warning(f"Skipping token {token_id}: {str(e)}")
                continue
        return nfts_for_sale
    except Exception as e:
        logger.error(f"Failed to get NFTs for sale: {e}")
        return []

def get_zksync_gas_params():
    return {
        'gasPrice': w3.eth.gas_price,
        'gas': 500000,  # Adequate for mint operations
    }