# enrichment_steps.py
# Purpose: Centralized step and status constants for enrichment_logs

class Step:
    INGESTION_RECEIVED = "ingestion_received"
    ENRICHMENT = "enrichment"
    CONTEXT_ENRICHMENT = "context_enrichment"
    UNPACKING_INIT = "unpacking_init"
    UNPACKING = "unpacking"
    ANALYTICS_FORWARDING = "analytics_forwarding"

class Status:
    NEW = "new"
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    FAIL = "fail"
    READY = "ready_for_unpacking"
