'use client';

import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  AlertDescription,
  AlertTitle,
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
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
  Separator,
  Skeleton,
} from '@outcometrik/ui';
import { errorMessage, SessionMenu, useSession } from '@outcometrik/access';
import {
  createCatalogRecord,
  getCatalogRows,
  type CatalogResource,
  type CatalogRow,
} from './api';

type CatalogData = Record<CatalogResource, CatalogRow[]>;

const resources: { id: CatalogResource; label: string; description: string }[] =
  [
    {
      id: 'departments',
      label: 'Department',
      description: 'Add a department to the institution.',
    },
    {
      id: 'programs',
      label: 'Program',
      description: 'Create a program under a department.',
    },
    {
      id: 'terms',
      label: 'Academic term',
      description: 'Add a term for the institution.',
    },
    {
      id: 'courses',
      label: 'Course',
      description: 'Add a catalog course owned by a department.',
    },
    {
      id: 'program-courses',
      label: 'Program course',
      description: 'Approve a course for a program before opening an offering.',
    },
    {
      id: 'offerings',
      label: 'Course offering',
      description: 'Open a course section for a program and term.',
    },
    {
      id: 'program-memberships',
      label: 'Program membership',
      description: 'Register a student account in a program.',
    },
    {
      id: 'instructor-assignments',
      label: 'Instructor assignment',
      description: 'Assign an instructor account to an offering.',
    },
    {
      id: 'enrollments',
      label: 'Enrollment',
      description: 'Enroll an active student account in an offering.',
    },
  ];

function textValue(row: CatalogRow, ...keys: string[]) {
  return keys
    .map((key) => row[key])
    .filter((value) => value !== undefined && value !== '')
    .join(' · ');
}

