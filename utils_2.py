import sqlite3

# Connect to the database
conn = sqlite3.connect("scoring_weights.db")
cursor = conn.cursor()

# Fetch all records from the internal_team table
cursor.execute("SELECT * FROM internal_team")
rows = cursor.fetchall()

# Get column names
columns = [description[0] for description in cursor.description]

# Print column headers
print(" | ".join(columns))
print("-" * 50)

# Print each row
for row in rows:
    print(" | ".join(str(item) for item in row))

# Close the connection
conn.close()
