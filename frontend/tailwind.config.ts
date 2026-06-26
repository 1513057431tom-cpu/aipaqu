import type { Config } from "tailwindcss"

export default {
  content: [
    "./app.vue",
    "./app/**/*.{vue,ts}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1f2933",
        panel: "#f7f8fa",
        accent: "#1f7a6d",
        warning: "#b7791f",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
} satisfies Config

