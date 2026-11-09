
import streamlit as st
import requests

# -------------------------------------------
# ALBA AI
# Albanian Legal and Institutional Writing
# -------------------------------------------

st.set_page_config(
    page_title="ALBA AI",
    page_icon="📘",
    layout="wide"
)

st.title("ALBA AI")
st.subheader(
    "AI Language Base for Albanian Legal and Institutional Writing"
)

st.info(
    "An AI-powered assistant for improving Albanian "
    "legal, administrative and institutional communication."
)

st.warning(
    "PROTOTYPE: Use only public or synthetic information. "
    "Do not enter confidential, personal, sensitive, "
    "contractual or unpublished documents."
)

# OpenRouter configuration
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_ID = "openrouter/free"

# Available tasks
TASKS = {
    "Improve Albanian institutional language":
        "Improve grammar, clarity, formality and institutional "
        "style while preserving the original meaning.",

    "Adapt English into formal Albanian":
        "Translate and adapt the text into accurate, natural "
        "Albanian institutional language. Avoid literal translation.",

    "Check legal and administrative terminology":
        "Identify potentially incorrect, inconsistent or ambiguous "
        "legal and administrative terminology.",

    "Draft an official email":
        "Prepare a formal Albanian institutional email using only "
        "the information supplied by the user.",

    "Prepare meeting minutes":
        "Prepare formal Albanian meeting minutes. Separate "
        "discussions, decisions, responsibilities and deadlines. "
        "Never invent missing information."
}

SYSTEM_PROMPT = """
You are ALBA AI, an assistant specialising in
Albanian legal, administrative and institutional writing.

Your task is to help prepare accurate and professional
Albanian-language documents for institutional communication.

RULES:
1. Write in clear, natural and professional Albanian.
2. Preserve the original meaning.
3. Avoid literal translations from English.
4. Do not invent facts, dates, institutions or commitments.
5. Never invent legislation, article numbers or legal references.
6. Identify uncertain legal and administrative terminology.
7. Mark missing information as [Për t'u konfirmuar].
8. Explain significant terminology changes.
9. Do not claim to have verified official legal sources.
10. All outputs require human review.

OUTPUT FORMAT:

### 1. Teksti i përmirësuar
Provide the complete revised text.

### 2. Shënime për terminologjinë
Explain important wording and terminology changes.

### 3. Çështje për verifikim
Identify issues requiring human review.

Respond in Albanian.
"""

task = st.selectbox(
    "Select the type of assistance",
    list(TASKS.keys())
)

user_text = st.text_area(
    "Enter your text",
    height=220,
    max_chars=4000,
    placeholder="Enter public or synthetic text here..."
)

safe_input = st.checkbox(
    "I confirm that this text is public or synthetic "
    "and contains no sensitive or confidential information."
)

if st.button("Analyse text", type="primary"):

    if not user_text.strip():
        st.warning("Please enter some text.")

    elif not safe_input:
        st.warning("Please confirm the data safety statement.")

    else:
        try:
            api_key = st.secrets.get("OPENROUTER_API_KEY", "")
        except Exception:
            api_key = ""

        if not api_key:
            st.error(
                "OPENROUTER_API_KEY is missing from "
                "Streamlit Secrets."
            )

        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "ALBA AI"
            }

            payload = {
                "model": MODEL_ID,
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Task: {task}\n\n"
                            f"Instructions: {TASKS[task]}\n\n"
                            f"Input text:\n{user_text}"
                        )
                    }
                ],
                "max_tokens": 1500
            }

            try:
                with st.spinner("ALBA AI is analysing your text..."):
                    response = requests.post(
                        API_URL,
                        headers=headers,
                        json=payload,
                        timeout=90
                    )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])

                    result = ""
                    if choices:
                        result = (
                            choices[0]
                            .get("message", {})
                            .get("content", "")
                        )

                    if isinstance(result, str) and result.strip():
                        st.success("Analysis completed successfully!")

                        st.subheader("ALBA AI Analysis")
                        st.markdown(result)

                        st.download_button(
                            "Download analysis",
                            data=result,
                            file_name="ALBA_AI_Analysis.txt",
                            mime="text/plain"
                        )

                        st.warning(
                            "AI-generated draft. Human review required. "
                            "Vetted legal sources are not connected yet."
                        )

                    else:
                        st.warning(
                            "The model returned no text. "
                            "Please try again."
                        )

                else:
                    st.error("OpenRouter could not process the request.")
                    st.write("HTTP status:", response.status_code)

                    if response.status_code == 401:
                        st.info("Check your OpenRouter API key.")
                    elif response.status_code == 402:
                        st.info(
                            "The account or selected service "
                            "requires available credits."
                        )
                    elif response.status_code == 429:
                        st.info(
                            "Free usage limit reached. "
                            "Try again later."
                        )
                    elif response.status_code == 404:
                        st.info(
                            "No compatible model was found."
                        )
                    else:
                        st.info(
                            "Check OpenRouter service status, "
                            "model availability and account access."
                        )

            except requests.exceptions.Timeout:
                st.error(
                    "The AI service did not respond in time. "
                    "Please try again."
                )

            except requests.exceptions.RequestException:
                st.error(
                    "A network error occurred while "
                    "connecting to OpenRouter."
                )

            except (ValueError, KeyError, TypeError):
                st.error(
                    "The AI service returned an unexpected response."
                )

st.divider()

st.caption(
    "ALBA AI | Experimental Prototype | "
    "Human Review Required"
)
