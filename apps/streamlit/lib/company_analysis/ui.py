import streamlit as st
from .data import CompanyReport


def render_report(report: CompanyReport):
    st.subheader(f"📄 {report.company} 企業ブリーフィング")
    
    # 概要セクション
    st.markdown("**概要**")
    if report.overview and report.overview != "—":
        st.write(report.overview)
    else:
        st.write("—")
    
    # 提供している製品・サービス
    st.markdown("**提供している製品・サービス**")
    if report.offerings and report.offerings != "—":
        st.write(report.offerings)
    else:
        st.write("—")
    
    # 顧客・市場
    st.markdown("**顧客・市場**")
    if report.customers_and_markets and report.customers_and_markets != "—":
        st.write(report.customers_and_markets)
    else:
        st.write("—")
    
    # 直近のニュース・動向
    st.markdown("**直近のニュース・動向**")
    if report.recent_news and report.recent_news != "—":
        st.write(report.recent_news)
    else:
        st.write("—")
    
    # 競合
    st.markdown("**競合**")
    if report.competitors and report.competitors != "—":
        st.write(report.competitors)
    else:
        st.write("—")
    
    # リスク・留意点
    st.markdown("**リスク・留意点**")
    if report.risks and report.risks != "—":
        st.write(report.risks)
    else:
        st.write("—")
    
    # 次回打ち合わせでの質問案
    st.markdown("**次回打ち合わせでの質問案**")
    if report.suggested_questions and len(report.suggested_questions) > 0:
        for q in report.suggested_questions:
            st.write(f"- {q}")
    else:
        st.write("—")
    
    # 参考リンク
    st.markdown("**参考リンク**")
    if report.sources and len(report.sources) > 0:
        for u in report.sources:
            st.write(f"- {u}")
    else:
        st.write("—")
    
    st.caption("※ 本ブリーフィングは公開Webの要約であり、正確性・最新性は各リンクをご確認ください。")
