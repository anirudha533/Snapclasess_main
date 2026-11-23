begin;

alter table public.subjects
    add column join_code text not null
    default upper(left(replace(gen_random_uuid()::text, '-', ''), 12)),
    add constraint subjects_join_code_unique unique (join_code);

create function public.join_subject_by_code(p_student_id bigint, p_join_code text)
returns text
language plpgsql
set search_path = ''
as $$
declare
    target_subject_id bigint;
begin
    select subject_id into target_subject_id
    from public.subjects
    where join_code = upper(btrim(p_join_code))
      and teacher_id is not null;

    if not found then
        return 'invalid_code';
    end if;

    insert into public.subject_students (subject_id, student_id)
    values (target_subject_id, p_student_id)
    on conflict (subject_id, student_id) do nothing;

    if found then
        return 'joined';
    end if;
    return 'already_joined';
end;
$$;

revoke execute on function public.join_subject_by_code(bigint, text)
    from public, anon, authenticated;
grant execute on function public.join_subject_by_code(bigint, text) to service_role;

commit;
