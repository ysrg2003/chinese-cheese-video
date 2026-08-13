-- Curriculum catalog migration for the English-first Xiangqi learning path.
-- The GitHub Actions runtime currently uses the equivalent local SQLite schema.

create table if not exists public.curriculum_lessons (
  lesson_key text primary key,
  sequence_no integer not null unique,
  stage text not null,
  playlist_key text not null,
  content_type text not null,
  difficulty text not null,
  format text not null,
  target_seconds numeric,
  title text not null,
  objective text not null,
  hook text not null,
  analysis_focus text not null,
  position_template text not null,
  prerequisites jsonb not null default '[]'::jsonb,
  lesson_payload jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.curriculum_episode_plans (
  lesson_key text not null references public.curriculum_lessons(lesson_key) on delete cascade,
  language text not null check (language in ('en', 'zh')),
  status text not null default 'planned' check (status in ('planned', 'queued', 'processing', 'published', 'retry', 'failed', 'blocked')),
  candidate_id text,
  job_id text,
  attempts integer not null default 0,
  published_at timestamptz,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (lesson_key, language)
);

create index if not exists curriculum_lessons_sequence_idx
  on public.curriculum_lessons (is_active, sequence_no);
create index if not exists curriculum_episode_plans_status_idx
  on public.curriculum_episode_plans (language, status, updated_at);

alter table public.curriculum_lessons enable row level security;
alter table public.curriculum_episode_plans enable row level security;

-- Seed rows are loaded from config/xiangqi_curriculum_en.json by the same
-- service-role bootstrap path that loads the local SQLite curriculum.
