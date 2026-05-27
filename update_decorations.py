"""Update decorations: fix garland, add position setting, add birthday confetti"""
import sqlite3

# 1. Update database - add position column
conn = sqlite3.connect('instance/portal.db')
cursor = conn.cursor()

# Check if position column exists
cursor.execute("PRAGMA table_info(site_decorations)")
columns = [col[1] for col in cursor.fetchall()]
if 'position' not in columns:
    cursor.execute(
        "ALTER TABLE site_decorations ADD COLUMN position VARCHAR(20) DEFAULT 'above'")
    print("Added position column to site_decorations")

conn.commit()
conn.close()
print("Database updated")
