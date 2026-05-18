/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        gold: '#b08d57',
      }
    },
  },
  plugins: [],
}
