from __future__ import annotations

from typing import Any
from typing import Dict

from app.config import settings
from app.services.approval_store import get_latest_approval
from app.temporal.client import get_temporal_client
from app.temporal.workflows import ControlledReleaseWorkflow
from temporalio.common import WorkflowIDReusePolicy


def _workflow_id_for_incident(incident_id: str) -> str:
    return f"controlled-release::{incident_id}"


async def check_temporal_health() -> Dict[str, Any]:
    if not settings.TEMPORAL_ENABLED:
        return {
            "enabled": False,
            "status": "disabled",
            "address": settings.TEMPORAL_ADDRESS,
            "namespace": settings.TEMPORAL_NAMESPACE,
        }

    try:
        await get_temporal_client()
        return {
            "enabled": True,
            "status": "reachable",
            "address": settings.TEMPORAL_ADDRESS,
            "namespace": settings.TEMPORAL_NAMESPACE,
            "task_queue": settings.TEMPORAL_TASK_QUEUE,
            "ui_url": settings.TEMPORAL_UI_URL,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "unreachable",
            "address": settings.TEMPORAL_ADDRESS,
            "namespace": settings.TEMPORAL_NAMESPACE,
            "task_queue": settings.TEMPORAL_TASK_QUEUE,
            "ui_url": settings.TEMPORAL_UI_URL,
            "error": str(exc),
        }


async def ensure_controlled_release_workflow(incident_packet: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.TEMPORAL_ENABLED:
        return {"available": False, "status": "disabled"}

    workflow_id = _workflow_id_for_incident(incident_packet["incident_id"])
    initial_approval = get_latest_approval(incident_packet["incident_id"])
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)

        try:
            await handle.describe()
            try:
                snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
                if snapshot.get("workflow_status") in {"completed", "rolled-back", "rejected", "changes-requested"}:
                    await client.start_workflow(
                        ControlledReleaseWorkflow.run,
                        {
                            "incident_packet": incident_packet,
                            "initial_phase": "shadow",
                            "auto_refresh_seconds": float(getattr(settings, "TEMPORAL_AUTO_REFRESH_SECONDS", 20.0)),
                            "initial_approval": initial_approval,
                        },
                        id=workflow_id,
                        task_queue=settings.TEMPORAL_TASK_QUEUE,
                        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                    )
                    return {
                        "available": True,
                        "status": "restarted",
                        "workflow_id": workflow_id,
                    }
            except Exception:
                pass
            return {
                "available": True,
                "status": "running",
                "workflow_id": workflow_id,
            }
        except Exception:
            await client.start_workflow(
                ControlledReleaseWorkflow.run,
                {
                    "incident_packet": incident_packet,
                    "initial_phase": "shadow",
                    "auto_refresh_seconds": float(getattr(settings, "TEMPORAL_AUTO_REFRESH_SECONDS", 20.0)),
                    "initial_approval": initial_approval,
                },
                id=workflow_id,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            )
            return {
                "available": True,
                "status": "started",
                "workflow_id": workflow_id,
            }
    except Exception as exc:
        return {
            "available": False,
            "status": "unavailable",
            "workflow_id": workflow_id,
            "error": str(exc),
        }


async def get_controlled_release_workflow_state(incident_id: str) -> Dict[str, Any]:
    workflow_id = _workflow_id_for_incident(incident_id)
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
        snapshot["workflow_id"] = workflow_id
        snapshot["namespace"] = settings.TEMPORAL_NAMESPACE
        snapshot["task_queue"] = settings.TEMPORAL_TASK_QUEUE
        snapshot["ui_url"] = settings.TEMPORAL_UI_URL
        return snapshot
    except Exception as exc:
        return {
            "available": False,
            "workflow_id": workflow_id,
            "namespace": settings.TEMPORAL_NAMESPACE,
            "task_queue": settings.TEMPORAL_TASK_QUEUE,
            "ui_url": settings.TEMPORAL_UI_URL,
            "workflow_status": "unavailable",
            "error": str(exc),
            "history": [],
        }


async def signal_temporal_approval(approval_record: Dict[str, Any]) -> Dict[str, Any]:
    workflow_id = _workflow_id_for_incident(approval_record["incident_id"])
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(ControlledReleaseWorkflow.record_approval, approval_record)
        snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
        snapshot["workflow_id"] = workflow_id
        snapshot["ui_url"] = settings.TEMPORAL_UI_URL
        return snapshot
    except Exception as exc:
        return {
            "available": False,
            "workflow_id": workflow_id,
            "workflow_status": "unavailable",
            "error": str(exc),
        }


async def signal_temporal_release_phase(
    incident_id: str,
    phase: str,
    note: str = "",
) -> Dict[str, Any]:
    workflow_id = _workflow_id_for_incident(incident_id)
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(
            ControlledReleaseWorkflow.advance_release,
            {
                "phase": phase,
                "note": note,
            },
        )
        snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
        snapshot["workflow_id"] = workflow_id
        snapshot["ui_url"] = settings.TEMPORAL_UI_URL
        return snapshot
    except Exception as exc:
        return {
            "available": False,
            "workflow_id": workflow_id,
            "workflow_status": "unavailable",
            "error": str(exc),
        }


async def signal_temporal_rollback(incident_id: str, reason: str) -> Dict[str, Any]:
    workflow_id = _workflow_id_for_incident(incident_id)
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(ControlledReleaseWorkflow.trigger_rollback, reason)
        snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
        snapshot["workflow_id"] = workflow_id
        snapshot["ui_url"] = settings.TEMPORAL_UI_URL
        return snapshot
    except Exception as exc:
        return {
            "available": False,
            "workflow_id": workflow_id,
            "workflow_status": "unavailable",
            "error": str(exc),
        }


async def signal_temporal_refresh(incident_id: str, note: str = "") -> Dict[str, Any]:
    workflow_id = _workflow_id_for_incident(incident_id)
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(ControlledReleaseWorkflow.request_refresh, note)
        snapshot = await handle.query(ControlledReleaseWorkflow.snapshot)
        snapshot["workflow_id"] = workflow_id
        snapshot["ui_url"] = settings.TEMPORAL_UI_URL
        return snapshot
    except Exception as exc:
        return {
            "available": False,
            "workflow_id": workflow_id,
            "workflow_status": "unavailable",
            "error": str(exc),
        }
