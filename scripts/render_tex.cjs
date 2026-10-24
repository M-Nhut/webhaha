// One isolated WASM TeX process per fragment. TeX sees a memory filesystem.
const fs = require('node:fs');
const path = require('node:path');
const { default: tex2svg, load, dumpMemfs } = require('node-tikzjax');
const logs = [];
console.log = (...args) => { if (logs.length < 80) logs.push(args.join(' ')); };
(async () => {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  // The DVI converter consumes TikZ's SVG specials. Wrap standalone tables
  // in a node so they get an SVG viewport too.
  const source = /^\s*\\begin\{(?:tabular\*?|tabularx|longtable)\}/.test(input.source)
    ? '\\begin{tikzpicture}\\node[inner sep=2pt]{' + input.source + '};\\end{tikzpicture}'
    : input.source;
  await load();
  const memory = dumpMemfs();
  for (const folder of ['tkz-tab', 'xkeyval']) {
    const directory = path.join(__dirname, '../vendor/tex', folder);
    for (const file of fs.readdirSync(directory)) {
      if (/\.(sty|tex)$/.test(file)) memory.writeFileSync('/tex_files/' + file, fs.readFileSync(path.join(directory, file)));
    }
  }
  const extra = /\\tkzTab/.test(source) ? '\\usepackage{tkz-tab}\n' : '';
  const svg = await tex2svg('\\begin{document}\n' + source + '\n\\end{document}', {
    showConsole: true, embedFontCss: false,
    texPackages: { amsmath: '', amssymb: '', array: '' },
    tikzLibraries: 'arrows.meta,calc,angles,quotes,patterns,positioning,shapes.geometric',
    addToPreamble: extra + (input.preamble || '')
  });
  if (/(?:^|\n)! |Missing character:/.test(logs.join('\n'))) {
    throw new Error('TeX reported missing characters or a compilation error.');
  }
  const root = path.dirname(require.resolve('node-tikzjax/package.json'));
  const css = fs.readFileSync(path.join(root, 'css/fonts.css'), 'utf8');
  const fonts = [];
  for (const match of css.matchAll(/@font-face\s*\{\s*font-family:\s*([\w-]+);\s*src:\s*url\('([^']+)'\);\s*\}/g)) {
    if (!svg.includes(match[1])) continue;
    fonts.push(`@font-face{font-family:${match[1]};src:url(data:font/ttf;base64,${fs.readFileSync(path.join(root, 'css', match[2])).toString('base64')})}`);
  }
  // Keep trusted font CSS separate from untrusted SVG until Python sanitizes it.
  process.stdout.write(JSON.stringify({svg, fonts: fonts.join('\n')}));
})().catch(error => {
  process.stdout.write(JSON.stringify({error: String(error.message), log: logs.join('\n').slice(-5000)}));
  process.exitCode = 1;
});
