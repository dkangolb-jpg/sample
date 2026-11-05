-- Storage 의 photos 버킷에 화면(anon 키)에서 그림을 올리고, 올라온 목록을 보게 허용한다
-- 다시 실행해도 오류가 나지 않는다 (버킷은 없을 때만 만들고, 허용 규칙은 지운 뒤 새로 만든다)

-- 1. photos 버킷이 없으면 만든다 (이미 있으면 설정을 건드리지 않는다)
insert into storage.buckets (id, name, public)
values ('photos', 'photos', false)
on conflict (id) do nothing;

-- 2. 있던 허용 규칙을 지운다
drop policy if exists "photos 목록 보기" on storage.objects;
drop policy if exists "photos 올리기"   on storage.objects;

-- 3. photos 버킷 안의 파일 목록 보기를 허용한다
create policy "photos 목록 보기" on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'photos');

-- 4. photos 버킷에 새 파일 올리기를 허용한다
create policy "photos 올리기" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'photos');

-- 5. 확인 : 버킷 한 줄, 허용 규칙 두 줄이 나오면 된다
select 'bucket' as kind, id as name, public::text as detail
from storage.buckets
where id = 'photos'
union all
select 'policy', policyname, cmd || ' / ' || array_to_string(roles, ', ')
from pg_policies
where schemaname = 'storage'
  and tablename  = 'objects'
  and policyname in ('photos 목록 보기', 'photos 올리기')
order by kind, name;
