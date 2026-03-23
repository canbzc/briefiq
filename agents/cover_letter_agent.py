import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class CoverLetterAgent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def run(self, requirements: dict, risks: dict, proposal: dict, lang: str = "en") -> str:
        """Analiz sonuçlarına göre Upwork cover letter üret."""
        pr = proposal.get("suggested_price_range", {})
        mr = proposal.get("market_rate_range", {})

        lang_instruction = (
            "Write the cover letter in Turkish."
            if lang == "tr"
            else "Write the cover letter in English."
        )

        prompt = f"""
        You are an expert Upwork freelancer writing a winning cover letter.
        Write a professional, personalized cover letter based on the project details below.
        {lang_instruction}

        Project type: {requirements.get("project_type")}
        Features requested: {", ".join(requirements.get("main_features") or [])}
        Tech stack mentioned: {", ".join(requirements.get("tech_stack") or []) or "not specified"}
        Client budget: {"$" + str(requirements.get("budget_min")) + "–$" + str(requirements.get("budget_max")) if requirements.get("budget_mentioned") else "not mentioned"}
        Deadline: {str(requirements.get("deadline_days")) + " days" if requirements.get("deadline_days") else "not specified"}

        Risk level: {risks.get("risk_level")}
        Proceed recommendation: {"YES" if risks.get("proceed_recommendation") else "NO"}

        Suggested price: ${pr.get("min")}–${pr.get("max")}
        Estimated delivery: {proposal.get("estimated_days")} days
        Proposal tone: {proposal.get("proposal_tone")}
        Key selling points: {", ".join(proposal.get("key_selling_points") or [])}
        Questions to ask: {", ".join(proposal.get("questions_to_ask_client") or [])}

        Rules:
        - Start with a hook that shows you understand the client's problem, NOT with "I"
        - Keep it under 200 words
        - Sound human, not robotic or salesy
        - Naturally mention the suggested price and delivery time
        - End with 1-2 of the questions to ask the client
        - Do NOT use generic phrases like "I am a professional developer with X years..."
        - Do NOT add a subject line or greeting like "Dear Client"
        - Return ONLY the cover letter text, nothing else
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()
