'use client';
import { useRouter } from 'next/navigation';
import { SignIn } from '@outcometrik/access';
export default function LoginPage() {
  const router = useRouter();
  return (
    <SignIn
      onSignedIn={(session) => {
        router.replace(
          session.scopes.some((s) => s.kind === 'institution')
            ? '/admin'
            : session.scopes.some((s) => s.kind === 'program')
              ? '/coordinator'
              : '/',
        );
        router.refresh();
      }}
    />
  );
}
