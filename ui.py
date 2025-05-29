import streamlit as st
from your_analysis_module import run_analysis

st.title("창업 입지 분석기")
budget = st.number_input("예산 입력", min_value=0)
if st.button("분석 시작"):
    result = run_analysis({"budget": budget})
    st.write(result)
