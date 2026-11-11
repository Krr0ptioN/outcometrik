'use client';
import {
  ArrowUpRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  UsersIcon,
  Building2Icon,
  BookOpenIcon,
} from 'lucide-react';
import {
  Avatar,
  AvatarFallback,
  Badge,
  Button,
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  Field,
  FieldLabel,
  Input,
  Separator,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import type { Dashboard } from './api';

export function PeoplePanel({
  data,
  search,
  page,
  busy,
  onSearch,
  onPage,
  onCreate,
  onManage,
}: {
  data: Dashboard;
  search: string;
  page: number;
  busy: boolean;
  onSearch: (value: string) => void;
  onPage: (page: number) => void;
  onCreate: () => void;
  onManage: (id: number) => void;
}) {
  return (
    <Card aria-labelledby="people-title" aria-busy={busy}>
      <CardHeader className="gap-4 sm:flex sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <CardTitle>
            <h2 id="people-title">
              Your people <Badge variant="secondary">{data.total}</Badge>
            </h2>
          </CardTitle>
          <CardDescription>
            Institution accounts and their assigned access.
          </CardDescription>
        </div>
        <Field className="sm:max-w-64">
          <FieldLabel htmlFor="people-search" className="sr-only">
            Search people
          </FieldLabel>
          <Input
            id="people-search"
            placeholder="Search by name or email…"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
        </Field>
      </CardHeader>
      <CardContent>
        {!data.users.length ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <UsersIcon />
              </EmptyMedia>
              <EmptyTitle>
                {search
                  ? 'No matching people'
                  : 'Start building your institution'}
              </EmptyTitle>
              <EmptyDescription>
                {search
                  ? 'Try another name, username, or email.'
                  : 'Create student and instructor accounts to get started.'}
              </EmptyDescription>
            </EmptyHeader>
            {!search && (
              <EmptyContent>
                <Button variant="outline" onClick={onCreate}>
                  Create an account
                </Button>
              </EmptyContent>
            )}
          </Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Name</TableHead>
                <TableHead scope="col">Role & scope</TableHead>
                <TableHead scope="col">Status</TableHead>
                <TableHead scope="col">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarFallback>
                          {(user.first_name || user.username)
                            .slice(0, 1)
                            .toUpperCase()}
                          {user.last_name.slice(0, 1).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col gap-1">
                        <p className="font-medium">
                          {[user.first_name, user.last_name]
                            .filter(Boolean)
                            .join(' ') || user.username}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {user.email || user.username}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-2">
                      {user.roles.map((role) => (
                        <div
                          className="flex flex-wrap items-center gap-2"
                          key={role.id}
                        >
                          <Badge variant="secondary">
                            {data.roles.find((r) => r.slug === role.role_id)
                              ?.name ?? role.role_id}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {
                              data.scopes.find((s) => s.id === role.scope_id)
                                ?.label
                            }
                          </span>
                        </div>
                      ))}
                      {user.grants.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {user.grants.length} direct{' '}
                          {user.grants.length === 1 ? 'grant' : 'grants'}
                        </span>
                      )}
                      {!user.roles.length && !user.grants.length && (
                        <span className="text-xs text-muted-foreground">
                          No access assigned
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? 'outline' : 'secondary'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onManage(user.id)}
                      aria-label={`Manage access for ${user.username}`}
                    >
                      Manage
                      <ArrowUpRightIcon data-icon="inline-end" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap justify-between gap-4">
        <p className="text-xs text-muted-foreground">
          {data.total
            ? `Showing ${(page - 1) * 20 + 1}–${Math.min(page * 20, data.total)} of ${data.total} people`
            : '0 people'}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1 || busy}
            onClick={() => onPage(page - 1)}
          >
            <ChevronLeftIcon data-icon="inline-start" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page * 20 >= data.total || busy}
            onClick={() => onPage(page + 1)}
          >
            Next
            <ChevronRightIcon data-icon="inline-end" />
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
export function StructurePanel({
  data,
  onCreate,
}: {
  data: Dashboard;
  onCreate: () => void;
}) {
  const programs = data.scopes.filter((s) => s.kind === 'program');
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Institution structure</h2>
        </CardTitle>
        <CardDescription>
          Programs contain course offerings. Access stays within its assigned
          scope.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!programs.length ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Building2Icon />
              </EmptyMedia>
              <EmptyTitle>Your first program starts here.</EmptyTitle>
              <EmptyDescription>
                Add a program, then create course offerings for instructors and
                students.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" onClick={onCreate}>
                Add a program
              </Button>
            </EmptyContent>
          </Empty>
        ) : (
          programs.map((program) => (
            <Card key={program.id}>
              <CardHeader>
                <CardTitle>
                  <h3>{program.label}</h3>
                </CardTitle>
                <CardDescription>Program</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-3">
                  {data.scopes
                    .filter((s) => s.parent_id === program.id)
                    .map((offering) => (
                      <li
                        className="flex flex-wrap items-center gap-3 text-sm"
                        key={offering.id}
                      >
                        <BookOpenIcon aria-hidden="true" className="size-4" />
                        <span>{offering.label}</span>
                        <Badge variant="outline">Course offering</Badge>
                      </li>
                    ))}
                </ul>
                {!data.scopes.some((s) => s.parent_id === program.id) && (
                  <p className="text-sm text-muted-foreground">
                    No course offerings yet.
                  </p>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </CardContent>
    </Card>
  );
}
export function ActivityPanel({
  data,
  onViewAll,
}: {
  data: Dashboard;
  onViewAll?: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Recent activity</h2>
        </CardTitle>
        <CardDescription>
          The latest 20 account and access changes.
        </CardDescription>
        {onViewAll && (
          <CardAction>
            <Button variant="ghost" size="sm" onClick={onViewAll}>
              View activity
              <ArrowUpRightIcon data-icon="inline-end" />
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
        {!data.audit.length ? (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>No activity yet</EmptyTitle>
              <EmptyDescription>
                Changes will appear here as your institution grows.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ul className="flex flex-col gap-4">
            {data.audit.map((event, index) => (
              <li className="flex flex-col gap-4" key={event.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium capitalize">
                      {event.action.replaceAll('.', ' ').replaceAll('_', ' ')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {event.actor}
                      {event.subject && ` · ${event.subject}`} ·{' '}
                      {data.scopes.find((s) => s.id === event.scope_id)?.label}
                    </p>
                  </div>
                  <time
                    className="text-xs text-muted-foreground"
                    dateTime={event.occurred_at}
                  >
                    {new Date(event.occurred_at).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </time>
                </div>
                {index < data.audit.length - 1 && <Separator />}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
