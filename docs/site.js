// Clover's website: what every page shares. MIT, like the app.
export const reduced = matchMedia('(prefers-reduced-motion: reduce)');

// A spring in Apple's two numbers: response (seconds, how quickly it gets there) and damping (1 = no overshoot, lower = bouncier).
// It starts from wherever the value is and at the speed it was going, so a gesture hands over without a seam and can grab it again.
export const spring = ({ from, to, v = 0, response = .38, damping = 1, update, done }) => {
  const s = { x: from, v }, w = 2 * Math.PI / response; let last = performance.now(), id = 0;
  const step = now => {
    for (let left = Math.min(.05, (now - last) / 1000); left > 1e-6; left -= .008) {
      const h = Math.min(.008, left); s.v += (w * w * (to - s.x) - 2 * damping * w * s.v) * h; s.x += s.v * h;
    }
    last = now; update(s.x, s.v);
    if (Math.abs(s.x - to) < .3 && Math.abs(s.v) < 6) { update(to, 0); id = 0; done?.(); } else id = requestAnimationFrame(step);
  };
  id = requestAnimationFrame(step);
  return { stop: () => { cancelAnimationFrame(id); id = 0; return s; }, get running() { return !!id; } };
};
// Where a flick at v px/s comes to rest (Apple's projection; .99 is a snappy deceleration)
export const project = (v, rate = .99) => v / 1000 * rate / (1 - rate);
// Past an edge it keeps following, ever more reluctantly
export const rubber = (d, dim) => Math.sign(d) * dim * (1 - 1 / (Math.abs(d) * .55 / dim + 1));

// The nav turns to glass once there is something to scroll under it
const nav = document.querySelector('.nav');
if (nav) { const paint = () => nav.classList.toggle('scrolled', scrollY > 8); addEventListener('scroll', paint, { passive: true }); paint(); }

// Rise in once, as they arrive
const seen = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); seen.unobserve(e.target); } }), { rootMargin: '0px 0px -8% 0px' });
document.querySelectorAll('.reveal').forEach(el => seen.observe(el));

// Copy buttons: data-copy holds the text, or the nearest code element does
document.addEventListener('click', async e => {
  const b = e.target.closest('.copy'); if (!b) return;
  const text = b.dataset.copy || b.parentElement.querySelector('code')?.textContent || '';
  try { await navigator.clipboard.writeText(text); } catch { return; }
  const was = b.textContent; b.textContent = 'Copied'; b.classList.add('done');
  setTimeout(() => { b.textContent = was; b.classList.remove('done'); }, 1400);
});

// Download buttons point at the newest release's zip once GitHub says which it is; until then (or offline) at the release page
const REPO = 'joinhackyard/clover';
fetch(`https://api.github.com/repos/${REPO}/releases/latest`, { headers: { Accept: 'application/vnd.github+json' } })
  .then(r => r.ok ? r.json() : null)
  .then(release => {
    if (!release) return;
    const zip = release.assets?.find(a => /-macOS\.zip$/.test(a.name));
    if (zip) document.querySelectorAll('[data-download]').forEach(a => a.href = zip.browser_download_url);
    document.querySelectorAll('[data-version]').forEach(el => el.textContent = release.tag_name);
    const mb = zip ? (zip.size / 1048576).toFixed(1) + ' MB' : '';
    document.querySelectorAll('[data-size]').forEach(el => el.textContent = mb);
  })
  .catch(() => {});
