# Local TeX extensions

These libraries are loaded into the in-memory filesystem of node-tikzjax. Runtime compilation has no network access.

- tkz-tab 2.12c (Alain Matthes), unmodified `tkz-tab.sty` and README from https://ctan.org/pkg/tkz-tab, LPPL 1.3 or later. Retrieved 2026-09-26. CTAN currently flags this package as temporarily withdrawn for author investigation; retain regression tests and review rendered tables.
- xkeyval, unmodified runtime files from the TeX Live archive https://mirrors.ctan.org/systems/texlive/tlnet/archive/xkeyval.tar.xz, LPPL; copyright and license notices remain in each file.

Only fixed packaged directories are loaded; uploaded documents cannot select host filesystem paths. Original source is retained in formula assets. Unsupported commands and malformed tables produce a visible error, never a replacement drawing.
