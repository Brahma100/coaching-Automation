import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { InlineSkeletonText } from './Skeleton.jsx';
import useRole from '../hooks/useRole';

function AdminProtectedRoute() {
  const { isAdmin, isAuthenticated, loading } = useRole();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <InlineSkeletonText />
      </div>
    );
  }

  if (!isAdmin) {
    const next = `${location.pathname}${location.search}`;
    if (isAuthenticated) {
      return <Navigate to="/today" replace />;
    }
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <Outlet />;
}

export default AdminProtectedRoute;
