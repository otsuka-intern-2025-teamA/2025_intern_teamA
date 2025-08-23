import asyncio
import logging
import os
import time
from typing import Dict, List

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import ResearchState


class Enricher:
    """Enriches curated documents with raw content."""
    
    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        self.batch_size = 20

    async def fetch_single_content(self, url: str, websocket_manager=None, job_id=None, category=None) -> Dict[str, str]:
        """Fetch raw content for a single URL."""
        content_start_time = time.perf_counter()
        try:
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="extracting",
                    message=f"Extracting content from {url}",
                    result={
                        "step": "Enriching",
                        "url": url,
                        "category": category
                    }
                )

            result = await self.tavily_client.extract(url)
            if result and result.get('results'):
                content_time = time.perf_counter() - content_start_time
                if websocket_manager and job_id:
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="extracted",
                        message=f"Successfully extracted content from {url} in {content_time:.2f}s",
                        result={
                            "step": "Enriching",
                            "url": url,
                            "category": category,
                            "success": True,
                            "extraction_time": f"{content_time:.2f}s"
                        }
                    )
                return {url: result['results'][0].get('raw_content', '')}
        except Exception as e:
            content_time = time.perf_counter() - content_start_time
            print(f"Error fetching raw content for {url}: {e}")
            error_msg = str(e)
            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="extraction_error",
                    message=f"Failed to extract content from {url} after {content_time:.2f}s: {error_msg}",
                    result={
                        "step": "Enriching",
                        "url": url,
                        "category": category,
                        "success": False,
                        "error": error_msg,
                        "extraction_time": f"{content_time:.2f}s"
                    }
                )
            return {url: '', "error": error_msg}
        return {url: ''}

    async def fetch_raw_content(self, urls: List[str], websocket_manager=None, job_id=None, category=None) -> Dict[str, str]:
        """Fetch raw content for multiple URLs in parallel."""
        batch_start_time = time.perf_counter()
        raw_contents = {}
        total_batches = (len(urls) + self.batch_size - 1) // self.batch_size

        # Create batches
        batches = [urls[i:i + self.batch_size] for i in range(0, len(urls), self.batch_size)]
        
        # Process batches in parallel with rate limiting
        semaphore = asyncio.Semaphore(3)  # Limit concurrent batches to 3
        
        async def process_batch(batch_num: int, batch_urls: List[str]) -> Dict[str, str]:
            batch_start = time.perf_counter()
            async with semaphore:
                if websocket_manager and job_id:
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="batch_start",
                        message=f"Processing batch {batch_num + 1}/{total_batches}",
                        result={
                            "step": "Enriching",
                            "batch": batch_num + 1,
                            "total_batches": total_batches,
                            "category": category
                        }
                    )

                # Process URLs in batch concurrently
                tasks = [self.fetch_single_content(url, websocket_manager, job_id, category) for url in batch_urls]
                results = await asyncio.gather(*tasks)
                
                # Combine results from batch
                batch_contents = {}
                for result in results:
                    batch_contents.update(result)
                
                batch_time = time.perf_counter() - batch_start
                logger.info(f"✅ Batch {batch_num + 1} completed in {batch_time:.2f}s with {len(batch_contents)} URLs")
                
                return batch_contents

        # Process all batches
        batch_results = await asyncio.gather(*[
            process_batch(i, batch) 
            for i, batch in enumerate(batches)
        ])

        # Combine results from all batches
        for batch_result in batch_results:
            raw_contents.update(batch_result)

        total_time = time.perf_counter() - batch_start_time
        logger.info(f"⏱️  Content enrichment completed in {total_time:.2f}s for {len(urls)} URLs")

        return raw_contents

    async def enrich_data(self, state: ResearchState) -> ResearchState:
        """Enrich curated documents with raw content."""
        enrich_start_time = time.perf_counter()
        company = state.get('company', 'Unknown Company')
        websocket_manager = state.get('websocket_manager')
        job_id = state.get('job_id')

        logger.info(f"🚀 Starting content enrichment for {company}")

        if websocket_manager and job_id:
            await websocket_manager.send_status_update(
                job_id=job_id,
                status="processing",
                message=f"Starting content enrichment for {company}",
                result={
                    "step": "Enriching",
                    "substep": "initialization"
                }
            )

        msg = [f"📚 Enriching curated data for {company}:"]

        # Process each type of curated data
        data_types = {
            'financial_data': ('💰 Financial', 'financial'),
            'news_data': ('📰 News', 'news'),
            'industry_data': ('🏭 Industry', 'industry'),
            'company_data': ('🏢 Company', 'company')
        }

        # Create tasks for parallel processing
        enrichment_tasks = []
        for data_field, (label, category) in data_types.items():
            curated_field = f'curated_{data_field}'
            curated_docs = state.get(curated_field, {})
            
            if not curated_docs:
                msg.append(f"\n• No curated {label} documents to enrich")
                continue

            # Find documents needing enrichment
            docs_needing_content = {url: doc for url, doc in curated_docs.items() 
                                  if not doc.get('raw_content')}
            
            if not docs_needing_content:
                msg.append(f"\n• All {label} documents already have raw content")
                continue
            
            msg.append(f"\n• Enriching {len(docs_needing_content)} {label} documents...")

            if websocket_manager and job_id:
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="category_start",
                    message=f"Processing {label} documents",
                    result={
                        "step": "Enriching",
                        "category": category,
                        "count": len(docs_needing_content)
                    }
                )

            # Create task for this category
            enrichment_tasks.append({
                'field': curated_field,
                'category': category,
                'label': label,
                'docs': docs_needing_content,
                'curated_docs': curated_docs
            })

        # Process all categories in parallel
        if enrichment_tasks:
            async def process_category(task):
                category_start_time = time.perf_counter()
                try:
                    raw_contents = await self.fetch_raw_content(
                        list(task['docs'].keys()),
                        websocket_manager,
                        job_id,
                        task['category']
                    )
                    
                    enriched_count = 0
                    error_count = 0
                    
                    for url, content_or_error in raw_contents.items():
                        if isinstance(content_or_error, dict) and content_or_error.get('error'):
                            # This is an error result - just skip it
                            error_count += 1
                        elif content_or_error:
                            # This is a successful content
                            task['curated_docs'][url]['raw_content'] = content_or_error
                            enriched_count += 1

                    # Update state with enriched documents
                    state[task['field']] = task['curated_docs']
                    
                    category_time = time.perf_counter() - category_start_time
                    logger.info(f"✅ {task['category']} enrichment completed in {category_time:.2f}s: {enriched_count} enriched, {error_count} errors")
                    
                    if websocket_manager and job_id:
                        await websocket_manager.send_status_update(
                            job_id=job_id,
                            status="category_complete",
                            message=f"Completed {task['label']} documents in {category_time:.2f}s",
                            result={
                                "step": "Enriching",
                                "category": task['category'],
                                "enriched": enriched_count,
                                "total": len(task['docs']),
                                "category_time": f"{category_time:.2f}s"
                            }
                        )
                    
                    return {
                        'category': task['category'],
                        'enriched': enriched_count,
                        'total': len(task['docs']),
                        'errors': error_count,
                        'time': category_time
                    }
                except Exception as e:
                    category_time = time.perf_counter() - category_start_time
                    # Log the error but don't fail the entire process
                    print(f"Error processing category {task['category']} after {category_time:.2f}s: {e}")
                    return {
                        'category': task['category'],
                        'enriched': 0,
                        'total': len(task['docs']),
                        'errors': len(task['docs']),
                        'time': category_time
                    }

            # Process all categories in parallel
            results = await asyncio.gather(*[process_category(task) for task in enrichment_tasks])
            
            # Calculate totals
            total_enriched = sum(r['enriched'] for r in results)
            total_documents = sum(r['total'] for r in results)
            total_errors = sum(r.get('errors', 0) for r in results)
            total_enrichment_time = time.perf_counter() - enrich_start_time

            # Send final status update
            if websocket_manager and job_id:
                status_message = f"Content enrichment complete in {total_enrichment_time:.2f}s. Successfully enriched {total_enriched}/{total_documents} documents"
                if total_errors > 0:
                    status_message += f". Skipped {total_errors} documents."
                
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="enrichment_complete",
                    message=status_message,
                    result={
                        "step": "Enriching",
                        "total_enriched": total_enriched,
                        "total_documents": total_documents,
                        "total_errors": total_errors,
                        "total_time": f"{total_enrichment_time:.2f}s"
                    }
                )

            logger.info(f"🎯 Content enrichment summary: {total_enriched}/{total_documents} documents enriched in {total_enrichment_time:.2f}s")

        # Update state with enrichment message
        messages = state.get('messages', [])
        messages.append(AIMessage(content="\n".join(msg)))
        state['messages'] = messages
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        try:
            return await self.enrich_data(state)
        except Exception as e:
            # Log the error but don't fail the research process
            print(f"Error in enrichment process: {e}")
            # Return the original state without any enrichment
            return state 