export interface DemoPersona {
  id: 'admin' | 'coordinator' | 'instructor' | 'student';
  name: string;
  roleLabel: string;
  summary: string;
  username: string;
  targetPath: '/admin' | '/coordinator' | '/instructor' | '/student';
}

export const DEMO_PERSONAS: readonly DemoPersona[] = [
  {
    id: 'admin',
    name: 'System Admin',
    roleLabel: 'Administrator',
    summary: 'Roles, direct grants & catalog',
    username: 'admin@acibadem.edu.tr',
    targetPath: '/admin',
  },
  {
    id: 'coordinator',
    name: 'Prof. Emre Karahan',
    roleLabel: 'Coordinator',
    summary: 'Cohort analytics & publish',
    username: 'emre.karahan@acibadem.edu.tr',
    targetPath: '/coordinator',
  },
  {
    id: 'instructor',
    name: 'Dr. Selin Kaya',
    roleLabel: 'Instructor',
    summary: 'Mapping studio & gradebook',
    username: 'selin.kaya@acibadem.edu.tr',
    targetPath: '/instructor',
  },
  {
    id: 'student',
    name: 'Deniz Aydın',
    roleLabel: 'Student',
    summary: 'PO1–PO11 attainment profile',
    username: 'deniz.aydin@live.acibadem.edu.tr',
    targetPath: '/student',
  },
] as const;

export interface DemoPersonaEnv {
  nodeEnv?: string;
  enableDemoPersonas?: string;
}

/**
 * Strictly gates the Quick Seeded Persona Switcher so it never ships to
 * production unless explicitly enabled via NEXT_PUBLIC_ENABLE_DEMO_PERSONAS=true.
 */
export function isDemoPersonasEnabled(env?: DemoPersonaEnv): boolean {
  const enableFlag =
    env !== undefined
      ? env.enableDemoPersonas
      : process.env.NEXT_PUBLIC_ENABLE_DEMO_PERSONAS;
  const nodeEnv = env !== undefined ? env.nodeEnv : process.env.NODE_ENV;

  if (enableFlag === 'true') return true;
  if (enableFlag === 'false') return false;
  return nodeEnv !== 'production';
}

export function getDemoPersonaPassword(
  override?: string,
  envPassword: string | undefined = process.env.NEXT_PUBLIC_DEMO_SEED_PASSWORD,
): string {
  const typed = override?.trim();
  if (typed) return typed;
  const configured = envPassword?.trim();
  if (configured) return configured;
  return 'choose-a-local-demo-password';
}

export interface SignInValidationErrors {
  username?: string;
  password?: string;
}

export function validateSignInFields(
  username: string,
  password: string,
): SignInValidationErrors {
  const errors: SignInValidationErrors = {};
  const trimmedUsername = username.trim();

  if (!trimmedUsername) {
    errors.username = 'Enter your institutional email or username.';
  } else if (trimmedUsername.length > 150) {
    errors.username = 'Username must be 150 characters or fewer.';
  }

  if (!password) {
    errors.password = 'Enter your password.';
  } else if (password.length > 1024) {
    errors.password = 'Password exceeds the maximum allowed length.';
  }

  return errors;
}
