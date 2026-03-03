module.exports = {
  default: {
    require: ["src/steps/**/*.ts", "src/core/hooks.ts"],
    format: [
      "progress",
      "allure-playwright"
    ],
    requireModule: ["ts-node/register"],
    paths: ["src/features/**/*.feature"],
    timeout: 60000
  }
};