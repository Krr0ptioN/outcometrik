'use client';

import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Empty, EmptyDescription, EmptyHeader, EmptyTitle, Skeleton } from '@outcometrik/ui';
import { SessionMenu, useSession } from '@outcometrik/access';
import { errorMessage } from '@outcometrik/access';
import { getCoordinatorWorkspace, getInstructorWorkspace, getStudentWorkspace } from './api';

function AccessGate({ children, title }: { children: ReactNode; title: string }) {
  return (
    <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
      <Empty><EmptyHeader><EmptyTitle><h1>{title}</h1></EmptyTitle><EmptyDescription>{children}</EmptyDescription></EmptyHeader></Empty>
    </main>
  );
}
function hasRole(session: ReturnType<typeof useSession>, role: string) {
  return Boolean(session.data?.roles.some((assignment) => assignment.role === role));
}
export function InstructorDashboard() {
  const session = useSession();
  const allowed = hasRole(session, 'instructor');
  const workspace = useQuery({ queryKey: ['academic', 'instructor'], queryFn: ({ signal }) => getInstructorWorkspace(signal), enabled: allowed });
  if (session.isPending) return <main className="mx-auto max-w-5xl space-y-4 p-8" role="status"><Skeleton className="h-12 w-64" /><Skeleton className="h-64 w-full" /></main>;
  if (!session.data?.user) return <AccessGate title="Sign in to continue."><a href="/login">Go to sign in →</a></AccessGate>;
  if (!allowed) return <AccessGate title="Instructor access required."><p>This account has no active instructor role.</p><SessionMenu /></AccessGate>;
  return (
    <main className="mx-auto flex min-h-svh max-w-6xl flex-col gap-6 p-8">
      <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-muted-foreground">Teaching workspace</p><h1 className="text-3xl font-semibold">Instructor dashboard</h1></div><SessionMenu /></header>
      {workspace.isPending && <p role="status">Loading your assigned offerings…</p>}
      {workspace.isError && <p role="alert">{errorMessage(workspace.error)}</p>}
      {workspace.data?.offerings.length === 0 && <p>No offerings are assigned to this account.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {workspace.data?.offerings.map((offering) => (
          <Card key={offering.id}>
            <CardHeader><CardTitle>{offering.label}</CardTitle><CardDescription>{offering.course} · {offering.program} · {offering.term}</CardDescription></CardHeader>
            <CardContent>
              <h2 className="mb-3 font-medium">Roster ({offering.roster.length})</h2>
              {offering.roster.length ? <ul className="divide-y">{offering.roster.map((student) => <li key={student.enrollment_id} className="flex items-center justify-between gap-4 py-2"><span>{student.name}</span><Badge variant="outline">{student.status}</Badge></li>)}</ul> : <p className="text-sm text-muted-foreground">No students are enrolled in this offering.</p>}
              <p className="mt-4 text-sm text-muted-foreground">Grade entry will appear when the gradebook is available.</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Button asChild variant="outline" className="self-start"><a href="/">All dashboards</a></Button>
    </main>
  );
}
export function CoordinatorAcademicOverview() {
  const session = useSession();
  const allowed = hasRole(session, 'program-coordinator');
  const workspace = useQuery({ queryKey: ['academic', 'coordinator'], queryFn: ({ signal }) => getCoordinatorWorkspace(signal), enabled: allowed });
  if (!allowed) return null;
  if (workspace.isPending) return <p className="mx-auto max-w-5xl p-8" role="status">Loading program roster…</p>;
  if (workspace.isError) return <p className="mx-auto max-w-5xl p-8" role="alert">{errorMessage(workspace.error)}</p>;
  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-8 pt-8" aria-labelledby="program-roster-title">
      <h2 id="program-roster-title" className="text-xl font-semibold">Academic roster</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {workspace.data.programs.map((program) => (
          <Card key={program.id}>
            <CardHeader><CardTitle>{program.label}</CardTitle><CardDescription>{program.department}</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <section><h3 className="mb-2 font-medium">Offerings</h3>{workspace.data.offerings.filter((offering) => offering.program_id === program.id).length ? <ul className="space-y-2">{workspace.data.offerings.filter((offering) => offering.program_id === program.id).map((offering) => <li key={offering.id} className="flex items-center justify-between gap-3 text-sm"><span>{offering.label} · {offering.term}</span><Badge variant="outline">{offering.enrolled} enrolled</Badge></li>)}</ul> : <p className="text-sm text-muted-foreground">No offerings yet.</p>}</section>
              <section><h3 className="mb-2 font-medium">Students</h3>{workspace.data.students.filter((student) => student.program_id === program.id).length ? <ul className="divide-y">{workspace.data.students.filter((student) => student.program_id === program.id).map((student) => <li key={`${student.id}-${student.program_id}`} className="flex items-center justify-between gap-3 py-2 text-sm"><span>{student.first_name || student.last_name ? `${student.first_name} ${student.last_name}`.trim() : student.username} · {student.student_number}</span><Badge variant="outline">{student.membership_status}</Badge></li>)}</ul> : <p className="text-sm text-muted-foreground">No program members yet.</p>}</section>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
export function StudentDashboard() {
  const session = useSession();
  const allowed = hasRole(session, 'student');
  const workspace = useQuery({ queryKey: ['academic', 'student'], queryFn: ({ signal }) => getStudentWorkspace(signal), enabled: allowed });
  if (session.isPending) return <main className="mx-auto max-w-5xl space-y-4 p-8" role="status"><Skeleton className="h-12 w-64" /><Skeleton className="h-64 w-full" /></main>;
  if (!session.data?.user) return <AccessGate title="Sign in to continue."><a href="/login">Go to sign in →</a></AccessGate>;
  if (!allowed) return <AccessGate title="Student access required."><p>This account has no active student role.</p><SessionMenu /></AccessGate>;
  return (
    <main className="mx-auto flex min-h-svh max-w-6xl flex-col gap-6 p-8">
      <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm text-muted-foreground">Learning workspace</p><h1 className="text-3xl font-semibold">Student dashboard</h1></div><SessionMenu /></header>
      {workspace.isPending && <p role="status">Loading your courses…</p>}
      {workspace.isError && <p role="alert">{errorMessage(workspace.error)}</p>}
      {workspace.data?.courses.length === 0 && <p>You are not enrolled in any offerings yet.</p>}
      <section aria-labelledby="my-courses-title"><h2 id="my-courses-title" className="mb-3 text-xl font-semibold">My courses</h2><div className="grid gap-4 md:grid-cols-2">{workspace.data?.courses.map((course) => <Card key={course.enrollment_id}><CardHeader><CardTitle>{course.course_code} · {course.section}</CardTitle><CardDescription>{course.course}</CardDescription></CardHeader><CardContent className="flex flex-wrap items-center justify-between gap-3"><span>{course.program} · {course.term}</span><Badge variant="outline">{course.enrollment_status}</Badge></CardContent></Card>)}</div></section>
      <section aria-labelledby="outcomes-title"><h2 id="outcomes-title" className="mb-3 text-xl font-semibold">Learning outcomes</h2>{workspace.data?.outcomes.length ? <p>Published outcome profile available.</p> : <p className="text-sm text-muted-foreground">No published outcome profile is available yet.</p>}</section>
      <Button asChild variant="outline" className="self-start"><a href="/">All dashboards</a></Button>
    </main>
  );
}
