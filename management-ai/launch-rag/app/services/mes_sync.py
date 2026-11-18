"""Read-only bridge from RAG to the Ruijing MES API."""

import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..core.config import settings

logger = logging.getLogger(__name__)


def _get_json(url: str) -> Any:
    headers = {"Accept": "application/json"}
    if settings.mes_api_token:
        headers["Authorization"] = f"Bearer {settings.mes_api_token}"
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if isinstance(data, dict):
        data = data.get("items", data.get("rows", data.get("lines", [])))
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _work_order_doc(item: dict[str, Any]) -> dict[str, str] | None:
    code = str(item.get("code") or item.get("workOrderCode") or "").strip()
    if not code:
        return None
    text = (
        f"MES work order {code}. Status: {item.get('status', 'unknown')}. "
        f"Product: {item.get('productCode', 'unknown')} ({item.get('productNameZh', '')}). "
        f"Line: {item.get('lineCode', 'unknown')}. Planned quantity: {item.get('plannedQty', 'unknown')}. "
        f"Completed quantity: {item.get('completedQty', 0)}. Due date: {item.get('dueDate', 'unknown')}."
    )
    return {"chunk_id": f"mes:work-order:{code}", "source": f"MES work order {code}", "text": text}


def _bom_doc(item: dict[str, Any], lines: list[dict[str, Any]] | None = None) -> dict[str, str] | None:
    bom_id = str(item.get("id") or "").strip()
    product = str(item.get("productCode") or item.get("product_code") or "").strip()
    revision = str(item.get("revision") or "").strip()
    if not bom_id or not product:
        return None
    material_text = ""
    if lines:
        material_text = " Materials: " + "; ".join(
            f"{line.get('materialCode', line.get('material_code', 'unknown'))} x {line.get('qtyPer', line.get('qty_per', 'unknown'))} {line.get('unit', 'PCS')}"
            for line in lines[:300]
        ) + "."
    text = (
        f"Released MES BOM for product {product}. BOM id: {bom_id}. Revision: {revision or 'unknown'}. "
        f"Status: {item.get('status', 'active')}. Material line count: {item.get('materialCount', item.get('lineCount', len(lines or [])))}."
        f"{material_text}"
    )
    return {"chunk_id": f"mes:bom:{bom_id}:{revision}", "source": f"MES BOM {product} {revision}", "text": text}


async def fetch_documents(limit: int = 200) -> list[dict[str, str]]:
    """Fetch work-order and released-BOM context without touching MES SQL."""
    base = settings.mes_api_base_url.rstrip("/")
    bounded = max(1, min(limit, 500))
    payloads: list[Any] = []
    for url in (f"{base}/pmc/work-orders?limit={bounded}", f"{base}/boms?status=active&limit={bounded}"):
        try:
            payloads.append(await asyncio.to_thread(_get_json, url))
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning("MES sync skipped %s: %s", url, exc)
            payloads.append(None)
    docs: list[dict[str, str]] = []
    for item in _items(payloads[0]):
        doc = _work_order_doc(item)
        if doc:
            docs.append(doc)
    bom_items = _items(payloads[1])
    async def enrich_bom(item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        bom_id = str(item.get("id") or "").strip()
        if not bom_id:
            return item, []
        try:
            detail = await asyncio.to_thread(_get_json, f"{base}/boms/{bom_id}")
            return item, _items(detail.get("data", detail))
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning("MES BOM detail skipped %s: %s", bom_id, exc)
            return item, []
    enriched_boms = await asyncio.gather(*(enrich_bom(item) for item in bom_items[: min(len(bom_items), 100)]))
    for item, lines in enriched_boms:
        doc = _bom_doc(item, lines)
        if doc:
            docs.append(doc)
    return docs
