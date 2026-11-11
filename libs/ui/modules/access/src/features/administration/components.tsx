'use client';
import { useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Building2Icon,
  BookOpenIcon,
  GraduationCapIcon,
  HistoryIcon,
  LayoutDashboardIcon,
  PlusIcon,
  ShieldCheckIcon,
  UsersIcon,
} from 'lucide-react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
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
import { SessionMenu, useSession } from '../session/components';
import { errorMessage, type Scope } from '../session/api';
import { getDashboard } from './api';
import { Modal, AccountForm, AccessForm } from './forms';
import { PeoplePanel, StructurePanel, ActivityPanel } from './panels';

type Tab = 'overview' | 'people' | 'structure' | 'activity';
const tabs = [
  { id: 'overview', title: 'Overview', icon: LayoutDashboardIcon },
  { id: 'people', title: 'People & access', icon: UsersIcon },
  { id: 'structure', title: 'Programs & offerings', icon: BookOpenIcon },
  { id: 'activity', title: 'Activity log', icon: HistoryIcon },
] satisfies { id: Tab; title: string; icon: typeof UsersIcon }[];
function Gate({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>
            <h1>{title}</h1>
          </EmptyTitle>
          <EmptyDescription>
            <div>{children}</div>
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    </main>
  );
}
export function AdminDashboard() {
  const session = useSession();
  if (session.isPending)
    return (
      <main className="mx-auto flex max-w-6xl flex-col gap-6 p-8" role="status">
        <span className="sr-only">Loading your institution…</span>
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-80 w-full" />
      </main>
    );
  if (session.isError)
    return (
      <Gate title="Unable to load your session">
        <p role="alert">{errorMessage(session.error)}</p>
        <Button className="mt-4" onClick={() => void session.refetch()}>
          Try again
        </Button>
      </Gate>
    );
  if (!session.data.user)
    return (
      <Gate title="Sign in to continue.">
        <p>Your institution workspace requires an administrator account.</p>
        <Button asChild className="mt-4">
          <a href="/login">Go to sign in →</a>
        </Button>
      </Gate>
    );
  const institutions = session.data.scopes.filter(
    (scope) => scope.kind === 'institution',
  );
  if (!institutions.length)
    return (
      <Gate title="Administrator access required">
        <p>Your account does not have institution administration access.</p>
        <div className="mt-4 flex flex-col items-center gap-4">
          <Button asChild variant="outline">
            <a href="/">Return to your workspace</a>
          </Button>
          <SessionMenu />
        </div>
      </Gate>
    );
  return <InstitutionWorkspace institutions={institutions} />;
}
function InstitutionWorkspace({ institutions }: { institutions: Scope[] }) {
  const [institutionId, setInstitutionId] = useState(institutions[0].id);
  const institution =
    institutions.find((s) => s.id === institutionId) ?? institutions[0];
  const [tab, setTab] = useState<Tab>('overview');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<'account' | number | null>(
    null,
  );
  const [notice, setNotice] = useState('');
  const dashboard = useQuery({
    queryKey: ['institution-admin', institution.id, search, page],
    queryFn: ({ signal }) => getDashboard(institution.id, search, page, signal),
    staleTime: 0,
    placeholderData: (previous, query) =>
      query?.queryKey[1] === institution.id ? previous : undefined,
  });
  const client = useQueryClient();
  async function saved(message: string) {
    setDialog(null);
    setNotice(message);
    await Promise.all([
      client.invalidateQueries({ queryKey: ['institution-admin'] }),
      client.invalidateQueries({ queryKey: ['session'] }),
    ]);
  }
  const data = dashboard.data;
  const person =
    typeof dialog === 'number'
      ? data?.users.find((u) => u.id === dialog)
      : undefined;
  const title = {
    overview: 'Institution overview',
    people: 'People & access',
    structure: 'Programs & offerings',
    activity: 'Activity log',
  }[tab];
  return (
    <SidebarProvider>
      <a className="skip-link" href="#admin-main">
        Skip to main content
      </a>
      <Sidebar role="complementary" aria-label="Institution administration">
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
            <Building2Icon aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">
                {institution.label}
              </p>
              <p className="text-xs text-muted-foreground">
                Institution workspace
              </p>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Administration</SidebarGroupLabel>
            <SidebarMenu aria-label="Institution navigation">
              {tabs.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    isActive={tab === item.id}
                    onClick={() => {
                      setTab(item.id);
                      setNotice('');
                    }}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <p className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground">
            <ShieldCheckIcon className="size-4" />
            Institution administration
          </p>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-5" />
            <span className="text-sm text-muted-foreground">
              Institution workspace
            </span>
          </div>
          <SessionMenu />
        </header>
        <Separator />
        <section
          id="admin-main"
          tabIndex={-1}
          className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6 lg:p-8"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">
                {institution.label}
              </p>
              <h1 className="text-3xl font-semibold tracking-tight">
                {title}.
              </h1>
              <p className="text-sm text-muted-foreground">
                {tab === 'overview'
                  ? 'Your people, programs, and access in one place.'
                  : tab === 'people'
                    ? 'Create accounts and give each person the access they need.'
                    : tab === 'structure'
                      ? 'Academic records define programs and offerings; their access scopes appear here automatically.'
                      : 'Account creation and access changes across your institution.'}
              </p>
            </div>
            {tab !== 'structure' && (
              <Button
                disabled={!data || dashboard.isError}
                onClick={() => {
                  setDialog('account');
                  setNotice('');
                }}
              >
                <PlusIcon data-icon="inline-start" />
                Create account
              </Button>
            )}
          </div>
          {institutions.length > 1 && (
            <Field className="max-w-sm">
              <FieldLabel htmlFor="institution">Institution</FieldLabel>
              <NativeSelect
                id="institution"
                value={institution.id}
                onChange={(e) => {
                  setInstitutionId(e.target.value);
                  setPage(1);
                  setSearch('');
                  setDialog(null);
                }}
              >
                {institutions.map((s) => (
                  <NativeSelectOption key={s.id} value={s.id}>
                    {s.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </Field>
          )}
          {notice && (
            <Alert role="status">
              <AlertTitle>Changes saved</AlertTitle>
              <AlertDescription>{notice}</AlertDescription>
            </Alert>
          )}
          {dashboard.isPending ? (
            <div className="flex flex-col gap-4" role="status">
              <span className="sr-only">Loading institution data…</span>
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-80 w-full" />
            </div>
          ) : dashboard.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to load institution data</AlertTitle>
              <AlertDescription>
                {errorMessage(dashboard.error)}
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => void dashboard.refetch()}
                >
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          ) : (
            data && (
              <>
                {tab === 'overview' && (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      {[
                        {
                          label: 'People',
                          count: data.counts.users,
                          description: 'Accounts in your institution',
                          icon: UsersIcon,
                        },
                        {
                          label: 'Programs',
                          count: data.counts.programs,
                          description: 'Across your institution',
                          icon: Building2Icon,
                        },
                        {
                          label: 'Course offerings',
                          count: data.counts.offerings,
                          description: 'Spaces for teaching and learning',
                          icon: BookOpenIcon,
                        },
                        {
                          label: 'Active roles',
                          count: data.counts.roles,
                          description: 'Scoped access assignments',
                          icon: ShieldCheckIcon,
                        },
                      ].map((metric) => (
                        <Card key={metric.label}>
                          <CardHeader className="flex flex-row items-center justify-between">
                            <CardTitle>{metric.label}</CardTitle>
                            <metric.icon
                              className="size-4 text-muted-foreground"
                              aria-hidden="true"
                            />
                          </CardHeader>
                          <CardContent>
                            <p className="text-3xl font-semibold tabular-nums">
                              {metric.count}
                            </p>
                          </CardContent>
                          <CardFooter>
                            <CardDescription>
                              {metric.description}
                            </CardDescription>
                          </CardFooter>
                        </Card>
                      ))}
                    </div>
                    <Card>
                      <CardHeader>
                        <CardTitle>One institution. Connected.</CardTitle>
                        <CardDescription>
                          Build your structure, bring your people together, and
                          keep access intentional.
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">{institution.label}</Badge>
                          <Badge variant="secondary">
                            Institution administration
                          </Badge>
                        </div>
                      </CardContent>
                      <CardFooter>
                        <Button
                          variant="outline"
                          onClick={() => setTab('structure')}
                        >
                          Manage programs & offerings
                        </Button>
                      </CardFooter>
                    </Card>
                  </>
                )}
                {(tab === 'overview' || tab === 'people') && (
                  <PeoplePanel
                    data={data}
                    search={search}
                    page={page}
                    busy={dashboard.isFetching}
                    onSearch={(value) => {
                      setSearch(value);
                      setPage(1);
                    }}
                    onPage={setPage}
                    onCreate={() => setDialog('account')}
                    onManage={setDialog}
                  />
                )}
                {tab === 'structure' && (
                  <StructurePanel data={data} />
                )}
                {(tab === 'overview' || tab === 'activity') && (
                  <ActivityPanel
                    data={data}
                    onViewAll={
                      tab === 'overview' ? () => setTab('activity') : undefined
                    }
                  />
                )}
                {dialog === 'account' && (
                  <Modal
                    title="Create an account"
                    onClose={() => setDialog(null)}
                  >
                    <AccountForm
                      data={data}
                      onSaved={() =>
                        void saved('Account created and initial role assigned.')
                      }
                    />
                  </Modal>
                )}
                {person && (
                  <Modal
                    title={`Manage access · ${person.username}`}
                    onClose={() => setDialog(null)}
                  >
                    <AccessForm
                      data={data}
                      person={person}
                      onSaved={() => void saved('Access updated.')}
                    />
                  </Modal>
                )}
              </>
            )
          )}
          <footer className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>Outcometrik · Learning, made visible.</span>
            <span>{institution.label}</span>
          </footer>
        </section>
      </SidebarInset>
    </SidebarProvider>
  );
}
