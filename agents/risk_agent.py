import json
import os
from groq import Groq
from dotenv import load_dotenv
from agents.proposal_agent import _pick_tier

load_dotenv()


def _detect_flags(requirements: dict) -> tuple[list[str], list[str]]:
    """Deterministik risk flag tespiti. (red_flags, risk_titles) döndürür."""
    tier, _ = _pick_tier(requirements)
    red_flags = []
    risk_titles = []

    # Tight Deadline: sadece deadline < days_min ise flag ekle
    deadline_days = requirements.get("deadline_days")
    if deadline_days and deadline_days < tier["days_min"]:
        red_flags.append("Tight deadline")
        risk_titles.append("Tight Deadline")

    # Bütçe flag'leri
    budget_mentioned = requirements.get("budget_mentioned", False)
    budget_max = requirements.get("budget_max") or 0
    if budget_mentioned and budget_max > 0:
        price_min = tier["price_min"]
        price_max = tier["price_max"]
        # Low Budget: piyasa minimumunun altındaysa
        if budget_max < price_min:
            red_flags.append("Low budget")
            risk_titles.append("Low Budget")
        # Tight Budget: piyasa range'inin alt %33'ündeyse (ama minimum üstündeyse)
        elif budget_max < price_min + (price_max - price_min) * 0.33:
            red_flags.append("Tight budget")
            risk_titles.append("Tight Budget")

    # Unclear requirements: features listesi boş veya çok kısaysa
    features = requirements.get("main_features") or []
    if len(features) < 2:
        red_flags.append("Unclear requirements")
        risk_titles.append("Unclear Requirements")

    return red_flags, risk_titles


def _compute_risk_level(risk_titles: list[str], budget_realistic: bool) -> tuple[str, bool]:
    """Risk seviyesi ve proceed önerisi hesapla."""
    has_tight_deadline = "Tight Deadline" in risk_titles
    has_low_budget = "Low Budget" in risk_titles
    has_tight_budget = "Tight Budget" in risk_titles
    has_unclear = "Unclear Requirements" in risk_titles

    if has_tight_deadline and has_low_budget:
        risk_level = "high"
    elif has_tight_deadline or has_low_budget:
        risk_level = "medium"
    elif has_tight_budget or has_unclear:
        # Tight budget tek başına low, deadline ile birleşince medium
        risk_level = "medium" if (has_tight_budget and has_tight_deadline) else "low"
    else:
        risk_level = "low"

    # Proceed: NO sadece HIGH risk + budget_realistic false birlikte ise
    proceed = not (risk_level == "high" and not budget_realistic)

    return risk_level, proceed


class RiskAgent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def run(self, requirements: dict) -> dict:
        tier, _ = _pick_tier(requirements)
        red_flags, risk_titles = _detect_flags(requirements)

        # Budget realistic hesabı (proposal_agent ile aynı mantık)
        budget_max = requirements.get("budget_max") or 0
        budget_realistic = not (
            requirements.get("budget_mentioned") and
            budget_max > 0 and
            budget_max < tier["price_min"]  # piyasa minimumunun altıysa gerçekçi değil
        )

        risk_level, proceed = _compute_risk_level(risk_titles, budget_realistic)

        # LLM: sadece her flag için açıklama üret
        prompt = f"""
        Write a short risk description for each of the following risk flags for a freelance project.
        Return valid JSON only, no extra text. All text must be in English.

        Project: {requirements.get("project_type")}, scope: {requirements.get("estimated_scope")}
        Risk flags: {risk_titles}
        Market rate: ${tier["price_min"]}–${tier["price_max"]}, timeline: {tier["days_min"]}–{tier["days_max"]} days
        Client deadline: {requirements.get("deadline_days")} days
        Client budget: ${requirements.get("budget_min")}–${requirements.get("budget_max")}

        Return a JSON array where each item matches one flag:
        [
            {{"title": "...", "description": "1-2 sentences explaining the risk", "severity": "low|medium|high"}}
        ]
        If risk_flags is empty, return an empty array [].
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        risks_list = json.loads(content.strip())

        return {
            "risk_level": risk_level,
            "risks": risks_list,
            "red_flags": red_flags,
            "proceed_recommendation": proceed,
        }
