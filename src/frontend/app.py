import streamlit as st
import requests

st.title("DSFS - Decentralized File Sharing System")

file = st.file_uploader("Upload your file")

if file is not None:
    if st.button("Upload"):
        response = requests.post(
            "http://127.0.0.1:8000/upload",
            files={"file": (file.name, file.getvalue())}
        )

        st.success("Upload successful!")
        st.json(response.json())