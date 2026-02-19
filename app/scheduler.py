import schedule
import time
import db
from datetime import datetime
import os

# Ensure DB is initialized or connection works
# db module handles connection via 'porsche_parts.db'

def job():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running Morning Brief Job...")
    try:
        db.generate_daily_advisor_brief()
        print("Morning Brief sent successfully.")
    except Exception as e:
        print(f"Error sending Morning Brief: {e}")

# Schedule the job every day at 08:00
schedule.every().day.at("08:00").do(job)

print("Scheduler started. Waiting for 08:00 trigger...")
print("Press Ctrl+C to exit.")

# Run immediately for testing? Uncomment to test.
# job()

while True:
    schedule.run_pending()
    time.sleep(60) # check every minute
