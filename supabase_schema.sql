
-- Create a simple table to store sightings per species
create table if not exists public.bird_sightings (
  species text primary key,
  seen boolean default false,
  first_seen_date date,
  notes text,
  updated_at timestamptz default now()
);

-- Enable Row Level Security (RLS)
alter table public.bird_sightings enable row level security;

-- Development-only policy: allow all operations for anon role.
-- For private/personal use only. Replace with authenticated policies for production.
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='bird_sightings' and policyname='allow_anon_rw') then
    create policy allow_anon_rw on public.bird_sightings
      for all using (true) with check (true);
  end if;
end $$;
