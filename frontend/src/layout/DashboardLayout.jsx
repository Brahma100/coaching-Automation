import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  FiBarChart2,
  FiBell,
  FiCalendar,
  FiChevronLeft,
  FiChevronRight,
  FiBookOpen,
  FiClock,
  FiGrid,
  FiHome,
  FiLogOut,
  FiMoon,
  FiMenu,
  FiAlertTriangle,
  FiUsers,
  FiSun,
  FiSearch,
  FiSettings,
  FiUser,
  FiUserCheck,
  FiUserX,
  FiX
} from 'react-icons/fi';
import { HiOutlineUserGroup } from 'react-icons/hi';

import useRole from '../hooks/useRole';
import { logout } from '../services/api';
import useTheme from '../hooks/useTheme';
import useTelegramLink from '../hooks/useTelegramLink';

const profileMenu = [
  { to: '/settings', label: 'My Profile', icon: FiUser },
  { to: '/settings/communication', label: 'Settings', icon: FiSettings }
];

function formatRoleLabel(role) {
  const value = String(role || '').trim().toLowerCase();
  if (value === 'admin') return 'Admin';
  if (value === 'teacher') return 'Teacher';
  if (value === 'student') return 'Student';
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : 'User';
}

function maskPhone(value) {
  const digits = String(value || '').replace(/\D/g, '');
  if (!digits) return 'Not available';
  if (digits.length <= 4) return `****${digits}`;
  return `******${digits.slice(-4)}`;
}

function profileInitials(profile, fallbackRole) {
  const roleText = formatRoleLabel(profile?.role || fallbackRole || 'user').toUpperCase();
  return roleText.slice(0, 2);
}

