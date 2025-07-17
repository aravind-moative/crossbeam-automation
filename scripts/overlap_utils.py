import json

def load_crossbeam_data():
    try:
        with open("data/crossbeam_records_50.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def prospect_score(prospect):
    size = prospect.get('opportunity_size', 0)
    relationship = prospect.get('relationship_status', 0)
    engagement_map = {'HIGH': 5, 'MEDIUM': 3, 'LOW': 1}
    engagement = engagement_map.get(prospect.get('engagement_score', '').upper(), 0)
    stage = prospect.get('opportunity_stage', 0)
    total = (
        (size / 5) * 0.25 +
        (relationship / 5) * 0.25 +
        (engagement / 5) * 0.25 +
        (stage / 5) * 0.25
    )
    return total * 5  # Scale to 0-5

def partner_score(partner):
    # Weighted, normalized scoring (0-5 scale)
    relevance = partner.get('opportunity_relevance_score', 0)
    strength = partner.get('relationship_strength_score', 0)
    support = partner.get('recent_deal_support', 0)
    winnability = partner.get('winnability_opinion', 0)
    total = (
        (relevance / 5) * 0.25 +
        (strength / 5) * 0.25 +
        (support / 5) * 0.25 +
        (winnability / 5) * 0.25
    )
    return total * 5  # Scale to 0-5

def get_logo_potential(prospect):
    return prospect.get('logo_potential', False)

def get_partner_champion_flag(partner):
    champ = partner.get('partner_champion', {})
    return champ.get('is_flagged', False)

class OverlapQualifier:
    def __init__(self):
        self.crossbeam_data = load_crossbeam_data()
        self.crossbeam_lookup = {record["record_id"]: record for record in self.crossbeam_data}

    def calculate_priority_score(self, record: dict) -> tuple:
        prospect = record.get('prospect_factors', {})
        partner = record.get('partner_insights', {})
        if get_logo_potential(prospect):
            # LOGO Potential is max normalized score
            return 5, {
                "logo_potential": True,
                "prospect": prospect,
                "partner": partner,
                "has_champion": get_partner_champion_flag(partner),
                "priority_score": 5,
                "priority_level": "LOGO POTENTIAL"
            }
        p_score = prospect_score(prospect) if prospect else None
        pa_score = partner_score(partner) if partner else None
        if p_score is not None and pa_score is not None:
            final_score = (p_score + pa_score) / 2
        elif p_score is not None:
            final_score = p_score
        elif pa_score is not None:
            final_score = pa_score
        else:
            final_score = 0
        context = {
            "logo_potential": False,
            "prospect": prospect,
            "partner": partner,
            "has_champion": get_partner_champion_flag(partner),
            "priority_score": final_score,
            "priority_level": "SCORED"
        }
        return final_score, context

    def should_process_overlap(self, record: dict) -> tuple:
        score, context = self.calculate_priority_score(record)
        return True, context

    def get_enhanced_record(self, record_id: str) -> dict:
        return self.crossbeam_lookup.get(record_id)

    def get_dynamic_message_frequency(self, priority_score: int) -> dict:
        return {"hierarchy_1": 3, "hierarchy_2": 2, "hierarchy_3": 1} 