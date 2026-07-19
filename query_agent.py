"""
query_agent.py

Example of the live request path: user asks something -> retrieve relevant
trick knowledge -> call Claude with the right "mode" (M1 / M2 / M10) -> return answer.

This is meant as a starting reference for your backend route, not a
finished production file — wire this logic into your actual API endpoint
(e.g. an Express or FastAPI route that the frontend chat calls).

SETUP
-----
pip install supabase voyageai anthropic

Same env vars as ingest_content.py, plus:
  ANTHROPIC_API_KEY
"""

import os
from supabase import create_client
import voyageai
import anthropic

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---- Mode-specific system prompts (M1 / M2 / M10) ----
SYSTEM_PROMPTS = {
    "routine": (  # M1: flow creation
        "You are a magic routine designer. Using ONLY the reference tricks "
        "provided in context, help the user build a coherent performance "
        "flow: pacing, sequencing, and dramatic build. Adapt the reference "
        "material to the user's stated skill level and props on hand. "
        "If the context doesn't contain a good fit for what they're asking, "
        "say so honestly rather than inventing a trick that doesn't exist."
    ),
    "script": (  # M2: patter/narrative
        "You are a magic scriptwriter. Write performance patter (the spoken "
        "narration a magician uses) for the routine or trick described. "
        "Match the user's stated performance style. Keep it natural to say "
        "out loud, not written prose."
    ),
    "training": (  # M10: training plan
        "You are a magic practice coach. Build a realistic, staged practice "
        "plan for the user's goal, given their skill level and practice "
        "history. Be concrete about what to drill each session and how to "
        "know when they're ready to move on."
    ),
}


def embed_query(query: str) -> list[float]:
    result = voyage.embed([query], model="voyage-3", input_type="query")
    return result.embeddings[0]


def retrieve_relevant_chunks(query: str, match_count: int = 5) -> list[dict]:
    """
    Uses hybrid search: keyword search + vector search, blended together.
    Falls back to pure vector search (match_trick_chunks) if you haven't
    run the hybrid_search_trick_chunks schema addition yet.
    """
    query_embedding = embed_query(query)
    try:
        response = supabase.rpc(
            "hybrid_search_trick_chunks",
            {"query_text": query, "query_embedding": query_embedding, "match_count": match_count},
        ).execute()
    except Exception:
        # Schema not updated yet - fall back to vector-only search
        response = supabase.rpc(
            "match_trick_chunks",
            {"query_embedding": query_embedding, "match_count": match_count},
        ).execute()
    return response.data


def build_context_block(chunks: list[dict]) -> str:
    if not chunks:
        return "No closely matching reference material was found."
    parts = [f"[Reference {i+1}]\n{c['content']}" for i, c in enumerate(chunks)]
    return "\n\n".join(parts)


def get_user_profile(user_id: str) -> dict:
    response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return response.data


def ask_agent(mode: str, user_message: str, user_id: str) -> str:
    """mode is one of: 'routine', 'script', 'training'"""
    profile = get_user_profile(user_id)
    chunks = retrieve_relevant_chunks(user_message)
    context_block = build_context_block(chunks)

    user_profile_block = (
        f"Skill level: {profile.get('skill_level')}\n"
        f"Style preference: {profile.get('style_preference')}\n"
        f"Props owned: {profile.get('props_owned')}"
    )

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPTS[mode],
        messages=[
            {
                "role": "user",
                "content": (
                    f"USER PROFILE:\n{user_profile_block}\n\n"
                    f"REFERENCE MATERIAL:\n{context_block}\n\n"
                    f"USER REQUEST:\n{user_message}"
                ),
            }
        ],
    )
    return response.content[0].text


if __name__ == "__main__":
    # quick manual test
    example_answer = ask_agent(
        mode="routine",
        user_message="Design a 3-minute coin routine for a beginner",
        user_id="REPLACE_WITH_A_REAL_USER_ID",
    )
    print(example_answer)
