import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Zap, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn } = useAuth();

  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const from = location.state?.from?.pathname || '/workspace';

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      setError('Please fill in all fields.');
      return;
    }
    setLoading(true);
    setError('');

    const { data, error: signInError } = await signIn({ email: form.email, password: form.password });
    setLoading(false);

    if (signInError) {
      if (signInError.message?.toLowerCase().includes('invalid login credentials')) {
        setError('Invalid email or password. Please try again.');
      } else if (signInError.message?.toLowerCase().includes('email not confirmed')) {
        navigate('/verify-email', { state: { email: form.email } });
      } else {
        setError(signInError.message || 'Sign in failed. Please try again.');
      }
      return;
    }

    toast.success('Welcome back!');
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#070709] flex items-center justify-center p-4">
      {/* Background gradient */}
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
          <h1 className="text-2xl font-semibold text-zinc-50 tracking-tight mb-1">Sign in</h1>
          <p className="text-zinc-500 text-sm">Welcome back to your workspace.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* Error message */}
          {error && (
            <div className="flex items-start gap-2.5 bg-red-500/8 border border-red-500/20 rounded-lg px-3.5 py-3 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

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
              placeholder="you@example.com"
              className="w-full bg-white/4 border border-white/8 rounded-lg px-3.5 py-2.5 text-zinc-100 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
            />
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Password</label>
              <Link to="/forgot-password" className="text-xs text-cyan-500 hover:text-cyan-400 transition-colors">
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={form.password}
                onChange={handleChange}
                placeholder="••••••••"
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
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-950 font-semibold text-sm rounded-lg py-2.5 transition-all mt-2"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Signing in…</>
            ) : (
              <>Sign in <ArrowRight className="w-4 h-4" /></>
            )}
          </button>
        </form>

        <p className="text-center text-zinc-500 text-sm mt-6">
          New to Nexora?{' '}
          <Link to="/signup" className="text-cyan-500 hover:text-cyan-400 transition-colors font-medium">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
