import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { InlineSkeletonText } from './Skeleton.jsx';
import { fetchActivationStatus, fetchTodayBrief } from '../services/api';

function ProtectedRoute() {
  const [loading, setLoading] = React.useState(true);
  const [allowed, setAllowed] = React.useState(false);
  const [activationIncomplete, setActivationIncomplete] = React.useState(false);
  const location = useLocation();

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await fetchTodayBrief();
        try {
          const status = await fetchActivationStatus();
          if (mounted) {
            setActivationIncomplete(Boolean(!status?.first_login_completed));
          }
        } catch {
          if (mounted) {
            setActivationIncomplete(false);
          }
        }
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
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  if (activationIncomplete && location.pathname !== '/welcome') {
    return <Navigate to="/welcome" replace />;
  }

  if (!activationIncomplete && location.pathname === '/welcome') {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
