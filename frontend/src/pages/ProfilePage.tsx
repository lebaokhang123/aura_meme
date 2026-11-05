import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, errorMessage } from '../api';

interface PublicProfile { username: string; display_name: string; bio: string | null; avatar_url: string | null }
export function ProfilePage() {
  const { username } = useParams();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const abort = new AbortController();
    setProfile(null); setError('');
    api<PublicProfile>('/users/' + encodeURIComponent(username ?? ''), { signal: abort.signal })
      .then(value => { if (!abort.signal.aborted) setProfile(value); })
      .catch(fault => { if (!abort.signal.aborted) setError(errorMessage(fault)); });
    return () => abort.abort();
  }, [username]);
  return <section className="w-full max-w-2xl mx-auto px-4 py-10">
    <h1 className="text-3xl font-bold break-words">{profile?.display_name ?? 'Public profile'}</h1>
    {error ? <p role="alert" className="mt-4">{error}</p> : !profile ? <p role="status">Loading profile…</p> : <>
      <div aria-hidden="true" className="mt-6 w-24 h-24 grid place-items-center rounded-full bg-primary text-on-primary text-3xl">{profile.display_name.slice(0, 1)}</div>
      <p className="mt-4 text-secondary">@{profile.username}</p>
      <p className="mt-4 whitespace-pre-wrap break-words">{profile.bio || 'No bio yet.'}</p>
    </>}
  </section>;
}
