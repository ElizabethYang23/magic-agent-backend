# Magic AI Assistant — Starter Backend

Three files, meant to be handed to your coder (or Claude Code) as a working starting point:

- **supabase_schema.sql** — run once in Supabase's SQL Editor. Sets up auth-linked
  profiles, the trick knowledge base (with vector search), training logs, and
  saved routines/scripts. Also sets up Row Level Security so users can only
  see their own private data.
- **ingest_content.py** — run once (or whenever you add new curated tricks).
  Reads `.md` files from a `./content` folder, chunks and embeds them, and
  loads them into Supabase.
- **query_agent.py** — the live request-handling logic: embed the user's
  question, retrieve the most relevant chunks, call Claude with the right
  mode (routine / script / training), return the answer. Wire this into your
  actual backend route (Express, FastAPI, etc.) — it's written as a plain
  reference script so it's easy to lift into any framework.

## Setup order

1. **Create a Supabase project** at supabase.com (free tier is enough for a class project).
2. Run `supabase_schema.sql` in the SQL Editor.
3. Grab your keys: Project Settings → API → `Project URL` and `service_role` key
   (service_role for the ingestion script only — your frontend/backend user-facing
   calls should use the `anon` key + Supabase auth instead, so RLS applies).
4. Get a Voyage AI key (voyageai.com) for embeddings, and an Anthropic API key.
5. `pip install supabase voyageai python-frontmatter anthropic`
6. Write 20-40 curated trick `.md` files into a `./content` folder (see the
   format described at the top of `ingest_content.py`).
7. `python ingest_content.py` — this fills your knowledge base.
8. Test retrieval + agent responses with `python query_agent.py`
   (swap in a real user_id from your `profiles` table after you've signed up
   a test user through your frontend's auth flow).
9. Wire `ask_agent()` into your actual backend API route, and have the
   frontend call that route from the chat UI.

## A note on content curation

Start smaller than you think you need — 20-40 well-written entries you trust
beat a huge pile of raw scraped text. Quality of the source material directly
drives quality of what the agent retrieves and says. Once the pipeline works
end-to-end on the small set, adding more content later is just running
`ingest_content.py` again on more files — the hard part (the pipeline) will
already be done.
