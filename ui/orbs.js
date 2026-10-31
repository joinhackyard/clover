// Clover orb + answer renderer. Original work for Clover by Hackyard (https://hackyard.org), MIT License (see LICENSE).
// One module, inlined by Clover.app at each page's /*ORBS*/ marker and imported from a Blob URL. Its minified-style export names
// are the pages' contract and must not change:
//   r(state, size) -> preset {mode, speed, opts}      M[mode](size, t, opts) -> frame      p(ctx, frame, dark, _) paints it
//   MML (the MathML namespace), markdown(text) -> DocumentFragment, shut(streamedText) -> the part safe to show now.
// Nothing here ever parses HTML: model text only becomes text nodes and elements we create ourselves.

// ─────────────────────────────── The orb: a small, calm four-leaf clover ───────────────────────────────
// Flat leaves in Clover green, no halo or sparkles: it shows state by how it moves, never by glowing. Colours follow the
// shared tokens (--accent #2E9E6A / dark #4CC38A, --sage #A8C3A0, --ink-3).
const PALETTE = {
  light: { deep: [31, 122, 80], leaf: [46, 158, 106], tip: [86, 182, 136], sage: [168, 195, 160], grey: [143, 138, 129], vein: 0.32, ring: 0.16 },
  dark: { deep: [46, 158, 106], leaf: [76, 195, 138], tip: [122, 212, 166], sage: [168, 195, 160], grey: [133, 128, 122], vein: 0.22, ring: 0.2 }
};
const TAU = Math.PI * 2;
const mix = (a, b, f) => a.map((v, i) => Math.round(v + (b[i] - v) * f));
const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const clamp01 = v => Math.max(0, Math.min(1, Number.isFinite(v) ? v : 0));
const pulse = x => { const s = Math.sin(Math.PI * (((x % 1) + 1) % 1)); return s * s * s * s; };   // a soft bump once per cycle, resting most of the time

// Each look is a handful of numbers the one painter understands. Every state is the same clover, moving differently.
//   breathe: slow size swing   turn: turns per second   wave: a bump that travels leaf to leaf (rate: laps per second)
//   hop: the bump lifts the leaf too   talk: a speech-like flutter   grey: 0 clover … 1 ink   level: leaves answer the voice
const LOOKS = {
  idle:      { speed: 1, breathe: 0.03, turn: 0, wave: 0, rate: 0, hop: 0, talk: 0, grey: 0 },
  listening: { speed: 1, breathe: 0.025, turn: 0, wave: 0.04, rate: 0.5, hop: 0, talk: 0, grey: 0, level: 1 },
  thinking:  { speed: 1, breathe: 0.01, turn: 0.05, wave: 0.13, rate: 1.1, hop: 0, talk: 0, grey: 0 },
  searching: { speed: 1, breathe: 0.01, turn: 0.03, wave: 0.11, rate: 0.8, hop: 0, talk: 0, grey: 0, glint: 1 },
  working:   { speed: 1, breathe: 0.01, turn: 0.02, wave: 0.1, rate: 1.6, hop: 1, talk: 0, grey: 0 },
  speaking:  { speed: 1, breathe: 0.015, turn: 0, wave: 0, rate: 0, hop: 0, talk: 1, grey: 0 },
  done:      { speed: 1, breathe: 0.02, turn: 0, wave: 0, rate: 0, hop: 0, talk: 0, grey: 0, ripe: 1 },
  error:     { speed: 1, breathe: 0.01, turn: 0, wave: 0, rate: 0, hop: 0, talk: 0, grey: 0.8 }
};
// The names pages already use, mapped onto the clover's looks.
const ALIAS = { breathing: 'idle', ready: 'idle', solving: 'thinking', connecting: 'thinking', composing: 'speaking', weaving: 'thinking',
  shaping: 'thinking', talking: 'speaking', failed: 'error', finished: 'done' };

