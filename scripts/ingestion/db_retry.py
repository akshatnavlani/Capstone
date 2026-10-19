"""Open the database connection, waiting for the network if it is not up yet.

A scheduled or restarted job often starts right after the laptop wakes up, before Wi-Fi and DNS are ready; the connection then
fails with "could not translate host name". Waiting a little fixes that. The error text is never logged (a connect error can
carry the connection string, which contains the password): only the kind of error and the attempt number are.
"""

import logging
import time

import psycopg2

log = logging.getLogger("db_retry")


def connect_with_retry(get_connection, attempts: int = 15, wait_seconds: float = 20):
    """Call get_connection() until it works; raise the last error after `attempts` tries (about 5 minutes by default)."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return get_connection()
        except psycopg2.OperationalError as e:
            last = e
            log.warning("database not reachable yet (attempt %d of %d, %s); waiting %d s", attempt, attempts, type(e).__name__, wait_seconds)
            time.sleep(wait_seconds)
    raise last
