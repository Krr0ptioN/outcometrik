'use client';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { request } from '@outcometrik/api';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
} from '@outcometrik/ui';
import { SessionMenu, useSession } from '../session/components';

type Scope = {
  id: string;
  kind: string;
  label: string;
  parent_id: string | null;
};
type Data = {
  programs: Scope[];
  offerings: Scope[];
  people: {
    id: number;
    username: string;
    email: string;
    role: string;
    offering_id: string;
    is_active: boolean;
  }[];
};
async function load(): Promise<Data> {
  return request('/api/access/coordinator/');
}
export function CoordinatorDashboard() {
  const session = useSession();
  const query = useQuery({ queryKey: ['coordinator'], queryFn: load });
  const client = useQueryClient();
  const [offer, setOffer] = useState('');
  const [role, setRole] = useState('student');
  const create = useMutation({
    mutationFn: (body: object) =>
      request('/api/access/coordinator/accounts/', { method: 'POST', body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['coordinator'] });
    },
  });
  if (session.isPending || query.isPending)
    return (
      <main className="p-8" role="status">
        Loading coordinator workspace…
      </main>
    );
  if (!session.data?.user || query.isError)
    return (
      <main className="p-8">
        <h1>Coordinator access required</h1>
        <a href="/login">Sign in</a>
      </main>
    );
  const data = query.data;
  const offerings = data.offerings;
  const offeringId = offerings.some((o) => o.id === offer)
    ? offer
    : (offerings[0]?.id ?? '');
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Program workspace</p>
          <h1 className="text-3xl font-semibold">Coordinator dashboard</h1>
        </div>
        <SessionMenu />
      </header>
      {data.programs.map((p) => (
        <Card key={p.id}>
          <CardHeader>
            <CardTitle>{p.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3">
              {offerings
                .filter((o) => o.parent_id === p.id)
                .map((o) => (
                  <section key={o.id}>
                    <h2 className="font-medium">{o.label}</h2>
                    <ul>
                      {data.people
                        .filter((u) => u.offering_id === o.id)
                        .map((u) => (
                          <li key={u.id}>
                            {u.username} ·{' '}
                            {u.role === 'instructor' ? 'Instructor' : 'Student'}{' '}
                            · {u.is_active ? 'Active' : 'Pending'}
                          </li>
                        ))}
                    </ul>
                  </section>
                ))}
            </div>
          </CardContent>
        </Card>
      ))}
      <Card>
        <CardHeader>
          <CardTitle>Create an account</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              create.mutate({
                username: f.get('username'),
                email: f.get('email'),
                first_name: f.get('first_name'),
                last_name: f.get('last_name'),
                scope: offeringId,
                role,
              });
              e.currentTarget.reset();
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="coord-name">Username</FieldLabel>
                <Input id="coord-name" name="username" required />
              </Field>
              <Field>
                <FieldLabel htmlFor="coord-email">Email</FieldLabel>
                <Input id="coord-email" name="email" type="email" required />
              </Field>
              <Field>
                <FieldLabel htmlFor="coord-first">First name</FieldLabel>
                <Input id="coord-first" name="first_name" />
              </Field>
              <Field>
                <FieldLabel htmlFor="coord-last">Last name</FieldLabel>
                <Input id="coord-last" name="last_name" />
              </Field>
              <Field>
                <FieldLabel htmlFor="coord-offering">Offering</FieldLabel>
                <NativeSelect
                  id="coord-offering"
                  value={offeringId}
                  onChange={(e) => setOffer(e.target.value)}
                >
                  {offerings.map((o) => (
                    <NativeSelectOption key={o.id} value={o.id}>
                      {o.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <Field>
                <FieldLabel htmlFor="coord-role">Role</FieldLabel>
                <NativeSelect
                  id="coord-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <NativeSelectOption value="student">
                    Student
                  </NativeSelectOption>
                  <NativeSelectOption value="instructor">
                    Instructor
                  </NativeSelectOption>
                </NativeSelect>
              </Field>
              {create.isError && (
                <p role="alert">
                  Could not create account. Check for a duplicate username.
                </p>
              )}
              <Button disabled={!offeringId || create.isPending}>
                Create pending account
              </Button>
              <p className="text-sm text-muted-foreground">
                An institution administrator must set a password and activate
                the account.
              </p>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
