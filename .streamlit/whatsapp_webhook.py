from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_message = request.form.get("Body", "")

    print("================================")
    print("WhatsApp message received:")
    print(incoming_message)
    print("================================")

    response = MessagingResponse()
    response.message(
        "✅ MacroSnap received your WhatsApp message!\n\n"
        f"You sent: {incoming_message}"
    )

    return Response(str(response), mimetype="text/xml")


@app.route("/", methods=["GET"])
def home():
    return "MacroSnap WhatsApp Webhook is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)