// A leaf is a heart whose point sits at the clover's middle; L is its length. Drawn pointing up, then rotated into place.
const leafPath = (ctx, L, w) => {
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.bezierCurveTo(-0.16 * L * w, -0.16 * L, -0.64 * L * w, -0.36 * L, -0.52 * L * w, -0.74 * L);
  ctx.bezierCurveTo(-0.42 * L * w, -1.02 * L, -0.08 * L * w, -1.04 * L, 0, -0.8 * L);
  ctx.bezierCurveTo(0.08 * L * w, -1.04 * L, 0.42 * L * w, -1.02 * L, 0.52 * L * w, -0.74 * L);
  ctx.bezierCurveTo(0.64 * L * w, -0.36 * L, 0.16 * L * w, -0.16 * L, 0, 0);
  ctx.closePath();
};

// One frame of one look: plain numbers, so a page can paint it anywhere (or the same frame many times).
// opts.level (0–1) or opts.levels ([4], one per leaf, already smoothed by the page's springs) make the leaves answer a voice.
const cloverFrame = (size, t, o) => {
  const react = !!o.levelReact || Array.isArray(o.levels), level = react ? clamp01(o.level) : 0;   // levels from another look: the leaves settle back on their springs
  const leaves = [];
  for (let k = 0; k < 4; k++) {
    const lv = react ? clamp01(o.levels?.[k] ?? level) : 0;
    const bump = o.wave ? pulse(t * o.rate - k / 4) : 0;
    const talk = o.talk ? 0.07 * (0.5 + 0.5 * Math.sin(t * 8.6 + k * 1.7)) * (0.55 + 0.45 * Math.sin(t * 2.1 + k * 0.9)) : 0;
    leaves.push({
      angle: Math.PI / 4 + k * TAU / 4 + o.turn * t * TAU + 0.05 * lv * Math.sin(t * 3 + k),
      len: size * 0.235 * (1 + o.breathe * Math.sin(t * 1.3 + k * 0.5) + o.wave * bump + talk + 0.17 * lv),
      width: 1 + 0.05 * lv,
      lift: size * (0.018 + 0.03 * lv + (o.hop ? 0.025 * bump : 0)),
      light: o.glint ? bump * 0.5 : bump * 0.25
    });
  }
  return { size, cx: size / 2, cy: size / 2, leaves, grey: o.grey || 0, ring: o.levelReact ? level : 0, ripe: o.ripe ? 1 : 0, small: size < 26 };
};

// Paint a frame. dark: drawn over Clover's dark surfaces (a lighter green); light: a deeper green on paper.
const paintFrame = (ctx, f, dark = true) => {
  const P = dark ? PALETTE.dark : PALETTE.light, { size, cx, cy } = f;
  const tone = c => f.grey ? mix(c, P.grey, f.grey) : c;
  ctx.save();
  if (f.ring > 0.02) {   // listening: one soft ring that opens a little with the voice
    ctx.beginPath(); ctx.arc(cx, cy, size * (0.4 + 0.06 * f.ring), 0, TAU);
    ctx.strokeStyle = rgba(P.leaf, P.ring * f.ring); ctx.lineWidth = Math.max(0.75, size * 0.022); ctx.stroke();
  }
  for (const leaf of f.leaves) {
    ctx.save();
    ctx.translate(cx + Math.sin(leaf.angle) * leaf.lift, cy - Math.cos(leaf.angle) * leaf.lift);
    ctx.rotate(leaf.angle);
    const g = ctx.createLinearGradient(0, 0, 0, -leaf.len);
    g.addColorStop(0, rgba(tone(P.deep), 1));
    g.addColorStop(0.5, rgba(tone(mix(P.leaf, P.tip, leaf.light)), 1));
    g.addColorStop(1, rgba(tone(mix(P.tip, [255, 255, 255], leaf.light * 0.4)), 1));
    leafPath(ctx, leaf.len, leaf.width); ctx.fillStyle = g; ctx.fill();
    if (!f.small) {   // the vein: one quiet line
      ctx.beginPath(); ctx.moveTo(0, -leaf.len * 0.16); ctx.lineTo(0, -leaf.len * 0.62);
      ctx.strokeStyle = `rgba(255,255,255,${P.vein})`; ctx.lineWidth = Math.max(0.5, size * 0.013); ctx.lineCap = 'round'; ctx.stroke();
    }
    ctx.restore();
  }
  // the heart of the clover: sage at rest, a touch brighter once something is done
  ctx.beginPath(); ctx.arc(cx, cy, size * (f.small ? 0.05 : 0.042), 0, TAU);
  ctx.fillStyle = rgba(tone(mix(P.sage, P.tip, f.ripe * 0.5)), 1); ctx.fill();
  ctx.restore();
};

