'use client';
import { useRouter } from 'next/navigation';
import { defaultDashboard, SignIn } from '@outcometrik/access';
export default function LoginPage() {
  const router = useRouter();
  return (
    <SignIn
      onSignedIn={(session) => {
        router.replace(
          defaultDashboard(session),
        );
        router.refresh();
      }}
    />
  );
}
