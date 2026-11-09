-- AI 에 넣은 것과 받은 답을 남기는 ai_logs 표를 만든다
-- 다시 실행해도 쌓인 기록은 지워지지 않는다 (표는 없을 때만 만들고, 허용 규칙은 지운 뒤 새로 만든다)

-- 1. 표가 없으면 만든다
create table if not exists public.ai_logs (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  kind       text not null,
  model      text not null,
  input      text not null,
  output     text not null
);

-- 1-1. 누가 남긴 기록인지 적는 owner 열이 없으면 더한다 (앞서 쌓인 기록은 비어 있다)
alter table public.ai_logs add column if not exists owner text;

-- 2. 있던 허용 규칙을 지운다
drop policy if exists "ai_logs 읽기" on public.ai_logs;
drop policy if exists "ai_logs 넣기" on public.ai_logs;

-- 3. 화면(anon 키)에서 읽기 · 넣기만 허용한다. 기록이므로 고치기 · 지우기는 열지 않는다
grant select, insert on public.ai_logs to anon, authenticated;

alter table public.ai_logs enable row level security;

create policy "ai_logs 읽기" on public.ai_logs
  for select to anon, authenticated using (true);

create policy "ai_logs 넣기" on public.ai_logs
  for insert to anon, authenticated with check (true);

-- 4. 확인 : 열 7개와 허용 규칙 2개가 나오면 된다
select 'column' as kind, column_name as name, data_type as detail
from information_schema.columns
where table_schema = 'public'
  and table_name   = 'ai_logs'
union all
select 'policy', policyname, cmd || ' / ' || array_to_string(roles, ', ')
from pg_policies
where schemaname = 'public'
  and tablename  = 'ai_logs'
order by kind, name;