const MODE_FRAMES = Object.fromEntries(Object.keys(LOOKS).map(k => [k, cloverFrame]));
const presets = new Map();
// size: the page's drawing size (20, 32 or 64; anything else works too). Small orbs move a little less.
function resolvePreset(state, size) {
  const mode = LOOKS[state] ? state : LOOKS[ALIAS[state]] ? ALIAS[state] : 'idle', key = mode + '@' + size;
  if (!presets.has(key)) {
    const look = LOOKS[mode], small = size < 40;
    presets.set(key, { mode, speed: look.speed * (small ? 0.85 : 1),
      opts: { ...look, wave: look.wave * (small ? 0.8 : 1), levelReact: !!look.level, level: 0 } });
  }
  return presets.get(key);
}
export { MODE_FRAMES as M, paintFrame as p, resolvePreset as r };

// ─────────────────────────────── Answers: safe Markdown and a small TeX → MathML ───────────────────────────────
// TeX → MathML, laid out by WebKit itself. Covers what short answers use; anything unknown throws and the source shows instead.
const MML = 'http://www.w3.org/1998/Math/MathML';
// name → [kind, glyph]: i = identifier (mi), o = operator (mo), f = fence-ish operator that never stretches, b = big operator (limits)
const SYMBOLS = (() => {
  const table = {}, put = (kind, list) => list.trim().split(/\s+/).forEach(pair => { const k = pair.indexOf('='); table[pair.slice(0, k)] = [kind, pair.slice(k + 1)]; });
  put('i', 'alpha=α beta=β gamma=γ delta=δ epsilon=ϵ varepsilon=ε zeta=ζ eta=η theta=θ vartheta=ϑ iota=ι kappa=κ lambda=λ mu=μ nu=ν xi=ξ pi=π ' +
    'varpi=ϖ rho=ρ varrho=ϱ sigma=σ varsigma=ς tau=τ upsilon=υ phi=ϕ varphi=φ chi=χ psi=ψ omega=ω Gamma=Γ Delta=Δ Theta=Θ Lambda=Λ Xi=Ξ Pi=Π ' +
    'Sigma=Σ Upsilon=Υ Phi=Φ Psi=Ψ Omega=Ω infty=∞ partial=∂ nabla=∇ emptyset=∅ varnothing=∅ ell=ℓ hbar=ℏ aleph=ℵ Re=ℜ Im=ℑ R=ℝ N=ℕ Z=ℤ Q=ℚ C=ℂ');
  put('o', 'cdot=⋅ times=× div=÷ pm=± mp=∓ ast=∗ star=⋆ bullet=∙ le=≤ leq=≤ ge=≥ geq=≥ ll=≪ gg=≫ ne=≠ neq=≠ approx=≈ equiv=≡ sim=∼ simeq=≃ cong=≅ ' +
    'propto=∝ to=→ rightarrow=→ leftarrow=← gets=← leftrightarrow=↔ Rightarrow=⇒ Leftarrow=⇐ implies=⇒ impliedby=⇐ Leftrightarrow=⇔ iff=⇔ ' +
    'mapsto=↦ uparrow=↑ downarrow=↓ in=∈ notin=∉ ni=∋ subset=⊂ supset=⊃ subseteq=⊆ supseteq=⊇ cup=∪ cap=∩ setminus=∖ forall=∀ exists=∃ ' +
    'nexists=∄ angle=∠ circ=∘ degree=° cdots=⋯ ldots=… dots=… vdots=⋮ ddots=⋱ perp=⊥ parallel=∥ neg=¬ lnot=¬ land=∧ wedge=∧ lor=∨ vee=∨ ' +
    'oplus=⊕ otimes=⊗ mid=∣ prime=′ therefore=∴ because=∵ int=∫ iint=∬ iiint=∭ oint=∮ %=% $=$ #=# &=& _=_');
  put('f', 'langle=⟨ rangle=⟩ lfloor=⌊ rfloor=⌋ lceil=⌈ rceil=⌉ lvert=| rvert=| lVert=‖ rVert=‖ {={ }=} |=‖ vert=|');
  put('b', 'sum=∑ prod=∏ coprod=∐ bigcup=⋃ bigcap=⋂ bigoplus=⨁ lim=lim max=max min=min sup=sup inf=inf');
  for (const [k, v] of [['limsup', 'lim\u2009sup'], ['liminf', 'lim\u2009inf'], ['argmax', 'arg\u2009max'], ['argmin', 'arg\u2009min']]) table[k] = ['b', v];
  return table;
})();
const FUNCTIONS = new Set('sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth log ln lg exp det gcd deg arg dim ker hom Pr'.split(' '));
const GAPS = { ',': '0.1667em', ':': '0.2222em', '>': '0.2222em', ';': '0.2778em', '!': '-0.1667em', ' ': '0.25em', quad: '1em', qquad: '2em', enspace: '0.5em' };
const MARKS = { hat: ['^', 0], widehat: ['^', 1], bar: ['‾', 1], overline: ['‾', 1], vec: ['→', 0], overrightarrow: ['→', 1], tilde: ['~', 0], widetilde: ['~', 1], dot: ['˙', 0], ddot: ['¨', 0] };
const ENVIRONMENTS = { matrix: ['', ''], pmatrix: ['(', ')'], bmatrix: ['[', ']'], Bmatrix: ['{', '}'], vmatrix: ['|', '|'], Vmatrix: ['‖', '‖'], cases: ['{', ''],
  aligned: ['', ''], align: ['', ''], 'align*': ['', ''], gathered: ['', ''], gather: ['', ''], 'gather*': ['', ''], split: ['', ''], array: ['', ''] };
