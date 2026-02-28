import smtplib
from email.mime.text import MIMEText
import traceback
import os

print("Testing SMTP connection...")
# Use the values we expect
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "porsche.tracker.app@gmail.com"
SENDER_PASSWORD = "rmkljmigockhnujw"
RECEIVER = "tsalem@porscheleb.com" # Send to self for testing

print(f"Connecting to {SMTP_SERVER}:{SMTP_PORT} as {SENDER_EMAIL}...")

try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.set_debuglevel(1) # Enable verbose debug output
    server.ehlo()
    print("Starting TLS...")
    server.starttls()
    server.ehlo()
    print("Logging in...")
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    
    msg = MIMEText("This is a test email format TLS")
    msg['Subject'] = 'Test Email'
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER
    
    print("Sending email...")
    server.sendmail(SENDER_EMAIL, RECEIVER, msg.as_string())
    server.quit()
    print("SUCCESS: Email sent!")
except Exception as e:
    print(f"FAILURE: Exception occurred:")
    traceback.print_exc()
