import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Zap, Loader2, AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function ForgotPasswordPage() {
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) { setErrorMsg('Please enter your email address.'); return; }
    setStatus('loading');
    setErrorMsg('');

    const { error } = await forgotPassword(email);
    if (error) {
      // Never reveal if email exists — show generic message
      setStatus('success');
      return;
    }
    setStatus('success');
  };

  return (
    <div className="min-h-screen bg-[#070709] flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(6,182,212,0.04)_0%,_transparent_70%)] pointer-events-none" />

      <div className="w-full max-w-sm relative">
        {/* Logo */}
        <div className="flex items-center gap-2.5 mb-10">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-zinc-100 font-semibold tracking-tight">Nexora AI</span>
        </div>

        {status === 'success' ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-5">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-2">Check your inbox</h1>
            <p className="text-zinc-400 text-sm leading-relaxed mb-6">
              If an account exists for <span className="text-zinc-200">{email}</span>, you'll receive a password reset link shortly.
            </p>
            <p className="text-zinc-600 text-xs mb-6">Check your spam folder if you don't see it within a few minutes.</p>
            <Link to="/login" className="inline-flex items-center gap-1.5 text-cyan-500 hover:text-cyan-400 text-sm transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <div className="mb-8">
              <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-1">Reset password</h1>
              <p className="text-zinc-500 text-sm">Enter your email and we'll send you a reset link.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {errorMsg && (
                <div className="flex items-start gap-2.5 bg-red-500/8 border border-red-500/20 rounded-lg px-3.5 py-3 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="email" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Email</label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={e => { setEmail(e.target.value); setErrorMsg(''); }}
                  placeholder="you@example.com"
                  className="w-full bg-white/4 border border-white/8 rounded-lg px-3.5 py-2.5 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-950 font-semibold text-sm rounded-lg py-2.5 transition-all"
              >
                {status === 'loading' ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Sending…</>
                ) : (
                  'Send reset link'
                )}
              </button>
            </form>

            <p className="text-center mt-6">
              <Link to="/login" className="inline-flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 text-sm transition-colors">
                <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
