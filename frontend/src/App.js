import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Navigate, useRoutes } from 'react-router-dom';

import PageLoader from './components/ui/PageLoader.jsx';
import GlobalToastHost from './components/ui/GlobalToastHost.jsx';
import { clearToastEvent } from './store/slices/appSlice.js';

const ProtectedRoute = React.lazy(() => import('./components/guards/ProtectedRoute.jsx'));
const StudentProtectedRoute = React.lazy(() => import('./components/guards/StudentProtectedRoute.jsx'));
const AdminProtectedRoute = React.lazy(() => import('./components/guards/AdminProtectedRoute.jsx'));
const DashboardLayout = React.lazy(() => import('./components/layout/DashboardLayout.jsx'));
const AdminLayout = React.lazy(() => import('./components/layout/AdminLayout.jsx'));
const StudentLayout = React.lazy(() => import('./components/layout/StudentLayout.jsx'));
const Actions = React.lazy(() => import('./pages/Actions.jsx'));
const Attendance = React.lazy(() => import('./pages/Attendance.jsx'));
const AttendanceToken = React.lazy(() => import('./pages/AttendanceToken.jsx'));
const ClassStartToken = React.lazy(() => import('./pages/ClassStartToken.jsx'));
const Dashboard = React.lazy(() => import('./pages/Dashboard.jsx'));
const Brain = React.lazy(() => import('./pages/Brain.jsx'));
const Today = React.lazy(() => import('./pages/Today.jsx'));
const TeacherCalendar = React.lazy(() => import('./pages/TeacherCalendar.jsx'));
const TimeCapacity = React.lazy(() => import('./pages/TimeCapacity.jsx'));
const Fees = React.lazy(() => import('./pages/Fees.jsx'));
const Homework = React.lazy(() => import('./pages/Homework.jsx'));
const Notes = React.lazy(() => import('./pages/Notes.jsx'));
const Login = React.lazy(() => import('./pages/Login.jsx'));
const Signup = React.lazy(() => import('./pages/Signup.jsx'));
const Onboard = React.lazy(() => import('./pages/Onboard.jsx'));
const Welcome = React.lazy(() => import('./pages/Welcome.jsx'));
const Risk = React.lazy(() => import('./pages/Risk.jsx'));
const Settings = React.lazy(() => import('./pages/Settings.jsx'));
const CommunicationSettings = React.lazy(() => import('./pages/CommunicationSettings.jsx'));
const AutomationRulesSettings = React.lazy(() => import('./pages/AutomationRulesSettings.jsx'));
const Integrations = React.lazy(() => import('./pages/Integrations.jsx'));
const Students = React.lazy(() => import('./pages/Students.jsx'));
const SessionSummaryToken = React.lazy(() => import('./pages/SessionSummaryToken.jsx'));
const Batches = React.lazy(() => import('./pages/Batches.jsx'));
const StudentPreferences = React.lazy(() => import('./pages/StudentPreferences.jsx'));
const AdminOpsDashboard = React.lazy(() => import('./pages/AdminOpsDashboard.jsx'));

const page = (Component) => React.createElement(Component);
const redirectDashboard = React.createElement(Navigate, { to: '/dashboard', replace: true });
const redirectLogin = React.createElement(Navigate, { to: '/login', replace: true });

function App() {
  const dispatch = useDispatch();
  const toastEvent = useSelector((state) => state?.app?.toastEvent || null);

  const routes = useRoutes([
    { path: '/login', element: page(Login) },
    { path: '/signup', element: page(Signup) },
    { path: '/onboard', element: page(Onboard) },
    { path: '/attendance/session/:sessionId', element: React.createElement(AttendanceToken, { expectedType: 'attendance_open' }) },
    { path: '/attendance/review/:sessionId', element: React.createElement(AttendanceToken, { expectedType: 'attendance_review', showCountdown: true }) },
    { path: '/class/start/:sessionId', element: page(ClassStartToken) },
    { path: '/session/summary/:sessionId', element: page(SessionSummaryToken) },
    {
      element: page(StudentProtectedRoute),
      children: [
        {
          element: page(StudentLayout),
          children: [{ path: '/student/preferences', element: page(StudentPreferences) }]
        }
      ]
    },
    {
      element: page(ProtectedRoute),
      children: [
        {
          element: page(DashboardLayout),
          children: [
            { path: '/', element: redirectDashboard },
            { path: '/dashboard', element: page(Dashboard) },
            { path: '/brain', element: page(Brain) },
            { path: '/welcome', element: page(Welcome) },
            { path: '/today', element: page(Today) },
            { path: '/calendar', element: page(TeacherCalendar) },
            { path: '/time-capacity', element: page(TimeCapacity) },
            { path: '/students', element: page(Students) },
            { path: '/batches', element: page(Batches) },
            { path: '/attendance', element: page(Attendance) },
            { path: '/fees', element: page(Fees) },
            { path: '/homework', element: page(Homework) },
            { path: '/notes', element: page(Notes) },
            { path: '/actions', element: page(Actions) },
            { path: '/risk', element: page(Risk) },
            { path: '/settings', element: page(Settings) },
            { path: '/settings/communication', element: page(CommunicationSettings) },
            { path: '/settings/automation-rules', element: page(AutomationRulesSettings) },
            { path: '/settings/integrations', element: page(Integrations) }
          ]
        }
      ]
    },
    {
      element: page(AdminProtectedRoute),
      children: [
        {
          element: page(AdminLayout),
          children: [{ path: '/admin/ops', element: page(AdminOpsDashboard) }]
        }
      ]
    },
    { path: '*', element: redirectLogin }
  ]);

  return React.createElement(
    React.Fragment,
    null,
    React.createElement(
      React.Suspense,
      { fallback: React.createElement(PageLoader) },
      routes
    ),
    React.createElement(GlobalToastHost, {
      event: toastEvent,
      onDone: () => dispatch(clearToastEvent()),
    })
  );
}

export default App;
