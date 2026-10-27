import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Loader2, Zap, AlertCircle } from 'lucide-react';

/**
 * AuthCallbackPage — handles Supabase email verification and password-reset redirects.
 *
 * Supabase supports two callback mechanisms:
 *   1. PKCE flow  — URL contains ?code=<code> query param (default for modern Supabase)
 *      → We call supabase.auth.exchangeCodeForSession() explicitly.
 *   2. Implicit flow — URL fragment contains #access_token=...&type=signup
 *      → The Supabase SDK parses these automatically via detectSessionInUrl: true.
 *
 * We handle BOTH so the page works regardless of which flow Supabase uses for the project.
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function handleCallback() {
      const url = new URL(window.location.href);
      const code = url.searchParams.get('code');
      const errorParam = url.searchParams.get('error');
      const errorDescription = url.searchParams.get('error_description');

      // Supabase error passed as query param (e.g. expired link)
      if (errorParam) {
        if (isMounted) setError(errorDescription || errorParam);
        setTimeout(() => {
          if (isMounted) navigate('/login?error=verification_failed', { replace: true });
        }, 3000);
        return;
      }

      // ── PKCE flow: exchange the one-time code for a session ──────────────
      if (code) {
        const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);

        if (!isMounted) return;

        if (exchangeError) {
          setError(exchangeError.message);
          setTimeout(() => {
            if (isMounted) navigate('/login?error=verification_failed', { replace: true });
          }, 3000);
          return;
        }

        if (data?.session) {
          // Check if this is a password-recovery token
          if (data.session.user?.recovery_sent_at) {
            navigate('/reset-password', { replace: true });
          } else {
            navigate('/workspace', { replace: true });
          }
          return;
        }
      }

      // ── Implicit flow: SDK already parsed the hash; wait for auth event ──
      const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
        if (!isMounted) return;

        if (event === 'SIGNED_IN' && session) {
          navigate('/workspace', { replace: true });
        } else if (event === 'PASSWORD_RECOVERY') {
          navigate('/reset-password', { replace: true });
        }
        // Don't redirect on initial null session — SDK may still be processing the hash
      });

      // Fallback: if neither flow triggers within 8 s, go to login
      const fallback = setTimeout(() => {
        if (isMounted) navigate('/login', { replace: true });
      }, 8000);

      return () => {
        subscription.unsubscribe();
        clearTimeout(fallback);
      };
    }

    const cleanup = handleCallback();

    return () => {
      isMounted = false;
      // handleCallback may return a cleanup fn asynchronously
      cleanup?.then?.(fn => fn?.());
    };
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-[#070709] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-sm text-center px-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-red-400" />
          </div>
          <p className="text-zinc-300 text-sm font-medium">Verification failed</p>
          <p className="text-zinc-500 text-xs">{error}</p>
          <p className="text-zinc-600 text-xs">Redirecting to login…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070709] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
          <Zap className="w-5 h-5 text-cyan-400" />
        </div>
        <div className="w-6 h-6 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
        <p className="text-zinc-500 text-sm">Verifying your account…</p>
      </div>
    </div>
  );
}
