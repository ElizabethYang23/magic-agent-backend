-- ============================================================
-- Magic AI Assistant — Supabase Schema
-- Run this in Supabase SQL Editor (Project > SQL Editor > New query)
-- ============================================================

-- 1. Enable the pgvector extension (for similarity search over embeddings)
create extension if not exists vector;

-- ============================================================
-- 2. PROFILES
-- Extends Supabase's built-in auth.users with magic-specific info.
-- A row is created automatically for every new signup (trigger below).
-- ============================================================
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  skill_level text check (skill_level in ('beginner', 'intermediate', 'advanced')) default 'beginner',
  style_preference text, -- e.g. "comedic", "mysterious", "cyber/modern"
  props_owned jsonb default '[]'::jsonb, -- e.g. ["cards", "coins", "thumb tip"]
  created_at timestamptz default now()
);

-- Auto-create a profile row whenever someone signs up
create function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ============================================================
-- 3. TRICKS — the curated knowledge base (metadata per trick)
-- ============================================================
create table tricks (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  effect_description text, -- what the audience sees/experiences
  method_summary text,      -- brief internal summary (not full exposure text)
  difficulty text check (difficulty in ('beginner', 'intermediate', 'advanced')),
  props_needed jsonb default '[]'::jsonb,
  tags text[] default '{}', -- e.g. {'cards','mentalism','close-up'}
  source text,              -- book/video/audio this came from, for your own reference
  created_at timestamptz default now()
);

-- ============================================================
-- 4. TRICK_CHUNKS — the actual searchable text chunks + embeddings
-- This is what RAG retrieval queries against.
-- Dimension 1024 matches Voyage AI's voyage-3 model — change if you use
-- a different embedding model (e.g. 1536 for OpenAI text-embedding-3-small).
-- ============================================================
create table trick_chunks (
  id uuid primary key default gen_random_uuid(),
  trick_id uuid references tricks(id) on delete cascade,
  content text not null,
  embedding vector(1024),
  created_at timestamptz default now()
);

-- Vector similarity index (speeds up nearest-neighbor search at scale;
-- fine to skip while your library is small, but harmless to add now)
create index on trick_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Similarity search function — called from your backend via supabase.rpc()
create or replace function match_trick_chunks (
  query_embedding vector(1024),
  match_count int default 5
) returns table (
  id uuid,
  trick_id uuid,
  content text,
  similarity float
)
language sql stable
as $$
  select
    trick_chunks.id,
    trick_chunks.trick_id,
    trick_chunks.content,
    1 - (trick_chunks.embedding <=> query_embedding) as similarity
  from trick_chunks
  order by trick_chunks.embedding <=> query_embedding
  limit match_count;
$$;

-- ============================================================
-- 5. TRAINING_LOGS — M10 (progress tracking)
-- ============================================================
create table training_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  trick_id uuid references tricks(id) on delete set null,
  practice_date date default current_date,
  minutes_practiced int,
  self_rating int check (self_rating between 1 and 5),
  notes text,
  created_at timestamptz default now()
);

-- ============================================================
-- 6. ROUTINES — M1 outputs (saved generated routines)
-- ============================================================
create table routines (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text,
  content text, -- the generated routine/flow text
  based_on_tricks uuid[] default '{}', -- trick ids it drew from
  created_at timestamptz default now()
);

-- ============================================================
-- 7. SCRIPTS — M2 outputs (saved generated patter/scripts)
-- ============================================================
create table scripts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  routine_id uuid references routines(id) on delete cascade,
  content text,
  tone text, -- e.g. "comedic", "dramatic"
  created_at timestamptz default now()
);

-- ============================================================
-- 8. ROW LEVEL SECURITY (RLS)
-- Users can only see/edit their own private data.
-- The trick library is shared knowledge, readable by any logged-in user.
-- ============================================================
alter table profiles enable row level security;
alter table training_logs enable row level security;
alter table routines enable row level security;
alter table scripts enable row level security;
alter table tricks enable row level security;
alter table trick_chunks enable row level security;

create policy "Users manage their own profile"
  on profiles for all using (auth.uid() = id);

create policy "Users manage their own training logs"
  on training_logs for all using (auth.uid() = user_id);

create policy "Users manage their own routines"
  on routines for all using (auth.uid() = user_id);

create policy "Users manage their own scripts"
  on scripts for all using (auth.uid() = user_id);

create policy "Any logged-in user can read the trick library"
  on tricks for select using (auth.role() = 'authenticated');

create policy "Any logged-in user can read trick chunks"
  on trick_chunks for select using (auth.role() = 'authenticated');

-- Note: only your ingestion script (using the service_role key, which
-- bypasses RLS) should be able to INSERT into tricks/trick_chunks.
-- Regular users should never write to the shared knowledge base directly.
