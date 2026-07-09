/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#F1F6F9',
          card: '#FFFFFF',
          dark: '#30526F',
          border: '#DFEBF1',
          primary: '#4C799E',
          alert: '#F9A806',
          alertBg: '#FEF8EB',
          success: '#1F7A4C',
          successBg: '#E7F9F0',
          text: '#2E2E2E',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
