const esbuild = require("esbuild");

const config = {
  entryPoints: ["./src/extension.ts"],
  bundle: true,
  outfile: "./dist/extension.js",
  external: ["vscode"],
  format: "cjs",
  platform: "node",
  minify: false,
  sourcemap: true,
  logLevel: "info",
};

async function main() {
  try {
    await esbuild.build(config);
    console.log("Bundling completed successfully.");
  } catch (err) {
    console.error("Bundling failed:", err);
    process.exit(1);
  }
}

main();
