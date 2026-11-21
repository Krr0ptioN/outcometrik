'use client';
import * as React from 'react';
import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRightIcon,
  EyeIcon,
  EyeOffIcon,
  LogOutIcon,
  ShieldCheckIcon,
} from 'lucide-react';
import {
  Alert,
  AlertDescription,
  BrandCrest,
  Button,
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
  Input,
  Skeleton,
  StatusDot,
  ThemeToggle,
} from '@outcometrik/ui';
import { errorMessage, getSession, signIn, signOut, type Session } from './api';
import {
  DEMO_PERSONAS,
  getDemoPersonaPassword,
  isDemoPersonasEnabled,
  validateSignInFields,
  type DemoPersona,
  type SignInValidationErrors,
} from './personas';

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
    return (
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Skeleton className="h-8 w-24" aria-label="Checking session" />
      </div>
    );
  if (!session.data?.user)
    return (
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Button asChild variant="ghost" size="sm">
          <a href="/login">
            Sign in
            <ArrowRightIcon data-icon="inline-end" />
          </a>
        </Button>
      </div>
    );
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span>{session.data.user.first_name || session.data.user.username}</span>
      {session.data.scopes.some((s) => s.kind === 'institution') && (
        <Button asChild variant="ghost" size="sm">
          <a href="/admin">Admin dashboard</a>
        </Button>
      )}
      {new Set(session.data.roles.map((assignment) => assignment.role)).has(
        'program-coordinator',
      ) && (
        <Button asChild variant="ghost" size="sm">
          <a href="/coordinator">Coordinator dashboard</a>
        </Button>
      )}
      {new Set(session.data.roles.map((assignment) => assignment.role)).has(
        'instructor',
      ) && (
        <Button asChild variant="ghost" size="sm">
          <a href="/instructor">Instructor dashboard</a>
        </Button>
      )}
      {new Set(session.data.roles.map((assignment) => assignment.role)).has(
        'student',
      ) && (
        <Button asChild variant="ghost" size="sm">
          <a href="/student">Student dashboard</a>
        </Button>
      )}
      <ThemeToggle />
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

function ProofSparkline() {
  return (
    <svg
      width="96"
      height="32"
      viewBox="0 0 96 32"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <defs>
        <linearGradient id="auth-proof-spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity="0.16" />
          <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M2 26 L24 22 L48 17 L72 13 L94 6 L94 31 L2 31 Z"
        fill="url(#auth-proof-spark-fill)"
      />
      <path
        d="M2 26 L24 22 L48 17 L72 13 L94 6"
        stroke="var(--accent-primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="94" cy="6" r="2.5" fill="var(--accent-primary)" />
    </svg>
  );
}

export interface SignInProps {
  onSignedIn: (session: Session) => void;
  showDemoPersonas?: boolean;
  notice?: string | null;
}

