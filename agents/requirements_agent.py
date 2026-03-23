import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class RequirementsAgent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def run(self, brief: str) -> dict:
        prompt = f"""
        Extract raw data from the freelance project brief below. Do NOT evaluate, judge, or make decisions.
        Just extract what is explicitly stated. Return valid JSON only, no extra text.
        All string values must be in English.

        Brief:
        {brief}

        Return format:
        {{
            "project_type": "...",
            "main_features": ["...", "..."],
            "tech_stack": ["...", "..."],
            "estimated_scope": "small|medium|large",
            "deadline_days": null,
            "budget_mentioned": true/false,
            "budget_min": null,
            "budget_max": null,
            "budget_currency": "USD",
            "raw_budget_text": "exact budget text from brief, or null if not mentioned"
        }}

        Rules:
        - tech_stack: only include what the client explicitly mentioned. If they didn't specify, return []
        - deadline_days: convert to number of days if mentioned (e.g. "2 weeks" = 14), else null
        - budget_min/budget_max: extract the numbers as-is, do not adjust or evaluate
        - Do not add fields that aren't in this format
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # Markdown code block varsa temizle, sonra parse et
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
