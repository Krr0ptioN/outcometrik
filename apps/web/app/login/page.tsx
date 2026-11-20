'use client';

import { useEffect, useState } from 'react';
import { resolvePostLoginRedirect, SignIn } from '@outcometrik/access';

export default function LoginPage() {
  const [nextPath, setNextPath] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(params.get('next'));
    if (params.get('unauthorized') === '1') {
      setNotice(
        'Your account does not have permission for that workspace. Sign in with an authorized account.',
      );
    }
  }, []);

  return (
    <SignIn
      notice={notice}
      onSignedIn={(session) => {
        window.location.replace(resolvePostLoginRedirect(session, nextPath));
      }}
    />
  );
}
