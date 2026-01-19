import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from scripts.overlap_utils import get_weights
from scripts.context_prompt import context_prompt

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiMessageGenerator:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

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
            "Do not use vague references like 'there' or 'mutual relationship'—be explicit (e.g., 'Our partner xxxx has a champion supporting this opportunity', 'In our opportunity yyyy, winnability is high'). "
            "Always state clearly who is the partner and who is the opportunity/account. Do not use star ratings or include any stars in the message. "
            "In this context, 'partner_champion' always refers to a champion in the partner organization, not in the opportunity/account. If there is a champion, always specify which company they are with."
        )

        if hierarchy_designations:
            hierarchy_desc = "Current hierarchy level: " + ", ".join([
                f"{level}={designation}" for level, designation in sorted(hierarchy_designations.items(), key=lambda x: int(x[0]))
            ]) + ". "
        else:
            hierarchy_desc = f"Current hierarchy level: {hierarchy_level} (1=Account Executive, 2=Sales Manager, 3=Executive Staff). "

        ae_name = overlap_context.get("ae_name", "Account Executive")

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
                        f"Account Executive: {ae_name} (Hierarchy 1). "
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
                        f"Account Executive: {ae_name}. "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: You are messaging Account Executive. Write a short, natural, and motivating Slack message (1–2 paragraphs max) about this highly strategic opportunity with significant brand and visibility upside. Encourage timely action and suggest connecting with the partner to discuss the next steps. Do not include a greeting or sign-off. Avoid scoring terms and the word 'logo'. Output only the Slack message."
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
                        f"Account Executive: {ae_name} (Hierarchy 1). "
                        f"Hierarchy: {hierarchy_desc}"
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: Write a professional, motivating, and business-focused Slack message for a Sales Manager (hierarchy 2). Highlight the opportunity and its benefit, and instruct to reach out to the Account Executive ({ae_name}) to take next steps. Reference the strategic value of collaboration and the benefit of leveraging the partner. Avoid awkward or robotic phrasing. Output only the Slack message text without markdown formatting or explanation. Avoid using scoring terms like 'HIGH', 'VERY LARGE', 'EARLY CRM STAGE', 'GOOD', etc. Ask to reach out to Account Executive. Be natural."
                    )
                else:
                    prompt = (
                        f"You are a partner operations assistant. "
                        f"Context: Overlap opportunity between our company and partner {partner_record_name} (type: {partner_company_type}) with mutual account {record_name}. "
                        f"Internal recipient: {internal_name}. "
                        f"Hierarchy: {hierarchy_desc}"
                        f"Message count: {count}. "
                        f"Account Executive: {ae_name}. "
                        f"Relevant context: {filtered_context if filtered_context else '{}'} {focus_text} "
                        f"{explicit_instructions} "
                        f"{context_prompt()}"
                        f"Instructions: You are writing to Account Executive. Write a concise, professional, and engaging Slack message for this scenario. Clearly communicate the benefit and value of this overlap opportunity, and what the team stands to gain if it is won. The message should be motivating and business-focused, not robotic or list-like. Output only the Slack message text without markdown formatting or explanation. Avoid using scoring terms like 'HIGH', 'VERY LARGE', 'EARLY CRM STAGE', 'GOOD', etc. Be natural and be direct."
                    )
        else:
            if overlap_context and overlap_context.get('logo_potential', False):
                # FOLLOW-UP — LOGO POTENTIAL
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
                        f"The AE is {ae_name}. Message count: {count}.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a one-line Slack message urging {internal_name} to check with {ae_name} and help move things forward with the partner. No need for scoring language or 'logo' references. Just be friendly and natural."
                    )
                else:
                    prompt = (
                        f"You're helping with a quick partner follow-up.\n"
                        f"This one’s for {internal_name} — overlap with {record_name} with partner {partner_record_name} ({partner_company_type}). AE on it is {ae_name}. Message count: {count}.\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a short, friendly one-liner nudging {internal_name} to the AE to check this strategic opportunity. Keep it natural and Slack-ready — no scores, no mention of 'logo'. Be friendly and natural."
                    )
            else:
                # FOLLOW-UP — NO LOGO POTENTIAL
                if hierarchy_level == 1:
                    prompt = (
                        f"You're helping with partner operations.\n"
                        f"We're looking on an overlap with {record_name} with partner {partner_record_name} ({partner_company_type}).\n"
                        f"This is for {internal_name} (message #{count}).\n"
                        f"{explicit_instructions} "
                        f"{context_prompt()}\n"
                        f"Write a quick, natural Slack nudge; Just one casual sentence nudging {internal_name} to loop in the partner. It is a followup message. Keep it light, helpful, and non-robotic. No em dashes."
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                slack_message = response.text.strip()
                return slack_message
            except Exception as e:
                logger.error(f"Error generating overlap message (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    # Final attempt failed, use fallback
                    return self.generate_fallback_message(
                        record_name, partner_record_name, partner_company_type, 
                        hierarchy_level, overlap_context, ae_name
                    )
                # Wait before retrying
                import time
                time.sleep(1)

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

    def generate_fallback_message(self, record_name: str, partner_record_name: str, partner_company_type: str, 
                                hierarchy_level: int, overlap_context: dict, ae_name: str) -> str:
        """Generate a fallback message when Gemini API fails."""
        if hierarchy_level == 3:
            return f"Executive Alert: High-priority opportunity {record_name} with partner {partner_record_name} ({partner_company_type}) requires executive attention. Please review and provide strategic guidance."
        elif hierarchy_level == 2:
            return f"Manager Alert: Opportunity {record_name} with partner {partner_record_name} needs escalation. Please connect with {ae_name} to drive this forward."
        else:
            return f"Partner Opportunity: {record_name} with {partner_record_name} ({partner_company_type}) needs attention. Please review and take action."

    def generate_sql_query(self, user_question: str, table_schema: str) -> str:
        """Generate SQL query from natural language question using Gemini AI."""
        prompt = f"""
You are a SQL expert. Given a user question and database schema, generate a valid SQLite query.

Database Schema:
{table_schema}

User Question: {user_question}

Instructions:
1. Generate ONLY the SQL query, no explanations, questions, or markdown
2. Use proper SQLite syntax
3. Make the query efficient and readable
4. If the question is unclear, generate a simple SELECT query that returns some data
5. Focus on the crossbeam_records table which contains partner-opportunity data
6. NEVER ask for clarification in the response - always generate a valid SQL query
7. Use the exact column names from the schema provided
8. For opportunity/partner queries, ALWAYS include opportunity_name and partner_name fields
9. AVOID using the 'id' field unless specifically requested
10. For priority/score queries, include relevant score fields and sort by score descending

Available columns for queries:
- opportunity_name, opportunity_website, opportunity_size_label, opportunity_size_score
- relationship_status_label, relationship_status_score, engagement_score_label, engagement_score_score
- opportunity_stage_label, opportunity_stage_score, winnability_label, winnability_score
- logo_potential, partner_name, partner_website, partner_size_label, partner_size_score
- stickiness_label, stickiness_score, relationship_strength_label, relationship_strength_score
- recent_deal_support_label, recent_deal_support_score, partner_champion_flagged

Example valid responses:
- SELECT opportunity_name, partner_name, opportunity_size_score FROM crossbeam_records WHERE opportunity_size_score > 3
- SELECT partner_name, COUNT(*) as count FROM crossbeam_records GROUP BY partner_name
- SELECT opportunity_name, partner_name, opportunity_size_score, opportunity_stage_label FROM crossbeam_records ORDER BY opportunity_size_score DESC LIMIT 10
- SELECT opportunity_name, partner_name, logo_potential, opportunity_stage_label FROM crossbeam_records WHERE logo_potential = 1

Generate the SQL query:
"""
        
        try:
            response = self.model.generate_content(prompt)
            sql_query = response.text.strip()
            
            # Clean up the response to ensure it's just SQL
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:]
            if sql_query.endswith('```'):
                sql_query = sql_query[:-3]
            
            sql_query = sql_query.strip()
            
            # Validate that it looks like SQL
            if not sql_query.upper().startswith('SELECT'):
                logger.warning(f"Generated query doesn't start with SELECT: {sql_query}")
                return "SELECT * FROM crossbeam_records LIMIT 10"
            
            # Check for common error patterns
            if any(error_word in sql_query.lower() for error_word in ['could', 'please', 'clarify', 'question', 'what do you mean']):
                logger.warning(f"Generated query contains clarification text: {sql_query}")
                return "SELECT * FROM crossbeam_records LIMIT 10"
            
            return sql_query
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return "SELECT * FROM crossbeam_records LIMIT 10"

    def generate_natural_response(self, user_question: str, query_results: list, result_count: int, sql_query: str) -> str:
        """Generate natural language response based on query results using Gemini AI."""
        prompt = f"""
You are a helpful business intelligence assistant for Nexus, a partner opportunity management system. Generate a natural, conversational response based on the user's question and the query results.

User Question: {user_question}
SQL Query Executed: {sql_query}
Number of Results: {result_count}

Query Results (first 5 rows):
{str(query_results[:5]) if query_results else "No results found"}

Instructions:
1. Analyze the actual data in the query results and provide specific insights
2. Mention specific opportunity names, partner names, scores, or stages from the data
3. Provide actionable business insights based on the data
4. Don't mention SQL or technical details
5. Be specific about what you found - don't just say "I found X results"
6. Keep responses concise but informative
7. Use business-friendly language
8. DO NOT use any markdown formatting (no **bold**, *italic*, or other formatting)
9. Use plain text only - no special characters for emphasis
10. If the data shows opportunities, mention specific ones by name
11. If the data shows scores, mention the score ranges or averages
12. If the data shows stages, mention which stages are most common
13. If the query asks about "lacking" or "weak" partner support, focus on opportunities with low partner scores
14. When analyzing partner support, look at relationship_strength_score, recent_deal_support_score, and stickiness_score
15. If partner scores are low (< 3), emphasize the need for improved partner engagement

Example responses based on actual data:
- "I found 15 high-priority opportunities including TechCorp (score: 85.2%), DataFlow (score: 82.1%), and CloudPeak (score: 78.9%). These are all in the 'Close to Win' stage and have strong partner relationships."
- "The top opportunities ready to close are InnovateTech with a score of 92.3% and NexGen Solutions at 88.7%. Both are in the 'Close to Win' stage and have logo potential."
- "I identified 8 opportunities in the 'Early CRM Stage' that haven't been touched yet, including StartUp Inc (score: 45.2%) and GrowthCorp (score: 42.8%). These need immediate attention."
- "The opportunities with the highest scores are TechNova (94.1%), DataCore (91.3%), and CloudTech (89.7%). All three are in advanced stages and have strong partner engagement."
- "I found 5 opportunities close to winning that lack strong partner support: TechCorp (relationship strength: 2.0), DataFlow (recent support: 1.5), and CloudPeak (stickiness: 2.5). These need immediate partner engagement to close successfully."

Natural Response:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating natural response: {e}")
            return f"I found {result_count} results for your query. The data is displayed in the visualization panel."

    def generate_visualization_config(self, user_question: str, query_results: list, sql_query: str) -> dict:
        """Generate visualization configuration based on query results using Gemini AI."""
        prompt = f"""
You are a data visualization expert. Analyze the user question and query results to determine the best visualization type and configuration.

User Question: {user_question}
SQL Query: {sql_query}
Query Results (first 10 rows):
{str(query_results[:10]) if query_results else "No results found"}

Available visualization types:
1. "bar_chart" - For comparing categories or showing distributions
2. "pie_chart" - For showing proportions of a whole
3. "line_chart" - For trends over time or continuous data
4. "scatter_plot" - For showing relationships between two variables
5. "metric_cards" - For key performance indicators
6. "heatmap" - For showing patterns in matrix data
7. "donut_chart" - For proportions with center space
8. "table" - For displaying detailed records with multiple columns

Instructions:
1. Analyze the query type and data structure
2. ALWAYS choose a visualization type - never use text_only
3. Determine what data to display on x-axis, y-axis, or other dimensions
4. Consider the user's intent and what insights they're seeking
5. For simple counts or statistics, use metric_cards
6. For lists or comparisons, use bar_chart
7. For distributions, use pie_chart or donut_chart
8. For detailed opportunity/partner records with many fields, consider table visualization
9. For aggregated data or summaries, use bar_chart, pie_chart, or metric_cards
10. Choose table ONLY when you absolutely need to show detailed individual records with multiple fields
11. Choose charts when you want to show patterns, comparisons, or distributions
12. Prefer bar_chart for partner comparisons and rankings
13. Prefer pie_chart for distributions and proportions
14. Prefer metric_cards for simple counts and KPIs
15. For "quick deal close" queries, prefer bar_chart showing partners by opportunity count or opportunities by winnability score
16. AVOID table visualization for "quick deal close" scenarios - use charts instead
17. For "partner-opportunity matrix" or "matrix" queries, ALWAYS use heatmap visualization
18. For queries about "lacking" or "weak" partner support, prefer bar_chart showing opportunities with their partner support scores
12. Return a JSON configuration with the following structure:
   {{
     "type": "visualization_type",
     "title": "Descriptive title",
     "subtitle": "Brief description",
     "data": {{
       "x_axis": "column_name or category",
       "y_axis": "column_name or value",
       "series": "column_name for grouping (optional)",
       "labels": "column_name for labels (optional)",
       "columns": ["column1", "column2", "column3"] (for table visualization)
     }},
     "options": {{
       "show_legend": true/false,
       "show_values": true/false,
       "sort_by": "column_name or 'value'",
       "limit": number_of_items_to_show
     }}
   }}

Examples:
- For "How many opportunities per partner?" → bar_chart with partner_name on x-axis, opportunity_count on y-axis
- For "What's the score distribution?" → pie_chart with score ranges on labels, counts on values
- For "How many total opportunities do we have?" → metric_cards with total count
- For "What's the average score?" → metric_cards with average score
- For "Show me top 10 partners by score" → bar_chart with partner_name on x-axis, avg_score on y-axis
- For "Which partners have logo potential?" → bar_chart with partner_name on x-axis, logo_potential_count on y-axis
- For "What's the breakdown by stage?" → pie_chart with opportunity_stage_label on labels, stage_count on values
- For "What's the distribution of opportunity sizes?" → pie_chart with opportunity_size_label on labels, size_count on values
- For "How are opportunities distributed across relationship statuses?" → pie_chart with relationship_status_label on labels, status_count on values
- For "Show me partner performance comparison" → bar_chart with partner_name on x-axis, avg_score on y-axis
- For "Which deals should we prioritize?" → bar_chart with partner_name on x-axis, avg_score on y-axis (showing partner performance)
- For "Show me high priority opportunities" → metric_cards showing total count, average score, high-priority count
- For "Big wins" or "prioritize" → pie_chart with opportunity_stage_label on labels, stage_count on values (showing pipeline distribution)
- For "Show me opportunities with high scores" → bar_chart with opportunity_name on x-axis, combined_score on y-axis (top opportunities)
- For "opportunities ready to close" → pie_chart with opportunity_stage_label on labels, stage_count on values (focusing on close-to-win)
- For "opportunities in good position" → bar_chart with partner_name on x-axis, opportunity_count on y-axis (partner opportunity counts)
- For "quick deal close" or "opportunities to consider for quick close" → bar_chart with partner_name on x-axis, opportunity_count on y-axis (showing which partners have most quick-close opportunities)
- For "which opportunities to consider for quick deal close" → bar_chart with opportunity_name on x-axis, winnability_score on y-axis (showing top opportunities by winnability)
- For "partner-opportunity matrix" or "matrix" → heatmap with partner_name on y-axis, opportunity_name on x-axis, combined_score_percent on values (showing score intensity grid)
- For "lacking partner support" or "weak partner support" → bar_chart with opportunity_name on x-axis, partner support scores on y-axis (showing relationship strength, recent support, stickiness scores)

Visualization Decision Guidelines:
- Use TABLE when: Showing detailed individual records with multiple fields (like specific opportunities with names, scores, stages)
- Use BAR_CHART when: Comparing categories, showing rankings, or displaying aggregated data
- Use PIE_CHART when: Showing proportions or distributions of a whole
- Use METRIC_CARDS when: Displaying simple counts, averages, or key performance indicators
- Use DONUT_CHART when: Showing proportions with additional context in the center

Visualization Configuration (JSON only):"""
        
        try:
            response = self.model.generate_content(prompt)
            config_text = response.text.strip()
            
            # Clean up the response to extract JSON
            if config_text.startswith('```json'):
                config_text = config_text[7:]
            if config_text.endswith('```'):
                config_text = config_text[:-3]
            
            import json
            config = json.loads(config_text.strip())
            return config
        except Exception as e:
            logger.error(f"Error generating visualization config: {e}")
            # Fallback to metric cards visualization
            return {
                "type": "metric_cards",
                "title": "Query Results",
                "subtitle": f"Showing {len(query_results)} results",
                "data": {
                    "metrics": [
                        {"label": "Total Results", "value": len(query_results)},
                        {"label": "Query Status", "value": "Completed"}
                    ]
                },
                "options": {
                    "show_legend": False,
                    "show_values": True
                }
            }
