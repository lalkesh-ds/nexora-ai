import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

// Full-screen loader
function AuthLoader() {
  return (
    <div className="flex items-center justify-center h-screen bg-[#070709]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
        <p className="text-zinc-500 text-sm">Restoring session…</p>
      </div>
    </div>
  );
}

/** Wraps protected routes — redirects unauthenticated users to /login */
export function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <AuthLoader />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

/** Redirects already-authenticated users away from auth pages */
export function RedirectIfAuth({ children }) {
  const { user, loading } = useAuth();

  if (loading) return <AuthLoader />;
  if (user) return <Navigate to="/workspace" replace />;
  return children;
}
