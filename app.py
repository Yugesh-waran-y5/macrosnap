import base64
import json

import requests
import streamlit as st
from twilio.rest import Client as TwilioClient

from prompts import SUMMARY_REQUEST_PROMPT, SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE


MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
)


# ============================================================
# SECRETS
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


# ============================================================
# TWILIO CLIENT
# ============================================================

@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
    )


twilio_client = get_twilio_client()


# ============================================================
# DISPLAY MESSAGES
# ============================================================

def render_message(message):
    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.write(message["content"])

        elif message["kind"] == "image":
            st.image(message["content"]["data"])


def add_message(role, kind, content):
    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
        }
    )

    render_message(st.session_state.messages[-1])


# ============================================================
# GEMINI REST API
# ============================================================

def ask_gemini(extra_prompt=None):
    """
    Sends the chat history to Gemini.
    If extra_prompt is given (e.g. the summary request), it is added
    as a final user turn without being saved in the chat history.
    """
    try:

        contents = []

        # Build conversation history
        for message in st.session_state.messages:

            if message["kind"] == "text":

                role = (
                    "model"
                    if message["role"] == "assistant"
                    else "user"
                )

                # Gemini expects the conversation to start with a user turn,
                # so skip the assistant welcome message at the beginning.
                if not contents and role == "model":
                    continue

                contents.append(
                    {
                        "role": role,
                        "parts": [
                            {
                                "text": message["content"]
                            }
                        ],
                    }
                )

            elif message["kind"] == "image":

                image_data = message["content"]["data"]
                mime_type = message["content"]["mime_type"]

                encoded_image = base64.b64encode(
                    image_data
                ).decode("utf-8")

                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": encoded_image,
                                }
                            }
                        ],
                    }
                )

        if extra_prompt:
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": extra_prompt
                        }
                    ],
                }
            )

        # Build request
        request_body = {
            "system_instruction": {
                "parts": [
                    {
                        "text": SYSTEM_PROMPT
                    }
                ]
            },
            "contents": contents,
        }

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{MODEL_NAME}:generateContent"
        )

        response = requests.post(
            url,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=60,
        )

        # Check API response
        if response.status_code != 200:
            return (
                f"Sorry, something went wrong: "
                f"{response.status_code} "
                f"{response.text}"
            )

        data = response.json()

        candidates = data.get("candidates", [])

        if not candidates:
            return "Sorry, Gemini returned no response."

        candidate = candidates[0]

        content = candidate.get("content", {})
        response_parts = content.get("parts", [])

        text_parts = []

        for part in response_parts:
            if "text" in part:
                text_parts.append(part["text"])

        if not text_parts:
            return "Sorry, Gemini returned an empty response."

        return "\n".join(text_parts)

    except requests.exceptions.Timeout:
        return "Sorry, Gemini request timed out. Please try again."

    except requests.exceptions.RequestException as error:
        return f"Sorry, network error: {error}"

    except Exception as error:
        return f"Sorry, something went wrong: {error}"


# ============================================================
# WHATSAPP TEXT CLEANING
# ============================================================

def clean_whatsapp_text(text):

    if not text:
        return "No nutrition summary available."

    text = " ".join(text.split())

    return (
        text[:1500] + "..."
        if len(text) > 1500
        else text
    )


# ============================================================
# SEND WHATSAPP
# ============================================================

def send_whatsapp(to_number, user_name, summary):

    try:

        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary),
            },
            ensure_ascii=False,
        )

        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:

        return False, str(error)


# ============================================================
# STEP 1: ONBOARDING
# ============================================================

if "onboarded" not in st.session_state:

    st.title("🥗 MacroSnap")

    st.caption(
        "Snap it. Track it. Text yourself the results."
    )

    with st.form("onboarding_form"):

        name = st.text_input("Your name")

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help="This is the number MacroSnap will text your summary to.",
        )

        submitted = st.form_submit_button(
            "Let's go 🚀"
        )

    if submitted:

        if (
            not name.strip()
            or not whatsapp_number.strip()
        ):

            st.warning(
                "Please fill in both your name and WhatsApp number."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# STEP 2: CHAT INTERFACE
# ============================================================

header_col, button_col = st.columns(
    [3, 2],
    vertical_alignment="center",
)


with header_col:

    st.title("🥗 MacroSnap")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 2
    )

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your day..."
        ):

            summary = ask_gemini(SUMMARY_REQUEST_PROMPT)

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary,
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )


st.caption(
    f"Logged in as "
    f"{st.session_state.name} "
    f"- updates go to "
    f"{st.session_state.whatsapp_number}"
)


# ============================================================
# SHOW CHAT
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
# USER INPUT + PHOTO
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


if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text


    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------

    if photo is not None:

        add_message(
            "user",
            "image",
            {
                "data": photo.getvalue(),
                "mime_type": photo.type,
            },
        )


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if text:

        add_message("user", "text", text)

    elif photo is not None:

        add_message(
            "user",
            "text",
            "What is this meal? Give me the calories and macros.",
        )


    # --------------------------------------------------------
    # GEMINI (history already contains the new messages)
    # --------------------------------------------------------

    with st.spinner("Crunching the numbers..."):

        answer = ask_gemini()


    # --------------------------------------------------------
    # DISPLAY ANSWER
    # --------------------------------------------------------

    add_message(
        "assistant",
        "text",
        answer,
    )