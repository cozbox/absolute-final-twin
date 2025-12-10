"""SQLite database implementation."""
import aiosqlite
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from app.core.models import Spot, SpotType, CheckResult, SpotStatus, ToSortItem
from app.core.memory import MemoryEngine


class Database:
    """SQLite database for TwinSync Spot."""
    
    def __init__(self, db_path: str = "/data/twinsync_spot.db"):
        self.db_path = db_path
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def init(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Spots table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS spots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    camera_entity_id TEXT NOT NULL,
                    spot_type TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    snoozed_until TEXT
                )
            """)
            
            # Checks table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spot_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    feedback TEXT NOT NULL,
                    items_to_sort TEXT,
                    FOREIGN KEY (spot_id) REFERENCES spots (id) ON DELETE CASCADE
                )
            """)
            
            await db.commit()
    
    async def create_spot(
        self,
        name: str,
        description: str,
        camera_entity_id: str,
        spot_type: SpotType,
        voice_id: str
    ) -> int:
        """Create a new spot."""
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO spots (name, description, camera_entity_id, spot_type, voice_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, description, camera_entity_id, spot_type.value, voice_id, now, now)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_spot(self, spot_id: int) -> Optional[Spot]:
        """Get a spot by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM spots WHERE id = ?", (spot_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                spot = self._row_to_spot(dict(row))
                
                # Get last check
                spot.last_check = await self._get_last_check(db, spot_id)
                
                # Calculate memory
                checks = await self._get_checks_for_memory(db, spot_id)
                spot.memory = MemoryEngine.calculate_memory(checks)
                
                return spot
    
    async def get_all_spots(self) -> List[Spot]:
        """Get all spots."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM spots ORDER BY updated_at DESC") as cursor:
                rows = await cursor.fetchall()
                
                spots = []
                for row in rows:
                    spot = self._row_to_spot(dict(row))
                    spot.last_check = await self._get_last_check(db, spot.id)
                    checks = await self._get_checks_for_memory(db, spot.id)
                    spot.memory = MemoryEngine.calculate_memory(checks)
                    spots.append(spot)
                
                return spots
    
    async def update_spot(
        self,
        spot_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        camera_entity_id: Optional[str] = None,
        spot_type: Optional[SpotType] = None,
        voice_id: Optional[str] = None
    ) -> bool:
        """Update a spot."""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if camera_entity_id is not None:
            updates.append("camera_entity_id = ?")
            params.append(camera_entity_id)
        if spot_type is not None:
            updates.append("spot_type = ?")
            params.append(spot_type.value)
        if voice_id is not None:
            updates.append("voice_id = ?")
            params.append(voice_id)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(spot_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE spots SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await db.commit()
            return True
    
    async def delete_spot(self, spot_id: int) -> bool:
        """Delete a spot and all its checks."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM spots WHERE id = ?", (spot_id,))
            await db.commit()
            return True
    
    async def snooze_spot(self, spot_id: int, until: datetime) -> bool:
        """Snooze a spot until a specific time."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE spots SET snoozed_until = ? WHERE id = ?",
                (until.isoformat(), spot_id)
            )
            await db.commit()
            return True
    
    async def unsnooze_spot(self, spot_id: int) -> bool:
        """Remove snooze from a spot."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE spots SET snoozed_until = NULL WHERE id = ?",
                (spot_id,)
            )
            await db.commit()
            return True
    
    async def add_check(self, spot_id: int, check_result: CheckResult) -> int:
        """Add a check result for a spot."""
        items_json = json.dumps([
            {
                "name": item.name,
                "location": item.location,
                "suggestion": item.suggestion
            }
            for item in check_result.items_to_sort
        ])
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO checks (spot_id, timestamp, status, score, feedback, items_to_sort)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    spot_id,
                    check_result.timestamp.isoformat(),
                    check_result.status.value,
                    check_result.score,
                    check_result.feedback,
                    items_json
                )
            )
            
            # Update spot's updated_at
            await db.execute(
                "UPDATE spots SET updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), spot_id)
            )
            
            await db.commit()
            return cursor.lastrowid
    
    async def get_checks(self, spot_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get check history for a spot."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checks WHERE spot_id = ? ORDER BY timestamp DESC LIMIT ?",
                (spot_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def reset_spot(self, spot_id: int) -> bool:
        """Reset a spot by deleting all its checks."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM checks WHERE spot_id = ?", (spot_id,))
            await db.commit()
            return True
    
    def _row_to_spot(self, row: Dict) -> Spot:
        """Convert a database row to a Spot object."""
        snoozed_until = None
        if row.get("snoozed_until"):
            snoozed_until = datetime.fromisoformat(row["snoozed_until"])
        
        return Spot(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            camera_entity_id=row["camera_entity_id"],
            spot_type=SpotType(row["spot_type"]),
            voice_id=row["voice_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            snoozed_until=snoozed_until
        )
    
    async def _get_last_check(self, db: aiosqlite.Connection, spot_id: int) -> Optional[CheckResult]:
        """Get the last check for a spot."""
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM checks WHERE spot_id = ? ORDER BY timestamp DESC LIMIT 1",
            (spot_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            row_dict = dict(row)
            items = []
            if row_dict.get("items_to_sort"):
                items_data = json.loads(row_dict["items_to_sort"])
                items = [
                    ToSortItem(
                        name=item["name"],
                        location=item["location"],
                        suggestion=item["suggestion"]
                    )
                    for item in items_data
                ]
            
            return CheckResult(
                timestamp=datetime.fromisoformat(row_dict["timestamp"]),
                status=SpotStatus(row_dict["status"]),
                score=row_dict["score"],
                feedback=row_dict["feedback"],
                items_to_sort=items
            )
    
    async def _get_checks_for_memory(self, db: aiosqlite.Connection, spot_id: int) -> List[Dict]:
        """Get checks for memory calculation."""
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM checks WHERE spot_id = ? ORDER BY timestamp DESC LIMIT 100",
            (spot_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
