import os
import io
import time
import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_s3_client():
    """Initialize and return S3 client with credentials for Filebase"""
    FILEBASE_KEY = os.getenv("FILEBASE_KEY")
    FILEBASE_SECRET = os.getenv("FILEBASE_SECRET")
    FILEBASE_ENDPOINT = os.getenv("FILEBASE_ENDPOINT", "https://s3.filebase.com")
    
    if not FILEBASE_KEY or not FILEBASE_SECRET:
        logger.error("Missing Filebase credentials in environment")
        raise ValueError("Filebase credentials not configured")
    
    try:
        # Create session with explicit credentials
        session = boto3.session.Session(
            aws_access_key_id=FILEBASE_KEY,
            aws_secret_access_key=FILEBASE_SECRET
        )
        
        # Create client with Filebase-specific configuration
        return session.client(
            's3',
            endpoint_url=FILEBASE_ENDPOINT,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
                connect_timeout=30,
                retries={'max_attempts': 3}
            ),
            region_name='us-east-1'
        )
    except Exception as e:
        logger.error(f"Error creating S3 client: {e}")
        raise

def upload_file_to_filebase(file_obj, key_prefix, filename, content_type=None):
    """Upload a file to Filebase and return IPFS URL"""
    try:
        s3 = get_s3_client()
        BUCKET_NAME = os.getenv("BUCKET_NAME", "zk-nft-marketplace")
        GATEWAY_URL = os.getenv("GATEWAY_URL", "https://ipfs.filebase.io/ipfs/")
        
        # Sanitize filename to remove any path components
        filename = os.path.basename(filename)
        s3_key = f"{key_prefix}/{filename}"
        
        # Handle different file object types
        if hasattr(file_obj, 'read'):
            # If it's a BytesIO or file-like object
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            content = file_obj.read()
            file_size = len(content)
            file_obj = io.BytesIO(content)
        elif hasattr(file_obj, 'file'):  # Flask FileStorage
            file_obj.stream.seek(0)
            content = file_obj.stream.read()
            file_size = len(content)
            file_obj = io.BytesIO(content)
        else:
            raise ValueError("Unsupported file object type")
        
        # Prepare upload parameters
        extra_args = {
            'Metadata': {'cid': 'true'}
        }
        if content_type:
            extra_args['ContentType'] = content_type
        
        logger.info(f"Uploading {filename} to Filebase ({file_size} bytes)")
        start_time = time.time()
        
        # Perform the upload
        s3.upload_fileobj(
            Fileobj=file_obj,
            Bucket=BUCKET_NAME,
            Key=s3_key,
            ExtraArgs=extra_args
        )
        
        upload_time = time.time() - start_time
        speed = file_size / (1024 * 1024) / upload_time  # MB/s
        logger.info(f"Upload completed in {upload_time:.2f}s ({speed:.2f} MB/s)")
        
        # Retrieve CID from metadata
        response = s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        cid = response['Metadata'].get('cid')
        
        if not cid:
            raise RuntimeError(f"CID metadata missing for {s3_key}")
        
        ipfs_url = f"{GATEWAY_URL}{cid}"
        logger.info(f"File uploaded to IPFS: {ipfs_url}")
        
        return ipfs_url, s3_key
        
    except NoCredentialsError:
        logger.error("Missing Filebase credentials")
        raise RuntimeError("Filebase credentials not configured")
    except ClientError as e:
        error_code = e.response['Error'].get('Code', 'Unknown')
        error_msg = e.response['Error'].get('Message', 'Unknown error')
        logger.error(f"Filebase API error [{error_code}]: {error_msg}")
        
        # Provide more user-friendly error messages
        if error_code == 'AccessDenied':
            raise RuntimeError("Permission denied. Check your Filebase credentials and bucket permissions.")
        elif error_code == 'NoSuchBucket':
            raise RuntimeError(f"Bucket '{BUCKET_NAME}' does not exist")
        else:
            raise RuntimeError(f"Filebase upload failed: {error_msg}")
            
    except Exception as e:
        logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
        raise RuntimeError(f"Upload failed: {str(e)}")