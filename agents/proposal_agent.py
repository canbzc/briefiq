import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def compute_brief_gaps(requirements: dict, risks: dict) -> list[str]:
    """
    Brief'teki eksiklikleri ve çelişkileri tespit et.
    Returns: list of actionable suggestion strings.
    """
    gaps = []
    tier, _ = _pick_tier(requirements)

    # Bütçe belirtilmemiş
    if not requirements.get("budget_mentioned"):
        gaps.append("Ask the client for a budget range — no budget mentioned.")

    # Deadline yok
    if not requirements.get("deadline_days"):
        gaps.append("Ask for a preferred delivery date — no deadline mentioned.")

    # Tech stack boş
    if not requirements.get("tech_stack"):
        gaps.append("Ask about preferred technologies or platforms (e.g. WordPress, React, Shopify).")

    # Az feature → brief belirsiz
    features = requirements.get("main_features") or []
    if len(features) < 2:
        gaps.append("Brief is too vague — ask the client to list specific features or pages needed.")

    # Scope büyük ama deadline çok kısa
    deadline_days = requirements.get("deadline_days")
    if deadline_days and deadline_days < tier["days_min"]:
        gaps.append(
            f"Scope vs deadline conflict: client wants {deadline_days}-day delivery "
            f"but this project type typically needs {tier['days_min']}+ days. Clarify scope or timeline."
        )

    # Bütçe var ama çok düşük ve belirsiz scope
    budget_max = requirements.get("budget_max") or 0
    if requirements.get("budget_mentioned") and budget_max > 0 and budget_max < tier["price_min"]:
        gaps.append(
            f"Budget is below market minimum — ask if the scope can be reduced "
            f"or if budget is flexible."
        )

    return gaps


def compute_apply_score(requirements: dict, risks: dict, proposal: dict) -> dict:
    """
    0-100 arası "Should I Apply?" skoru hesapla.

    Ağırlıklar:
      Bütçe uyumu     : 40 puan
      Deadline uyumu  : 25 puan
      Gereksinim netliği: 20 puan
      Risk seviyesi   : 15 puan
    """
    tier, _ = _pick_tier(requirements)
    score = 0

    # --- Bütçe uyumu (40 puan) ---
    budget_mentioned = requirements.get("budget_mentioned", False)
    budget_max = requirements.get("budget_max") or 0
    price_min = tier["price_min"]
    price_max = tier["price_max"]

    if not budget_mentioned or budget_max == 0:
        # Bütçe belirtilmemiş → orta puan
        score += 25
    elif budget_max >= price_min + (price_max - price_min) * 0.5:
        # Üst yarı → tam puan
        score += 40
    elif budget_max >= price_min:
        # Alt yarı ama minimum üstü → kademeli puan
        ratio = (budget_max - price_min) / ((price_max - price_min) * 0.5 + 1)
        score += round(15 + ratio * 25)
    else:
        # Minimumun altı → 0
        score += 0

    # --- Deadline uyumu (25 puan) ---
    deadline_days = requirements.get("deadline_days")
    days_min = tier["days_min"]
    days_max = tier["days_max"]

    if not deadline_days:
        # Deadline yok → tam puan
        score += 25
    elif deadline_days >= days_min:
        # Makul deadline → kademeli puan (ne kadar rahat o kadar iyi)
        comfort = min((deadline_days - days_min) / max(days_max - days_min, 1), 1.0)
        score += round(15 + comfort * 10)
    else:
        # Çok sıkı deadline → 0
        score += 0

    # --- Gereksinim netliği (20 puan) ---
    features = requirements.get("main_features") or []
    if len(features) >= 4:
        score += 20
    elif len(features) == 3:
        score += 16
    elif len(features) == 2:
        score += 10
    elif len(features) == 1:
        score += 5
    else:
        score += 0

    # --- Risk seviyesi (15 puan) ---
    risk_level = risks.get("risk_level", "low")
    if risk_level == "low":
        score += 15
    elif risk_level == "medium":
        score += 7
    else:
        score += 0

    score = max(0, min(100, score))

    # Karar etiketi
    if score >= 70:
        label = "Apply"
        color = "green"
    elif score >= 45:
        label = "Proceed with Caution"
        color = "yellow"
    else:
        label = "Skip"
        color = "red"

    return {"score": score, "label": label, "color": color}

