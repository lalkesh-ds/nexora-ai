import React, { useState } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Zap, Mail, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function VerifyEmailPage() {
  const location = useLocation();
  const email = location.state?.email || '';
  const { resendVerification } = useAuth();

  const [status, setStatus] = useState('idle'); // idle | sending | sent | error
  const [cooldown, setCooldown] = useState(0);

  const handleResend = async () => {
    if (!email || cooldown > 0) return;
    setStatus('sending');

    const { error } = await resendVerification(email);
    if (error) {
      setStatus('error');
      return;
    }

    setStatus('sent');
    // 60 second cooldown
    let secs = 60;
    setCooldown(secs);
    const timer = setInterval(() => {
      secs -= 1;
      setCooldown(secs);
      if (secs <= 0) {
        clearInterval(timer);
        setStatus('idle');
      }
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-[#070709] flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(6,182,212,0.04)_0%,_transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-sm relative text-center">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-10">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-zinc-100 font-semibold tracking-tight">Nexora AI</span>
        </div>

        <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-6">
          <Mail className="w-8 h-8 text-cyan-400" />
        </div>

        <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-2">Check your email</h1>
        <p className="text-zinc-400 text-sm leading-relaxed mb-1">
          We sent a verification link to
        </p>
        {email && (
          <p className="text-zinc-200 text-sm font-medium mb-4">{email}</p>
        )}
        <p className="text-zinc-500 text-sm leading-relaxed mb-8">
          Click the link in your email to verify your account. You may need to check your spam folder.
        </p>

        {/* Resend */}
        <div className="space-y-3">
          {status === 'sent' && (
            <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm bg-emerald-500/8 border border-emerald-500/20 rounded-lg py-2.5 px-4">
              <CheckCircle2 className="w-4 h-4" />
              Verification email resent.
            </div>
          )}
          {status === 'error' && (
            <div className="flex items-center justify-center gap-2 text-red-400 text-sm bg-red-500/8 border border-red-500/20 rounded-lg py-2.5 px-4">
              <AlertCircle className="w-4 h-4" />
              Failed to resend. Please try again.
            </div>
          )}

          <button
            onClick={handleResend}
            disabled={!email || status === 'sending' || cooldown > 0}
            className="w-full flex items-center justify-center gap-2 border border-white/10 hover:border-white/20 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 hover:text-zinc-100 text-sm rounded-lg py-2.5 transition-all bg-white/4 hover:bg-white/6"
          >
            {status === 'sending' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Sending…</>
            ) : cooldown > 0 ? (
              `Resend in ${cooldown}s`
            ) : (
              'Resend verification email'
            )}
          </button>

          <Link
            to="/login"
            className="block text-center text-zinc-500 hover:text-zinc-300 text-sm transition-colors py-1"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
