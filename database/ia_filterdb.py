import logging
from struct import pack
import re
import base64
from hydrogram.file_id import FileId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from info import USE_CAPTION_FILTER, FILES_DATABASE_URL, SECOND_FILES_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, MAX_BTN

logger = logging.getLogger(__name__)

# --- Primary Database ---
client = AsyncIOMotorClient(FILES_DATABASE_URL)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# --- Secondary Database (Optional) ---
if SECOND_FILES_DATABASE_URL:
    second_client = AsyncIOMotorClient(SECOND_FILES_DATABASE_URL)
    second_db = second_client[DATABASE_NAME]
    second_collection = second_db[COLLECTION_NAME]
else:
    second_collection = None


async def save_file(media):
    """Save file in database (Async)"""
    file_id = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.file_name))
    file_caption = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.caption))
    
    document = {
        '_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': file_caption
    }
    
    try:
        await collection.insert_one(document)
        logger.info(f'Saved - {file_name}')
        return 'suc'
    except DuplicateKeyError:
        logger.warning(f'Already Saved - {file_name}')
        return 'dup'
    except Exception:
        # Fallback to Second DB if First is Full/Error
        if second_collection:
            try:
                await second_collection.insert_one(document)
                logger.info(f'Saved to 2nd db - {file_name}')
                return 'suc'
            except DuplicateKeyError:
                logger.warning(f'Already Saved in 2nd db - {file_name}')
                return 'dup'
            except Exception as e:
                logger.error(f"Error saving to 2nd DB: {e}")
                return 'err'
        else:
            logger.error(f'Primary DB Full/Error and No Second DB Configured')
            return 'err'

async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None):
    """Get search results from both databases"""
    query = str(query).strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        regex = query

    if USE_CAPTION_FILTER:
        filter_q = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter_q = {'file_name': regex}

    # Fetch from DB 1
    cursor = collection.find(filter_q)
    # Important: to_list is non-blocking
    results = await cursor.to_list(length=100) # Limit buffer

    # Fetch from DB 2 (if exists)
    if second_collection:
        cursor2 = second_collection.find(filter_q)
        results2 = await cursor2.to_list(length=100)
        results.extend(results2)

    # Filter Logic (Language & Pagination)
    if lang:
        lang_files = [file for file in results if lang.lower() in file['file_name'].lower()]
        files = lang_files[offset:][:max_results]
        total_results = len(lang_files)
        next_offset = offset + max_results
        if next_offset >= total_results:
            next_offset = ''
        return files, next_offset, total_results

    # Standard Pagination
    total_results = len(results)
    files = results[offset:][:max_results]
    next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ''   
    return files, next_offset, total_results

async def delete_files(query):
    """Delete files matching query from both DBs"""
    query = query.strip()
    if not query: return 0
    
    if ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return 0
        
    filter_q = {'file_name': regex}
    
    result1 = await collection.delete_many(filter_q)
    total_deleted = result1.deleted_count
    
    if second_collection:
        result2 = await second_collection.delete_many(filter_q)
        total_deleted += result2.deleted_count
    
    return total_deleted

async def get_file_details(query):
    """Get single file details"""
    file_details = await collection.find_one({'_id': query})
    if not file_details and second_collection:
        file_details = await second_collection.find_one({'_id': query})
    return file_details

async def db_count_documents():
    """Count files in DB 1"""
    return await collection.count_documents({})

async def second_db_count_documents():
    """Count files in DB 2"""
    if second_collection:
        return await second_collection.count_documents({})
    return 0

# --- File ID Helpers (No Changes Logic) ---

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id

