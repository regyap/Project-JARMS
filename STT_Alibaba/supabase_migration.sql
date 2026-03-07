-- Project JARMS — Supabase Migration
-- Run this in the Supabase SQL Editor to create the triages table

create table if not exists triages (
  id                  bigserial primary key,
  user_id             int,
  audio_file          text,

  -- STT Results
  transcript          text,
  stt_confidence      float,
  language_detected   text,
  silence_detected    boolean default false,

  -- Triage Results
  urgency_bucket      text check (urgency_bucket in (
                        'life_threatening',
                        'emergency',
                        'minor_emergency',
                        'non_emergency',
                        'unknown',
                        'requires_review'
                      )),
  urgency_score       float check (urgency_score >= 0 and urgency_score <= 1),
  triage_flags        jsonb,
  reasoning           text,
  recommended_actions jsonb,

  -- SBAR Report
  sbar_situation      text,
  sbar_background     text,
  sbar_assessment     text,
  sbar_recommendation text,

  -- Metadata
  created_at          timestamptz default now()
);

-- Index for fast lookup by user
create index if not exists triages_user_id_idx on triages (user_id);

-- Index for urgency bucket filtering (operator queue)
create index if not exists triages_urgency_bucket_idx on triages (urgency_bucket);

-- Index for time-based ordering
create index if not exists triages_created_at_idx on triages (created_at desc);
