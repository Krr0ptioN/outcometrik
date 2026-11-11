'use client';
import { useState, type FormEvent, type ReactNode } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
  Separator,
} from '@outcometrik/ui';
import { errorMessage } from '../session/api';
import {
  assignAccess,
  activateAccount,
  createAccount,
  createScope,
  revokeAccess,
  type Dashboard,
  type Person,
} from './api';

export function FormError({ error }: { error: unknown }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Unable to save changes</AlertTitle>
      <AlertDescription>{errorMessage(error)}</AlertDescription>
    </Alert>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Manage accounts and access within your institution.
          </DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  );
}
export function AccountForm({
  data,
  onSaved,
}: {
  data: Dashboard;
  onSaved: () => void;
}) {
  const [scopeId, setScopeId] = useState(
    data.scopes.find((s) => s.kind === 'offering')?.id ?? data.scope_id,
  );
  const [role, setRole] = useState('student');
  const scope = data.scopes.find((s) => s.id === scopeId);
  const roles = data.roles.filter((r) => r.scope_kind === scope?.kind);
  const selectedRole =
    roles.find((r) => r.slug === role)?.slug ?? roles[0]?.slug ?? '';
  const create = useMutation({ mutationFn: createAccount, onSuccess: onSaved });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      username: String(form.get('username')),
      email: String(form.get('email')),
      first_name: String(form.get('first_name')),
      last_name: String(form.get('last_name')),
      password: String(form.get('password')),
      scope: scopeId,
      role: selectedRole,
    });
  }
  return (
    <form onSubmit={submit}>
      <FieldGroup>
        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="first-name">First name</FieldLabel>
            <Input
              id="first-name"
              name="first_name"
              autoComplete="off"
              maxLength={150}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="last-name">Last name</FieldLabel>
            <Input
              id="last-name"
              name="last_name"
              autoComplete="off"
              maxLength={150}
            />
          </Field>
        </FieldGroup>
        <Field>
          <FieldLabel htmlFor="account-email">Institution email</FieldLabel>
          <Input
            id="account-email"
            type="email"
            name="email"
            autoComplete="off"
            required
            maxLength={254}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="account-username">Username</FieldLabel>
          <Input
            id="account-username"
            name="username"
            autoComplete="off"
            required
            maxLength={150}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="account-password">Initial password</FieldLabel>
          <Input
            id="account-password"
            type="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            aria-describedby="password-guidance"
          />
          <FieldDescription id="password-guidance">
            Use a strong, unique password of at least 8 characters. Share it
            through your institution’s secure channel.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="account-scope">Assign to</FieldLabel>
          <NativeSelect
            id="account-scope"
            value={scopeId}
            onChange={(e) => setScopeId(e.target.value)}
          >
            {data.scopes.map((s) => (
              <NativeSelectOption key={s.id} value={s.id}>
                {s.label} · {s.kind}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
        <Field>
          <FieldLabel htmlFor="account-role">Initial role</FieldLabel>
          <NativeSelect
            id="account-role"
            value={selectedRole}
            required
            onChange={(e) => setRole(e.target.value)}
          >
            {roles.map((r) => (
              <NativeSelectOption key={r.slug} value={r.slug}>
                {r.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
        {!data.scopes.some((s) => s.kind === 'offering') && (
          <Alert>
            <AlertTitle>Set up a course offering first</AlertTitle>
            <AlertDescription>
              Student and instructor accounts need a course offering. Add a
              program and offering from Programs & offerings.
            </AlertDescription>
          </Alert>
        )}
        {create.isError && <FormError error={create.error} />}
        <Button type="submit" disabled={create.isPending || !selectedRole}>
          {create.isPending ? 'Creating account…' : 'Create account →'}
        </Button>
      </FieldGroup>
    </form>
  );
}
export function ScopeForm({
  data,
  onSaved,
}: {
  data: Dashboard;
  onSaved: () => void;
}) {
  const [kind, setKind] = useState('program');
  const [parentId, setParentId] = useState(data.scope_id);
  const parents = data.scopes.filter(
    (s) => s.kind === (kind === 'program' ? 'institution' : 'program'),
  );
  const selectedParent =
    parents.find((s) => s.id === parentId)?.id ?? parents[0]?.id ?? '';
  const create = useMutation({ mutationFn: createScope, onSuccess: onSaved });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      label: String(form.get('label')),
      kind,
      parent: selectedParent,
    });
  }
  return (
    <form onSubmit={submit}>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="scope-type">Type</FieldLabel>
          <NativeSelect
            id="scope-type"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <NativeSelectOption value="program">Program</NativeSelectOption>
            <NativeSelectOption value="offering">
              Course offering
            </NativeSelectOption>
          </NativeSelect>
        </Field>
        <Field>
          <FieldLabel htmlFor="scope-name">Name</FieldLabel>
          <Input
            id="scope-name"
            name="label"
            required
            maxLength={160}
            placeholder={
              kind === 'program'
                ? 'e.g. Computer Engineering'
                : 'e.g. CSE 301 · Fall 2026'
            }
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="scope-parent">
            {kind === 'program' ? 'Institution' : 'Program'}
          </FieldLabel>
          <NativeSelect
            id="scope-parent"
            value={selectedParent}
            onChange={(e) => setParentId(e.target.value)}
            required
          >
            {parents.map((s) => (
              <NativeSelectOption key={s.id} value={s.id}>
                {s.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
        {!selectedParent && (
          <Alert>
            <AlertDescription>
              Create a program before adding a course offering.
            </AlertDescription>
          </Alert>
        )}
        {create.isError && <FormError error={create.error} />}
        <Button type="submit" disabled={create.isPending || !selectedParent}>
          {create.isPending
            ? 'Saving…'
            : `Add ${kind === 'program' ? 'program' : 'course offering'} →`}
        </Button>
      </FieldGroup>
    </form>
  );
}
export function AccessForm({
  data,
  person,
  onSaved,
}: {
  data: Dashboard;
  person: Person;
  onSaved: () => void;
}) {
  const [scopeId, setScopeId] = useState(
    data.scopes.find((s) => s.kind === 'offering')?.id ?? data.scope_id,
  );
  const [kind, setKind] = useState('role');
  const [selection, setSelection] = useState('');
  const roles = data.roles.filter(
    (r) => r.scope_kind === data.scopes.find((s) => s.id === scopeId)?.kind,
  );
  const options =
    kind === 'role'
      ? roles.map((r) => ({ id: r.slug, label: r.name }))
      : data.capabilities.map((c) => ({ id: c, label: c }));
  const selected =
    options.find((o) => o.id === selection)?.id ?? options[0]?.id ?? '';
  const add = useMutation({ mutationFn: assignAccess, onSuccess: onSaved });
  const revoke = useMutation({
    mutationFn: ({ kind, id }: { kind: 'roles' | 'grants'; id: string }) =>
      revokeAccess(kind, id),
    onSuccess: onSaved,
  });
  const pending = add.isPending || revoke.isPending;
  const activate = useMutation({
    mutationFn: (password: string) => activateAccount(person.id, password),
    onSuccess: onSaved,
  });
  return (
    <div className="flex flex-col gap-6">
      {!person.is_active && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const password = new FormData(event.currentTarget).get(
              'activation-password',
            );
            if (typeof password === 'string') activate.mutate(password);
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="activation-password">
                Set password and activate
              </FieldLabel>
              <Input
                id="activation-password"
                name="activation-password"
                type="password"
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </Field>
            {activate.isError && <FormError error={activate.error} />}
            <Button disabled={activate.isPending}>
              {activate.isPending ? 'Activating…' : 'Activate account'}
            </Button>
          </FieldGroup>
        </form>
      )}
      <section
        className="flex flex-col gap-3"
        aria-labelledby="current-access-title"
      >
        <h3 id="current-access-title" className="font-medium">
          Current access
        </h3>
        {!person.roles.length && !person.grants.length && (
          <p className="text-sm text-muted-foreground">
            No access assigned. Add a role or capability below.
          </p>
        )}
        {[...person.roles, ...person.grants].map((a) => (
          <div className="flex items-center justify-between gap-4" key={a.id}>
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium">
                {a.role_id
                  ? data.roles.find((r) => r.slug === a.role_id)?.name
                  : a.capability_id}
              </p>
              <p className="text-xs text-muted-foreground">
                {data.scopes.find((s) => s.id === a.scope_id)?.label} ·{' '}
                {a.role_id ? 'Role' : 'Direct grant'}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={pending}
              onClick={() =>
                revoke.mutate({
                  kind: a.role_id ? 'roles' : 'grants',
                  id: a.id,
                })
              }
              aria-label={`Revoke ${a.role_id ?? a.capability_id} in ${data.scopes.find((s) => s.id === a.scope_id)?.label}`}
            >
              Revoke
            </Button>
          </div>
        ))}
      </section>
      <Separator />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate({
            user: person.id,
            scope: scopeId,
            ...(kind === 'role'
              ? { role: selected }
              : { capability: selected }),
          });
        }}
      >
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="access-scope">Scope</FieldLabel>
            <NativeSelect
              id="access-scope"
              value={scopeId}
              onChange={(e) => setScopeId(e.target.value)}
            >
              {data.scopes.map((s) => (
                <NativeSelectOption key={s.id} value={s.id}>
                  {s.label} · {s.kind}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>
          <Field>
            <FieldLabel htmlFor="access-type">Access type</FieldLabel>
            <NativeSelect
              id="access-type"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              <NativeSelectOption value="role">Role</NativeSelectOption>
              <NativeSelectOption value="capability">
                Direct capability
              </NativeSelectOption>
            </NativeSelect>
          </Field>
          <Field>
            <FieldLabel htmlFor="access-selection">
              {kind === 'role' ? 'Role' : 'Capability'}
            </FieldLabel>
            <NativeSelect
              id="access-selection"
              required
              value={selected}
              onChange={(e) => setSelection(e.target.value)}
            >
              {options.map((o) => (
                <NativeSelectOption key={o.id} value={o.id}>
                  {o.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            {kind === 'capability' && (
              <FieldDescription>
                A direct grant applies only to this capability in this exact
                scope.
              </FieldDescription>
            )}
          </Field>
          {(add.isError || revoke.isError) && (
            <FormError error={add.error ?? revoke.error} />
          )}
          <Button type="submit" disabled={pending || !selected}>
            {pending ? 'Updating access…' : 'Assign access →'}
          </Button>
        </FieldGroup>
      </form>
    </div>
  );
}
