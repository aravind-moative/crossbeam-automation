import sqlite3

# Connect to SQLite DB
conn = sqlite3.connect("scoring_weights.db")
cursor = conn.cursor()

# Get min values for all the scoring columns
cursor.execute("""
    SELECT
        MIN(opportunity_size_score),
        MIN(relationship_status_score),
        MIN(engagement_score_score),
        MIN(opportunity_stage_score),
        MIN(winnability_score),
        MIN(relationship_strength_score),
        MIN(recent_deal_support_score),
        MIN(stickiness_score)
    FROM crossbeam_records
""")
min_values = cursor.fetchone()

# Get the ID of the first row (ordered by rowid)
cursor.execute("SELECT id FROM crossbeam_records ORDER BY rowid LIMIT 1")
first_id = cursor.fetchone()[0]

# Update first row with min values and logo_potential = 1 (True)
cursor.execute("""
    UPDATE crossbeam_records
    SET
        opportunity_size_score = ?,
        relationship_status_score = ?,
        engagement_score_score = ?,
        opportunity_stage_score = ?,
        winnability_score = ?,
        relationship_strength_score = ?,
        recent_deal_support_score = ?,
        stickiness_score = ?,
        logo_potential = 1
    WHERE id = ?
""", (*min_values, first_id))

conn.commit()
conn.close()

print("✅ First row updated with minimum scores and logo_potential = true.")
