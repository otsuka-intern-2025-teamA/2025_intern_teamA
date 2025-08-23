import logging
import os
import time

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import InputState, ResearchState

logger = logging.getLogger(__name__)

class GroundingNode:
    """Gathers initial grounding data about the company."""
    
    def __init__(self) -> None:
        self.tavily_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    async def initial_search(self, state: InputState) -> ResearchState:
        grounding_start_time = time.perf_counter()
        # Add debug logging at the start to check websocket manager
        if websocket_manager := state.get('websocket_manager'):
            logger.info("Websocket manager found in state")
        else:
            logger.warning("No websocket manager found in state")
        
        company = state.get('company', 'Unknown Company')
        msg = f"🎯 Initiating research for {company}...\n"
        
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"🎯 Initiating research for {company}",
                    result={"step": "Initializing"}
                )

        site_scrape = {}
        error_str = None  # Initialize error_str variable

        # Only attempt extraction if we have a URL
        if url := state.get('company_url'):
            msg += f"\n🌐 Analyzing company website: {url}"
            logger.info(f"🌐 Starting website analysis for {url}")
            
            # Send initial briefing status
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Analyzing company website",
                        result={"step": "Initial Site Scrape"}
                    )

            try:
                logger.info("🚀 Initiating Tavily extraction")
                extraction_start = time.perf_counter()
                site_extraction = await self.tavily_client.extract(url, extract_depth="basic")
                extraction_time = time.perf_counter() - extraction_start
                
                raw_contents = []
                for item in site_extraction.get("results", []):
                    if content := item.get("raw_content"):
                        raw_contents.append(content)
                
                if raw_contents:
                    site_scrape = {
                        'title': company,
                        'raw_content': "\n\n".join(raw_contents)
                    }
                    logger.info(f"✅ Successfully extracted {len(raw_contents)} content sections in {extraction_time:.2f}s")
                    msg += f"\n✅ Successfully extracted content from website in {extraction_time:.2f}s"
                    if websocket_manager := state.get('websocket_manager'):
                        if job_id := state.get('job_id'):
                            await websocket_manager.send_status_update(
                                job_id=job_id,
                                status="processing",
                                message=f"Successfully extracted content from website in {extraction_time:.2f}s",
                                result={
                                    "step": "Initial Site Scrape",
                                    "extraction_time": f"{extraction_time:.2f}s",
                                    "content_sections": len(raw_contents)
                                }
                            )
                else:
                    logger.warning(f"⚠️ No content found in extraction results after {extraction_time:.2f}s")
                    msg += f"\n⚠️ No content found in website extraction after {extraction_time:.2f}s"
                    if websocket_manager := state.get('websocket_manager'):
                        if job_id := state.get('job_id'):
                            await websocket_manager.send_status_update(
                                job_id=job_id,
                                status="processing",
                                message=f"⚠️ No content found in provided URL after {extraction_time:.2f}s",
                                result={
                                    "step": "Initial Site Scrape",
                                    "extraction_time": f"{extraction_time:.2f}s"
                                }
                            )
            except Exception as e:
                extraction_time = time.perf_counter() - extraction_start if 'extraction_start' in locals() else 0
                error_str = str(e)
                logger.error(f"❌ Website extraction error after {extraction_time:.2f}s: {error_str}", exc_info=True)
                error_msg = f"⚠️ Error extracting website content after {extraction_time:.2f}s: {error_str}"
                print(error_msg)
                msg += f"\n{error_msg}"
                if websocket_manager := state.get('websocket_manager'):
                    if job_id := state.get('job_id'):
                        await websocket_manager.send_status_update(
                            job_id=job_id,
                            status="website_error",
                            message=error_msg,
                            result={
                                "step": "Initial Site Scrape", 
                                "error": error_str,
                                "extraction_time": f"{extraction_time:.2f}s",
                                "continue_research": True  # Continue with research even if website extraction fails
                            }
                        )
        else:
            msg += "\n⏩ No company URL provided, proceeding directly to research phase"
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="No company URL provided, proceeding directly to research phase",
                        result={"step": "Initializing"}
                    )
        # Add context about what information we have
        context_data = {}
        if hq := state.get('hq_location'):
            msg += f"\n📍 Company HQ: {hq}"
            context_data["hq_location"] = hq
        if industry := state.get('industry'):
            msg += f"\n🏭 Industry: {industry}"
            context_data["industry"] = industry
        
        # Initialize ResearchState with input information
        research_state = {
            # Copy input fields
            "company": state.get('company'),
            "company_url": state.get('company_url'),
            "hq_location": state.get('hq_location'),
            "industry": state.get('industry'),
            # Initialize research fields
            "messages": [AIMessage(content=msg)],
            "site_scrape": site_scrape,
            # Pass through websocket info
            "websocket_manager": state.get('websocket_manager'),
            "job_id": state.get('job_id')
        }

        # If there was an error in the initial extraction, store it in the state
        if error_str and "⚠️ Error extracting website content:" in msg:
            research_state["error"] = error_str

        grounding_time = time.perf_counter() - grounding_start_time
        logger.info(f"✅ Grounding completed in {grounding_time:.2f}s for {company}")
        
        return research_state

    async def run(self, state: InputState) -> ResearchState:
        return await self.initial_search(state)
