begin;

grant select (student_id, name, face_embedding, voice_embedding),
    insert (name, face_embedding, voice_embedding) on public.students to service_role;
grant select, insert on public.subjects, public.subject_students to service_role;
grant select, insert on public.attendance_logs to service_role;
grant usage on sequence public.students_student_id_seq, public.subjects_subject_id_seq,
    public.attendance_logs_id_seq to service_role;

create unique index attendance_once_per_day on public.attendance_logs
    (subject_id, student_id, (("timestamp" at time zone 'Asia/Kolkata')::date));

create function public.record_student_attendance(p_student_id bigint, p_subject_id bigint)
returns text
language plpgsql
set search_path = ''
as $$
begin
    insert into public.attendance_logs (student_id, subject_id)
    select student_id, subject_id from public.subject_students
    where student_id = p_student_id and subject_id = p_subject_id
    on conflict (subject_id, student_id, (("timestamp" at time zone 'Asia/Kolkata')::date))
    do nothing;
    if found then
        return 'recorded';
    end if;
    if exists (
        select 1 from public.subject_students
        where student_id = p_student_id and subject_id = p_subject_id
    ) then
        return 'already_recorded';
    end if;
    return 'not_enrolled';
end;
$$;

revoke execute on function public.record_student_attendance(bigint, bigint)
    from public, anon, authenticated;
grant execute on function public.record_student_attendance(bigint, bigint) to service_role;

commit;
