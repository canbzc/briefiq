import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class NegotiationAgent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def run(self, requirements: dict, risks: dict, proposal: dict, lang: str = "en") -> str:
        """Risk flag'lerine göre müzakere mesajı üret."""
        red_flags = risks.get("red_flags", [])
        risk_level = risks.get("risk_level", "medium")
        pr = proposal.get("suggested_price_range", {})
        mr = proposal.get("market_rate_range", {})
        deadline_days = requirements.get("deadline_days")
        estimated_days = proposal.get("estimated_days")

        lang_instruction = (
            "Write the message in Turkish."
            if lang == "tr"
            else "Write the message in English."
        )

        prompt = f"""
        You are an experienced freelancer who needs to negotiate better terms with a client.
        Write a polite but firm negotiation message addressing the specific issues below.
        {lang_instruction}

        Project: {requirements.get("project_type")}
        Features: {", ".join(requirements.get("main_features") or [])}
        Risk level: {risk_level}
        Red flags: {red_flags}
        Client budget: {"$" + str(requirements.get("budget_min", 0)) + "–$" + str(requirements.get("budget_max", 0)) if requirements.get("budget_mentioned") else "not mentioned"}
        Market rate: ${mr.get("min")}–${mr.get("max")}
        Suggested price: ${pr.get("min")}–${pr.get("max")}
        Client deadline: {str(deadline_days) + " days" if deadline_days else "not specified"}
        Realistic timeline: {estimated_days} days

        Rules:
        - Address ONLY the flagged issues (budget, deadline, unclear requirements)
        - Be respectful and solution-oriented, not confrontational
        - Propose a specific counter-offer (price or timeline)
        - Keep it under 150 words
        - Do NOT start with "Dear Client" or "Hi"
        - Do NOT use "I am a professional..." type phrases
        - End with a question or call to action
        - Return ONLY the message text, nothing else
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )

        return response.choices[0].message.content.strip()