export function SignIn({
  onSignedIn,
  showDemoPersonas = isDemoPersonasEnabled(),
  notice = null,
}: SignInProps) {
  const client = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<SignInValidationErrors>({});
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null);

  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);

  const login = useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      signIn(credentials.username, credentials.password),
    onSuccess: async (session) => {
      setPassword('');
      setActivePersonaId(null);
      await client.cancelQueries();
      client.clear();
      client.setQueryData(['session'], session);
      onSignedIn(session);
    },
    onError: () => {
      setActivePersonaId(null);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateSignInFields(username, password);
    setFieldErrors(errors);

    if (errors.username) {
      usernameInputRef.current?.focus();
      return;
    }
    if (errors.password) {
      passwordInputRef.current?.focus();
      return;
    }

    login.mutate({ username: username.trim(), password });
  }

  function handlePersonaSignIn(persona: DemoPersona) {
    setFieldErrors({});
    setUsername(persona.username);
    setActivePersonaId(persona.id);
    const demoPassword = getDemoPersonaPassword(password);
    login.mutate({ username: persona.username, password: demoPassword });
  }

  const usernameInvalid = Boolean(fieldErrors.username || login.isError);
  const passwordInvalid = Boolean(fieldErrors.password || login.isError);

  return (
    <div
      data-slot="auth-split-shell"
      className="grid min-h-svh w-full bg-background text-foreground lg:grid-cols-[minmax(0,1fr)_minmax(0,0.92fr)]"
    >
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      {/* Left pane: Institutional sign-in form */}
      <main
        id="main-content"
        tabIndex={-1}
        className="flex min-h-svh flex-col justify-between px-6 py-6 outline-none sm:px-10 sm:py-8"
      >
        <div className="flex items-center justify-between gap-4">
          <BrandCrest subtitle="Acıbadem University · Computer Engineering" />
          <ThemeToggle variant="ghost" size="icon-sm" />
        </div>

        <div className="mx-auto my-auto w-full max-w-[380px] py-10">
          <header className="mb-6">
            <h1 className="text-[26px] font-semibold tracking-[-0.025em] text-foreground">
              Pick up where you left off
            </h1>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              Sign in with your university credentials. Access is scoped to your
              assigned roles and capabilities.
            </p>
          </header>

          {notice ? (
            <Alert className="mb-5">
              <AlertDescription>{notice}</AlertDescription>
            </Alert>
          ) : null}

          <form onSubmit={handleSubmit} noValidate>
            <FieldGroup className="gap-4">
              <Field data-invalid={usernameInvalid || undefined}>
                <FieldLabel htmlFor="login-username">
                  Institutional email
                </FieldLabel>
                <Input
                  ref={usernameInputRef}
                  id="login-username"
                  name="username"
                  type="email"
                  autoComplete="username"
                  placeholder="name.surname@acibadem.edu.tr"
                  maxLength={150}
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    if (fieldErrors.username) {
                      setFieldErrors((prev) => ({
                        ...prev,
                        username: undefined,
                      }));
                    }
                  }}
                  aria-invalid={usernameInvalid || undefined}
                  aria-describedby={
                    fieldErrors.username ? 'login-username-error' : undefined
                  }
                />
                {fieldErrors.username ? (
                  <FieldError id="login-username-error">
                    {fieldErrors.username}
                  </FieldError>
                ) : null}
              </Field>

              <Field data-invalid={passwordInvalid || undefined}>
                <FieldLabel htmlFor="login-password">Password</FieldLabel>
                <div className="relative">
                  <Input
                    ref={passwordInputRef}
                    id="login-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    maxLength={1024}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (fieldErrors.password) {
                        setFieldErrors((prev) => ({
                          ...prev,
                          password: undefined,
                        }));
                      }
                    }}
                    aria-invalid={passwordInvalid || undefined}
                    aria-describedby={
                      fieldErrors.password ? 'login-password-error' : undefined
                    }
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-[var(--radius-input)] text-muted-foreground transition-colors duration-150 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none"
                  >
                    {showPassword ? (
                      <EyeOffIcon className="size-4" aria-hidden="true" />
                    ) : (
                      <EyeIcon className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                {fieldErrors.password ? (
                  <FieldError id="login-password-error">
                    {fieldErrors.password}
                  </FieldError>
                ) : null}
              </Field>

              {login.isError ? (
                <Alert variant="destructive" role="alert">
                  <AlertDescription>{errorMessage(login.error)}</AlertDescription>
                </Alert>
              ) : null}

              <Button
                type="submit"
                disabled={login.isPending}
                className="mt-1 h-10 w-full"
              >
                <span>
                  {login.isPending ? 'Signing in…' : 'Continue to workspace'}
                </span>
                <ArrowRightIcon className="size-4" aria-hidden="true" />
              </Button>
            </FieldGroup>
          </form>

          {showDemoPersonas ? (
            <section
              aria-label="Quick seeded persona switcher"
              data-slot="demo-persona-switcher"
              className="mt-6"
            >
              <div className="mb-3 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
                <span>or sign in as a seeded persona</span>
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
              </div>

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {DEMO_PERSONAS.map((persona) => {
                  const isBusy =
                    login.isPending && activePersonaId === persona.id;
                  return (
                    <button
                      key={persona.id}
                      type="button"
                      disabled={login.isPending}
                      onClick={() => handlePersonaSignIn(persona)}
                      data-persona={persona.id}
                      className="flex flex-col items-start rounded-[var(--radius-card)] border border-border bg-card px-3 py-2.5 text-left transition-[background-color,border-color] duration-150 ease-out hover:border-[var(--accent-border)] hover:bg-[var(--surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none"
                    >
                      <span className="text-[13px] font-semibold text-foreground">
                        {isBusy ? 'Signing in…' : persona.name}
                      </span>
                      <span className="text-[11.5px] text-muted-foreground">
                        {persona.summary}
                      </span>
                    </button>
                  );
                })}
              </div>
              <p className="mt-2.5 text-[11.5px] text-muted-foreground">
                Development only. Uses local seeded accounts from{' '}
                <code className="tabular-mono">seed_demo</code>.
              </p>
            </section>
          ) : null}
        </div>

        <p className="text-xs text-muted-foreground">
          Need an account or access scope update? Contact your institution
          administrator.
        </p>
      </main>

      {/* Right pane: Tinted navy institutional proof panel (never saturated brand flood) */}
      <aside
        aria-label="Platform verification summary"
        data-slot="auth-proof-pane"
        className="hidden flex-col justify-between border-l border-border bg-sidebar p-12 lg:flex"
      >
        <div>
          <StatusDot variant="success" label="Pilot active · 2026–2027 Fall" />
        </div>

        <div className="w-full max-w-[420px] rounded-[var(--radius-card)] border border-border bg-card p-6 shadow-sm">
          <p className="text-xs font-medium text-muted-foreground">
            Verified cohort attainment
          </p>
          <div className="mt-2 flex items-end justify-between gap-4">
            <p className="tabular-mono text-[34px] leading-none font-semibold tracking-[-0.025em] text-[var(--accent-primary)]">
              81.2
            </p>
            <ProofSparkline />
          </div>
          <p className="mt-2.5 text-xs text-muted-foreground">
            Mean across 7 measured POs · n=42 of 45 students · Series v1
          </p>

          <dl className="mt-5 grid gap-2.5 border-t border-border pt-4 text-xs">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted-foreground">Scoring precision</dt>
              <dd className="tabular-mono font-medium text-foreground">
                Decimal · ROUND_HALF_UP
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted-foreground">Publication ledger</dt>
              <dd className="tabular-mono font-medium text-foreground">
                Immutable snapshots
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-muted-foreground">Authorization</dt>
              <dd className="inline-flex items-center gap-1.5 font-medium text-foreground">
                <ShieldCheckIcon
                  className="size-3.5 text-[var(--accent-primary)]"
                  aria-hidden="true"
                />
                <span>Scoped least-privilege</span>
              </dd>
            </div>
          </dl>
        </div>

        <p className="text-xs text-muted-foreground">
          Acıbadem University Computer Engineering · Decimal-precision outcome
          attainment ledger
        </p>
      </aside>
    </div>
  );
}
