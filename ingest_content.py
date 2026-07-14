"""
ingest_content.py

One-time (or run-whenever-you-add-content) script that:
  1. Reads curated trick files from a local folder
  2. Splits each into overlapping text chunks
  3. Embeds each chunk (Voyage AI)
  4. Stores trick metadata + chunks + embeddings in Supabase

SETUP
-----
pip install supabase voyageai python-frontmatter

Environment variables needed (set these in your shell or a .env file):
  SUPABASE_URL           -> Project Settings > API > Project URL
  SUPABASE_SERVICE_KEY   -> Project Settings > API > service_role key
                            (NOT the anon key — this script needs write access
                            that bypasses RLS, since regular users shouldn't
                            write to the shared knowledge base)
  VOYAGE_API_KEY         -> from https://www.voyageai.com/

CONTENT FOLDER FORMAT
----------------------
Put one .md file per trick in ./content/, formatted like:

    ---
    title: Rising Card
    difficulty: intermediate
    props: [cards]
    tags: [cards, classic]
    source: "Card College Vol. 1"
    ---
    Effect: A freely selected card rises out of the deck...

    Method summary: relies on a thread/gimmick setup...
    (your own notes/summary — keep this reasonably brief, this is
    context for the AI, not a public tutorial page)

The frontmatter (between the --- lines) becomes the `tricks` row.
Everything after it becomes the text that gets chunked and embedded.
"""

import os
import glob
import uuid
import frontmatter
from supabase import create_client
import voyageai

# ---- Config ----
CONTENT_DIR = "./content"
CHUNK_SIZE = 800       # characters per chunk (rough proxy for tokens)
CHUNK_OVERLAP = 100    # overlap so context isn't lost at chunk boundaries
EMBED_MODEL = "voyage-3"

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
voyage = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Simple sliding-window chunker. Good enough for a curated, well-structured library."""
    text = text.strip()
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Batch-embed a list of text chunks."""
    result = voyage.embed(chunks, model=EMBED_MODEL, input_type="document")
    return result.embeddings


def ingest_file(filepath: str):
    post = frontmatter.load(filepath)
    meta = post.metadata
    body = post.content

    # 1. Insert trick metadata
    trick_row = {
        "id": str(uuid.uuid4()),
        "title": meta.get("title", os.path.basename(filepath)),
        "difficulty": meta.get("difficulty", "beginner"),
        "props_needed": meta.get("props", []),
        "tags": meta.get("tags", []),
        "source": meta.get("source", ""),
        "effect_description": body.split("Method summary:")[0].strip()[:1000],
        "method_summary": body,
    }
    supabase.table("tricks").insert(trick_row).execute()
    trick_id = trick_row["id"]

    # 2. Chunk + embed + store
    chunks = chunk_text(body)
    embeddings = embed_chunks(chunks)

    rows = [
        {"trick_id": trick_id, "content": chunk, "embedding": embedding}
        for chunk, embedding in zip(chunks, embeddings)
    ]
    supabase.table("trick_chunks").insert(rows).execute()

    print(f"Ingested '{trick_row['title']}' -> {len(chunks)} chunks")


def main():
    files = glob.glob(os.path.join(CONTENT_DIR, "*.md"))
    if not files:
        print(f"No .md files found in {CONTENT_DIR}. Add some curated trick files first.")
        return
    for filepath in files:
        ingest_file(filepath)
    print(f"\nDone. Ingested {len(files)} tricks.")


if __name__ == "__main__":
    main()
