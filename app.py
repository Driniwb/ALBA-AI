import streamlit as st

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
    "Prototype for Albanian legal and institutional writing. "
    "Use only public or synthetic information. "
    "Do not enter personal, confidential or sensitive data."
)

task = st.selectbox(
    "Select the type of assistance",
    [
        "Improve Albanian institutional language",
        "Adapt English into formal Albanian",
        "Check legal and administrative terminology",
        "Draft an official email",
        "Prepare meeting minutes"
    ]
)

user_text = st.text_area(
    "Enter your text",
    height=220,
    placeholder="Paste a public or synthetic text here..."
)

if st.button("Analyse text", type="primary"):
    if not user_text.strip():
        st.warning("Please enter some text.")
    else:
        st.subheader("Selected task")
        st.write(task)

        st.subheader("Original text")
        st.write(user_text)

        st.warning(
            "AI analysis is not yet connected. "
            "The next development stage will add the "
            "language model and vetted reference library."
        )

st.divider()
st.caption(
    "ALBA AI | Prototype | Human review required"
)

