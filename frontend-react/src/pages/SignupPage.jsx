import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Zap, ArrowRight, Loader2, AlertCircle, Check } from 'lucide-react';
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

export default function SignupPage() {
  const navigate = useNavigate();
  const { signUp } = useAuth();

  const [form, setForm] = useState({ fullName: '', email: '', password: '', confirmPassword: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const validate = () => {
    if (!form.fullName.trim()) return 'Full name is required.';
    if (!form.email) return 'Email is required.';
    if (form.password.length < 8) return 'Password must be at least 8 characters.';
    if (form.password !== form.confirmPassword) return 'Passwords do not match.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) { setError(validationError); return; }

    setLoading(true);
    setError('');

    const { data, error: signUpError } = await signUp({
      email: form.email,
      password: form.password,
      fullName: form.fullName.trim(),
    });
    setLoading(false);

    if (signUpError) {
      // Don't reveal if email already exists
      if (signUpError.message?.toLowerCase().includes('already registered') ||
          signUpError.message?.toLowerCase().includes('already exists')) {
        navigate('/verify-email', { state: { email: form.email } });
        return;
      }
      setError(signUpError.message || 'Sign up failed. Please try again.');
      return;
    }

    // If user was created but needs email confirmation
    navigate('/verify-email', { state: { email: form.email } });
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

        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-1">Create account</h1>
          <p className="text-zinc-500 text-sm">Start your Nexora AI workspace.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && (
            <div className="flex items-start gap-2.5 bg-red-500/8 border border-red-500/20 rounded-lg px-3.5 py-3 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Full name */}
          <div className="space-y-1.5">
            <label htmlFor="fullName" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Full name</label>
            <input
              id="fullName"
              name="fullName"
              type="text"
              autoComplete="name"
              required
              value={form.fullName}
              onChange={handleChange}
              placeholder="Ada Lovelace"
              className="w-full bg-white/4 border border-white/8 rounded-lg px-3.5 py-2.5 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
            />
          </div>

          {/* Email */}
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={handleChange}
              placeholder="ada@example.com"
              className="w-full bg-white/4 border border-white/8 rounded-lg px-3.5 py-2.5 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
            />
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Password</label>
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
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <PasswordStrength password={form.password} />
          </div>

          {/* Confirm password */}
          <div className="space-y-1.5">
            <label htmlFor="confirmPassword" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Confirm password</label>
            <div className="relative">
              <input
                id="confirmPassword"
                name="confirmPassword"
                type={showConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={form.confirmPassword}
                onChange={handleChange}
                placeholder="Re-enter password"
                className={`w-full bg-white/4 border rounded-lg px-3.5 py-2.5 pr-10 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 transition-all ${
                  form.confirmPassword && form.password !== form.confirmPassword
                    ? 'border-red-500/40 focus:ring-red-500/40'
                    : 'border-white/8 focus:ring-cyan-500/50 focus:border-cyan-500/50'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                aria-label={showConfirm ? 'Hide password' : 'Show password'}
              >
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {form.confirmPassword && form.password !== form.confirmPassword && (
              <p className="text-xs text-red-400 mt-1">Passwords do not match.</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-950 font-semibold text-sm rounded-lg py-2.5 transition-all mt-2"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Creating account…</>
            ) : (
              <>Create account <ArrowRight className="w-4 h-4" /></>
            )}
          </button>

          <p className="text-center text-zinc-600 text-xs pt-1">
            By creating an account you agree to our Terms of Service.
          </p>
        </form>

        <p className="text-center text-zinc-500 text-sm mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-cyan-500 hover:text-cyan-400 transition-colors font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
