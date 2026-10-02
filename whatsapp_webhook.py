import os

from flask import Flask, request
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ==============================
# Twilio configuration
# ==============================

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID")

print("================================")
print("MacroSnap WhatsApp Webhook")
print("================================")
print("Twilio Account SID loaded:", bool(TWILIO_ACCOUNT_SID))
print("Twilio Auth Token loaded:", bool(TWILIO_AUTH_TOKEN))
print("WhatsApp number:", TWILIO_WHATSAPP_NUMBER)
print("Content SID loaded:", bool(TWILIO_CONTENT_SID))
print("================================")

client = Client(
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN
)


# ==============================
# WhatsApp webhook
# ==============================

@app.route("/whatsapp", methods=["POST"])
def whatsapp():

    incoming_message = request.form.get("Body", "")
    sender = request.form.get("From", "")

    print("================================")
    print("WhatsApp message received:")
    print(incoming_message)
    print("From:")
    print(sender)
    print("================================")

    try:

        # Send WhatsApp template using Twilio Content API
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=sender,
            content_sid=TWILIO_CONTENT_SID,
            content_variables='{"1": "Test MacroSnap"}'
        )

        print("Reply sent successfully!")
        print("Message SID:", message.sid)
        print("================================")

        return "OK", 200

    except Exception as e:

        print("================================")
        print("TWILIO ERROR:")
        print(str(e))
        print("================================")

        return "Twilio error", 500


# ==============================
# Home
# ==============================

@app.route("/", methods=["GET"])
def home():
    return "MacroSnap WhatsApp Webhook is running!"


# ==============================
# Start server
# ==============================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=3000,
        debug=False
    )