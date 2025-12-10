"""API routes for TwinSync Spot."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.models import SpotType, SPOT_TEMPLATES
from app.core.voices import get_all_voices
from app.core.analyzer import SpotAnalyzer
from app.core.memory import MemoryEngine
from app.camera.ha_adapter import HACamera
from app.db import Database


router = APIRouter(prefix="/api")


# Request/Response models
class CreateSpotRequest(BaseModel):
    name: str
    description: str
    camera_entity_id: str
    spot_type: str
    voice_id: str


class UpdateSpotRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    camera_entity_id: Optional[str] = None
    spot_type: Optional[str] = None
    voice_id: Optional[str] = None


class SnoozeRequest(BaseModel):
    hours: int


class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None


# Routes
@router.get("/spots")
async def get_spots(request: Request):
    """Get all spots."""
    db: Database = request.app.state.db
    spots = await db.get_all_spots()
    
    return {
        "spots": [
            {
                "id": spot.id,
                "name": spot.name,
                "description": spot.description,
                "camera_entity_id": spot.camera_entity_id,
                "spot_type": spot.spot_type.value,
                "voice_id": spot.voice_id,
                "created_at": spot.created_at.isoformat(),
                "updated_at": spot.updated_at.isoformat(),
                "snoozed_until": spot.snoozed_until.isoformat() if spot.snoozed_until else None,
                "last_check": {
                    "timestamp": spot.last_check.timestamp.isoformat(),
                    "status": spot.last_check.status.value,
                    "score": spot.last_check.score,
                    "feedback": spot.last_check.feedback,
                    "items_to_sort": [
                        {
                            "name": item.name,
                            "location": item.location,
                            "suggestion": item.suggestion
                        }
                        for item in spot.last_check.items_to_sort
                    ]
                } if spot.last_check else None,
                "memory": {
                    "patterns": {
                        "recurring_items": spot.memory.patterns.recurring_items,
                        "best_day": spot.memory.patterns.best_day,
                        "worst_day": spot.memory.patterns.worst_day,
                        "current_streak": spot.memory.patterns.current_streak,
                        "best_streak": spot.memory.patterns.best_streak
                    },
                    "total_checks": spot.memory.total_checks,
                    "pass_rate": spot.memory.pass_rate
                } if spot.memory else None
            }
            for spot in spots
        ]
    }


@router.post("/spots")
async def create_spot(request: Request, data: CreateSpotRequest):
    """Create a new spot."""
    db: Database = request.app.state.db
    
    try:
        spot_type = SpotType(data.spot_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid spot type")
    
    spot_id = await db.create_spot(
        name=data.name,
        description=data.description,
        camera_entity_id=data.camera_entity_id,
        spot_type=spot_type,
        voice_id=data.voice_id
    )
    
    return {"id": spot_id, "message": "Spot created successfully"}


@router.get("/spots/{spot_id}")
async def get_spot(request: Request, spot_id: int):
    """Get a specific spot."""
    db: Database = request.app.state.db
    spot = await db.get_spot(spot_id)
    
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    
    # Get check history
    checks = await db.get_checks(spot_id)
    
    return {
        "spot": {
            "id": spot.id,
            "name": spot.name,
            "description": spot.description,
            "camera_entity_id": spot.camera_entity_id,
            "spot_type": spot.spot_type.value,
            "voice_id": spot.voice_id,
            "created_at": spot.created_at.isoformat(),
            "updated_at": spot.updated_at.isoformat(),
            "snoozed_until": spot.snoozed_until.isoformat() if spot.snoozed_until else None,
            "last_check": {
                "timestamp": spot.last_check.timestamp.isoformat(),
                "status": spot.last_check.status.value,
                "score": spot.last_check.score,
                "feedback": spot.last_check.feedback,
                "items_to_sort": [
                    {
                        "name": item.name,
                        "location": item.location,
                        "suggestion": item.suggestion
                    }
                    for item in spot.last_check.items_to_sort
                ]
            } if spot.last_check else None,
            "memory": {
                "patterns": {
                    "recurring_items": spot.memory.patterns.recurring_items,
                    "best_day": spot.memory.patterns.best_day,
                    "worst_day": spot.memory.patterns.worst_day,
                    "current_streak": spot.memory.patterns.current_streak,
                    "best_streak": spot.memory.patterns.best_streak
                },
                "total_checks": spot.memory.total_checks,
                "pass_rate": spot.memory.pass_rate
            } if spot.memory else None
        },
        "checks": checks
    }


@router.put("/spots/{spot_id}")
async def update_spot(request: Request, spot_id: int, data: UpdateSpotRequest):
    """Update a spot."""
    db: Database = request.app.state.db
    
    spot_type = None
    if data.spot_type:
        try:
            spot_type = SpotType(data.spot_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid spot type")
    
    success = await db.update_spot(
        spot_id=spot_id,
        name=data.name,
        description=data.description,
        camera_entity_id=data.camera_entity_id,
        spot_type=spot_type,
        voice_id=data.voice_id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Spot not found")
    
    return {"message": "Spot updated successfully"}


@router.delete("/spots/{spot_id}")
async def delete_spot(request: Request, spot_id: int):
    """Delete a spot."""
    db: Database = request.app.state.db
    await db.delete_spot(spot_id)
    return {"message": "Spot deleted successfully"}


@router.post("/spots/{spot_id}/check")
async def check_spot(request: Request, spot_id: int):
    """Check a spot by analyzing camera snapshot."""
    db: Database = request.app.state.db
    camera: HACamera = request.app.state.camera
    analyzer: SpotAnalyzer = request.app.state.analyzer
    
    # Get spot
    spot = await db.get_spot(spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    
    # Check if snoozed
    if spot.snoozed_until and spot.snoozed_until > datetime.now():
        raise HTTPException(status_code=400, detail="Spot is snoozed")
    
    # Get camera snapshot
    snapshot = await camera.get_snapshot(spot.camera_entity_id)
    if not snapshot:
        raise HTTPException(status_code=500, detail="Failed to get camera snapshot")
    
    # Get memory context
    memory_context = None
    if spot.memory:
        memory_context = MemoryEngine.get_memory_context(spot.memory)
    
    # Analyze
    check_result = await analyzer.analyze_spot(
        image_data=snapshot,
        spot_description=spot.description,
        voice_id=spot.voice_id,
        memory_context=memory_context
    )
    
    # Save check result
    await db.add_check(spot_id, check_result)
    
    return {
        "timestamp": check_result.timestamp.isoformat(),
        "status": check_result.status.value,
        "score": check_result.score,
        "feedback": check_result.feedback,
        "items_to_sort": [
            {
                "name": item.name,
                "location": item.location,
                "suggestion": item.suggestion
            }
            for item in check_result.items_to_sort
        ]
    }


@router.post("/spots/{spot_id}/reset")
async def reset_spot(request: Request, spot_id: int):
    """Reset a spot by deleting all check history."""
    db: Database = request.app.state.db
    await db.reset_spot(spot_id)
    return {"message": "Spot reset successfully"}


@router.post("/spots/{spot_id}/snooze")
async def snooze_spot(request: Request, spot_id: int, data: SnoozeRequest):
    """Snooze a spot for a number of hours."""
    db: Database = request.app.state.db
    
    until = datetime.now() + timedelta(hours=data.hours)
    await db.snooze_spot(spot_id, until)
    
    return {"message": f"Spot snoozed for {data.hours} hours"}


@router.post("/spots/{spot_id}/unsnooze")
async def unsnooze_spot(request: Request, spot_id: int):
    """Remove snooze from a spot."""
    db: Database = request.app.state.db
    await db.unsnooze_spot(spot_id)
    return {"message": "Spot unsnoozed"}


@router.post("/check-all")
async def check_all_spots(request: Request):
    """Check all non-snoozed spots."""
    db: Database = request.app.state.db
    camera: HACamera = request.app.state.camera
    analyzer: SpotAnalyzer = request.app.state.analyzer
    
    spots = await db.get_all_spots()
    results = []
    
    for spot in spots:
        # Skip snoozed spots
        if spot.snoozed_until and spot.snoozed_until > datetime.now():
            continue
        
        # Get snapshot
        snapshot = await camera.get_snapshot(spot.camera_entity_id)
        if not snapshot:
            results.append({
                "spot_id": spot.id,
                "spot_name": spot.name,
                "error": "Failed to get camera snapshot"
            })
            continue
        
        # Get memory context
        memory_context = None
        if spot.memory:
            memory_context = MemoryEngine.get_memory_context(spot.memory)
        
        # Analyze
        check_result = await analyzer.analyze_spot(
            image_data=snapshot,
            spot_description=spot.description,
            voice_id=spot.voice_id,
            memory_context=memory_context
        )
        
        # Save
        await db.add_check(spot.id, check_result)
        
        results.append({
            "spot_id": spot.id,
            "spot_name": spot.name,
            "status": check_result.status.value,
            "score": check_result.score
        })
    
    return {"results": results}


@router.get("/cameras")
async def get_cameras(request: Request):
    """Get available Home Assistant cameras."""
    camera: HACamera = request.app.state.camera
    cameras = await camera.get_cameras()
    
    return {
        "cameras": [
            {
                "entity_id": cam.entity_id,
                "name": cam.name,
                "state": cam.state
            }
            for cam in cameras
        ]
    }


@router.get("/spot-types")
async def get_spot_types():
    """Get available spot types and templates."""
    return {
        "types": [t.value for t in SpotType],
        "templates": SPOT_TEMPLATES
    }


@router.get("/voices")
async def get_voices():
    """Get available voice personalities."""
    return {"voices": get_all_voices()}


@router.get("/settings")
async def get_settings(request: Request):
    """Get current settings and status."""
    import os
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    return {
        "gemini_api_key_configured": bool(gemini_key),
        "supervisor_token_configured": bool(os.getenv("SUPERVISOR_TOKEN"))
    }
