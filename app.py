
import streamlit as st
from huggingface_hub import InferenceClient

# --------------------------------------------------
# ALBA AI - Albanian Legal & Institutional Assistant
# --------------------------------------------------

st.set_page_config(
    page_title="ALBA AI",
    page_icon="📘",
    layout="wide"
)

st.title("ALBA AI")
st.subheader(
    "AI Language Base for Albanian Legal and Institutional Writing"
)

st.caption(
    "An AI-powered assistant for clearer and more accurate "
    "Albanian legal and institutional communication."
)

st.warning(
    "DATA PROTECTION: Use only public or synthetic texts. "
    "Do not enter personal, sensitive, confidential, "
    "contractual or unpublished institutional information."
)

# AI MODEL
MODEL_ID = "openai/gpt-oss-120b:cheapest"

# TASKS
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

# INSTRUCTIONS FOR EACH TASK
TASK_INSTRUCTIONS = {
    "Improve Albanian institutional language":
        "Improve the Albanian language, institutional tone, "
        "clarity, grammar and structure. Preserve the meaning.",

    "Adapt English into formal Albanian":
        "Translate and adapt the English text into natural, "
        "formal Albanian institutional language. "
        "Avoid literal translations.",

    "Check legal and administrative terminology":
        "Review the text for potentially incorrect or "
        "inconsistent Albanian legal and administrative "
        "terminology. Flag uncertain terminology.",

    "Draft an official email":
        "Prepare a clear and professional Albanian "
        "institutional email based only on the information "
        "provided. Do not invent dates or commitments.",

    "Prepare meeting minutes":
        "Prepare structured meeting minutes in Albanian "
        "with discussion points, decisions and action items. "
        "Do not invent participants, deadlines or decisions."
}

SYSTEM_PROMPT = """
You are ALBA AI, an assistant for Albanian legal,
administrative and institutional writing.

Your purpose is to help improve the quality of
written communication with Albanian public institutions.

GENERAL RULES:

1. Write in accurate, formal and natural Albanian.
2. Preserve the meaning of the original text.
3. Avoid literal English-to-Albanian translations.
4. Do not invent facts, names, dates or institutions.
5. Never invent laws, articles or legal references.
6. Do not claim that terminology has been verified
   against official sources unless references are provided.
7. Identify uncertain legal terminology.
8. Clearly mark missing information as
   [Për t'u konfirmuar].
9. Do not treat your response as final legal advice.
10. Prefer clear, professional and concise formulations.

OUTPUT FORMAT:

### 1. Improved Albanian version
Provide the complete improved text.

### 2. Terminology and language notes
Explain the most important changes briefly.

### 3. Points requiring human review
List uncertain information or terminology.
If none is identified, say so without claiming
that the text has been legally verified.

Respond in Albanian.
"""

# CHECK TOKEN CONFIGURATION
token = st.secrets.get("HF_TOKEN", "")

if not token:
    st.error(
        "Hugging Face token is missing. "
        "Add HF_TOKEN in Streamlit App Settings > Secrets."
    )

# GENERATE RESPONSE
if st.button("Analyse text", type="primary"):

    if not user_text.strip():
        st.warning("Please enter a text.")

    elif not safe_input:
        st.warning(
            "Please confirm that the text is safe to process."
        )

    elif not token:
        st.error(
            "AI connection unavailable: HF_TOKEN is not configured."
        )

    else:
        try:
            client = InferenceClient(
                api_key=token,
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
                        f"Selected task: {task}\n\n"
                        f"Instructions: {TASK_INSTRUCTIONS[task]}\n\n"
                        f"Text to process:\n{user_text}"
                    )
                }
            ]

            with st.spinner("ALBA AI is processing your text..."):
                response = client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.2
                )

            result = response.choices[0].message.content

            if result:
                st.success("Analysis completed.")

                st.subheader("ALBA AI Analysis")
                st.markdown(result)

                st.download_button(
                    label="Download analysis",
                    data=result,
                    file_name="ALBA_AI_Analysis.txt",
                    mime="text/plain"
                )

                st.info(
                    "This output is AI-generated and requires "
                    "human review. Official reference documents "
                    "have not yet been connected."
                )
            else:
                st.warning(
                    "The model returned an empty response. "
                    "Try a shorter text."
                )

        except Exception as error:
            # Do not display full error messages:
            # they may contain request or account details.
status = getattr(
    getattr(error, "response", None),
    "status_code",
    None
)
            error_type = type(error).__name__

            st.error("The AI request failed.")
            st.write("Error type:", error_type)

            if isinstance(status, int):
                st.write("HTTP status:", status)

            if status == 401 or status == 403:
                st.info(
                    "Check the Hugging Face token and "
                    "Inference Providers permissions."
                )
            elif status == 402:
                st.info(
                    "Your inference credits may be exhausted "
                    "or the provider may require billing."
                )
            elif status == 429:
                st.info(
                    "Rate limit reached. Try again later."
                )
            else:
                st.info(
                    "Check model availability, provider access "
                    "and Hugging Face inference credits."
                )

st.divider()

st.caption(
    "ALBA AI | Experimental Prototype | "
    "Human Review Required"
)