const NOOPS = new Set(['displaystyle', 'textstyle', 'scriptstyle', 'limits', 'nolimits', '\\', 'nonumber', 'notag']);

function texToMath(source, display) {
  if (source.length > 3000) throw Error('too long');
  const toks = [], spots = [];
  for (const m of source.matchAll(/\\(?:[A-Za-z]+\*?|.)|\d+(?:\.\d+)?|\S/g)) { toks.push(m[0]); spots.push(m.index); }
  let at = 0;
  const bad = () => { throw Error('tex'); };
  const mk = (tag, kids = [], attrs) => { const n = document.createElementNS(MML, tag); if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]); n.append(...kids); return n; };
  const wrap = list => list.length === 1 ? list[0] : mk('mrow', list);
  const fence = ch => mk('mo', [ch], { fence: 'true', stretchy: 'true' });
  // the source between the braces of the next {…}, exactly as typed (\text keeps its spaces)
  const verbatim = () => {
    if (toks[at] !== '{') bad();
    let depth = 0, end = at;
    for (; end < toks.length; end++) { if (toks[end] === '{') depth++; else if (toks[end] === '}' && --depth === 0) break; }
    if (end >= toks.length) bad();
    const text = source.slice(spots[at] + 1, spots[end]); at = end + 1;
    return text.replace(/\\(.)/g, '$1');
  };
  const delimiter = () => {
    const d = toks[at++]; if (d === undefined) bad();
    if (d === '.') return '';
    if (d[0] !== '\\') return d;
    const s = SYMBOLS[d.slice(1)]; return s ? s[1] : bad();
  };
  const sequence = stops => { const out = []; while (at < toks.length && !stops.includes(toks[at])) out.push(withScripts()); return wrap(out); };
  const argument = () => {   // {…} or a single atom; a number as an argument gives one digit (\frac12)
    if (toks[at] !== '{') return atom(true);
    at++; const inner = sequence(['}']); if (toks[at++] !== '}') bad(); return inner;
  };
  const atom = asArgument => {
    const tok = toks[at++];
    if (tok === undefined || tok === '}' || tok === '&') bad();
    if (tok === '{') { at--; return argument(); }
    if (/^\d/.test(tok)) {
      if (asArgument && tok.length > 1) { toks[--at] = tok.slice(1); spots[at]++; return mk('mn', [tok[0]]); }
      return mk('mn', [tok]);
    }
    if (tok[0] !== '\\') {
      if (/^[A-Za-z]$/.test(tok)) return mk('mi', [tok]);
      const glyph = { '-': '−', '*': '∗', "'": '′' }[tok] || tok;
      return mk('mo', [glyph], /^[()[\]|]$/.test(tok) ? { stretchy: 'false' } : undefined);   // only \left…\right grows
    }
    const name = tok.slice(1);
    switch (name) {
      case 'frac': case 'dfrac': case 'tfrac': case 'cfrac': return mk('mfrac', [argument(), argument()]);
      case 'binom': case 'dbinom': case 'tbinom': return wrap([mk('mo', ['(']), mk('mfrac', [argument(), argument()], { linethickness: '0' }), mk('mo', [')'])]);
      case 'sqrt': {
        if (toks[at] !== '[') return mk('msqrt', [argument()]);
        at++; const index = sequence([']']); if (toks[at++] !== ']') bad();
        return mk('mroot', [argument(), index]);
      }
      case 'text': case 'textrm': case 'textit': case 'mbox': case 'textnormal': return mk('mtext', [verbatim()]);
      case 'textbf': return mk('mtext', [verbatim()], { mathvariant: 'bold' });
      case 'mathrm': case 'operatorname': return mk('mi', [verbatim()], { mathvariant: 'normal' });
      case 'mathbb': { const s = SYMBOLS[verbatim()]; return s && s[0] === 'i' ? mk('mi', [s[1]]) : bad(); }
      case 'mathbf': case 'boldsymbol': case 'bm': { const g = argument(); g.setAttribute('mathvariant', 'bold'); return g; }
      case 'underline': return mk('munder', [argument(), mk('mo', ['_'], { stretchy: 'true' })], { accentunder: 'true' });
      case 'boxed': return mk('mrow', [argument()], { style: 'border: 1px solid; padding: 3px 5px' });
      case 'left': {
        const open = delimiter(), body = sequence(['\\right']); if (toks[at++] !== '\\right') bad();
        const close = delimiter();
        return wrap([open && fence(open), body, close && fence(close)].filter(Boolean));
      }
      case 'begin': {
        const env = verbatim(), sides = ENVIRONMENTS[env] || bad();
        if (env === 'array') verbatim();   // its column spec
        const rows = [[]];
        for (;;) {
          rows[rows.length - 1].push(sequence(['&', '\\\\', '\\end']));
          const sep = toks[at++];
          if (sep === '&') continue;
          if (sep === '\\\\') { rows.push([]); continue; }
          if (sep === '\\end') { verbatim(); break; }
          bad();
        }
        const attrs = /^(align|aligned|split)/.test(env) ? { columnalign: 'right left', columnspacing: '0' } : env === 'cases' ? { columnalign: 'left left' } : undefined;
        const kept = rows.filter(row => row.some(cell => cell.childNodes.length || cell.textContent));
        const table = mk('mtable', kept.map(row => mk('mtr', row.map(cell => mk('mtd', [cell])))), attrs);
        return wrap([sides[0] && fence(sides[0]), table, sides[1] && fence(sides[1])].filter(Boolean));
      }
    }
    if (MARKS[name]) { const [glyph, stretch] = MARKS[name]; return mk('mover', [argument(), mk('mo', [glyph], { stretchy: String(!!stretch) })], { accent: 'true' }); }
    if (name in GAPS) return mk('mspace', [], { width: GAPS[name] });
    if (NOOPS.has(name)) return mk('mrow');
    if (FUNCTIONS.has(name)) { const n = mk('mi', [name]); n.isFunction = true; return n; }
    const sym = SYMBOLS[name];
    if (!sym) bad();
    if (sym[0] === 'i') return mk('mi', [sym[1]]);
    if (sym[0] === 'b') { const n = mk('mo', [sym[1]], { movablelimits: 'true' }); n.takesLimits = true; return n; }
    return mk('mo', [sym[1]], sym[0] === 'f' ? { stretchy: 'false' } : undefined);
  };
  const withScripts = () => {
    const base = atom(false);
    let sub = null, sup = null;
    while (toks[at] === '_' && !sub || toks[at] === '^' && !sup) { if (toks[at++] === '_') sub = argument(); else sup = argument(); }
    let node = base;
    if (sub && sup) node = mk(base.takesLimits ? 'munderover' : 'msubsup', [base, sub, sup]);
    else if (sub) node = mk(base.takesLimits ? 'munder' : 'msub', [base, sub]);
    else if (sup) node = mk(base.takesLimits ? 'mover' : 'msup', [base, sup]);
    // \sin x: TeX's thin space after a function name, unless its argument is in parentheses
    return base.isFunction && toks[at] && toks[at] !== '(' ? mk('mrow', [node, mk('mspace', [], { width: '0.1667em' })]) : node;
  };
  const body = sequence([]);
  if (at < toks.length) bad();
  return mk('math', [body], display ? { display: 'block' } : { displaystyle: 'true' });   // inline fractions full size, as in a textbook
}
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const math = (src, display) => { try { return texToMath(src.trim(), display); } catch { return el('span', display ? 'tex block' : 'tex', src.trim()); } };   // unreadable TeX: what the model wrote

