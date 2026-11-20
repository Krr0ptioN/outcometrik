export { SignIn, SessionMenu, useSession, type SignInProps } from './features/session/components';
export { defaultDashboard, errorMessage } from './features/session/api';
export type { Session, Scope, User } from './features/session/api';
export {
  DEMO_PERSONAS,
  isDemoPersonasEnabled,
  getDemoPersonaPassword,
  validateSignInFields,
  type DemoPersona,
  type DemoPersonaEnv,
  type SignInValidationErrors,
} from './features/session/personas';
export {
  hasWorkspaceAccess,
  getUnauthorizedRedirect,
  resolvePostLoginRedirect,
  isSafeInternalPath,
  formatShellUser,
  type WorkspaceRole,
} from './features/session/role-access';
export {
  RoleWorkspaceShell,
  type RoleWorkspaceShellProps,
} from './features/session/role-shell';
export { AdminDashboard } from './features/administration/components';
export { CoordinatorDashboard } from './features/coordinator/components';
