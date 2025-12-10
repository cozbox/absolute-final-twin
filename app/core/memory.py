"""Memory and pattern detection engine."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter
from app.core.models import SpotPatterns, SpotMemory, CheckResult, SpotStatus


class MemoryEngine:
    """Analyzes check history to detect patterns."""
    
    @staticmethod
    def analyze_patterns(checks: List[Dict]) -> SpotPatterns:
        """Analyze check history to find patterns."""
        if not checks:
            return SpotPatterns()
        
        # Find recurring items
        all_items = []
        for check in checks:
            if check.get("items_to_sort"):
                import json
                items = json.loads(check["items_to_sort"]) if isinstance(check["items_to_sort"], str) else check["items_to_sort"]
                for item in items:
                    all_items.append(item.get("name", "").lower())
        
        # Count occurrences
        item_counts = Counter(all_items)
        recurring_items = [item for item, count in item_counts.most_common(5) if count > 1]
        
        # Analyze by day of week
        day_scores: Dict[str, List[int]] = {}
        for check in checks:
            timestamp = datetime.fromisoformat(check["timestamp"].replace('Z', '+00:00'))
            day = timestamp.strftime("%A")
            score = check.get("score", 0)
            
            if day not in day_scores:
                day_scores[day] = []
            day_scores[day].append(score)
        
        # Find best and worst days
        day_averages = {day: sum(scores) / len(scores) for day, scores in day_scores.items() if scores}
        best_day = max(day_averages, key=day_averages.get) if day_averages else None
        worst_day = min(day_averages, key=day_averages.get) if day_averages else None
        
        # Calculate streaks
        current_streak = 0
        best_streak = 0
        temp_streak = 0
        
        # Sort checks by timestamp
        sorted_checks = sorted(checks, key=lambda x: x["timestamp"])
        
        for check in sorted_checks:
            status = check.get("status", "unknown")
            if status == SpotStatus.PASS.value:
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 0
        
        # Current streak is the last continuous passing streak
        for check in reversed(sorted_checks):
            status = check.get("status", "unknown")
            if status == SpotStatus.PASS.value:
                current_streak += 1
            else:
                break
        
        return SpotPatterns(
            recurring_items=recurring_items,
            best_day=best_day,
            worst_day=worst_day,
            current_streak=current_streak,
            best_streak=best_streak
        )
    
    @staticmethod
    def calculate_memory(checks: List[Dict]) -> Optional[SpotMemory]:
        """Calculate memory/context from check history."""
        if not checks:
            return None
        
        patterns = MemoryEngine.analyze_patterns(checks)
        
        # Calculate pass rate
        total_checks = len(checks)
        passed_checks = sum(1 for check in checks if check.get("status") == SpotStatus.PASS.value)
        pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0.0
        
        return SpotMemory(
            patterns=patterns,
            last_updated=datetime.now(),
            total_checks=total_checks,
            pass_rate=pass_rate
        )
    
    @staticmethod
    def get_memory_context(memory: Optional[SpotMemory]) -> str:
        """Generate a text summary of memory for the analyzer."""
        if not memory:
            return ""
        
        context_parts = []
        
        if memory.patterns.recurring_items:
            items_str = ", ".join(memory.patterns.recurring_items[:3])
            context_parts.append(f"Items that often appear: {items_str}")
        
        if memory.patterns.current_streak > 0:
            context_parts.append(f"Current passing streak: {memory.patterns.current_streak} checks")
        
        if memory.patterns.best_day:
            context_parts.append(f"This spot is usually best on {memory.patterns.best_day}")
        
        context_parts.append(f"Overall pass rate: {memory.pass_rate:.0f}%")
        
        return " | ".join(context_parts)