function DashboardLayout() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const { status: telegramLink, beginLink, refreshStatus } = useTelegramLink();
  const [mobileSidebarOpen, setMobileSidebarOpen] = React.useState(false);
  const [userMenuOpen, setUserMenuOpen] = React.useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem('dashboard.sidebar.collapsed') === '1';
  });
  const { isAdmin, role, profile } = useRole();
  const userMenuRef = React.useRef(null);
  const roleLabel = formatRoleLabel(profile?.role || role || (isAdmin ? 'admin' : 'teacher'));
  const subtitle = maskPhone(profile?.phone);
  const initials = profileInitials(profile, role || (isAdmin ? 'admin' : 'teacher'));

  const onLogout = async () => {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  };

  const closeMobileSidebar = () => setMobileSidebarOpen(false);

  React.useEffect(() => {
    const onDocClick = (event) => {
      if (!userMenuRef.current) return;
      if (!userMenuRef.current.contains(event.target)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('dashboard.sidebar.collapsed', sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  const primaryMenu = React.useMemo(() => {
    const base = [
      { to: '/brain', label: 'Operational Brain', icon: FiHome },
      { to: '/today', label: 'Today View', icon: FiClock },
      { to: '/calendar', label: 'Teacher Calendar', icon: FiCalendar },
      { to: '/time-capacity', label: 'Time & Capacity', icon: FiBarChart2 },
      { to: '/dashboard', label: 'Dashboard', icon: FiGrid },
        { to: '/attendance', label: 'Manage Attendance', icon: FiBookOpen },
        { to: '/students', label: 'Manage Students', icon: FiUserCheck },
        { to: '/batches', label: 'Manage Batch', icon: FiCalendar },
        { to: '/notes', label: 'Notes', icon: FiBell },
        { to: '/risk', label: 'Skill Progress', icon: FiBarChart2 },
      { to: '/actions', label: 'Pending Actions', icon: FiUserX }
    ];
    if (isAdmin) {
      base.splice(2, 0, { to: '/admin/ops', label: 'Admin Ops', icon: FiAlertTriangle });
    }
    return base;
  }, [isAdmin]);

  const renderSidebarContent = ({ collapsed = false, mobile = false } = {}) => (
    <>
      <div className="mb-8 flex items-center justify-between">
        <h1 className={`font-extrabold tracking-tight ${collapsed ? 'text-[22px]' : 'text-[30px]'}`}>
          <span className="text-[#48bf6d]">Learning</span>
          {!collapsed ? <span className="text-[#2f7bf6]">Mate</span> : null}
        </h1>
        {mobile ? (
          <button
            type="button"
            onClick={closeMobileSidebar}
            className="rounded-lg border border-slate-200 p-2 text-slate-600 lg:hidden dark:border-slate-700 dark:text-slate-300"
          >
            <FiX />
          </button>
        ) : null}
      </div>

      <nav className="space-y-2">
        {primaryMenu.map((item) => (
          <NavLink
            key={`${item.to}-${item.label}`}
            to={item.to}
            onClick={closeMobileSidebar}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              `flex items-center rounded-xl px-4 py-3 text-sm font-semibold transition ${
                collapsed ? 'justify-center px-3' : 'gap-3'
              } ${
                isActive
                  ? 'bg-[#e6f0ff] text-[#2f7bf6] dark:bg-slate-800 dark:text-[#66a3ff]'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {!collapsed ? item.label : null}
          </NavLink>
        ))}
      </nav>

      <div className="my-7 border-t border-slate-200 dark:border-slate-700" />

      <nav className="space-y-2">
        {profileMenu.map((item) => (
          <NavLink
            key={`${item.to}-${item.label}`}
            to={item.to}
            onClick={closeMobileSidebar}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              `flex items-center rounded-xl px-4 py-3 text-sm font-semibold transition ${
                collapsed ? 'justify-center px-3' : 'gap-3'
              } ${
                isActive
                  ? 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {!collapsed ? item.label : null}
          </NavLink>
        ))}
      </nav>

      {!collapsed ? (
        <div className="mt-8 rounded-2xl bg-[#f0f4ff] p-4 text-center shadow-sm dark:bg-slate-800">
          <div className="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-[#5b5cff] to-[#2f7bf6] text-white">
            <HiOutlineUserGroup className="h-8 w-8" />
          </div>
          <p className="text-lg font-bold text-slate-800 dark:text-slate-100">Student Group</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-300">Create a study group and chat with students.</p>
          <button className="mt-3 rounded-full bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white">Create Group</button>
        </div>
      ) : null}
    </>
  );

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {mobileSidebarOpen ? (
        <button
          type="button"
          aria-label="Close menu overlay"
          onClick={closeMobileSidebar}
          className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden"
        />
      ) : null}

      <div className={`mx-auto w-full lg:grid ${sidebarCollapsed ? 'lg:grid-cols-[88px,1fr]' : 'lg:grid-cols-[280px,1fr]'}`}>
        <aside className={`hidden min-h-screen border-r border-slate-200 bg-white py-8 dark:border-slate-800 dark:bg-slate-900 lg:block ${sidebarCollapsed ? 'px-3' : 'px-6'}`}>
          {renderSidebarContent({ collapsed: sidebarCollapsed })}
        </aside>

        <aside
          className={`fixed inset-y-0 left-0 z-40 w-[280px] border-r border-slate-200 bg-white px-6 py-8 transition-transform duration-200 dark:border-slate-800 dark:bg-slate-900 lg:hidden ${
            mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          {renderSidebarContent({ mobile: true })}
        </aside>

        <div className="min-w-0">
          <header className="border-b border-slate-200 bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-900 sm:px-6">
            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(true)}
                className="grid h-10 w-10 place-items-center rounded-lg border border-slate-200 text-slate-600 lg:hidden dark:border-slate-700 dark:text-slate-300"
              >
                <FiMenu />
              </button>
              <button
                type="button"
                onClick={() => setSidebarCollapsed((prev) => !prev)}
                aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                className="hidden h-10 w-10 place-items-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 lg:grid dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {sidebarCollapsed ? <FiChevronRight /> : <FiChevronLeft />}
              </button>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-[#f8fafc] px-4 py-2.5 dark:border-slate-700 dark:bg-slate-800">
                  <FiSearch className="text-slate-400" />
                  <input
                    placeholder="Search for Students, Programs, Assignment..."
                    className="w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                </div>
              </div>

              <div className="ml-auto flex items-center gap-2 sm:gap-4">
                <button
                  type="button"
                  onClick={toggleTheme}
                  aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                  className="grid h-10 w-10 place-items-center rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {isDark ? <FiSun className="h-4 w-4" /> : <FiMoon className="h-4 w-4" />}
                </button>
                <button className="relative grid h-9 w-9 place-items-center rounded-full border border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-300 sm:h-10 sm:w-10">
                  <FiBell />
                </button>
                <div className="relative" ref={userMenuRef}>
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((prev) => !prev)}
                    className="flex items-center gap-3 rounded-xl border border-slate-200 px-2 py-1.5 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
                  >
                    <div className="hidden text-right sm:block">
                      <p className="text-sm font-bold text-slate-800 dark:text-slate-100">{roleLabel}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
                    </div>
                    <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-[#ffd6a8] to-[#f08d5f] text-xs font-bold text-white sm:h-10 sm:w-10 sm:text-sm">{initials}</div>
                  </button>

                  {userMenuOpen ? (
                    <div className="absolute right-0 top-[calc(100%+8px)] z-50 w-64 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          navigate('/dashboard');
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <FiHome className="h-4 w-4" />
                        Dashboard
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          navigate('/students');
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <FiUsers className="h-4 w-4" />
                        Manage Students
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          navigate('/settings/communication');
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <FiUser className="h-4 w-4" />
                        My Profile
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          navigate('/settings');
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <FiSettings className="h-4 w-4" />
                        Settings
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          toggleTheme();
                          setUserMenuOpen(false);
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        {isDark ? <FiSun className="h-4 w-4" /> : <FiMoon className="h-4 w-4" />}
                        {isDark ? 'Light Mode' : 'Dark Mode'}
                      </button>
                      <div className="my-1 border-t border-slate-200 dark:border-slate-700" />
                      <button
                        type="button"
                        onClick={onLogout}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-900/20"
                      >
                        <FiLogOut className="h-4 w-4" />
                        Logout
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </header>

          <main className="p-4 sm:p-6">
            {!telegramLink.loading && !telegramLink.linked ? (
              <div className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">
                      Your number is not linked to Telegram. Link it to receive OTP and all notifications.
                    </p>
                    {telegramLink.error ? (
                      <p className="mt-1 text-xs opacity-90">{telegramLink.error}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={beginLink}
                    disabled={telegramLink.starting}
                    className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    {telegramLink.starting ? 'Opening Telegram...' : 'Link Telegram'}
                  </button>
                  <button
                    type="button"
                    onClick={() => refreshStatus()}
                    disabled={telegramLink.checking}
                    className="rounded-lg border border-amber-500 px-3 py-2 text-sm font-semibold text-amber-800 disabled:opacity-60 dark:border-amber-600 dark:text-amber-200"
                  >
                    {telegramLink.checking ? 'Checking...' : "I've linked"}
                  </button>
                </div>
              </div>
            ) : null}
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

export default DashboardLayout;
