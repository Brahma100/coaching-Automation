/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef8ff',
          100: '#d9efff',
          500: '#2780f8',
          600: '#1f68da',
          700: '#1f53ad',
          900: '#1b2f63'
        }
      },
      boxShadow: {
        panel: '0 8px 24px rgba(16,24,40,.08)'
      }
    }
  },
  plugins: []
};
