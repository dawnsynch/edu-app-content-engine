import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        dawn: {
          ink: "#1c2430",
          mist: "#eef4f8",
          line: "#d7e1e8",
          teal: "#0f766e",
          gold: "#b7791f"
        }
      }
    }
  },
  plugins: []
};

export default config;

