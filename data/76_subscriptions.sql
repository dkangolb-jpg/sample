-- 76_subscriptions.csv 를 subscriptions 표로 만든다
-- 다시 실행하면 표를 지우고 새로 만들어 CSV 12줄만 남은 처음 상태로 돌아온다

-- 1. 있던 표(와 거기 붙은 허용 규칙)를 지운다
drop table if exists public.subscriptions cascade;

-- 2. 표를 만든다
create table public.subscriptions (
  id          bigint generated always as identity primary key,
  name        text    not null,
  category    text    not null,
  monthly_fee integer not null check (monthly_fee >= 0),
  last_used   date    not null,
  created_at  timestamptz not null default now()
);

-- 3. CSV 내용을 넣는다
insert into public.subscriptions (name, category, monthly_fee, last_used) values
  ('영화 · 드라마 구독', '영상',     13500,  '2026-10-18'),
  ('음악 구독',          '음악',     10900,  '2026-10-20'),
  ('클라우드 저장공간',  '업무',     2400,   '2026-10-19'),
  ('헬스장',             '운동',     55000,  '2026-03-02'),
  ('신문 구독',          '읽을거리', 150000, '2026-10-21'),
  ('우유 배달',          '먹거리',   18000,  '2026-10-21'),
  ('정수기 렌털',        '생활',     23900,  '2026-10-21'),
  ('꽃 정기배송',        '생활',     19800,  '2026-09-28'),
  ('전자책 구독',        '읽을거리', 9900,   '2026-08-15'),
  ('반찬 정기배송',      '먹거리',   64000,  '2026-10-16'),
  ('커피 원두 정기배송', '먹거리',   17000,  '2026-10-12'),
  ('문서 작성 도구',     '업무',     8900,   '2026-10-22');

-- 4. 화면(anon 키)에서 읽기 · 넣기 · 고치기 · 지우기를 허용한다
grant select, insert, update, delete on public.subscriptions to anon, authenticated;

alter table public.subscriptions enable row level security;

create policy "subscriptions 읽기" on public.subscriptions
  for select to anon, authenticated using (true);

create policy "subscriptions 넣기" on public.subscriptions
  for insert to anon, authenticated with check (true);

create policy "subscriptions 고치기" on public.subscriptions
  for update to anon, authenticated using (true) with check (true);

create policy "subscriptions 지우기" on public.subscriptions
  for delete to anon, authenticated using (true);

-- 5. 확인 : 12줄이 나오면 된다
select * from public.subscriptions order by id;
