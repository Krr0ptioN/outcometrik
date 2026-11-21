'use client';

import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useState } from 'react';
import {
  BookOpenIcon,
  GraduationCapIcon,
  LayoutDashboardIcon,
  UsersIcon,
} from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Separator,
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  Skeleton,
} from '@outcometrik/ui';
import { SessionMenu, useSession } from '@outcometrik/access';
import { errorMessage } from '@outcometrik/access';
import { SyllabusWorkspace, ProgramOutcomeSets } from '../syllabus/components';
import {
  getCoordinatorWorkspace,
  getInstructorWorkspace,
  getStudentWorkspace,
} from './api';
import { RosterCsvImportDialog } from './roster-import';
import {
  InstructorGradebook,
  StudentGradeSummary,
} from '../gradebook/components';

function AccessGate({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>
            <h1>{title}</h1>
          </EmptyTitle>
          <EmptyDescription>{children}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </main>
  );
}
function hasRole(session: ReturnType<typeof useSession>, role: string) {
  return Boolean(
    session.data?.roles.some((assignment) => assignment.role === role),
  );
}
export function InstructorDashboard() {
  const session = useSession();
  const allowed = hasRole(session, 'instructor');
  const workspace = useQuery({
    queryKey: ['academic', 'instructor'],
    queryFn: ({ signal }) => getInstructorWorkspace(signal),
    enabled: allowed,
  });
  const [tab, setTab] = useState<'overview' | 'gradebook'>('overview');
  const [selectedOffering, setSelectedOffering] = useState('');
  if (session.isPending)
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-8" role="status">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  if (session.isError)
    return (
      <AccessGate title="Unable to load your session.">
        <p role="alert">{errorMessage(session.error)}</p>
        <Button onClick={() => void session.refetch()}>Try again</Button>
      </AccessGate>
    );
  if (!session.data?.user)
    return (
      <AccessGate title="Sign in to continue.">
        <a href="/login">Go to sign in →</a>
      </AccessGate>
    );
  if (!allowed)
    return (
      <AccessGate title="Instructor access required.">
        <p>This account has no active instructor role.</p>
        <SessionMenu />
      </AccessGate>
    );
  const offerings = workspace.data?.offerings ?? [];
  const enrolledCount = offerings.reduce(
    (total, offering) =>
      total +
      offering.roster.filter((student) => student.status === 'enrolled').length,
    0,
  );
  const offering = offerings.find((item) => item.id === selectedOffering);
  const currentTitle = tab === 'overview' ? 'Instructor dashboard' : 'Gradebook';
  return (
    <SidebarProvider>
      <a className="skip-link" href="#instructor-main">
        Skip to main content
      </a>
      <Sidebar role="complementary" aria-label="Instructor workspace">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild>
                <a href="/">
                  <GraduationCapIcon />
                  <span>Outcometrik</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <div className="flex items-center gap-3 px-2 py-4">
            <BookOpenIcon aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">
                Teaching workspace
              </p>
              <p className="text-xs text-muted-foreground">Instructor tools</p>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Teaching</SidebarGroupLabel>
            <SidebarMenu aria-label="Instructor navigation">
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={tab === 'overview'}
                  onClick={() => setTab('overview')}
                >
                  <LayoutDashboardIcon />
                  <span>Overview</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={tab === 'gradebook'}
                  onClick={() => setTab('gradebook')}
                >
                  <UsersIcon />
                  <span>Grades & roster</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <Button asChild variant="outline" className="w-full">
            <a href="/">All dashboards</a>
          </Button>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-5" />
            <span className="text-sm text-muted-foreground">
              Teaching workspace
            </span>
          </div>
          <SessionMenu />
        </header>
        <Separator />
        <section
          id="instructor-main"
          tabIndex={-1}
          className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6 lg:p-8"
        >
          <div>
            <p className="text-sm text-muted-foreground">
              Instructor workspace
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">
              {currentTitle}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {tab === 'overview'
                ? 'Your assigned offerings, rosters, and grading work in one place.'
                : 'Enter and correct grades, review history, and release grades to students.'}
            </p>
          </div>
          {tab === 'overview' ? (
            <>
              {workspace.isPending && (
                <p role="status">Loading your assigned offerings…</p>
              )}
              {workspace.isError && (
                <p role="alert">{errorMessage(workspace.error)}</p>
              )}
              {workspace.data && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardDescription>Assigned offerings</CardDescription>
                        <CardTitle className="text-3xl">
                          {offerings.length}
                        </CardTitle>
                      </CardHeader>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardDescription>
                          Active students across your rosters
                        </CardDescription>
                        <CardTitle className="text-3xl">
                          {enrolledCount}
                        </CardTitle>
                      </CardHeader>
                    </Card>
                  </div>
                  {offerings.length ? (
                    <section
                      aria-labelledby="assigned-offerings-title"
                      className="space-y-4"
                    >
                      <div>
                        <h2
                          id="assigned-offerings-title"
                          className="text-xl font-semibold"
                        >
                          Assigned offerings
                        </h2>
                        <p className="text-sm text-muted-foreground">
                          Choose an offering to open its gradebook and roster
                          operations.
                        </p>
                      </div>
                      <div className="grid gap-4 xl:grid-cols-2">
                        {offerings.map((item) => {
                          const activeStudents = item.roster.filter(
                            (student) => student.status === 'enrolled',
                          ).length;
                          return (
                            <Card key={item.id}>
                              <CardHeader>
                                <CardTitle>{item.label}</CardTitle>
                                <CardDescription>
                                  {item.course} · {item.program} · {item.term}
                                </CardDescription>
                              </CardHeader>
                              <CardContent className="space-y-4">
                                <div className="flex flex-wrap gap-2">
                                  <Badge variant="outline">
                                    {activeStudents} active students
                                  </Badge>
                                  {activeStudents !== item.roster.length && (
                                    <Badge variant="secondary">
                                      {item.roster.length - activeStudents}{' '}
                                      inactive
                                    </Badge>
                                  )}
                                </div>
                                {item.roster.length ? (
                                  <ul className="divide-y rounded-md border px-3">
                                    {item.roster.slice(0, 5).map((student) => (
                                      <li
                                        key={student.enrollment_id}
                                        className="flex items-center justify-between gap-4 py-2 text-sm"
                                      >
                                        <span>{student.name}</span>
                                        <Badge
                                          variant={
                                            student.status === 'enrolled'
                                              ? 'outline'
                                              : 'secondary'
                                          }
                                        >
                                          {student.status}
                                        </Badge>
                                      </li>
                                    ))}
                                    {item.roster.length > 5 && (
                                      <li className="py-2 text-sm text-muted-foreground">
                                        and {item.roster.length - 5} more
                                        students
                                      </li>
                                    )}
                                  </ul>
                                ) : (
                                  <p className="text-sm text-muted-foreground">
                                    No students are enrolled in this offering.
                                  </p>
                                )}
                                <SyllabusWorkspace
                                  offering={item.id}
                                  canDraft
                                  canApprove={false}
                                />
                                <Button
                                  onClick={() => {
                                    setSelectedOffering(item.id);
                                    setTab('gradebook');
                                  }}
                                >
                                  Open gradebook
                                </Button>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    </section>
                  ) : (
                    <Empty>
                      <EmptyHeader>
                        <EmptyTitle>No offerings assigned</EmptyTitle>
                        <EmptyDescription>
                          When an offering is assigned to you, its roster and
                          grade operations will appear here.
                        </EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}
                </>
              )}
            </>
          ) : (
            <InstructorGradebook
              embedded
              defaultOfferingId={offering?.id ?? selectedOffering}
            />
          )}
        </section>
      </SidebarInset>
    </SidebarProvider>
  );
}
export function CoordinatorAcademicOverview({
  children,
  embedded = false,
}: {
  children?: ReactNode;
  embedded?: boolean;
}) {
  const session = useSession();
  const allowed = hasRole(session, 'program-coordinator');
  const workspace = useQuery({
    queryKey: ['academic', 'coordinator'],
    queryFn: ({ signal }) => getCoordinatorWorkspace(signal),
    enabled: allowed,
  });
  if (!allowed) return null;
  if (workspace.isPending)
    return (
      <p
        className={embedded ? 'text-sm text-muted-foreground' : 'mx-auto max-w-5xl p-8'}
        role="status"
      >
        Loading program roster…
      </p>
    );
  if (workspace.isError)
    return (
      <p
        className={embedded ? 'text-sm text-destructive' : 'mx-auto max-w-5xl p-8'}
        role="alert"
      >
        {errorMessage(workspace.error)}
      </p>
    );
  return (
    <section
      className={
        embedded
          ? 'flex w-full flex-col gap-6'
          : 'mx-auto flex w-full max-w-5xl flex-col gap-4 px-8 pt-8'
      }
      aria-labelledby="program-roster-title"
    >
      {workspace.data.programs.length > 0 && (
        <>
          <h2 id="program-roster-title" className="text-lg font-semibold tracking-tight">
            Academic roster
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
        {workspace.data.programs.map((program) => (
          <Card key={program.id}>
            <CardHeader>
              <CardTitle>{program.label}</CardTitle>
              <CardDescription>{program.department}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ProgramOutcomeSets program={program.id} />
              <section>
                <h3 className="mb-2 font-medium">Offerings</h3>
                {workspace.data.offerings.filter(
                  (offering) => offering.program_id === program.id,
                ).length ? (
                  <ul className="space-y-2">
                    {workspace.data.offerings
                      .filter((offering) => offering.program_id === program.id)
                      .map((offering) => (
                        <li
                          key={offering.id}
                          className="flex items-center justify-between gap-3 text-sm"
                        >
                          <span>
                            {offering.label} · {offering.term}
                          </span>
                          <Badge variant="outline">
                            {offering.enrolled} enrolled
                          </Badge>
                          <div className="flex flex-wrap items-center gap-2">
                            <RosterCsvImportDialog
                              offeringId={offering.id}
                              offeringLabel={`${offering.label} · ${offering.term}`}
                            />
                            <SyllabusWorkspace
                              offering={offering.id}
                              programId={program.id}
                              canDraft
                              canApprove
                            />
                          </div>
                        </li>
                      ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No offerings yet.
                  </p>
                )}
              </section>
              <section>
                <h3 className="mb-2 font-medium">Students</h3>
                {workspace.data.students.filter(
                  (student) => student.program_id === program.id,
                ).length ? (
                  <ul className="divide-y">
                    {workspace.data.students
                      .filter((student) => student.program_id === program.id)
                      .map((student) => (
                        <li
                          key={`${student.id}-${student.program_id}`}
                          className="flex items-center justify-between gap-3 py-2 text-sm"
                        >
                          <span>
                            {student.first_name || student.last_name
                              ? `${student.first_name} ${student.last_name}`.trim()
                              : student.username}{' '}
                            · {student.student_number}
                          </span>
                          <Badge variant="outline">
                            {student.membership_status}
                          </Badge>
                        </li>
                      ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No program members yet.
                  </p>
                )}
              </section>
            </CardContent>
          </Card>
        ))}
          </div>
        </>
      )}
      {children}
    </section>
  );
}
export function StudentDashboard({ children }: { children?: ReactNode }) {
  const session = useSession();
  const allowed = hasRole(session, 'student');
  const workspace = useQuery({
    queryKey: ['academic', 'student'],
    queryFn: ({ signal }) => getStudentWorkspace(signal),
    enabled: allowed,
  });
  if (session.isPending)
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-8" role="status">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  if (!session.data?.user)
    return (
      <AccessGate title="Sign in to continue.">
        <a href="/login">Go to sign in →</a>
      </AccessGate>
    );
  if (!allowed)
    return (
      <AccessGate title="Student access required.">
        <p>This account has no active student role.</p>
        <SessionMenu />
      </AccessGate>
    );
  return (
    <main className="mx-auto flex min-h-svh max-w-6xl flex-col gap-6 p-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Learning workspace</p>
          <h1 className="text-3xl font-semibold">Student dashboard</h1>
        </div>
        <SessionMenu />
      </header>
      {workspace.isPending && <p role="status">Loading your courses…</p>}
      {workspace.isError && <p role="alert">{errorMessage(workspace.error)}</p>}
      {workspace.data?.courses.length === 0 && (
        <p>You are not enrolled in any offerings yet.</p>
      )}
      <section aria-labelledby="my-courses-title">
        <h2 id="my-courses-title" className="mb-3 text-xl font-semibold">
          My courses
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {workspace.data?.courses.map((course) => (
            <Card key={course.enrollment_id}>
              <CardHeader>
                <CardTitle>
                  {course.course_code} · {course.section}
                </CardTitle>
                <CardDescription>{course.course}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <span>
                  {course.program} · {course.term}
                </span>
                <Badge variant="outline">{course.enrollment_status}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
      <section aria-labelledby="outcomes-title">
        <h2 id="outcomes-title" className="mb-3 text-xl font-semibold">
          Learning outcomes
        </h2>
        {workspace.data?.outcomes.length ? (
          <p>Published outcome profile available.</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            No published outcome profile is available yet.
          </p>
        )}
      </section>
      <StudentGradeSummary />
      {children}
      <Button asChild variant="outline" className="self-start">
        <a href="/">All dashboards</a>
      </Button>
    </main>
  );
}
