'use client';
import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GraduationCapIcon, LogOutIcon, ArrowRightIcon } from 'lucide-react';
import {
  Alert,
  AlertDescription,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
  Separator,
  Skeleton,
} from '@outcometrik/ui';
import { errorMessage, getSession, signIn, signOut, type Session } from './api';

export function useSession() {
  return useQuery({
    queryKey: ['session'],
    queryFn: ({ signal }) => getSession(signal),
    staleTime: 0,
  });
}
export function SessionMenu() {
  const session = useSession();
  const client = useQueryClient();
  const logout = useMutation({
    mutationFn: signOut,
    onSuccess: async () => {
      await client.cancelQueries();
      client.clear();
      window.location.assign('/login');
    },
  });
  if (session.isPending)
    return <Skeleton className="h-8 w-24" aria-label="Checking session" />;
  if (!session.data?.user)
    return (
      <Button asChild variant="ghost" size="sm">
        <a href="/login">
          Sign in
          <ArrowRightIcon data-icon="inline-end" />
        </a>
      </Button>
    );
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span>{session.data.user.first_name || session.data.user.username}</span>
      {session.data.scopes.some((s) => s.kind === 'institution') && (
        <Button asChild variant="ghost" size="sm">
          <a href="/admin">Admin dashboard</a>
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        disabled={logout.isPending}
        onClick={() => logout.mutate()}
      >
        <LogOutIcon data-icon="inline-start" />
        {logout.isPending ? 'Signing out…' : 'Sign out'}
      </Button>
      {logout.isError && (
        <span role="alert" className="text-destructive">
          {errorMessage(logout.error)}
        </span>
      )}
    </div>
  );
}
export function SignIn({
  onSignedIn,
}: {
  onSignedIn: (session: Session) => void;
}) {
  const client = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const login = useMutation({
    mutationFn: () => signIn(username, password),
    onSuccess: async (session) => {
      setPassword('');
      await client.cancelQueries();
      client.clear();
      client.setQueryData(['session'], session);
      onSignedIn(session);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate();
  }
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <section className="hidden flex-col justify-between gap-12 bg-secondary p-12 lg:flex">
        <a className="flex items-center gap-3 text-xl font-semibold" href="/">
          <GraduationCapIcon aria-hidden="true" />
          Outcometrik
        </a>
        <div className="flex max-w-md flex-col gap-6">
          <p className="text-sm font-medium text-muted-foreground">
            Institution workspace
          </p>
          <h1 className="font-serif text-5xl leading-tight tracking-tight">
            Great outcomes start with connection.
          </h1>
          <p className="leading-relaxed text-muted-foreground">
            One workspace for the people, programs, and learning that move your
            institution forward.
          </p>
        </div>
        <p className="text-sm text-muted-foreground">Learning, made visible.</p>
      </section>
      <main
        className="flex min-h-svh items-center justify-center p-6 sm:p-12"
        id="main"
      >
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>
              <h2>Welcome back.</h2>
            </CardTitle>
            <CardDescription>
              Sign in with your institution account to continue.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit}>
              <FieldGroup>
                <Field data-invalid={login.isError || undefined}>
                  <FieldLabel htmlFor="username">Username</FieldLabel>
                  <Input
                    id="username"
                    name="username"
                    autoComplete="username"
                    autoFocus
                    required
                    maxLength={150}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    aria-invalid={login.isError || undefined}
                  />
                </Field>
                <Field data-invalid={login.isError || undefined}>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    required
                    maxLength={1024}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    aria-invalid={login.isError || undefined}
                  />
                </Field>
                {login.isError && (
                  <Alert variant="destructive">
                    <AlertDescription>
                      {errorMessage(login.error)}
                    </AlertDescription>
                  </Alert>
                )}
                <Button type="submit" disabled={login.isPending}>
                  {login.isPending
                    ? 'Signing in…'
                    : 'Sign in to your workspace'}
                  <ArrowRightIcon data-icon="inline-end" />
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
          <Separator />
          <CardFooter>
            <p className="text-sm text-muted-foreground">
              Need an account or help signing in? Contact your institution
              administrator.
            </p>
          </CardFooter>
        </Card>
      </main>
    </div>
  );
}
