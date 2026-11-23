-- Keep student biometrics accessible only to the server-side database client.
grant select (student_id, name, face_embedding) on public.students to service_role;
