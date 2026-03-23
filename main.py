import json
from agents.requirements_agent import RequirementsAgent
from agents.risk_agent import RiskAgent
from agents.proposal_agent import ProposalAgent

# Test için örnek brief
SAMPLE_BRIEF = """
I need a landing page for my restaurant. It should have a menu section,
contact form, and Google Maps integration. Mobile friendly is a must.
Budget is around $200-300. Need it done in 2 weeks.
"""

def print_section(title: str, data: dict):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)
    print(json.dumps(data, indent=2, ensure_ascii=False))

def main():
    brief = SAMPLE_BRIEF.strip()

    print("\nFreelance Brief Analyzer")
    print(f"\nBrief:\n{brief}")

    # 1. Adım: Requirements Agent
    print("\n[1/3] Requirements analiz ediliyor...")
    req_agent = RequirementsAgent()
    requirements = req_agent.run(brief)
    print_section("REQUIREMENTS", requirements)

    # 2. Adım: Risk Agent (requirements çıktısını alır)
    print("\n[2/3] Riskler değerlendiriliyor...")
    risk_agent = RiskAgent()
    risks = risk_agent.run(requirements)
    print_section("RISK ANALYSIS", risks)

    # 3. Adım: Proposal Agent (her ikisini alır)
    print("\n[3/3] Proposal oluşturuluyor...")
    proposal_agent = ProposalAgent()
    proposal = proposal_agent.run(requirements, risks)
    print_section("PROPOSAL STRATEGY", proposal)

    # Final rapor
    print(f"\n{'='*50}")
    print("  FINAL RAPOR")
    print('='*50)
    print(f"Risk Seviyesi : {risks.get('risk_level', '?').upper()}")
    print(f"Devam Önerisi : {'EVET' if risks.get('proceed_recommendation') else 'HAYIR'}")
    print(f"Piyasa Oranı  : ${proposal['market_rate_range']['min']} - ${proposal['market_rate_range']['max']}")
    print(f"Önerilen Fiyat: ${proposal['suggested_price_range']['min']} - ${proposal['suggested_price_range']['max']}")
    print(f"Bütçe Gerçekçi: {'EVET' if proposal.get('budget_realistic', True) else 'HAYIR'}")
    if proposal.get('budget_note'):
        print(f"Bütçe Notu    : {proposal.get('budget_note')}")
    print(f"Süre          : {proposal.get('estimated_days', '?')} gün")
    print(f"\nÖzet: {proposal.get('proposal_summary', '')}")
    print('='*50)

if __name__ == "__main__":
    main()
