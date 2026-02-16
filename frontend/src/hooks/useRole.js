import React from 'react';

import { fetchStudentMe, fetchTeacherProfile } from '../services/api';
import { setGlobalToastDurationSeconds } from '../services/api';

function useRole() {
  const [role, setRole] = React.useState('');
  const [profile, setProfile] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const profile = await fetchTeacherProfile();
        const roleValue = (profile?.role || '').toLowerCase();
        if (mounted) {
          setGlobalToastDurationSeconds(profile?.ui_toast_duration_seconds ?? 5);
          setProfile(profile || null);
          setRole(roleValue);
          setIsAuthenticated(Boolean(roleValue));
        }
      } catch {
        try {
          await fetchStudentMe();
          if (mounted) {
            setProfile(null);
            setRole('student');
            setIsAuthenticated(true);
          }
        } catch {
          if (mounted) {
            setProfile(null);
            setRole('');
            setIsAuthenticated(false);
          }
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
  }, []);

  return {
    role,
    profile,
    loading,
    isAuthenticated,
    isAdmin: role === 'admin',
    isTeacher: role === 'teacher',
    isStudent: role === 'student'
  };
}

export default useRole;