# Upwork piyasa verileri (2024-2025 güncel)
PROJECT_TYPES = {
    "simple landing page": {
        "description": "Template-based or copy existing, 1 page, minimal customization",
        "price_min": 50, "price_max": 300,
        "days_min": 1, "days_max": 5
    },
    "custom landing page": {
        "description": "Custom design, responsive, branded",
        "price_min": 200, "price_max": 800,
        "days_min": 3, "days_max": 10
    },
    "advanced landing page": {
        "description": "Animations, third-party integrations, complex layout",
        "price_min": 500, "price_max": 2000,
        "days_min": 7, "days_max": 21
    },
    "ecommerce website": {
        "description": "Product pages, cart, checkout, payment integration (Shopify/WooCommerce)",
        "price_min": 300, "price_max": 1500,
        "days_min": 7, "days_max": 30
    },
    "mobile app": {
        "description": "iOS or Android app, basic to medium complexity",
        "price_min": 1000, "price_max": 5000,
        "days_min": 30, "days_max": 60
    },
    "logo and branding": {
        "description": "Logo design, brand kit, color palette",
        "price_min": 100, "price_max": 1000,
        "days_min": 3, "days_max": 14
    },
    "dashboard or admin panel": {
        "description": "Data visualization, user management, CRUD operations",
        "price_min": 500, "price_max": 5000,
        "days_min": 14, "days_max": 60
    },
}

TIER_UPGRADES = [
    # Maps
    "google maps", "maps integration",
    # Payment
    "payment", "stripe", "paypal", "checkout",
    # Auth
    "user authentication", "user login", "login system", "auth",
    # CMS
    "cms", "wordpress", "content management",
    # API
    "api integration", "third-party api", "rest api",
    # Chat / booking
    "live chat", "booking", "reservation",
    # Forms with backend
    "contact form", "form submission",
    # Multilingual
    "multilingual", "multi-language",
    # Animations
    "animation", "gsap", "parallax",
]

# Landing page tier sırası (upgrade için)
LANDING_PAGE_TIERS = [
    "simple landing page",
    "custom landing page",
    "advanced landing page",
]

def _check_upgrades(features: list) -> list[str]:
    """Features listesinde upgrade tetikleyen özellikler varsa döndür."""
    features_lower = " ".join(f.lower() for f in features)
    return [u for u in TIER_UPGRADES if u in features_lower]


def _infer_tier_from_features(features: list) -> str | None:
    """Features listesine bakarak proje tipini tahmin et. Belirsiz proje tiplerinde kullanılır."""
    text = " ".join(f.lower() for f in features)
    if any(k in text for k in ["cart", "checkout", "product page", "payment", "shop", "store", "order"]):
        return "ecommerce website"
    if any(k in text for k in ["dashboard", "chart", "analytics", "admin", "crud", "data visualization"]):
        return "dashboard or admin panel"
    return None


def _pick_tier(requirements: dict) -> tuple[dict, str]:
    """Project type ve scope'a göre tier seç, feature upgrade uygula.
    Returns (tier dict, tier_upgrade_reason string)."""
    project_type = (requirements.get("project_type") or "").lower()
    scope = (requirements.get("estimated_scope") or "small").lower()
    features = requirements.get("main_features") or []

    # Açık proje tipi eşleştirmesi — upgrade uygulanmaz
    if any(k in project_type for k in ["ecommerce", "e-commerce", "shop", "store", "online store"]):
        return PROJECT_TYPES["ecommerce website"], ""
    if any(k in project_type for k in ["mobile", "app", "ios", "android", "flutter", "react native"]):
        return PROJECT_TYPES["mobile app"], ""
    if any(k in project_type for k in ["dashboard", "admin", "panel", "saas", "web app", "web application"]):
        return PROJECT_TYPES["dashboard or admin panel"], ""
    if any(k in project_type for k in ["logo", "brand", "identity", "design"]):
        return PROJECT_TYPES["logo and branding"], ""

    # Belirsiz tip ("website", "site", "portfolio", "blog", vb.) → feature'a göre tahmin et
    vague_types = ["website", "site", "web", "portfolio", "blog", "wordpress", "page", ""]
    if any(project_type == v or project_type.startswith(v) for v in vague_types):
        inferred = _infer_tier_from_features(features)
        if inferred:
            return PROJECT_TYPES[inferred], ""

    # Landing page / belirsiz → scope'a göre başlangıç tier'ı
    if scope == "large":
        tier_name = "advanced landing page"
    elif scope == "medium":
        tier_name = "custom landing page"
    else:
        tier_name = "simple landing page"

    # Feature-based upgrade
    matched = _check_upgrades(requirements.get("main_features") or [])
    upgrade_reason = ""
    if matched:
        current_index = LANDING_PAGE_TIERS.index(tier_name)
        # Zaten en üst tier'daysa upgrade olmaz
        if current_index < len(LANDING_PAGE_TIERS) - 1:
            tier_name = LANDING_PAGE_TIERS[current_index + 1]
            upgrade_reason = (
                f"Tier upgraded due to: {', '.join(matched)}. "
                f"These features add complexity beyond the base scope."
            )

    return PROJECT_TYPES[tier_name], upgrade_reason


