import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Zap, Loader2, AlertCircle, CheckCircle2, Check } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

function PasswordStrength({ password }) {
  const checks = [
    { label: 'At least 8 characters', ok: password.length >= 8 },
    { label: 'Contains a number', ok: /\d/.test(password) },
    { label: 'Contains a letter', ok: /[a-zA-Z]/.test(password) },
  ];
  if (!password) return null;
  return (
    <ul className="space-y-1 mt-2">
      {checks.map(c => (
        <li key={c.label} className={`flex items-center gap-1.5 text-xs ${c.ok ? 'text-emerald-400' : 'text-zinc-500'}`}>
          <Check className={`w-3 h-3 ${c.ok ? 'opacity-100' : 'opacity-30'}`} />
          {c.label}
        </li>
      ))}
    </ul>
  );
}

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const { resetPassword, session } = useAuth();

  const [form, setForm] = useState({ password: '', confirm: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | loading | success | error | invalid
  const [errorMsg, setErrorMsg] = useState('');

  // Supabase injects the recovery tokens into the URL on redirect
  // The official SDK's onAuthStateChange fires PASSWORD_RECOVERY event
  useEffect(() => {
    if (!session) {
      // If no active session at all, wait briefly then show invalid state
      const t = setTimeout(() => setStatus('invalid'), 2000);
      return () => clearTimeout(t);
    }
  }, [session]);

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setErrorMsg('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.password.length < 8) {
      setErrorMsg('Password must be at least 8 characters.'); return;
    }
    if (form.password !== form.confirm) {
      setErrorMsg('Passwords do not match.'); return;
    }
    setStatus('loading');
    setErrorMsg('');

    const { error } = await resetPassword(form.password);
    if (error) {
      if (error.message?.toLowerCase().includes('expired') ||
          error.message?.toLowerCase().includes('invalid')) {
        setStatus('invalid');
      } else {
        setErrorMsg(error.message || 'Failed to reset password. Please try again.');
        setStatus('idle');
      }
      return;
    }

    setStatus('success');
    setTimeout(() => navigate('/login'), 3000);
  };

  if (status === 'invalid') {
    return (
      <div className="min-h-screen bg-[#070709] flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-zinc-50 mb-2">Link expired or invalid</h1>
          <p className="text-zinc-500 text-sm mb-6">
            This password reset link has expired or already been used. Please request a new one.
          </p>
          <Link to="/forgot-password" className="text-cyan-500 hover:text-cyan-400 text-sm transition-colors">
            Request a new reset link
          </Link>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen bg-[#070709] flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-5">
            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
          </div>
          <h1 className="text-xl font-semibold text-zinc-50 mb-2">Password updated</h1>
          <p className="text-zinc-400 text-sm mb-4">Your password has been changed successfully.</p>
          <p className="text-zinc-600 text-xs">Redirecting to sign in…</p>
        </div>
      </div>
    );
  }

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

        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-1">Set new password</h1>
          <p className="text-zinc-500 text-sm">Choose a strong password for your account.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {errorMsg && (
            <div className="flex items-start gap-2.5 bg-red-500/8 border border-red-500/20 rounded-lg px-3.5 py-3 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">New password</label>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={form.password}
                onChange={handleChange}
                placeholder="Min. 8 characters"
                className="w-full bg-white/4 border border-white/8 rounded-lg px-3.5 py-2.5 pr-10 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
              />
              <button type="button" onClick={() => setShowPassword(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <PasswordStrength password={form.password} />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirm" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Confirm password</label>
            <div className="relative">
              <input
                id="confirm"
                name="confirm"
                type={showConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={form.confirm}
                onChange={handleChange}
                placeholder="Re-enter password"
                className={`w-full bg-white/4 border rounded-lg px-3.5 py-2.5 pr-10 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 transition-all ${
                  form.confirm && form.password !== form.confirm
                    ? 'border-red-500/40 focus:ring-red-500/40'
                    : 'border-white/8 focus:ring-cyan-500/50 focus:border-cyan-500/50'
                }`}
              />
              <button type="button" onClick={() => setShowConfirm(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors">
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={status === 'loading'}
            className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-950 font-semibold text-sm rounded-lg py-2.5 transition-all mt-2"
          >
            {status === 'loading' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Updating…</>
            ) : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  );
}