function recordLabel(
  resource: CatalogResource,
  row: CatalogRow,
  data: CatalogData,
) {
  if (resource === 'program-courses') {
    const program = data.programs.find(
      (item) => item.id === String(row.program),
    );
    const course = data.courses.find((item) => item.id === String(row.course));
    return [
      textValue(program ?? ({} as CatalogRow), 'code', 'title'),
      textValue(course ?? ({} as CatalogRow), 'code', 'title'),
      row.status,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  if (resource === 'offerings') {
    const course = data.courses.find((item) => item.id === String(row.course));
    const term = data.terms.find((item) => item.id === String(row.term));
    return [
      textValue(course ?? ({} as CatalogRow), 'code', 'title'),
      row.section,
      textValue(term ?? ({} as CatalogRow), 'year', 'season'),
    ]
      .filter(Boolean)
      .join(' · ');
  }
  return textValue(row, 'code', 'name', 'title', 'year', 'season', 'status');
}

function optionsFor(resource: CatalogResource, data: CatalogData) {
  const getOptions = (
    key: CatalogResource,
    label: (row: CatalogRow) => string,
  ) => data[key].map((row) => ({ value: row.id, label: label(row) }));
  switch (resource) {
    case 'departments':
      return [
        {
          name: 'institution',
          label: 'Institution',
          options: [] as { value: string; label: string }[],
        },
      ];
    case 'programs':
      return [
        {
          name: 'department',
          label: 'Department',
          options: getOptions('departments', (row) =>
            textValue(row, 'code', 'name'),
          ),
        },
      ];
    case 'terms':
      return [
        {
          name: 'institution',
          label: 'Institution',
          options: [] as { value: string; label: string }[],
        },
      ];
    case 'courses':
      return [
        {
          name: 'home_department',
          label: 'Home department',
          options: getOptions('departments', (row) =>
            textValue(row, 'code', 'name'),
          ),
        },
      ];
    case 'program-courses':
      return [
        {
          name: 'program',
          label: 'Program',
          options: getOptions('programs', (row) =>
            textValue(row, 'code', 'title'),
          ),
        },
        {
          name: 'course',
          label: 'Course',
          options: getOptions('courses', (row) =>
            textValue(row, 'code', 'title'),
          ),
        },
      ];
    case 'offerings':
      return [
        {
          name: 'program',
          label: 'Program',
          options: getOptions('programs', (row) =>
            textValue(row, 'code', 'title'),
          ),
        },
        {
          name: 'course',
          label: 'Course',
          options: getOptions('courses', (row) =>
            textValue(row, 'code', 'title'),
          ),
        },
        {
          name: 'term',
          label: 'Term',
          options: getOptions('terms', (row) =>
            textValue(row, 'year', 'season'),
          ),
        },
      ];
    case 'program-memberships':
      return [
        {
          name: 'program',
          label: 'Program',
          options: getOptions('programs', (row) =>
            textValue(row, 'code', 'title'),
          ),
        },
        {
          name: 'admitted_term',
          label: 'Admitted term (optional)',
          options: getOptions('terms', (row) =>
            textValue(row, 'year', 'season'),
          ),
          optional: true,
        },
      ];
    case 'instructor-assignments':
      return [
        {
          name: 'offering',
          label: 'Offering',
          options: getOptions('offerings', (row) =>
            textValue(row, 'section', 'id'),
          ),
        },
      ];
    case 'enrollments':
      return [
        {
          name: 'offering',
          label: 'Offering',
          options: getOptions('offerings', (row) =>
            textValue(row, 'section', 'id'),
          ),
        },
      ];
  }
}

function fieldsFor(resource: CatalogResource) {
  switch (resource) {
    case 'departments':
      return [
        ['code', 'Department code', 'text'],
        ['name', 'Department name', 'text'],
      ];
    case 'programs':
      return [
        ['code', 'Program code', 'text'],
        ['title', 'Program title', 'text'],
      ];
    case 'terms':
      return [
        ['year', 'Year', 'number'],
        ['season', 'Season', 'select:season'],
        ['starts_at', 'Starts on', 'date'],
        ['ends_at', 'Ends on', 'date'],
      ];
    case 'courses':
      return [
        ['code', 'Course code', 'text'],
        ['title', 'Course title', 'text'],
        ['ects', 'ECTS', 'number'],
        ['credits', 'Credits', 'number'],
      ];
    case 'program-courses':
      return [
        ['effective_from', 'Effective from', 'date'],
        ['effective_to', 'Effective to (optional)', 'date:optional'],
        ['status', 'Association status', 'select:association'],
      ];
    case 'offerings':
      return [
        ['section', 'Section', 'text'],
        ['status', 'Offering status', 'select:offering'],
      ];
    case 'program-memberships':
      return [
        ['user', 'Student account ID', 'number'],
        ['student_number', 'Student number', 'text'],
        ['status', 'Membership status', 'select:membership'],
      ];
    case 'instructor-assignments':
      return [
        ['user', 'Instructor account ID', 'number'],
        ['assignment_role', 'Assignment role', 'select:assignment'],
      ];
    case 'enrollments':
      return [
        ['student', 'Student account ID', 'number'],
        ['attempt_number', 'Attempt number', 'number'],
        ['status', 'Enrollment status', 'select:enrollment'],
      ];
  }
}

const selectValues: Record<string, { value: string; label: string }[]> = {
  season: ['fall', 'spring', 'summer'].map((value) => ({
    value,
    label: value[0].toUpperCase() + value.slice(1),
  })),
  association: [
    { value: 'approved', label: 'Approved' },
    { value: 'proposed', label: 'Proposed' },
  ],
  offering: [{ value: 'active', label: 'Active' }],
  membership: ['active', 'inactive', 'graduated'].map((value) => ({
    value,
    label: value[0].toUpperCase() + value.slice(1),
  })),
  assignment: [
    { value: 'instructor', label: 'Instructor' },
    { value: 'assistant', label: 'Assistant' },
  ],
  enrollment: ['enrolled', 'completed', 'withdrawn', 'incomplete'].map(
    (value) => ({ value, label: value[0].toUpperCase() + value.slice(1) }),
  ),
};

function defaultFor(resource: CatalogResource, name: string) {
  if (name === 'season') return 'fall';
  if (resource === 'program-courses' && name === 'status') return 'approved';
  if (resource === 'offerings' && name === 'status') return 'active';
  if (resource === 'program-memberships' && name === 'status') return 'active';
  if (resource === 'instructor-assignments' && name === 'assignment_role')
    return 'instructor';
  if (resource === 'enrollments' && name === 'status') return 'enrolled';
  return '';
}

function RecordForm({
  resource,
  institutionId,
  data,
  onSaved,
}: {
  resource: CatalogResource;
  institutionId: string;
  data: CatalogData;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (body: Record<string, string | number>) =>
      createCatalogRecord(resource, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['academic-catalog'] });
      onSaved();
    },
  });
  const optionFields = optionsFor(resource, data);
  const fields = fieldsFor(resource);
  const selected = resources.find((item) => item.id === resource);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body: Record<string, string | number> = {};
    for (const [name, value] of form.entries()) {
      if (typeof value !== 'string' || value === '') continue;
      body[name] = [
        'year',
        'ects',
        'credits',
        'user',
        'attempt_number',
      ].includes(name)
        ? Number(value)
        : value;
    }
    if (['departments', 'terms'].includes(resource))
      body.institution = institutionId;
    create.mutate(body);
  }

  return (
    <form onSubmit={submit}>
      <FieldGroup>
        <p className="text-sm text-muted-foreground">{selected?.description}</p>
        {optionFields.map((field) => (
          <Field key={field.name}>
            <FieldLabel htmlFor={`catalog-${field.name}`}>
              {field.label}
            </FieldLabel>
            {field.options.length === 0 &&
            ['institution'].includes(field.name) ? (
              <Input
                id={`catalog-${field.name}`}
                value={institutionId}
                readOnly
              />
            ) : (
              <NativeSelect
                id={`catalog-${field.name}`}
                name={field.name}
                required={!(field as { optional?: boolean }).optional}
                defaultValue=""
              >
                <NativeSelectOption value="">
                  Choose {field.label.toLowerCase()}
                </NativeSelectOption>
                {field.options.map((option) => (
                  <NativeSelectOption key={option.value} value={option.value}>
                    {option.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            )}
          </Field>
        ))}
        {fields.map(([name, label, type]) => {
          const isSelect = type.startsWith('select:');
          const selectKey = type.split(':')[1];
          return (
            <Field key={name}>
              <FieldLabel htmlFor={`catalog-${name}`}>{label}</FieldLabel>
              {isSelect ? (
                <NativeSelect
                  id={`catalog-${name}`}
                  name={name}
                  required
                  defaultValue={defaultFor(resource, name)}
                >
                  {selectValues[selectKey].map((option) => (
                    <NativeSelectOption key={option.value} value={option.value}>
                      {option.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              ) : (
                <Input
                  id={`catalog-${name}`}
                  name={name}
                  type={type.replace(':optional', '')}
                  min={type === 'number' ? 1 : undefined}
                  required={!type.endsWith(':optional')}
                />
              )}
              {name === 'user' || name === 'student' ? (
                <FieldDescription>
                  Use the account ID shown by the account creation response.
                </FieldDescription>
              ) : null}
            </Field>
          );
        })}
        {create.isError && (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Unable to create record</AlertTitle>
            <AlertDescription>{errorMessage(create.error)}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={create.isPending}>
          {create.isPending
            ? 'Saving…'
            : `Create ${selected?.label.toLowerCase()}`}
        </Button>
      </FieldGroup>
    </form>
  );
}

export function AcademicCatalogDashboard() {
  const session = useSession();
  const [institutionId, setInstitutionId] = useState('');
  const [resource, setResource] = useState<CatalogResource>('departments');
  const [notice, setNotice] = useState('');
  const institutions =
    session.data?.scopes.filter((scope) => scope.kind === 'institution') ?? [];
  const selectedInstitution =
    institutions.find((scope) => scope.id === institutionId) ?? institutions[0];
  const isAdministrator = Boolean(
    session.data?.roles.some(
      (assignment) =>
        assignment.role === 'administrator' &&
        assignment.scope.kind === 'institution',
    ),
  );
  const catalog = useQuery({
    queryKey: ['academic-catalog', selectedInstitution?.id],
    enabled: Boolean(selectedInstitution && isAdministrator),
    queryFn: async ({ signal }) => {
      const institution = selectedInstitution?.id;
      if (!institution) return {} as CatalogData;
      const [
        departments,
        allPrograms,
        terms,
        allCourses,
        allProgramCourses,
        allOfferings,
      ] = await Promise.all([
        getCatalogRows('departments', { institution }, signal),
        getCatalogRows('programs', {}, signal),
        getCatalogRows('terms', { institution }, signal),
        getCatalogRows('courses', {}, signal),
        getCatalogRows('program-courses', {}, signal),
        getCatalogRows('offerings', {}, signal),
      ]);
      const departmentIds = new Set(departments.map((row) => row.id));
      const programs = allPrograms.filter((row) =>
        departmentIds.has(String(row.department)),
      );
      const programIds = new Set(programs.map((row) => row.id));
      const courses = allCourses.filter((row) =>
        departmentIds.has(String(row.home_department)),
      );
      const offerings = allOfferings.filter((row) =>
        programIds.has(String(row.program)),
      );
      const scopedProgramCourses = allProgramCourses.filter((row) =>
        programIds.has(String(row.program)),
      );
      return {
        departments,
        programs,
        terms,
        courses,
        'program-courses': scopedProgramCourses,
        offerings,
        'program-memberships': [],
        'instructor-assignments': [],
        enrollments: [],
      };
    },
  });

  if (session.isPending)
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-8" role="status">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-72 w-full" />
      </main>
    );
  if (session.isError)
    return (
      <main className="mx-auto max-w-3xl p-8">
        <Alert variant="destructive" role="alert">
          <AlertTitle>Unable to verify access</AlertTitle>
          <AlertDescription>{errorMessage(session.error)}</AlertDescription>
        </Alert>
      </main>
    );
  if (!session.data?.user)
    return (
      <main className="mx-auto max-w-3xl p-8">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>Sign in to manage academic structure</EmptyTitle>
            <EmptyDescription>
              <a href="/login">Go to sign in →</a>
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </main>
    );
  if (!isAdministrator || !selectedInstitution)
    return (
      <main className="mx-auto max-w-3xl p-8">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>Institution administrator access required</EmptyTitle>
            <EmptyDescription>
              This setup workspace is limited to institution administrators.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </main>
    );

  const data = catalog.data;
  return (
    <main className="mx-auto flex min-h-svh max-w-6xl flex-col gap-6 p-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Institution setup</p>
          <h1 className="text-3xl font-semibold">Academic structure</h1>
        </div>
        <SessionMenu />
      </header>
      <Button asChild variant="outline" className="self-start">
        <a href="/admin">Back to institution dashboard</a>
      </Button>
      {institutions.length > 1 && (
        <Field>
          <FieldLabel htmlFor="catalog-institution">Institution</FieldLabel>
          <NativeSelect
            id="catalog-institution"
            value={selectedInstitution.id}
            onChange={(event) => setInstitutionId(event.target.value)}
          >
            {institutions.map((institution) => (
              <NativeSelectOption key={institution.id} value={institution.id}>
                {institution.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
      )}
      {notice && (
        <Alert role="status">
          <AlertTitle>Record created</AlertTitle>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {catalog.isPending ? (
        <div className="space-y-4" role="status">
          <span className="sr-only">Loading academic records…</span>
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : catalog.isError ? (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Unable to load academic records</AlertTitle>
          <AlertDescription>
            {errorMessage(catalog.error)}
            <Button
              variant="outline"
              className="mt-3"
              onClick={() => void catalog.refetch()}
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : data ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <Card>
            <CardHeader>
              <CardTitle>Create academic record</CardTitle>
              <CardDescription>
                Build the catalog in order. A program course must be approved
                before you can create its offering.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field>
                <FieldLabel htmlFor="catalog-resource">Record type</FieldLabel>
                <NativeSelect
                  id="catalog-resource"
                  value={resource}
                  onChange={(event) =>
                    setResource(event.target.value as CatalogResource)
                  }
                >
                  {resources.map((item) => (
                    <NativeSelectOption key={item.id} value={item.id}>
                      {item.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <Separator />
              <RecordForm
                key={`${selectedInstitution.id}-${resource}`}
                resource={resource}
                institutionId={selectedInstitution.id}
                data={data}
                onSaved={() =>
                  setNotice(
                    `${resources.find((item) => item.id === resource)?.label} saved. Related records refreshed.`,
                  )
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Setup progress</CardTitle>
              <CardDescription>
                Records visible in this institution’s authorized scopes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {resources.slice(0, 6).map((item) => (
                <section
                  key={item.id}
                  aria-labelledby={`catalog-list-${item.id}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3
                      id={`catalog-list-${item.id}`}
                      className="text-sm font-medium"
                    >
                      {item.label}
                    </h3>
                    <Badge variant="outline">{data[item.id].length}</Badge>
                  </div>
                  {data[item.id].length ? (
                    <ul className="mt-2 max-h-36 space-y-1 overflow-y-auto text-sm text-muted-foreground">
                      {data[item.id].map((row) => (
                        <li key={row.id} className="truncate">
                          {recordLabel(item.id, row, data)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-sm text-muted-foreground">
                      No records yet.
                    </p>
                  )}
                </section>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : null}
      <p className="text-sm text-muted-foreground">
        Student and instructor accounts are created in People & access. Copy the
        account ID from the creation response when adding memberships,
        assignments, or enrollments here.
      </p>
    </main>
  );
}
