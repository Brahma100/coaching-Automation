import React from 'react';

import { fetchStudentMe, fetchTeacherProfile } from '../services/api';

function useRole() {
  const [role, setRole] = React.useState('');
  const [loading, setLoading] = React.useState(true);
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const profile = await fetchTeacherProfile();
        const roleValue = (profile?.role || '').toLowerCase();
        if (mounted) {
          setRole(roleValue);
          setIsAuthenticated(Boolean(roleValue));
        }
      } catch {
        try {
          await fetchStudentMe();
          if (mounted) {
            setRole('student');
            setIsAuthenticated(true);
          }
        } catch {
          if (mounted) {
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
    loading,
    isAuthenticated,
    isAdmin: role === 'admin',
    isTeacher: role === 'teacher',
    isStudent: role === 'student'
  };
}

export default useRole;
