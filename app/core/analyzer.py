"""Image analysis using Gemini API."""
import os
import base64
import json
import aiohttp
from datetime import datetime
from typing import Optional, List
from app.core.models import CheckResult, SpotStatus, ToSortItem
from app.core.voices import get_voice_prompt


class SpotAnalyzer:
    """Analyzes spot images using Gemini 2.0 Flash."""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-2.0-flash-exp"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
    
    async def analyze_spot(
        self,
        image_data: bytes,
        spot_description: str,
        voice_id: str,
        memory_context: Optional[str] = None
    ) -> CheckResult:
        """Analyze a spot image and return results."""
        if not self.api_key:
            return CheckResult(
                timestamp=datetime.now(),
                status=SpotStatus.UNKNOWN,
                score=0,
                feedback="Gemini API key not configured",
                items_to_sort=[]
            )
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # Build the prompt
        voice_prompt = get_voice_prompt(voice_id)
        
        prompt = f"""You are analyzing a space to see if it matches this description:
"{spot_description}"

{voice_prompt}

Based on the image:
1. Does it match the description? (yes/no)
2. Give it a score from 0-100 (0 = completely off, 100 = perfect match)
3. Provide feedback in your voice style
4. List any items that need to be sorted/organized (max 5)

{f"Context from previous checks: {memory_context}" if memory_context else ""}

Respond in this exact JSON format:
{{
  "matches": true/false,
  "score": 0-100,
  "feedback": "your feedback here",
  "items_to_sort": [
    {{"name": "item name", "location": "where it is", "suggestion": "what to do with it"}}
  ]
}}"""
        
        # Prepare API request
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}?key={self.api_key}",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return CheckResult(
                            timestamp=datetime.now(),
                            status=SpotStatus.UNKNOWN,
                            score=0,
                            feedback=f"API error: {error_text[:100]}",
                            items_to_sort=[]
                        )
                    
                    result = await response.json()
                    
                    # Extract text from response
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Parse JSON from text (remove markdown code blocks if present)
                    text = text.strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                    
                    data = json.loads(text)
                    
                    # Build CheckResult
                    status = SpotStatus.PASS if data.get("matches", False) else SpotStatus.FAIL
                    score = max(0, min(100, data.get("score", 0)))
                    feedback = data.get("feedback", "No feedback provided")
                    
                    items = []
                    for item_data in data.get("items_to_sort", [])[:5]:
                        items.append(ToSortItem(
                            name=item_data.get("name", "Unknown"),
                            location=item_data.get("location", ""),
                            suggestion=item_data.get("suggestion", "")
                        ))
                    
                    return CheckResult(
                        timestamp=datetime.now(),
                        status=status,
                        score=score,
                        feedback=feedback,
                        items_to_sort=items
                    )
        
        except Exception as e:
            return CheckResult(
                timestamp=datetime.now(),
                status=SpotStatus.UNKNOWN,
                score=0,
                feedback=f"Analysis error: {str(e)}",
                items_to_sort=[]
            )
