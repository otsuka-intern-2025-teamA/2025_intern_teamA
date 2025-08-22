import asyncio
from typing import List, Dict, Any, Tuple

from agent.state import AgentState, Doc
from agent.planner import build_seed_queries, plan_next_queries
from research.search import tavily_search, resolve_company
from research.scrape import fetch_and_extract
from research.summarize import make_briefings, compile_markdown

async def run_agentic(company: str, locale: str, sections: List[str], max_steps: int = 5
                     ) -> Tuple[str, List[Dict], Dict[str, Any], Dict[str, str]]:
    """
    Agentic цикл: Plan → Act (search/scrape) → Observe → Critic → (repeat) → Editor
    Возвращает (markdown, sources, meta, briefings).
    """
    resolved_name, seed_urls = await resolve_company(company)
    st = AgentState(company=resolved_name, locale=locale, sections=sections, max_steps=max_steps)

    # SEED: заранее известные запросы и URL
    st.pending_queries.extend(build_seed_queries(resolved_name, sections))
    st.known_urls.update(seed_urls)

    # Первый сбор: скрапим seed_urls (если есть)
    if seed_urls:
        seed_docs = await fetch_and_extract(list(seed_urls))
        for d in seed_docs:
            st.docs.append(Doc(url=d["url"], title=d.get("title",""), text=d["text"]))

    # Итеративный цикл
    while st.step < st.max_steps:
        st.step += 1

        # ACT(search): выполним до N поисков за шаг
        batch_q = st.pending_queries[:4]
        st.pending_queries = st.pending_queries[4:]
        found_urls: List[str] = []
        if batch_q:
            results = await asyncio.gather(*[tavily_search(q, k=6) for q in batch_q])
            for urls in results:
                for u in urls:
                    if u not in st.known_urls:
                        st.known_urls.add(u)
                        found_urls.append(u)

        # ACT(scrape): подтянем контент
        if found_urls:
            docs = await fetch_and_extract(found_urls[:16])
            for d in docs:
                st.docs.append(Doc(url=d["url"], title=d.get("title",""), text=d["text"]))

        # CRITIC: достаточно ли покрытия?
        missing = st.missing_sections()
        no_more_actions = not batch_q and not found_urls
        if no_more_actions and not missing:
            break  # всё покрыто и действия кончились
        if not missing and st.step >= 2:
            # если после ≥2 шагов секции покрыты — завершаем
            break

        # PLAN: если есть ещё шаги и что добирать — спланируем новые запросы
        if st.step < st.max_steps:
            titles = [d.title or d.url for d in st.docs][-20:]
            next_qs = plan_next_queries(st.company, missing, titles)
            # в конец очереди
            st.pending_queries.extend([q for q in next_qs if q])

        # если нечего делать вообще — выходим
        if not st.pending_queries and not found_urls:
            break

    # EDITOR: финальная генерация секций и отчёта
    # Преобразуем docs обратно в формат summarize.make_briefings
    raw_docs = [{"url": d.url, "title": d.title, "text": d.text} for d in st.docs]
    briefings = await make_briefings(st.company, raw_docs, st.locale, st.sections)
    md, sources = await compile_markdown(st.company, briefings, raw_docs)
    meta = {"resolved_name": st.company, "source_count": len(sources), "agent_steps": st.step}

    return md, sources, meta, briefings
