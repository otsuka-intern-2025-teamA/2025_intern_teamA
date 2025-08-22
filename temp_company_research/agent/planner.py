from typing import List, Dict
from research.summarize import CLIENT  # AzureOpenAI клиент уже настроен в summarize.py

SYSTEM = (
    "You are a research planner. Based on the target company and missing sections, "
    "propose up to 3 high-value web search queries per section. "
    "Output as plain lines in the format: <section>: <query>."
)

def build_seed_queries(company: str, sections: List[str]) -> List[str]:
    qs = []
    if "profile" in sections:
        qs += [f"{company} company overview business model official site",
               f"{company} wikipedia investors"]
    if "products" in sections:
        qs += [f"{company} products services portfolio customers"]
    if "market" in sections:
        qs += [f"{company} competitors industry market share",
               f"{company} competitor list vs"]
    if "financials" in sections:
        qs += [f"{company} financial results revenue operating income funding",
               f"{company} annual report presentation pdf"]
    if "news" in sections:
        qs += [f"{company} recent news last 12 months",
               f"{company} press release site:ir OR site:news"]
    if "risks" in sections:
        qs += [f"{company} risks litigation compliance incident",
               f"{company} 規制 リスク 訴訟 罰金"]
    # удалим дубликаты, сохраним порядок
    seen = set()
    out = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out

def plan_next_queries(company: str, missing_sections: List[str], context_titles: List[str]) -> List[str]:
    """LLM-планировщик: выдает до 6 новых запросов (по 1–3 на секцию)."""
    if not missing_sections:
        return []
    context = "\n".join(f"- {t}" for t in context_titles[:12])
    user = (
        f"Company: {company}\n"
        f"Missing sections: {', '.join(missing_sections)}\n"
        f"Known document titles:\n{context}\n\n"
        f"Return only lines like 'section: query' (no numbering)."
    )
    resp = CLIENT.chat.completions.create(
        model="gpt-5-mini",  # использует активный Azure deployment по имени в summarize.py
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
    )
    text = resp.choices[0].message.content.strip()
    queries: List[str] = []
    for line in text.splitlines():
        line = line.strip(" -*\t")
        if not line:
            continue
        # ожидаем формат "<section>: <query>"
        if ":" in line:
            _, q = line.split(":", 1)
            q = q.strip()
            if q:
                queries.append(q)
        else:
            # на случай, если модель не поставила "section:"
            queries.append(line)
    # ограничим до 6
    return queries[:6]
