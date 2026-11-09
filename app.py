
import streamlit as st
from huggingface_hub import InferenceClient

# ALBA AI - Albanian Legal and Institutional Writing

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
    "ALBA AI supports clearer and more accurate Albanian "
    "legal and institutional communication."
)

st.warning(
    "DATA PROTECTION: Use only public or synthetic texts. "
    "Do not enter personal, confidential, sensitive or "
    "unpublished institutional information."
)

# Hugging Face model
MODEL_ID = "openai/gpt-oss-120b"

# Available tasks
TASKS = [
    "Improve Albanian institutional language",
    "Adapt English into formal Albanian",
    "Check legal and administrative terminology",
    "Draft an official email",
    "Prepare meeting minutes"
]

task = st.selectbox(
    "Select the type of assistance",
    TASKS
)

user_text = st.text_area(
    "Enter your text",
    height=220,
    max_chars=6000,
    placeholder="Enter a public or synthetic text..."
)

safe_input = st.checkbox(
    "I confirm that this text contains no personal, "
    "confidential or sensitive information."
)

TASK_INSTRUCTIONS = {
    "Improve Albanian institutional language":
        "Improve grammar, clarity, tone and institutional "
        "style. Preserve the original meaning.",

    "Adapt English into formal Albanian":
        "Translate and adapt the text into natural, formal "
        "Albanian institutional language.",

    "Check legal and administrative terminology":
        "Identify potentially incorrect, inconsistent or "
        "unclear legal and administrative terminology.",

    "Draft an official email":
        "Prepare a professional Albanian institutional email "
        "using only the information provided.",

    "Prepare meeting minutes":
        "Prepare formal Albanian meeting minutes, including "
        "discussion points and action items. Do not invent "
        "decisions, deadlines or responsibilities."
}

SYSTEM_PROMPT = """
You are ALBA AI, an assistant specialising in Albanian
legal, administrative and institutional writing.

Your purpose is to improve Albanian-language communication
with ministries, agencies, municipalities and public institutions.

RULES:

1. Write in accurate, natural and professional Albanian.
2. Preserve the meaning of the original text.
3. Avoid literal translations from English.
4. Do not invent facts, names, institutions or dates.
5. Never invent legal provisions or references.
6. Use established legal and administrative terminology.
7. Flag terminology requiring verification.
8. Mark missing information as [Për t'u konfirmuar].
9. Do not present the output as final legal advice.
10. Do not claim to have checked official sources unless
    those sources were actually provided.

OUTPUT:

### 1. Teksti i përmirësuar
Provide the complete revised Albanian text.

### 2. Shënime për terminologjinë
Explain important language and terminology changes.

### 3. Çështje për verifikim
Identify uncertainties requiring human review.

Respond in Albanian.
"""

# Read token securely
try:
    HF_TOKEN = st.secrets.get("HF_TOKEN", "")
except Exception:
    HF_TOKEN = ""

# Analysis button
if st.button("Analyse text", type="primary"):

    if not user_text.strip():
        st.warning("Please enter a text.")

    elif not safe_input:
        st.warning(
            "Please confirm that your text is safe to process."
        )

    elif not HF_TOKEN:
        st.error(
            "HF_TOKEN is missing from Streamlit Secrets."
        )

    else:
        try:
            client = InferenceClient(
                api_key=HF_TOKEN,
                provider="auto",
                timeout=90
            )

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": (
                        f"Task: {task}\n"
                        f"Instructions: {TASK_INSTRUCTIONS[task]}\n\n"
                        f"Text:\n{user_text}"
                    )
                }
            ]

            with st.spinner("ALBA AI is analysing your text..."):
                response = client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages,
                    max_tokens=1200,
                    temperature=0.2
                )

            result = response.choices[0].message.content

            if result:
                st.success("Analysis completed successfully.")

                st.subheader("ALBA AI Analysis")
                st.markdown(result)

                st.download_button(
                    label="Download analysis",
                    data=result,
                    file_name="ALBA_AI_Analysis.txt",
                    mime="text/plain"
                )

                st.warning(
                    "AI-generated draft. Human review required. "
                    "Vetted legal reference documents are not "
                    "yet connected."
                )
            else:
                st.warning(
                    "The AI model returned an empty response."
                )

        except Exception as error:

            error_type = type(error).__name__

            # Extract HTTP status correctly
            response_obj = getattr(error, "response", None)

            status = getattr(
                response_obj,
                "status_code",
                None
            )

            if status is None:
                status = getattr(
                    error,
                    "status_code",
                    None
                )

            st.error("The AI request failed.")
            st.write("Error type:", error_type)

            if status is not None:
                st.write("HTTP status:", status)
            else:
                st.write(
                    "HTTP status: Not available"
                )

            # Show safe troubleshooting guidance
            if status == 400:
                st.info(
                    "The model rejected the request or "
                    "one of its parameters."
                )

            elif status == 401:
                st.info(
                    "Invalid or expired Hugging Face token. "
                    "Check Streamlit Secrets."
                )

            elif status == 402:
                st.info(
                    "Inference credits may be exhausted "
                    "or billing may be required."
                )

            elif status == 403:
                st.info(
                    "Permission denied. Check the token's "
                    "Inference Providers permissions."
                )

            elif status == 404:
                st.info(
                    "The selected model or inference endpoint "
                    "could not be found."
                )

            elif status == 429:
                st.info(
                    "Request limit reached. Try again later."
                )

            elif status in (500, 502, 503, 504):
                st.info(
                    "The inference provider encountered "
                    "a server error."
                )

            else:
                st.info(
                    "Check model availability, inference "
                    "permissions, provider access and credits."
                )

st.divider()

st.caption(
    "ALBA AI | Experimental Prototype | "
    "Human Review Required"
)
