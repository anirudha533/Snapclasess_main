begin;

alter table public.teachers add column if not exists password_hash text;

grant select, insert on public.teachers to service_role;
grant usage on sequence public.teachers_teacher_id_seq to service_role;

commit;
