"""Canonical station adapter names for the shared Agent runtime."""

ADAPTERS = {
    "module_pda": {"station": "PDA", "equipment": "pda"},
    "module_aoi": {"station": "AOI", "equipment": "aoi"},
    "module_ict": {"station": "ICT", "equipment": "ict"},
    "module_fct": {"station": "FCT", "equipment": "fct"},
    "module_depanel": {"station": "DEPANEL", "equipment": "depanel"},
    "module_shell_binding": {"station": "SHELL_BINDING", "equipment": "shell_binding"},
    "module_assembly_ate": {"station": "ASSEMBLY_ATE", "equipment": "assembly_ate"},
    "module_supersonic": {"station": "SUPERSONIC", "equipment": "supersonic"},
    "module_aging_cab": {"station": "AGING_CAB", "equipment": "aging_cab"},
    "module_hivolt_ate": {"station": "HIVOLT_ATE", "equipment": "hivolt_ate"},
    "module_packing_ate": {"station": "PACKING_ATE", "equipment": "packing_ate"},
    "module_outer_box_binding": {"station": "OUTER_BOX_BINDING", "equipment": "outer_box_binding"},
    "module_pallet_binding": {"station": "PALLET_BINDING", "equipment": "pallet_binding"},
}


def validate_adapter_name(name: str) -> str:
    key = str(name or "").strip().lower()
    if key not in ADAPTERS:
        raise ValueError(f"Unknown station adapter: {name}")
    return key


def adapter_metadata(name: str):
    return dict(ADAPTERS[validate_adapter_name(name)])
