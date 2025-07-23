import os
from dotenv import load_dotenv
import google.generativeai as genai
from scripts.overlap_utils import get_weights
from scripts.context_prompt import context_prompt

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiMessageGenerator:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-pro")

    def generate_overlap_message(
        self,
        record_name: str,
        overlap_type: str,
        internal_name: str,
        partner_record_name: str,
        partner_company_type: str,
        count: int,
        hierarchy_level: int = 1,
        overlap_context: dict = None,
        hierarchy_designations: dict = None,
        ae_name: str = None
    ) -> str:
        # --- Filter and order context by weights ---
        opportunity_weights = get_weights('opportunity')
        partner_weights = get_weights('partner')
        def filter_and_order(section, weights):
            if not overlap_context or section not in overlap_context:
                return {}
            # If all weights are zero or missing, return the full section context
            if not any(w > 0 for w in weights.values()):
                return dict(overlap_context[section])
            # Only include fields with weight > 0, order by weight descending
            items = [(k, v) for k, v in overlap_context[section].items() if weights.get(k, 0) > 0]
            items.sort(key=lambda x: -weights.get(x[0], 0))
            return {k: v for k, v in items}
        filtered_context = dict(overlap_context) if overlap_context else {}
        filtered_context['opportunity'] = filter_and_order('opportunity', opportunity_weights)
        filtered_context['partner'] = filter_and_order('partner', partner_weights)
        focus_parts = []
        for section, weights, label in [
            ('opportunity', opportunity_weights, 'Opportunity'),
            ('partner', partner_weights, 'Partner')
        ]:
            focus = [k.replace('_', ' ').title() for k, w in weights.items() if w > 0]
            if focus:
                focus_parts.append(f"{label}: {', '.join(focus)}")
        focus_text = "Focus on: " + "; ".join(focus_parts) if focus_parts else ""
        # --- Updated prompt instructions ---
        explicit_instructions = (
            "When mentioning any attribute (such as champion, relationship, support, etc.), always specify whether it refers to the partner or the opportunity/account. "
            "Do not use vague references like 'there' or 'mutual relationship'—be explicit (e.g., 'Our partner xxxx has a champion supporting this opportunity', 'At our opportunity yyyy, winnability is high'). "
            "Always state clearly who is the partner and who is the opportunity/account. Do not use star ratings or include any stars in the message. "
            "In this context, 'partner_champion' always refers to a champion at the partner organization, not at the opportunity/account. If there is a champion, always specify which company they are with."
        )

        if hierarchy_designations:
            hierarchy_desc = "Current hierarchy level: " + ", ".join([
                f"{level}={designation}" for level, designation in sorted(hierarchy_designations.items(), key=lambda x: int(x[0]))
            ]) + ". "
        else:
            hierarchy_desc = f"Current hierarchy level: {hierarchy_level} (1=Account Executive, 2=Sales Manager, 3=Executive Staff). "

        if count == 1:
            if overlap_context and overlap_context.get('logo_potential', False):
                # FIRST MESSAGE — LOGO POTENTIAL
                if hierarchy_level == 3:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name} (Executive, Hierarchy 3). "
                        f"Hierarchy: {hierarchy_desc} "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a short internal message (1–2 paragraphs max) explaining that this opportunity, which involves our partner and opportunity, has already been routed through the usual channels but hasn't gained enough traction. It is a highly strategic, market-defining engagement with potential for major visibility or brand impact. Tactfully suggest that executive visibility or involvement may now be necessary to move it forward. Be clear, solution-oriented, and constructive — no blaming. Avoid using scoring terms or the word 'logo'. Do not include greeting or sign-off. Output only the Slack message. Be friendly and be direct."
                    )
                elif hierarchy_level == 2:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name} (Sales Manager, Hierarchy 2). "
                        f"Account Executive: {ae_name if ae_name else 'N/A'} (Hierarchy 1). "
                        f"Hierarchy: {hierarchy_desc} "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a short, professional message (1–2 paragraphs max) to the Sales Manager about a high-visibility, strategic opportunity. Encourage them to reach out to the Account Executive ({ae_name}) to and drive this forward. This is an escalation message to Sales Manager since Account Executive missed to respond but don't mention this. Be actionable and motivating, without using robotic phrases or scoring terms. Don’t say 'logo'. No greeting or sign-off. Output only the Slack message. Be friendly and natural."
                    )
                else:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name}. "
                        f"Hierarchy: {hierarchy_desc} "
                        f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a short, natural, and motivating Slack message (1–2 paragraphs max) about this highly strategic opportunity with significant brand and visibility upside. Encourage timely action and suggest connecting with the partner to discuss the next steps. Do not include a greeting or sign-off. Avoid scoring terms and the word 'logo'. Output only the Slack message."
                    )
            else:
                # FIRST MESSAGE — NO LOGO POTENTIAL
                if hierarchy_level == 3:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name} (Executive, Hierarchy 3). "
                        f"Hierarchy: {hierarchy_desc}"
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a short, professional internal message that explains a request, opportunity, or initiative has already been routed through the usual channels but hasn’t gained enough traction. The message should suggest that executive-level involvement or visibility may now be necessary to move it forward. Keep the tone clear, tactful, and solution-oriented — not blaming, just highlighting the need for a higher-level push. Output only the Slack message text without markdown formatting or explanation. Avoid using scoring terms like 'HIGH', 'VERY LARGE', 'EARLY CRM STAGE', 'GOOD', etc. Be natural and be direct."
                    )
                elif hierarchy_level == 2:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name} (Sales Manager, Hierarchy 2). "
                        f"Account Executive: {ae_name if ae_name else 'N/A'} (Hierarchy 1). "
                        f"Hierarchy: {hierarchy_desc}"
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a professional, motivating, and business-focused Slack message for a Sales Manager (hierarchy 2). Highlight the opportunity and its benefit, and instruct to reach out to the Account Executive (provide both name and designation) to take next steps. Reference the strategic value of collaboration and the benefit of leveraging the partner. Avoid awkward or robotic phrasing. Output only the Slack message text without markdown formatting or explanation. Avoid using scoring terms like 'HIGH', 'VERY LARGE', 'EARLY CRM STAGE', 'GOOD', etc. Ask to reach out to Account Executive. Be natural."
                    )
                else:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name}. "
                        f"Hierarchy: {hierarchy_desc}"
                        f"Message count: {count}. "
                        f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a concise, professional, and engaging Slack message for this scenario. Clearly communicate the benefit and value of this overlap opportunity, and what the team stands to gain if it is won. The message should be motivating and business-focused, not robotic or list-like. Output only the Slack message text without markdown formatting or explanation. Avoid using scoring terms like 'HIGH', 'VERY LARGE', 'EARLY CRM STAGE', 'GOOD', etc. Be natural and be direct."
                    )
        else:
            if overlap_context and overlap_context.get('logo_potential', False):
                # FOLLOW-UP — LOGO POTENTIAL (Short & Strategic)
                if hierarchy_level == 3:
                    prompt = (
                        f"You're assisting with partner ops strategy.\n"
                        f"This is a follow-up for {internal_name} (Exec, Hierarchy 3) about a strategic overlap with {record_name} with partner {partner_record_name} ({partner_company_type}).\n"
                        f"Message count: {count}.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a short, one-sentence message nudging exec attention on this high-impact opportunity. No need for intros or sign-offs — just keep it crisp and business-focused. Be natural."
                    )
                elif hierarchy_level == 2:
                    prompt = (
                        f"You're helping nudge Sales Management.\n"
                        f"This one’s for {internal_name} (Hierarchy 2) regarding a valuable overlap with {record_name} with partner {partner_record_name} ({partner_company_type}).\n"
                        f"The AE is {ae_name if ae_name else 'N/A'}. Message count: {count}.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a one-line Slack message urging {internal_name} to sync with {ae_name} and help move things forward with the partner. No need for scoring language or 'logo' references. Just be friendly and natural."
                    )
                else:
                    prompt = (
                        f"You're helping with a quick partner follow-up.\n"
                        f"This one’s for {internal_name} — overlap with {record_name} with partner {partner_record_name} ({partner_company_type}). AE on it is {ae_name if ae_name else 'N/A'}. Message count: {count}.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a short, friendly one-liner nudging {internal_name} to check in with the AE or partner on this strategic opportunity. Keep it natural and Slack-ready — no scores, no mention of 'logo'. Be friendly and natural."
                    )

            else:
                # FOLLOW-UP — NO LOGO POTENTIAL (Short & Tactical)
                if hierarchy_level == 1:
                    prompt = (
                        f"You're helping with partner operations.\n"
                        f"We're looking at an overlap with {record_name} with partner {partner_record_name} ({partner_company_type}).\n"
                        f"This is for {internal_name} (message #{count}).\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a quick, natural Slack nudge — just one casual sentence nudging {internal_name} to loop in the partner. It is a followup message. Keep it light, helpful, and non-robotic. No em dashes."
                    )
                elif hierarchy_level == 3:
                    prompt = (
                        f"You're supporting partner strategy visibility.\n"
                        f"Overlap with {record_name}, partner is {partner_record_name} ({partner_company_type}).\n"
                        f"This is a short exec-level follow-up for {internal_name} (message #{count}).\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a super-brief follow-up (1–2 sentences) that subtly nudges for visibility or alignment. It is a followup message. No intros or sign-offs — just the core message. Be friendly and casual."
                    )
                else:
                    prompt = (
                        f"You're helping with partner follow-ups.\n"
                        f"We’ve got an overlap with account, {record_name} with {partner_record_name} ({partner_company_type}).\n"
                        f"This message is for {internal_name} (message #{count}), and {ae_name} is the AE involved.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a clean one-line reminding {internal_name} to check in with {ae_name} and align on next steps with the partner. It is a followup message. Make it sound friendly, quick, and Slack-like. Be casual."
                    )

        response = self.model.generate_content(prompt)
        slack_message = response.text.strip()
        return slack_message

    def generate_priority_summary(self, overlap_context: dict) -> str:
        if not overlap_context:
            return "Priority data not available"
        priority_level = overlap_context.get('priority_level', 'Unknown')
        score = overlap_context.get('priority_score', 0)
        logo = 'LOGO' if overlap_context.get('logo_potential', False) else ''
        opportunity = overlap_context.get('opportunity', {})
        partner = overlap_context.get('partner', {})
        opportunity_score = (
            opportunity.get('opportunity_size', 0)
            + opportunity.get('relationship_status', 0)
            + (5 if opportunity.get('engagement_score', '').upper() == 'HIGH' else 3 if opportunity.get('engagement_score', '').upper() == 'MEDIUM' else 1 if opportunity.get('engagement_score', '').upper() == 'LOW' else 0)
            + opportunity.get('opportunity_stage', 0)
        ) if opportunity else None
        partner_score = (
            partner.get('opportunity_relevance_score', 0)
            + partner.get('relationship_strength_score', 0)
            + partner.get('recent_deal_support', 0)
            + partner.get('winnability_opinion', 0)
        ) if partner else None
        summary = f"Priority: {priority_level} ({score}) {logo} | Opportunity Score: {opportunity_score if opportunity_score is not None else 'N/A'} | Partner Score: {partner_score if partner_score is not None else 'N/A'}"
        summary += f" | Opportunity: Size={opportunity.get('opportunity_size', 'N/A')}, Rel={opportunity.get('relationship_status', 'N/A')}, Eng={opportunity.get('engagement_score', 'N/A')}, Stage={opportunity.get('opportunity_stage', 'N/A')}"
        summary += f" | Partner: RelScore={partner.get('opportunity_relevance_score', 'N/A')}, Strength={partner.get('relationship_strength_score', 'N/A')}, Support={partner.get('recent_deal_support', 'N/A')}, Winnability={partner.get('winnability_opinion', 'N/A')}"
        if overlap_context.get('has_champion'):
            summary += " | 🏆 Champion"
        return summary
