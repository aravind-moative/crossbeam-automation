def context_prompt():
    return """
Key Attributes:
Prospect: opportunity_size, relationship_status, engagement_score, opportunity_stage, winnability, logo_potential
Partner: relationship_strength_score, recent_deal_support, stickiness_score, partner_champion

Definitions:

With PROSPECTS:
- Opportunity Size: Indicates potential deal value
- Relationship Status: Reflects our familiarity with the account
- Engagement Score: Measures how actively the account is responding
- Opportunity Stage: Early stage = more flexible, Late stage = decision is near
- Winnability: Your judgment of how likely we are to win the deal

With PARTNERS:
- Stickiness Score: How deeply the partner is involved in the opportunity (e.g., tech integration, co-selling)
- Partner Champion: Someone at the partner org who is actively supporting the deal (flagged if present, not scored)
- Relationship Strength Score: How strong or strategic our relationship with the partner is
- Recent Deal Support: How supportive the partner has been in recent joint deals

Scoring Reference:
With PROSPECTS:
- Opportunity Size:
  • 1 = SMALL
  • 3 = MEDIUM
  • 4 = LARGE
  • 5 = VERY LARGE

- Relationship Status:
  • 1 = New
  • 3 = Past
  • 5 = Existing

- Engagement Score:
  • 1 = LOW
  • 3 = MEDIUM
  • 5 = HIGH

- Opportunity Stage:
  • 1 = EARLY CRM STAGE -  Opportunity is in a very early phase. There's more room to influence, but less certainty about the outcome. Ideal for early engagement and shaping the deal
  • 5 = LATE STAGE – Opportunity is close to decision or closure. There's less room to shape, but higher confidence that the deal is real and actionable. Good for execution and closing support

- Winnability:
  • 1 = LOW
  • 3 = NEUTRAL
  • 5 = HIGH

With PARTNERS:
- Stickiness Score: [0–5]
  • 0 = Not involved at all
  • 1–2 = Slight to moderate involvement
  • 3–4 = Strong involvement
  • 5 = Critically embedded

- Relationship Strength Score:
  • 1 = COLD
  • 3 = TRANSACTIONAL
  • 5 = STRATEGIC

- Recent Deal Support:
  • 1 = POOR
  • 3 = ADEQUATE
  • 5 = GOOD

Important Writing Guidelines:
- Write a short Slack-style message (1–2 natural, motivating paragraphs)
- Don’t list attributes directly or sound like you're reading from a rubric
- Be strategic, clear, and actionable — but conversational
- Mention specific signals like "low engagement from the account" or "Partner hasn't been very active in past deals", instead of labels or scores
- If there's no champion at the partner, don't force the mention
- Focus on what action to take next
- Emphasize the high brand or visibility potential, but avoid the word "logo"
- Do not include greetings or sign-offs
- Output only the Slack message
- Don't use all the exact parameters we have; Just make a more natural message as to a coworker while we see him while break
- Be direct and be friendly and casual
- Do not use em dashes or bullet points
- DO NOT USE THE FOLLOWING TERMS EXPLICITLY; BUT IN A FRIENDLY WAY
- Never say overlap opportunity at; instead say overlap opportunity with
      opportunity_size
      relationship_status
      engagement_score
      opportunity_stage
      winnability
      logo_potential
      stickiness_score
      relationship_strength_score
      recent_deal_support
      partner_champion
"""