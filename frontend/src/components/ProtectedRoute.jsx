import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { InlineSkeletonText } from './Skeleton.jsx';
import { fetchTodayBrief } from '../services/api';

function ProtectedRoute() {
  const [loading, setLoading] = React.useState(true);
  const [allowed, setAllowed] = React.useState(false);
  const location = useLocation();

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await fetchTodayBrief();
        if (mounted) {
          setAllowed(true);
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
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
