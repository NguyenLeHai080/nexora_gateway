import { Navigate, Outlet } from 'react-router-dom';
import type { Role } from '../../../core/types';
import { useAuth } from '../hooks/useAuth';

export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, hydrated } = useAuth();
  if (!hydrated) return <div className="boot-loader">Dang tai Nexora Console...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

