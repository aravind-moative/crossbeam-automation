import os
from dotenv import load_dotenv
import google.generativeai as genai

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
        # Build dynamic hierarchy description
        if hierarchy_designations:
            hierarchy_desc = "Current hierarchy level: " + ", ".join([
                f"{level}={designation}" for level, designation in sorted(hierarchy_designations.items(), key=lambda x: int(x[0]))
            ]) + ". "
        else:
            hierarchy_desc = f"Current hierarchy level: {hierarchy_level} (1=Account Executive, 2=Sales Manager, 3=Executive Staff). "
        overlap_strength = ""
        if count == 1 and overlap_context:
            final_score = overlap_context.get('priority_score', None)
            if final_score is not None:
                try:
                    stars = int(round(float(final_score)))
                    star_rating = '★' * stars + '★' * (5 - stars)
                except:
                    star_rating = ''
                if star_rating:
                    overlap_strength = f"Overlap Strength: {star_rating}\n"
        # Special handling for logo potential
        if overlap_context and overlap_context.get('logo_potential', False):
            prompt = (
                f"You are a partner operations assistant. "
                f"Context: Ground-breaking overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                f"Internal recipient: {internal_name}. "
                f"Hierarchy: {hierarchy_desc}"
                f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                f"Relevant context: {overlap_context if overlap_context else '{}'} "
                f"Instructions: Write a message emphasizing that this is a very important, ground-breaking opportunity with exceptional strategic value and urgency. Do not mention calculations, scores, or star ratings. The message should be motivating, business-focused, and convey the urgency and significance of this opportunity. Output only the Slack message text without markdown formatting or explanation. "
            )
        elif count == 1:
            if hierarchy_level == 3:
                prompt = (
                    f"You are a partner operations assistant. "
                    f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                    f"Internal recipient: {internal_name} (Executive, Hierarchy 3). "
                    f"Hierarchy: {hierarchy_desc}"
                    f"Relevant context: {overlap_context if overlap_context else '{}'} "
                    f"Instructions: Write a short, professional internal message that explains a request, opportunity, or initiative has already been routed through the usual channels but hasn’t gained enough traction. The message should suggest that executive-level involvement or visibility may now be necessary to move it forward. Keep the tone clear, tactful, and solution-oriented — not blaming, just highlighting the need for a higher-level push. If overlap strength (stars) is available, place the star rating on its own line immediately after the opening line, before continuing with the rest of the message. Output only the Slack message text without markdown formatting or explanation. "
                    f"{overlap_strength}"
                )
            elif hierarchy_level == 2:
                prompt = (
                    f"You are a partner operations assistant. "
                    f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                    f"Internal recipient: {internal_name} (Sales Manager, Hierarchy 2). "
                    f"Account Executive: {ae_name if ae_name else 'N/A'} (Hierarchy 1). "
                    f"Hierarchy: {hierarchy_desc}"
                    f"Relevant context: {overlap_context if overlap_context else '{}'} "
                    f"Instructions: Write a professional, motivating, and business-focused Slack message for a Sales Manager (hierarchy 2). Do not say you are flagging an opportunity 'for' someone else. Instead, highlight the opportunity and its benefit, and instruct the recipient to connect with the Account Executive (provide both name and designation) to take next steps. Reference the strategic value of collaboration and the benefit of leveraging the partner. Avoid awkward or robotic phrasing. If overlap strength (stars) is available, place the star rating on its own line immediately after the opening line, before continuing with the rest of the message. Do not use chatbot-like language or generic CTAs. Output only the Slack message text without markdown formatting or explanation. "
                    f"{overlap_strength}"
                )
            else:
                prompt = (
                    f"You are a partner operations assistant. "
                    f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                    f"Internal recipient: {internal_name}. "
                    f"Hierarchy: {hierarchy_desc}"
                    f"Message count: {count}. "
                    f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                    f"Relevant context: {overlap_context if overlap_context else '{}'} "
                    f"Instructions: Write a concise, professional, and engaging Slack message for this scenario. Do not just state facts or scores—clearly communicate the benefit and value of this overlap opportunity, and what the team stands to gain if it is won. The message should be motivating and business-focused, not robotic or list-like. If overlap strength (stars) is available, place the star rating on its own line immediately after the opening line, before continuing with the rest of the message. Do not use chatbot-like language or generic CTAs. Output only the Slack message text without markdown formatting or explanation. "
                    f"{overlap_strength}"
                )
        else:
            # For follow-up messages in hierarchy 1, adjust the prompt to ask to connect with the partner
            if hierarchy_level == 1:
                prompt = (
                    f"You are a partner operations assistant. "
                    f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                    f"Internal recipient: {internal_name}. "
                    f"Hierarchy: {hierarchy_desc}"
                    f"Message count: {count}. "
                    f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                    f"Relevant context: {overlap_context if overlap_context else '{}'} "
                    f"Instructions: Write a casual, precise, and short follow-up Slack message for this scenario. This is {count}th time we followup. The message should be friendly, direct, and focused on nudging action, without being overly formal or detailed. Reference the opportunity and its benefit for our company. Instruct the recipient to connect directly with the partner or send a mail to discuss next steps or strategy. Keep the tone light and conversational. Output only the Slack message text without markdown formatting or explanation."
                    f"{overlap_strength}"
                )
            else:
                prompt = (
                    f"You are a partner operations assistant. "
                    f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
                    f"Internal recipient: {internal_name}. "
                    f"Hierarchy: {hierarchy_desc}"
                    f"Message count: {count}. "
                    f"Account Executive: {ae_name if ae_name else 'N/A'}. "
                    f"Relevant context: {overlap_context if overlap_context else '{}'} "
                    f"Instructions: Write a casual, precise, and short follow-up Slack message for this scenario. The message should be friendly, direct, and focused on nudging action, without being overly formal or detailed. Reference the opportunity and its benefit for our company, and reference connecting with the Account Executive by name and designation. Keep the tone light and conversational. Output only the Slack message text without markdown formatting or explanation. Just ask to connect with Account Executive to discuss about the opportunity."
                    f"{overlap_strength}"
                )
        print(prompt, "PROMPT IS HERE")
        response = self.model.generate_content(prompt)
        slack_message = response.text.strip()
        # For hierarchy 1, message 1, append the LLM-generated email draft
        if hierarchy_level == 1 and count == 1:
            email_draft = self.generate_enhanced_email_draft(
                record_name=record_name,
                partner_record_name=partner_record_name,
                partner_company_type=partner_company_type,
                overlap_context=overlap_context,
                sender_name=internal_name,
                sender_title="Account Executive",  # or fetch dynamically if needed
                company_name="Moative"
            )
            slack_message += "\n\n---\n\nEMAIL DRAFT:\n" + email_draft
        return slack_message

    def generate_enhanced_email_draft(
        self,
        record_name: str,
        partner_record_name: str,
        partner_company_type: str,
        overlap_context: dict = None,
        sender_name: str = "",
        sender_title: str = "",
        company_name: str = "Moative"
    ) -> str:
        # Construct a single, context-rich prompt for the LLM to generate the email draft
        prompt = (
            f"You are a partner operations assistant. "
            f"Context: Collaboration opportunity between {company_name} and partner {partner_record_name} (type: {partner_company_type}) at mutual account {record_name}. "
            f"Sender: {sender_name}, {sender_title} at {company_name}. "
            f"Relevant context: {overlap_context if overlap_context else '{}'} "
            f"Instructions: Write a concise, catchy, and professional business email draft for this scenario. The email should include a clear subject, a formal greeting, a brief background/context, a summary of the opportunity and its significance, and the benefit of the overlap or collaboration. The tone should be professional but engaging, and the message should capture the value and benefit of the opportunity. Do not use chatbot-like language or generic CTAs. Output only the email draft text, including subject, greeting, body, and closing, but do not use markdown formatting or explanation. "
        )
        print(prompt, "EMAIL PROMPT IS HERE")
        response = self.model.generate_content(prompt)
        email = response.text.strip()
        return email

    def generate_priority_summary(self, overlap_context: dict) -> str:
        if not overlap_context:
            return "Priority data not available"
        priority_level = overlap_context.get('priority_level', 'Unknown')
        score = overlap_context.get('priority_score', 0)
        logo = 'LOGO' if overlap_context.get('logo_potential', False) else ''
        prospect = overlap_context.get('prospect', {})
        partner = overlap_context.get('partner', {})
        prospect_score = (
            prospect.get('opportunity_size', 0)
            + prospect.get('relationship_status', 0)
            + (5 if prospect.get('engagement_score', '').upper() == 'HIGH' else 3 if prospect.get('engagement_score', '').upper() == 'MEDIUM' else 1 if prospect.get('engagement_score', '').upper() == 'LOW' else 0)
            + prospect.get('opportunity_stage', 0)
        ) if prospect else None
        partner_score = (
            partner.get('opportunity_relevance_score', 0)
            + partner.get('relationship_strength_score', 0)
            + partner.get('recent_deal_support', 0)
            + partner.get('winnability_opinion', 0)
        ) if partner else None
        summary = f"Priority: {priority_level} ({score}) {logo} | Prospect Score: {prospect_score if prospect_score is not None else 'N/A'} | Partner Score: {partner_score if partner_score is not None else 'N/A'}"
        summary += f" | Prospect: Size={prospect.get('opportunity_size', 'N/A')}, Rel={prospect.get('relationship_status', 'N/A')}, Eng={prospect.get('engagement_score', 'N/A')}, Stage={prospect.get('opportunity_stage', 'N/A')}"
        summary += f" | Partner: RelScore={partner.get('opportunity_relevance_score', 'N/A')}, Strength={partner.get('relationship_strength_score', 'N/A')}, Support={partner.get('recent_deal_support', 'N/A')}, Winnability={partner.get('winnability_opinion', 'N/A')}"
        if overlap_context.get('has_champion'):
            summary += " | 🏆 Champion"
        return summary
