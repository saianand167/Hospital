import socket
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# ── DNS / Connectivity Fix ──────────────────────────────────────────────────
# The local DNS server blocks resolution of *.neon.tech hostnames.
# psycopg2 supports 'hostaddr' to connect via IP while keeping the original
# hostname in 'host' for SSL SNI certificate verification.
# We pre-resolve the hostname using Google DNS (8.8.8.8) via dnspython
# and pass the resolved IP as hostaddr in connect_args.

_NEON_HOST = None
_NEON_HOSTADDR = None

def _resolve_neon_host(db_url: str):
    """Extract hostname from DATABASE_URL and resolve it via Google DNS."""
    global _NEON_HOST, _NEON_HOSTADDR
    try:
        # Parse host from postgresql://user:pass@HOST/db
        parts = db_url.split('@')
        if len(parts) >= 2:
            host_part = parts[1].split('/')[0]
            _NEON_HOST = host_part.split(':')[0]
    except Exception:
        return None, None

    # First try system DNS
    try:
        ip = socket.gethostbyname(_NEON_HOST)
        _NEON_HOSTADDR = ip
        logger.info(f"[DB] System DNS resolved {_NEON_HOST} → {ip}")
        return _NEON_HOST, ip
    except socket.gaierror:
        pass

    # Fallback: use Google DNS via dnspython
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1']
        answers = resolver.resolve(_NEON_HOST, 'A')
        ip = str(answers[0])
        _NEON_HOSTADDR = ip
        logger.info(f"[DB] Google DNS resolved {_NEON_HOST} → {ip}")
        return _NEON_HOST, ip
    except Exception as e:
        logger.warning(f"[DB] DNS fallback failed: {e}")

    # Hardcoded last-resort IPs for known Neon endpoints
    neon_fallback = {
        'ep-rapid-credit-axefz0l8.c-4.us-east-2.aws.neon.tech': '18.226.241.3'
    }
    if _NEON_HOST in neon_fallback:
        ip = neon_fallback[_NEON_HOST]
        _NEON_HOSTADDR = ip
        logger.warning(f"[DB] Using hardcoded IP {ip} for {_NEON_HOST}")
        return _NEON_HOST, ip

    return _NEON_HOST, None


_neon_host, _neon_ip = _resolve_neon_host(settings.DATABASE_URL)

# Build connect_args: if we have an IP, set hostaddr for DNS bypass
_connect_args = {}
if _neon_ip:
    _connect_args["hostaddr"] = _neon_ip
    logger.info(f"[DB] Using hostaddr={_neon_ip} for SSL-safe DNS bypass")

# ─────────────────────────────────────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=60,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