class ProposalAgent:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def run(self, requirements: dict, risks: dict) -> dict:
        tier, tier_upgrade_reason = _pick_tier(requirements)

        # --- Bütçe değerlendirmesi (Python, LLM değil) ---
        budget_mentioned = requirements.get("budget_mentioned", False)
        budget_min = requirements.get("budget_min") or 0
        budget_max = requirements.get("budget_max") or 0
        price_min = tier["price_min"]
        price_max = tier["price_max"]

        budget_realistic = True
        budget_note = ""

        if budget_mentioned and budget_max > 0:
            budget_display = (
                f"${budget_min}–${budget_max}" if budget_min > 0 else f"up to ${budget_max}"
            )
            if budget_max < price_min:
                # Piyasa minimumunun altı → gerçekçi değil
                budget_realistic = False
                budget_note = (
                    f"Client budget ({budget_display}) is below market rate "
                    f"(${price_min}–${price_max}) for this project type."
                )
            elif budget_max < price_min + (price_max - price_min) * 0.33:
                # Alt %33 bandı → uyarı ver ama gerçekçi say
                budget_note = (
                    f"Client budget ({budget_display}) is on the low end of market rate "
                    f"(${price_min}–${price_max}). Negotiation may be needed."
                )

        # --- Önerilen fiyat ---
        # budget_min null/0 ise tier min'ini kullan
        if budget_realistic and budget_mentioned and budget_max > 0:
            suggested_min = budget_min if budget_min > 0 else tier["price_min"]
            suggested_max = budget_max
        else:
            suggested_min = tier["price_min"]
            suggested_max = tier["price_max"]

        # --- Deadline değerlendirmesi (Python, LLM değil) ---
        deadline_days = requirements.get("deadline_days")
        deadline_warning = ""
        if deadline_days and deadline_days < tier["days_min"]:
            deadline_warning = (
                f"Deadline is very tight ({deadline_days} days). "
                f"Minimum realistic timeline for this project is {tier['days_min']} days. "
                f"Consider negotiating."
            )

        estimated_days = tier["days_min"] if not deadline_days else max(deadline_days, tier["days_min"])

        # --- Saatlik oran hesabı ---
        # Tier'ın gün minimumunu baz al (deadline değil, gerçek çalışma süresi)
        # Günde ortalama 6 saat verimli çalışma varsayımı
        work_days = tier["days_min"]
        estimated_hours = work_days * 6
        hourly_min = round(suggested_min / estimated_hours, 1) if estimated_hours > 0 else None
        hourly_max = round(suggested_max / estimated_hours, 1) if estimated_hours > 0 else None

        # --- LLM: sadece metin alanları ---
        prompt = f"""
        You are a freelance proposal writer. Write a brief proposal strategy based on the project below.
        Return valid JSON only, no extra text. All text must be in English.

        Project type: {requirements.get("project_type")}
        Features: {requirements.get("main_features")}
        Scope: {requirements.get("estimated_scope")}
        Risk level: {risks.get("risk_level")}
        Red flags: {risks.get("red_flags")}
        Suggested price: ${suggested_min}–${suggested_max}
        Estimated days: {estimated_days}
        Budget realistic: {budget_realistic}

        Return format:
        {{
            "proposal_tone": "confident|cautious|enthusiastic",
            "key_selling_points": ["...", "...", "..."],
            "questions_to_ask_client": ["...", "...", "..."],
            "proposal_summary": "2-3 sentence summary"
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        llm_output = json.loads(content.strip())

        apply_score = compute_apply_score(requirements, risks, {
            "suggested_price_range": {"min": suggested_min, "max": suggested_max},
        })
        brief_gaps = compute_brief_gaps(requirements, risks)

        return {
            "apply_score": apply_score,
            "brief_gaps": brief_gaps,
            "market_rate_range": {"min": tier["price_min"], "max": tier["price_max"], "currency": "USD"},
            "suggested_price_range": {"min": suggested_min, "max": suggested_max, "currency": "USD"},
            "budget_realistic": budget_realistic,
            "budget_note": budget_note,
            "tier_upgrade_reason": tier_upgrade_reason,
            "deadline_warning": deadline_warning,
            "estimated_days": estimated_days,
            "estimated_hours": estimated_hours,
            "hourly_rate_range": {"min": hourly_min, "max": hourly_max, "currency": "USD"},
            "proposal_tone": llm_output.get("proposal_tone", "confident"),
            "key_selling_points": llm_output.get("key_selling_points", []),
            "questions_to_ask_client": llm_output.get("questions_to_ask_client", []),
            "proposal_summary": llm_output.get("proposal_summary", ""),
        }
