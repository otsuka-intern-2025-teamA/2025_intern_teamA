
import streamlit as st
from data import CompanyReport

def render_report(report: CompanyReport):
    st.subheader(f"📄 {report.company} 企業ブリーフィング")
    st.markdown("**概要**")
    st.write(report.overview or "—")
    st.markdown("**提供している製品・サービス**")
    st.write(report.offerings or "—")
    st.markdown("**顧客・市場**")
    st.write(report.customers_and_markets or "—")
    st.markdown("**直近のニュース・動向**")
    st.write(report.recent_news or "—")
    st.markdown("**競合**")
    st.write(report.competitors or "—")
    st.markdown("**リスク・留意点**")
    st.write(report.risks or "—")
    st.markdown("**次回打ち合わせでの質問案**")
    if report.suggested_questions:
        for q in report.suggested_questions:
            st.write(f"- {q}")
    else:
        st.write("—")
    st.markdown("**参考リンク**")
    if report.sources:
        for u in report.sources:
            st.write(f"- {u}")
    else:
        st.write("—")
    st.caption("※ 本ブリーフィングは公開Webの要約であり、正確性・最新性は各リンクをご確認ください。")
