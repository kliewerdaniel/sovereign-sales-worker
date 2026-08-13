import cwv from "eslint-config-next/core-web-vitals";
import ts from "eslint-config-next/typescript";

// eslint-config-next@16 ships native flat configs — import them directly.
// The previous FlatCompat wrapper crashed ESLint 9 with
// "TypeError: Converting circular structure to JSON" because it tried to
// serialise the circular flat-config object. Native flat arrays avoid that.
const eslintConfig = [
  ...cwv,
  ...ts,
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "demo_video/**",
    ],
  },
];

export default eslintConfig;
