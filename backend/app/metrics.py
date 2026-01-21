from prometheus_client import make_asgi_app, Counter, Histogram
import os

# Prometheus metrics
supabase_db_calls_total = Counter(
    'supabase_db_calls_total',
    'Total number of Supabase database calls',
    ['operation', 'table']
)

processing_time = Histogram(
    'invoice_processing_time_seconds',
    'Time spent processing invoices',
    ['status']
)

def record_db_call(operation: str, table: str):
    """Record a Supabase database call"""
    supabase_db_calls_total.labels(operation=operation, table=table).inc()

def record_processing_time(status: str, duration: float):
    """Record invoice processing time"""
    processing_time.labels(status=status).observe(duration)

def setup_metrics():
    """Setup Prometheus metrics endpoint"""
    return make_asgi_app()
