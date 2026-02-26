import db
from datetime import datetime
import sys

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing one-time Morning Brief Job...")
    try:
        db.generate_daily_advisor_brief()
        print("Morning Brief sent successfully.")
    except Exception as e:
        print(f"Error sending Morning Brief: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
