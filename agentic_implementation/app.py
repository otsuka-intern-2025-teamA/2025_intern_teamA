import os, requests, json
import streamlit as st
from typing import List
import asyncio
import uuid
from config import get_settings
from data import SearchHit, CompanyReport
from ui import render_report

st.set_page_config(page_title="Company Intel Bot (Agentic AI)", page_icon="🔎", layout="wide")

# Backend API configuration
BACKEND_URL = "http://localhost:8000"

def run_agentic_research(company: str, company_url: str = None, industry: str = None, hq_location: str = None):
    """Run research using the agentic AI backend"""
    try:
        # Start research job
        response = requests.post(
            f"{BACKEND_URL}/research",
            json={
                "company": company,
                "company_url": company_url,
                "industry": industry,
                "hq_location": hq_location
            },
            timeout=30
        )
        
        if response.status_code != 200:
            st.error(f"Failed to start research: {response.text}")
            return None
            
        data = response.json()
        job_id = data.get("job_id")
        
        if not job_id:
            st.error("No job ID received from backend")
            return None
            
        st.info(f"Research job started with ID: {job_id}")
        
        # Wait for completion (in a real app, you'd use WebSocket for real-time updates)
        st.info("Waiting for research to complete...")
        
        # Poll for results
        max_attempts = 60  # 5 minutes with 5-second intervals
        for attempt in range(max_attempts):
            try:
                result_response = requests.get(f"{BACKEND_URL}/research/{job_id}/report", timeout=10)
                if result_response.status_code == 200:
                    result_data = result_response.json()
                    if result_data.get("report"):
                        st.success("Research completed!")
                        return result_data["report"]
                        
                # Wait before next attempt
                import time
                time.sleep(5)
                
            except requests.exceptions.RequestException:
                time.sleep(5)
                continue
                
        st.error("Research timed out. Please try again.")
        return None
        
    except Exception as e:
        st.error(f"Error during research: {str(e)}")
        return None

def create_simple_report_from_agentic_result(company: str, agentic_report: str) -> CompanyReport:
    """Convert the agentic AI report to your original CompanyReport format"""
    # The agentic report is already comprehensive, so we'll use it as the overview
    # and create a structured format that matches your original UI
    return CompanyReport(
        company=company,
        overview=agentic_report,
        offerings="See overview above for detailed information",
        customers_and_markets="See overview above for detailed information", 
        recent_news="See overview above for detailed information",
        competitors="See overview above for detailed information",
        risks="See overview above for detailed information",
        suggested_questions=[
            "Can you provide more details about your recent business developments?",
            "What are your main competitive advantages in the market?",
            "How do you see the industry evolving in the next 2-3 years?",
            "What challenges are you currently facing?"
        ],
        sources=["Research conducted by Agentic AI system"]
    )

def main():
    st.title("🔎 企業インテリジェンス（Agentic AI版）")
    st.write("会社名を入力すると、高度なAIエージェントが包括的な企業調査を実行します。")
    
    st.info("""
    **新機能**: このバージョンでは、単純なLLM要約ではなく、高度なAIエージェントが
    複数の情報源から包括的な企業調査を実行します。より詳細で正確な情報が得られます。
    """)

    with st.sidebar:
        st.header("設定")
        st.caption("環境変数は .env で設定できます。")
        
        # Additional fields for the agentic backend
        company_url = st.text_input("会社URL（オプション）", placeholder="https://example.com")
        industry = st.text_input("業界（オプション）", placeholder="IT、製造業、金融など")
        hq_location = st.text_input("本社所在地（オプション）", placeholder="東京、大阪など")
        
        st.caption("これらの追加情報があると、より正確な調査結果が得られます。")

    company = st.text_input("企業名（例: 大塚商会、楽天グループ、ソニーグループ）")
    run = st.button("調べる")

    if run and company.strip():
        st.info("高度なAIエージェントによる調査を開始中…")
        
        # Run the agentic research
        agentic_report = run_agentic_research(
            company.strip(),
            company_url if company_url.strip() else None,
            industry if industry.strip() else None,
            hq_location if hq_location.strip() else None
        )
        
        if agentic_report:
            # Convert to your original format and display
            report = create_simple_report_from_agentic_result(company.strip(), agentic_report)
            render_report(report)
            
            # Add download option for the full report
            st.download_button(
                label="📄 完全なレポートをダウンロード",
                data=agentic_report,
                file_name=f"{company}_research_report.md",
                mime="text/markdown"
            )
        else:
            st.error("調査に失敗しました。もう一度お試しください。")

if __name__ == "__main__":
    main()
