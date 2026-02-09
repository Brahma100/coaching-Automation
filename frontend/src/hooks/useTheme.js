import React from 'react';

const STORAGE_KEY = 'coaching-theme';

function detectInitialTheme() {
  if (typeof window === 'undefined') {
    return 'light';
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') {
    return stored;
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function useTheme() {
  const [theme, setTheme] = React.useState(() => detectInitialTheme());

  React.useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = React.useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  return {
    theme,
    isDark: theme === 'dark',
    setTheme,
    toggleTheme
  };
}

export default useTheme;
