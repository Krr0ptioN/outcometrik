'use client';
import { defaultDashboard, SignIn } from '@outcometrik/access';

export default function LoginPage() {
  return (
    <SignIn
      onSignedIn={(session) => {
        window.location.replace(defaultDashboard(session));
      }}
    />
  );
}
