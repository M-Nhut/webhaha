const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const dest = path.join(root, 'static/vendor');
const checkOnly = process.argv.includes('--check');
// If node_modules has mathjax/alpine, refresh them; otherwise preserve existing vendor assets
const mathjaxSrc = path.join(root, 'node_modules/mathjax/es5');
if (!checkOnly && fs.existsSync(mathjaxSrc)) {
  fs.mkdirSync(path.join(dest, 'mathjax/output/chtml'), {recursive: true});
  fs.copyFileSync(path.join(mathjaxSrc, 'tex-mml-chtml.js'), path.join(dest, 'mathjax/tex-mml-chtml.js'));
  fs.cpSync(path.join(mathjaxSrc, 'output/chtml/fonts'), path.join(dest, 'mathjax/output/chtml/fonts'), {recursive: true});
}
const alpineSrc = path.join(root, 'node_modules/alpinejs/dist/cdn.min.js');
if (!checkOnly && fs.existsSync(alpineSrc)) {
  fs.mkdirSync(path.join(dest, 'alpine'), {recursive: true});
  fs.copyFileSync(alpineSrc, path.join(dest, 'alpine/alpine.min.js'));
}
// The compact distribution ships browser assets; refresh only when packages exist.
// Fail clearly instead of reporting success with an incomplete installation.
const required = [
  'static/css/main.css',
  'static/css/tokens.css',
  'static/css/base.css',
  'static/css/components.css',
  'static/css/shell.css',
  'static/css/question-content.css',
  'static/js/ui-shell.js',
  'static/js/native-dialog.js',
  'static/js/math-config.js',
  'static/js/formula_renderer.js',
  'static/images/logo-transparent.png',
  'static/images/avatar-default.svg',
  'static/fonts/be-vietnam-pro/be-vietnam-pro-400.ttf',
  'static/fonts/be-vietnam-pro/be-vietnam-pro-500.ttf',
  'static/fonts/be-vietnam-pro/be-vietnam-pro-600.ttf',
  'static/fonts/be-vietnam-pro/be-vietnam-pro-700.ttf',
  'static/fonts/be-vietnam-pro/OFL.txt',
  'static/vendor/mathjax/tex-mml-chtml.js',
  'static/vendor/mathjax/output/chtml/fonts/tex.js',
  'static/vendor/mathjax/output/chtml/fonts/woff-v2/MathJax_Main-Regular.woff',
  'static/vendor/alpine/alpine.min.js',
  'static/vendor/lucide/lucide.min.js',
  'static/vendor/lucide/LICENSE',
  'static/vendor/chartjs/chart.umd.js',
  'static/vendor/chartjs/LICENSE.md',
  'node_modules/node-tikzjax/package.json',
];
const missing = required.filter(file => {
  const absolute = path.join(root, file);
  return !fs.existsSync(absolute) || !fs.statSync(absolute).isFile() || !fs.statSync(absolute).size;
});
if (missing.length) {
  throw new Error(`Missing local application assets: ${missing.join(', ')}`);
}
// Loading the worker also checks its transitive JavaScript dependencies.
require('node-tikzjax');
// Remember the verified executable used for setup when Python's PATH differs.
if (!checkOnly) fs.writeFileSync(path.join(root, '.latex-node-path'), process.execPath, 'utf8');
console.log(`Local application assets verified (${required.length} files${checkOnly ? ', read only' : ''}).`);
