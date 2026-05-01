import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        coal: '#111111',
        ember: '#c96b2c',
        parchment: '#f4ead7',
        ash: '#9c9489',
        wine: '#5f1e18',
      },
      boxShadow: {
        card: '0 20px 60px rgba(0, 0, 0, 0.28)',
      },
      backgroundImage: {
        grain:
          "radial-gradient(circle at 20% 20%, rgba(201,107,44,0.14), transparent 30%), radial-gradient(circle at 80% 0%, rgba(95,30,24,0.18), transparent 30%), linear-gradient(180deg, rgba(17,17,17,0.96), rgba(17,17,17,1))",
      },
    },
  },
  plugins: [],
};

export default config;
