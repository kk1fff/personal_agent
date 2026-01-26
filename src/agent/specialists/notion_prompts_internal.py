"""Internal LLM prompts for NotionIntelligenceEngine multi-step processing."""

INTENT_ANALYSIS_PROMPT = """You are analyzing a user's question to create an optimal search strategy for a Notion workspace.

## Workspace Context
{workspace_context}

## User Question
{user_question}

## Additional Context
{context_hint}

## Search Scope
{search_scope}
- "precise": User expects a single specific document
- "exploratory": User wants to browse/discover related content
- "comprehensive": User needs information from multiple sources

## Your Task
Generate a search strategy with:
1. 1-3 primary search queries (semantic search terms that capture the intent, not just keywords)
2. Optional fallback queries if primary might miss relevant content
3. What type of content you expect to find

Think about:
- What concepts and topics relate to the user's question?
- What synonyms or related terms might be used in the pages?
- Should we search for specific document types (meeting notes, project docs, etc.)?

Output as JSON (no markdown, no code blocks):
{{
    "primary_queries": ["query1", "query2"],
    "fallback_queries": ["fallback1"],
    "expected_content_type": "meeting notes about X",
    "reasoning": "Brief explanation of why these queries will find relevant content"
}}
"""

RERANK_PROMPT = """You are evaluating search results for relevance to a user's question.

## User Question
{user_question}

## Search Results
{results_json}

## Your Task
For each result, assign a relevance score (0.0 to 1.0) based on:
- How directly it might answer the question (based on title, path, and summary)
- How recent/authoritative the content appears
- Whether the title/path suggest relevant content

Scoring Guidelines:
- 0.9-1.0: Highly likely to contain the exact answer
- 0.7-0.8: Very relevant, likely contains useful information
- 0.5-0.6: Possibly relevant, worth checking
- 0.3-0.4: Tangentially related
- 0.0-0.2: Unlikely to be helpful

Output as JSON array (no markdown, no code blocks):
[
    {{
        "page_id": "...",
        "relevance_score": 0.85,
        "relevance_reasoning": "Directly addresses the project status based on title and path"
    }},
    ...
]

Include ALL results from the input, scored appropriately.
"""

SYNTHESIS_PROMPT = """You are synthesizing an answer from Notion pages to answer a user's question.

## User Question
{user_question}

## Retrieved Pages
{pages_content}

## Your Task
1. Synthesize a comprehensive answer using the retrieved content
2. Include specific citations with page references
3. Note any information gaps
4. Suggest follow-up questions if relevant

Guidelines:
- Be accurate and cite your sources using [Page: Title] format
- If the pages don't contain the answer, say so clearly
- Don't make up information that isn't in the pages
- Be concise but complete

## Response Format
Provide your answer in natural language with inline citations, followed by a JSON metadata block.

Example:
Based on your notes, the project deadline is March 15th [Page: Project Timeline]. The key deliverables include the API documentation and testing suite [Page: Q1 Goals].

---METADATA---
{{
    "confidence": 0.85,
    "citations": [
        {{"page_id": "abc123", "title": "Project Timeline", "path": "Work/Projects/Timeline", "excerpt": "Deadline: March 15th"}},
        {{"page_id": "def456", "title": "Q1 Goals", "path": "Work/Goals/Q1", "excerpt": "Deliverables: API docs, testing"}}
    ],
    "gaps_identified": "No information found about budget allocation",
    "follow_up_suggestions": ["What is the budget for the project?", "Who is responsible for each deliverable?"]
}}
"""

SYNTHESIS_NO_RESULTS_PROMPT = """You are helping a user who searched their Notion workspace but found no relevant results.

## User Question
{user_question}

## Search Queries Tried
{queries_tried}

## Your Task
Provide a helpful response that:
1. Acknowledges the search didn't find relevant content
2. Suggests what might help (different search terms, checking if the content exists)
3. Offers to help in other ways

Be concise and helpful. Don't apologize excessively.

---METADATA---
{{
    "confidence": 0.0,
    "citations": [],
    "gaps_identified": "No matching content found in Notion workspace",
    "follow_up_suggestions": ["Try searching with different keywords", "Check if this information is stored elsewhere"]
}}
"""