// ── inline: a small scanner, so the renderer and the streaming guard (shut) agree on exactly what is closed ──
const WORDY = /[\p{L}\p{N}_]/u;
const LINK_URL = /^(?:https?:|mailto:)[^\s)]+/;
// The span [start, end) of an inline construct opening at i, with what it holds; null when nothing (closed) opens here.
const spanAt = (s, i) => {
  const c = s[i], next = s[i + 1], prev = s[i - 1];
  const closeAt = (mark, from, test = () => true) => { for (let j = s.indexOf(mark, from); j >= 0; j = s.indexOf(mark, j + 1)) { if (s[j - 1] !== '\\' && test(j)) return j; } return -1; };
  if (c === '\\' && (next === '[' || next === '(')) {
    const end = s.indexOf(next === '[' ? '\\]' : '\\)', i + 2);
    if (end > i + 2) return { kind: next === '[' ? 'block' : 'math', start: i, end: end + 2, body: s.slice(i + 2, end) };
    return null;
  }
  if (c === '$' && prev !== '\\') {
    if (next === '$') {
      const end = closeAt('$$', i + 2);
      return end > i + 2 ? { kind: 'block', start: i, end: end + 2, body: s.slice(i + 2, end) } : null;
    }
    if (!next || /\s/.test(next)) return null;
    for (let j = i + 1; j < s.length; j++) {   // inline math: no line break inside, hugs its $ signs, and "$5 or $10" stays money
      if (s[j] === '\n') return null;
      if (s[j] === '\\') { j++; continue; }
      if (s[j] === '$') return !/\s/.test(s[j - 1]) && !/\d/.test(s[j + 1] || '') ? { kind: 'math', start: i, end: j + 1, body: s.slice(i + 1, j) } : null;
    }
    return null;
  }
  if (c === '*' && next === '*') {
    const end = s.indexOf('**', i + 2), body = s.slice(i + 2, end);
    return end > i + 2 && !body.includes('*') ? { kind: 'strong', start: i, end: end + 2, body } : null;
  }
  if (c === '~' && next === '~') {
    const end = s.indexOf('~~', i + 2), body = s.slice(i + 2, end);
    return end > i + 2 && !body.includes('\n') ? { kind: 'del', start: i, end: end + 2, body } : null;
  }
  if (c === '`') {
    const end = s.indexOf('`', i + 1);
    return end > i + 1 ? { kind: 'code', start: i, end: end + 1, body: s.slice(i + 1, end) } : null;
  }
  if (c === '[') {
    const close = s.indexOf(']', i + 1);
    if (close <= i + 1 || s[close + 1] !== '(' || s.slice(i + 1, close).includes('[')) return null;
    const url = s.slice(close + 2).match(LINK_URL)?.[0];
    return url && s[close + 2 + url.length] === ')' ? { kind: 'link', start: i, end: close + 3 + url.length, body: s.slice(i + 1, close), url } : null;
  }
  if (c === 'h' && /^https?:\/\//.test(s.slice(i, i + 8))) {
    let url = s.slice(i).match(/^https?:\/\/[^\s<>()]+/)[0];
    url = url.replace(/[.,;:!?'"]+$/, '');
    return url.length > 8 ? { kind: 'url', start: i, end: i + url.length, url } : null;
  }
  if (c === '*' && next && !/[\s*]/.test(next)) {
    const end = s.indexOf('*', i + 1);
    return end > i + 1 ? { kind: 'em', start: i, end: end + 1, body: s.slice(i + 1, end) } : null;
  }
  if (c === '_' && next && !/[\s_]/.test(next) && !(prev && (WORDY.test(prev) || prev === '\\'))) {
    const end = s.indexOf('_', i + 1);
    return end > i + 1 && !WORDY.test(s[end + 1] || '') ? { kind: 'em', start: i, end: end + 1, body: s.slice(i + 1, end) } : null;
  }
  return null;
};
const spans = s => { const out = []; for (let i = 0; i < s.length; i++) { const sp = spanAt(s, i); if (sp) { out.push(sp); i = sp.end - 1; } } return out; };
const inline = (parent, text) => {
  const plain = s => s.replace(/\\\$/g, '$').split('\n').forEach((line, k) => { if (k) parent.append(el('br')); if (line) parent.append(line); });   // a line break the model wrote stays one
  let from = 0;
  for (const sp of spans(text)) {
    plain(text.slice(from, sp.start)); from = sp.end;
    if (sp.kind === 'block' || sp.kind === 'math') parent.append(math(sp.body, sp.kind === 'block'));
    else if (sp.kind === 'code') parent.append(el('code', '', sp.body));
    else if (sp.kind === 'link') { const a = el('a', '', sp.body); a.href = a.title = sp.url; parent.append(a); }
    else if (sp.kind === 'url') { const a = el('a', '', sp.url); a.href = sp.url; parent.append(a); }
    else inline(parent.appendChild(el(sp.kind)), sp.body);   // strong, em, del
  }
  plain(text.slice(from));
  return parent;
};

// ── blocks ──
const LIST_ITEM = /^\s*([-*•+]|\d+[.)])\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const FENCE = /^\s*(```|~~~)\s*([\w+#.-]*)/;
const HEADING = /^\s*#{1,6}\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const cellsOf = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
const markdown = text => {
  const out = document.createDocumentFragment(), lines = String(text).replace(/\r/g, '').split('\n');
  const tableAt = i => TABLE_ROW.test(lines[i]) && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1] || '');
  const startsBlock = i => LIST_ITEM.test(lines[i]) || FENCE.test(lines[i]) || HEADING.test(lines[i]) || RULE.test(lines[i]) || QUOTE.test(lines[i]) || tableAt(i);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m = line.match(FENCE);
    if (m) {   // a fenced block keeps its lines exactly (code, a small text drawing)
      const body = [];
      while (++i < lines.length && !/^\s*(```|~~~)\s*$/.test(lines[i])) body.push(lines[i]);
      i++;
      const pre = el('pre', '', body.join('\n')); if (m[2]) pre.setAttribute('data-lang', m[2].toLowerCase());
      out.append(pre); continue;
    }
    if (tableAt(i)) {
      const box = el('div', 'table'), table = box.appendChild(el('table')), head = table.appendChild(el('tr'));
      cellsOf(lines[i]).forEach(c => head.append(inline(el('th'), c)));
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) { const tr = table.appendChild(el('tr')); cellsOf(lines[i++]).forEach(c => tr.append(inline(el('td'), c))); }
      out.append(box); continue;
    }
    if ((m = line.match(HEADING))) { out.append(inline(el('div', 'h'), m[1])); i++; continue; }
    if (RULE.test(line)) { out.append(el('hr')); i++; continue; }
    if ((m = line.match(LIST_ITEM))) {
      const numbered = /\d/.test(m[1]), list = el(numbered ? 'ol' : 'ul');
      if (numbered && parseInt(m[1]) !== 1) list.start = parseInt(m[1]);
      while (i < lines.length && (m = lines[i].match(LIST_ITEM)) && /\d/.test(m[1]) === numbered) { list.append(inline(el('li'), m[2])); i++; }
      out.append(list); continue;
    }
    if (QUOTE.test(line)) {
      const said = [];
      while (i < lines.length && (m = lines[i].match(QUOTE))) { said.push(m[1]); i++; }
      const q = el('blockquote'); q.append(...[...markdown(said.join('\n')).childNodes]); out.append(q); continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !(para.length && startsBlock(i))) para.push(lines[i++].trim());
    out.append(inline(el('p'), para.join('\n')));
  }
  return out;
};

