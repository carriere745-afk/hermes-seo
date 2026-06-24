"""Rate limiter — protection anti-abus et quota management.

Deux niveaux:
1. Global IP-based (100 requests/hour)
2. Per-project (max_actions_per_day, defaut 20)
"""

import logging
import time
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger("hermes.rate_limiter")

# Global IP tracking (in-memory, resets on restart)
_ip_buckets: dict[str, list[float]] = defaultdict(list)
GLOBAL_RATE_LIMIT = 100  # requests per hour
GLOBAL_WINDOW = 3600  # 1 hour in seconds


def check_ip_rate(ip: str) -> bool:
    """Verifie si l'IP a depasse la limite globale. Retourne True si autorise."""
    now = time.time()
    bucket = _ip_buckets[ip]

    # Nettoyer les entrees expirees
    bucket = [t for t in bucket if now - t < GLOBAL_WINDOW]
    _ip_buckets[ip] = bucket

    if len(bucket) >= GLOBAL_RATE_LIMIT:
        logger.warning(f"Rate limit atteint pour IP {ip}: {len(bucket)}/{GLOBAL_RATE_LIMIT} req/h")
        return False

    bucket.append(now)
    return True


def check_project_quota(project) -> bool:
    """Verifie si le projet a depasse son quota quotidien. Retourne True si autorise."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Reset quotidien
    last_reset = getattr(project, '_last_quota_reset', '')
    if last_reset != today:
        project.actions_executed_today = 0
        project._last_quota_reset = today

    return project.actions_executed_today < project.max_actions_per_day


def get_quota_remaining(project) -> int:
    """Retourne le nombre d'actions restantes pour aujourd'hui."""
    check_project_quota(project)  # Ensure reset
    return max(0, project.max_actions_per_day - project.actions_executed_today)


def get_ip_stats(ip: str = "") -> dict:
    """Retourne les statistiques de rate limiting."""
    now = time.time()
    if ip:
        bucket = [t for t in _ip_buckets.get(ip, []) if now - t < GLOBAL_WINDOW]
        return {"ip": ip, "requests_last_hour": len(bucket), "limit": GLOBAL_RATE_LIMIT}
    total = sum(
        len([t for t in bucket if now - t < GLOBAL_WINDOW])
        for bucket in _ip_buckets.values()
    )
    return {"total_ips_tracked": len(_ip_buckets), "total_requests": total}
