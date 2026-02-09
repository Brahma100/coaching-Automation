import React from 'react';
import { Navigate, useRoutes } from 'react-router-dom';

import { PageSkeleton } from './components/Skeleton.jsx';

const ProtectedRoute = React.lazy(() => import('./components/ProtectedRoute.jsx'));
const DashboardLayout = React.lazy(() => import('./layout/DashboardLayout.jsx'));
const Actions = React.lazy(() => import('./pages/Actions.jsx'));
const Attendance = React.lazy(() => import('./pages/Attendance.jsx'));
const Dashboard = React.lazy(() => import('./pages/Dashboard.jsx'));
const Fees = React.lazy(() => import('./pages/Fees.jsx'));
const Homework = React.lazy(() => import('./pages/Homework.jsx'));
const Login = React.lazy(() => import('./pages/Login.jsx'));
const Signup = React.lazy(() => import('./pages/Signup.jsx'));
const Risk = React.lazy(() => import('./pages/Risk.jsx'));
const Settings = React.lazy(() => import('./pages/Settings.jsx'));
const Students = React.lazy(() => import('./pages/Students.jsx'));
const Batches = React.lazy(() => import('./pages/Batches.jsx'));

const page = (Component) => React.createElement(Component);
const redirectDashboard = React.createElement(Navigate, { to: '/dashboard', replace: true });
const redirectLogin = React.createElement(Navigate, { to: '/login', replace: true });

function App() {
  const routes = useRoutes([
    { path: '/login', element: page(Login) },
    { path: '/signup', element: page(Signup) },
    {
      element: page(ProtectedRoute),
      children: [
        {
          element: page(DashboardLayout),
          children: [
            { path: '/', element: redirectDashboard },
            { path: '/dashboard', element: page(Dashboard) },
            { path: '/students', element: page(Students) },
            { path: '/batches', element: page(Batches) },
            { path: '/attendance', element: page(Attendance) },
            { path: '/fees', element: page(Fees) },
            { path: '/homework', element: page(Homework) },
            { path: '/actions', element: page(Actions) },
            { path: '/risk', element: page(Risk) },
            { path: '/settings', element: page(Settings) }
          ]
        }
      ]
    },
    { path: '*', element: redirectLogin }
  ]);

  return React.createElement(
    React.Suspense,
    { fallback: React.createElement(PageSkeleton) },
    routes
  );
}

export default App;