// A streamed answer stops just before any mark that has not closed yet (**bold, `code, [link, ~~, $math), so marks never flash as
// symbols. Its last line decides, except display math ($$, \[, \() which may still be open lines back. Inside an open ``` all is text.
const shut = s => {
  if ((s.match(/^\s*(```|~~~)/gm) || []).length % 2) return s;
  const lineStart = s.lastIndexOf('\n') + 1, line = s.slice(lineStart);
  let blank = s;   // closed constructs blanked out, so only marks still open remain
  for (const sp of spans(s)) blank = blank.slice(0, sp.start) + ' '.repeat(sp.end - sp.start) + blank.slice(sp.end);
  const cuts = [];
  const pairs = (mark, str) => str.split(mark).length - 1;
  if (pairs('**', line) % 2) cuts.push(lineStart + line.lastIndexOf('**'));
  if (pairs('~~', line) % 2) cuts.push(lineStart + line.lastIndexOf('~~'));
  if (pairs('`', line) % 2) cuts.push(lineStart + line.lastIndexOf('`'));
  const bracket = line.search(/\[[^\]]*$/); if (bracket >= 0) cuts.push(lineStart + bracket);   // [1] or [ ] shows at once; a link still arriving waits
  const dollar = blank.slice(lineStart).search(/(?<!\\)\$(?![\d\s])/); if (dollar >= 0) cuts.push(lineStart + dollar);   // a $ before a digit is a price
  const block = blank.search(/(?<!\\)\$\$|\\[[(]/); if (block >= 0) cuts.push(block);
  return cuts.length ? s.slice(0, Math.min(...cuts)) : s;
};
export { MML, markdown, shut };
