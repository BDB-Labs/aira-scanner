"""
AIRA test fixture — deliberately contains violations for scanner validation.
DO NOT use in production.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

# C03: Broad exception suppression
def fetch_data(source):
    try:
        result = source.get()
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        # No re-raise — failure swallowed

# C01: Success integrity
def save_record(db, record):
    try:
        db.insert(record)
        return True  # C01: returns True even after exception
    except Exception:
        return True  # still True!

# C06: Ambiguous return contracts
def find_user(user_id):
    if user_id is None:
        return None  # absence
    try:
        user = db.get(user_id)
        return user
    except Exception:
        return None  # failure — same as absence!
    if not user.active:
        return None  # disabled — still same!

# C08: Unsupervised background task
async def start_background_sync():
    asyncio.create_task(sync_worker())  # no supervision

async def sync_worker():
    pass

# C11: Non-deterministic model call
def get_recommendation(context):
    response = llm.complete(context, temperature=0.9)  # C11: non-zero temp
    return response

# C05: Bypass flag
TESTING_BYPASS = True
SKIP_VALIDATION = False

# C10: Startup that swallows errors
def initialize_system():
    try:
        connect_database()
        verify_audit_log()
    except Exception as e:
        logger.warning(f"Startup error: {e}")
        # Continues anyway — C10 violation

def connect_database():
    pass

def verify_audit_log():
    pass

# C15: Retry without idempotency
def retry_payment(payment_id, attempts=3):
    for attempt in range(attempts):
        try:
            result = payment_service.charge(payment_id)  # write op, no idempotency key
            return result
        except Exception:
            continue
