"""Home Assistant camera adapter."""
import os
import aiohttp
from typing import List, Optional
from app.core.models import Camera


class HACamera:
    """Interface with Home Assistant cameras."""
    
    def __init__(self):
        self.supervisor_token = os.getenv("SUPERVISOR_TOKEN")
        self.ha_url = "http://supervisor/core/api"
    
    async def get_cameras(self) -> List[Camera]:
        """Get all available camera entities from Home Assistant."""
        if not self.supervisor_token:
            return []
        
        headers = {
            "Authorization": f"Bearer {self.supervisor_token}",
            "Content-Type": "application/json",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ha_url}/states",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        return []
                    
                    states = await response.json()
                    
                    # Filter for camera entities
                    cameras = []
                    for entity in states:
                        if entity.get("entity_id", "").startswith("camera."):
                            cameras.append(Camera(
                                entity_id=entity["entity_id"],
                                name=entity.get("attributes", {}).get("friendly_name", entity["entity_id"]),
                                state=entity.get("state", "unknown")
                            ))
                    
                    return cameras
        
        except Exception:
            return []
    
    async def get_snapshot(self, camera_entity_id: str) -> Optional[bytes]:
        """Get a snapshot from a camera entity."""
        if not self.supervisor_token:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.supervisor_token}",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ha_url}/camera_proxy/{camera_entity_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status != 200:
                        return None
                    
                    return await response.read()
        
        except Exception:
            return None
    
    async def test_camera(self, camera_entity_id: str) -> bool:
        """Test if a camera is accessible."""
        snapshot = await self.get_snapshot(camera_entity_id)
        return snapshot is not None
