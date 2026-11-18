# -*- coding: utf-8 -*-
"""Single common local-agent component for Manual and Auto lines.

The implementation lives in ``local_agent_baseline`` for compatibility with
existing imports; this is the stable public module used by both domains.
"""
from .local_agent_baseline import LocalAgentBaseline, ROLE_PERMISSIONS, ROLES

__all__ = ["LocalAgentBaseline", "ROLE_PERMISSIONS", "ROLES"]
