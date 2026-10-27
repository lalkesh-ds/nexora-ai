import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Loader2, Zap } from 'lucide-react';

/**
 * AuthCallbackPage — handles the Supabase email verification redirect.
 * Supabase sends users to /auth/callback with tokens in the URL fragment.
 * The Supabase SDK parses these automatically via detectSessionInUrl.
 * We just wait for the session to be established, then redirect.
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session) {
        // Email successfully verified and signed in
        navigate('/workspace', { replace: true });
      } else if (event === 'PASSWORD_RECOVERY') {
        navigate('/reset-password', { replace: true });
      } else if (!session) {
        // No session established — link may have been invalid/expired
        navigate('/login?error=verification_failed', { replace: true });
      }
    });

    // Fallback timeout
    const fallback = setTimeout(() => {
      navigate('/login', { replace: true });
    }, 8000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(fallback);
    };
  }, [navigate]);

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
