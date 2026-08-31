import { Navigate, Outlet } from 'react-router-dom';

/** Redirects unauthenticated visitors to the login page. */
export default function RequireAuth() {
  const token = localStorage.getItem('pulse_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
