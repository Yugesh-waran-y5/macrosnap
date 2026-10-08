import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
    layout="centered",
)


# ============================================================
# SECRETS
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]


# ============================================================
# CLIENTS
# ============================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# ============================================================
# MESSAGE FUNCTIONS
# ============================================================

def render_message(message):
    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.write(message["content"])

        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    message = {
        "role": role,
        "kind": kind,
        "content": content,
    }

    st.session_state.messages.append(message)

    render_message(message)


# ============================================================
# GEMINI
# ============================================================

def ask_gemini(parts):

    try:
        response = st.session_state.chat.send_message(parts)

        if response.text:
            return response.text

        return "Sorry, Gemini returned an empty response."

    except Exception as error:
        return f"Sorry, something went wrong with Gemini: {error}"


# ============================================================
# WHATSAPP TEXT CLEANING
# ============================================================

def clean_whatsapp_text(text):

    if not text:
        return "No nutrition summary available."

    # Remove excessive spaces and newlines
    text = " ".join(text.split())

    # Keep WhatsApp message reasonably short
    if len(text) > 1500:
        text = text[:1500] + "..."

    return text


# ============================================================
# WHATSAPP NUMBER
# ============================================================

def normalize_whatsapp_number(number):
    """
    Converts:

        +919876543210

    into:

        whatsapp:+919876543210

    Also prevents:

        whatsapp:whatsapp:+919876543210
    """

    number = number.strip()

    if number.startswith("whatsapp:"):
        return number

    return f"whatsapp:{number}"


# ============================================================
# SEND WHATSAPP
# ============================================================
def send_whatsapp(to_number, user_name, summary):
    try:
        whatsapp_to = normalize_whatsapp_number(to_number)

        clean_summary = clean_whatsapp_text(summary)

        message_text = (
            f"Hi {user_name}, here's your MacroSnap nutrition summary:\n\n"
            f"{clean_summary}\n\n"
            "Stay healthy! 🥗"
        )

        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_to,
            body=message_text,
        )

        return True, message.sid

    except Exception as error:
        return False, str(error)


# ============================================================
# ONBOARDING
# ============================================================

if "onboarded" not in st.session_state:

    st.title("🥗 MacroSnap")

    st.caption(
        "Snap it. Track it. Text yourself the results."
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name",
        )

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help=(
                "Use the same WhatsApp number that "
                "joined your Twilio Sandbox."
            ),
        )

        submitted = st.form_submit_button(
            "Let's go 🚀",
            use_container_width=True,
        )

    if submitted:

        if not name.strip() or not whatsapp_number.strip():

            st.warning(
                "Please fill in both your name and WhatsApp number."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            # Create Gemini chat
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# MACROSNAP HEADER
# ============================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)


with header_col:

    st.title("🥗 MacroSnap")


with button_col:

    if st.button(
        "📤 Send to WhatsApp",
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your nutrition..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary,
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

            st.caption(
                f"Twilio Message SID: {info}"
            )

        else:

            st.error(
                "Couldn't send the WhatsApp message."
            )

            st.code(
                info,
                language="text",
            )


# ============================================================
# USER INFORMATION
# ============================================================

st.caption(
    f"Logged in as {st.session_state.name} "
    f"- updates go to {st.session_state.whatsapp_number}"
)


# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        ),
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
    ],
)


# ============================================================
# PROCESS USER INPUT
# ============================================================

if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []


    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes,
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type,
            )
        )


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text,
        )

        parts.append(text)


    # --------------------------------------------------------
    # PHOTO ONLY
    # --------------------------------------------------------

    elif photo is not None:

        parts.append(
            "What is this meal? "
            "Give me the calories and macros."
        )


    # --------------------------------------------------------
    # GEMINI RESPONSE
    # --------------------------------------------------------

    if parts:

        with st.spinner(
            "Crunching the numbers..."
        ):

            answer = ask_gemini(parts)

        add_message(
            "assistant",
            "text",
            answer,
        )