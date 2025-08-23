import time
from langchain_core.messages import AIMessage

from ..classes import ResearchState


class Collector:
    """Collects and organizes all research data before curation."""

    async def collect(self, state: ResearchState) -> ResearchState:
        """Collect and verify all research data is present."""
        collect_start_time = time.perf_counter()
        company = state.get('company', 'Unknown Company')
        msg = [f"📦 Collecting research data for {company}:"]

        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"Collecting research data for {company}",
                    result={"step": "Collecting"}
                )
        
        # Check each type of research data
        research_types = {
            'financial_data': '💰 Financial',
            'news_data': '📰 News',
            'industry_data': '🏭 Industry',
            'company_data': '🏢 Company'
        }
        
        total_docs = 0
        for data_field, label in research_types.items():
            data = state.get(data_field, {})
            if data:
                doc_count = len(data)
                total_docs += doc_count
                msg.append(f"• {label}: {doc_count} documents collected")
            else:
                msg.append(f"• {label}: No data found")
        
        # Update state with collection message
        messages = state.get('messages', [])
        messages.append(AIMessage(content="\n".join(msg)))
        state['messages'] = messages
        
        collect_time = time.perf_counter() - collect_start_time
        print(f"✅ Data collection completed in {collect_time:.2f}s: {total_docs} total documents")
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        return await self.collect(state)