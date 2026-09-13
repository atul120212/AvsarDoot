/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f2744",
        saffron: "#c45c26",
        leaf: "#1f7a4d",
      },
    },
  },
  plugins: [],
};
