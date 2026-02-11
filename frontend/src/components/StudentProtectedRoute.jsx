import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { InlineSkeletonText } from './Skeleton.jsx';
import { fetchStudentMe } from '../services/api';

function StudentProtectedRoute() {
  const [loading, setLoading] = React.useState(true);
  const [allowed, setAllowed] = React.useState(false);
  const location = useLocation();

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const payload = await fetchStudentMe();
        const role = payload?.role?.toUpperCase?.() || '';
        if (mounted) {
          setAllowed(role === 'STUDENT');
        }
      } catch {
        if (mounted) {
          setAllowed(false);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, [location.pathname]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <InlineSkeletonText />
      </div>
    );
  }

  if (!allowed) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <Outlet />;
}

export default StudentProtectedRoute;
