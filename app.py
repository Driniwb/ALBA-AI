
import streamlit as st
from huggingface_hub import InferenceClient

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
    "Prototype for public and synthetic texts only. "
    "Do not enter personal, confidential or sensitive information."
)

tasks = [
    "Improve Albanian institutional language",
    "Adapt English into formal Albanian",
    "Check legal and administrative terminology",
    "Draft an official email",
    "Prepare meeting minutes"
]

task = st.selectbox("Select the type of assistance", tasks)

user_text = st.text_area(
    "Enter your text",
    height=220,
    placeholder="Enter a public or synthetic text..."
)

safe_input = st.checkbox(
    "I confirm that this text contains no personal, "
    "confidential or sensitive information."
)

if st.button("Analyse text", type="primary"):

    if not user_text.strip():
        st.warning("Please enter a text.")

    elif not safe_input:
        st.warning("Please confirm that your text is safe to process.")

    elif "HF_TOKEN" not in st.secrets:
        st.error("Hugging Face token is missing from Streamlit Secrets.")

    else:
        prompt = f"""
You are ALBA, an AI assistant specialising in
Albanian legal, administrative and institutional writing.

Selected task: {task}

Instructions:
- Write in accurate, natural and professional Albanian.
- Preserve the original meaning.
- Avoid literal translations from English.
- Do not invent facts, legal provisions or references.
- Do not claim that terminology has been verified
  against official sources unless sources were provided.
- Identify uncertain legal terminology.
- Mark missing information as [To be confirmed].

Provide three sections:
1. Improved Albanian text
2. Terminology and language notes
3. Points requiring human review

Input text:
{user_text}
"""

        try:
            client = InferenceClient(
                provider="auto",
                token=st.secrets["HF_TOKEN"]
            )

            with st.spinner("ALBA is analysing your text..."):
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a careful Albanian legal "
                                "and institutional writing assistant."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=1200
                )

            result = response.choices[0].message.content

            st.subheader("ALBA AI Analysis")
            st.markdown(result or "No response was generated.")

            st.warning(
                "AI-generated draft. Human review is required. "
                "Official legal sources have not yet been connected."
            )

        except Exception:
            st.error(
                "The AI service could not process this request. "
                "Check the Hugging Face token, provider access "
                "and available inference quota."
            )

st.divider()
st.caption("ALBA AI | Prototype | Human review required")
