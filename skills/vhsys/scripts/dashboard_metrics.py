#!/usr/bin/env python3
"""Dashboard metrics para skill vhsys — Agente CFO."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from base import now_iso

# TODO: substituir stub pelo client real quando disponível
# from vhsys_client import VHSYSERPClient

def get_metrics() -> dict:
    try:
        # client = VHSYSERPClient()
        # return client.get_dashboard_metrics()
        return {'health': {'status': 'not_configured', 'last_sync': now_iso()}}
    except Exception as e:
        return {'health': {'status': 'error', 'error': str(e), 'last_sync': now_iso()}}

if __name__ == '__main__':
    print(json.dumps(get_metrics(), default=str))
