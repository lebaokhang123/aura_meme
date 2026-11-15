// Lucian UX/UI Prompt #363 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#363
// Lucian UX/UI Prompt #352 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#352
// Lucian UX/UI Prompt #226 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#226
// Lucian UX/UI Prompt #330 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#330
export const BACKGROUND_EFFECTS = Object.freeze(['violet-base', 'lucian-363', 'lucian-352-deep-sea', 'lucian-226', 'lucian-330']);

export function mountBackground(root, effect) {
  if (!BACKGROUND_EFFECTS.includes(effect) || effect === 'violet-base') return () => {};
  const canvas = root.querySelector('canvas');
  const cx = canvas?.getContext('2d');
  if (!cx) return () => {};
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  let W = 0, H = 0, mobile = false, state, raf = 0, last = 0, visible = true, disposed = false;
  let ptr = null, lastAdd = 0;
  const random = Math.random;
  function spawnFlow(p) {
    p.x = random() * W; p.y = random() * H; p.life = 60 + random() * 160; p.h = random(); return p;
  }
  function spawnStar(s, far) {
    s.x = (random() - .5) * 2 * W / 340; s.y = (random() - .5) * 2 * H / 330;
    s.z = far ? 1 : .05 + random() * .95; s.pz = s.z; return s;
  }
  function spawnBeam() {
    const v = random() < .5, line = (1 + Math.floor(random() * Math.max(1, (v ? W : H) / 34 - 1))) * 34 - 1;
    const dir = random() < .5 ? 1 : -1;
    state.beams.push({ v, l: line, p: dir > 0 ? -60 : (v ? H : W) + 60, d: dir, sp: 110 + random() * 90, len: 50 + random() * 40, c: ['129,140,248', '45,212,191', '244,114,182'][Math.floor(random() * 3)] });
  }
  function drawDots(now) {
    cx.clearRect(0, 0, W, H);
    state.waves = state.waves.filter(w => now - w.t < 2600);
    for (const d of state.dots) {
      let h = 0;
      for (const w of state.waves) {
        const age = (now - w.t) / 1000, k = Math.hypot(d[0] - w.x, d[1] - w.y) - age * 170;
        if (k > 0 || k < -90) continue;
        h += Math.sin(k / 14) * Math.exp(k / 60) * w.a * Math.exp(-age * 1.3);
      }
      const m = Math.max(-1, Math.min(1.6, h)), calm = Math.abs(m) < .04;
      cx.globalAlpha = calm ? .55 : 1;
      cx.fillStyle = calm ? state.idle : `hsl(${(230 - Math.max(0, m) * 110).toFixed(0)} 85% ${(58 - Math.min(0, m) * 10).toFixed(0)}%)`;
      cx.beginPath(); cx.arc(d[0], d[1] - m * 3, 1.6 + Math.max(0, m) * 3.4, 0, 6.2832); cx.fill();
    }
    cx.globalAlpha = 1;
  }
  function drawFlow(dt) {
    state.time += dt;
    const t = state.time;
    cx.globalAlpha = .07; cx.fillStyle = '#04121C'; cx.fillRect(0, 0, W, H); cx.globalAlpha = 1;
    const groups = [[], [], [], [], [], []];
    for (const p of state.particles) {
      const a = (Math.sin(p.x * .011 + t * .25) + Math.cos(p.y * .013 - t * .19) + Math.sin((p.x + p.y) * .006 + t * .12)) * Math.PI * .66;
      let vx = Math.cos(a) * 46, vy = Math.sin(a) * 46;
      if (ptr) {
        const dx = p.x - ptr.x, dy = p.y - ptr.y, d = Math.hypot(dx, dy);
        if (d < 95 && d > 1) { const f = (1 - d / 95) * 160; vx += -dy / d * f - dx / d * f * .25; vy += dx / d * f - dy / d * f * .25; }
      }
      const nx = p.x + vx * dt, ny = p.y + vy * dt;
      groups[Math.min(5, (p.h * 6) | 0)].push(p.x, p.y, nx, ny);
      p.x = nx; p.y = ny; p.life -= 1;
      if (p.life < 0 || nx < -5 || nx > W + 5 || ny < -5 || ny > H + 5) spawnFlow(p);
    }
    cx.lineWidth = 1.1; cx.lineCap = 'round';
    groups.forEach((g, k) => {
      cx.strokeStyle = `hsla(${(175 + 40 * k / 5).toFixed(0)},85%,${58 + k * 4}%,.55)`; cx.beginPath();
      for (let j = 0; j < g.length; j += 4) { cx.moveTo(g[j], g[j + 1]); cx.lineTo(g[j + 2], g[j + 3]); }
      cx.stroke();
    });
  }
  function drawBeams(dt) {
    state.acc += dt;
    if (state.acc > .42 && state.beams.length < (mobile ? 5 : 9)) { state.acc = 0; spawnBeam(); }
    cx.clearRect(0, 0, W, H);
    state.beams = state.beams.filter(b => b.d > 0 ? b.p < (b.v ? H : W) + 70 : b.p > -70);
    for (const b of state.beams) {
      b.p += b.d * b.sp * dt;
      const x0 = b.v ? b.l : b.p - b.d * b.len, y0 = b.v ? b.p - b.d * b.len : b.l, x1 = b.v ? b.l : b.p, y1 = b.v ? b.p : b.l;
      const gradient = cx.createLinearGradient(x0, y0, x1, y1);
      gradient.addColorStop(0, `rgba(${b.c},0)`); gradient.addColorStop(1, `rgba(${b.c},.95)`);
      cx.strokeStyle = gradient; cx.lineWidth = 1.6; cx.beginPath(); cx.moveTo(x0 + .5, y0 + .5); cx.lineTo(x1 + .5, y1 + .5); cx.stroke();
      cx.fillStyle = `rgba(${b.c},1)`; cx.shadowColor = `rgba(${b.c},1)`; cx.shadowBlur = 8;
      cx.beginPath(); cx.arc(x1 + .5, y1 + .5, 1.8, 0, 6.2832); cx.fill(); cx.shadowBlur = 0;
    }
  }
  function drawStars(dt) {
    const aim = ptr ? { x: (ptr.x / W - .5) * 2, y: (ptr.y / H - .5) * 2 } : { x: 0, y: 0 };
    state.steer.x += (aim.x - state.steer.x) * (1 - Math.pow(.05, dt));
    state.steer.y += (aim.y - state.steer.y) * (1 - Math.pow(.05, dt));
    cx.fillStyle = 'rgba(2,3,10,.9)'; cx.fillRect(0, 0, W, H); cx.lineCap = 'round';
    const ox = W / 2 + state.steer.x * 70, oy = H / 2 + state.steer.y * 60;
    // Ambient cruise preserves the original projection without making page controls trigger warp.
    for (const s of state.stars) {
      s.pz = s.z; s.z -= .22 * dt;
      if (s.z <= .02) { spawnStar(s, true); continue; }
      const x = ox + s.x / s.z * 150, y = oy + s.y / s.z * 150;
      const px = ox + s.x / (s.pz + .22 * .03) * 150, py = oy + s.y / (s.pz + .22 * .03) * 150;
      if (x < -20 || x > W + 20 || y < -20 || y > H + 20) { spawnStar(s, true); continue; }
      cx.strokeStyle = `rgba(255,255,255,${Math.min(1, (1 - s.z) * 1.4).toFixed(2)})`; cx.lineWidth = Math.max(.6, (1 - s.z) * 2.6);
      cx.beginPath(); cx.moveTo(px, py); cx.lineTo(x + .01, y); cx.stroke();
    }
  }
  function draw(now, dt) {
    if (effect === 'lucian-363') drawDots(now);
    else if (effect === 'lucian-352-deep-sea') drawFlow(Math.min(.04, dt));
    else if (effect === 'lucian-226') drawBeams(dt);
    else drawStars(dt);
  }
  function staticFrame() {
    if (effect === 'lucian-352-deep-sea') {
      cx.fillStyle = '#04121C'; cx.fillRect(0, 0, W, H);
      for (let k = 0; k < 120; k++) drawFlow(.016);
    } else draw(performance.now(), 0);
  }
  function stop() { if (raf) cancelAnimationFrame(raf); raf = 0; }
  function frame(now) {
    raf = 0;
    if (disposed || document.hidden || !visible || media.matches || !root.isConnected) return;
    const dt = Math.min(.05, Math.max(0, (now - last) / 1000)); last = now;
    draw(now, dt); raf = requestAnimationFrame(frame);
  }
  function run() {
    stop();
    if (disposed || document.hidden || !visible || !W || !H) return;
    if (media.matches) { staticFrame(); return; }
    last = performance.now(); raf = requestAnimationFrame(frame);
  }
  function resize() {
    if (disposed) return;
    const box = root.getBoundingClientRect(), width = Math.round(box.width), height = Math.round(box.height);
    if (width === W && height === H && state) return;
    stop(); W = width; H = height;
    if (!W || !H) return;
    mobile = W <= 768;
    // shortcut: full-screen canvases cap raster size at 4M pixels; raise after device profiling.
    const dpr = Math.min(mobile ? 1.25 : 2, window.devicePixelRatio || 1, Math.sqrt(4000000 / (W * H)));
    canvas.width = Math.max(1, Math.round(W * dpr)); canvas.height = Math.max(1, Math.round(H * dpr)); cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    state = { time: 0, dots: [], waves: [], particles: [], beams: [], stars: [], acc: 0, steer: { x: 0, y: 0 }, idle: getComputedStyle(root).getPropertyValue('--background-dot').trim() || '#948f9a' };
    if (effect === 'lucian-363') {
      const gap = Math.max(17, Math.ceil(Math.sqrt(W * H / (mobile ? 1600 : 6500))));
      for (let y = gap; y < H - 4; y += gap) for (let x = gap; x < W - 4; x += gap) state.dots.push([x, y]);
    } else if (effect === 'lucian-352-deep-sea') {
      for (let i = 0; i < (mobile ? 300 : 900); i++) state.particles.push(spawnFlow({}));
      cx.fillStyle = '#04121C'; cx.fillRect(0, 0, W, H);
    } else if (effect === 'lucian-226') {
      for (let i = 0; i < 4; i++) { spawnBeam(); state.beams[i].p = (state.beams[i].v ? H : W) * (.2 + i * .18); }
    } else for (let i = 0; i < (mobile ? 140 : 280); i++) state.stars.push(spawnStar({}, false));
    draw(performance.now(), 0); run();
  }
  function pointer(event) {
    if (disposed || media.matches || document.hidden || !visible || !state) return;
    const box = root.getBoundingClientRect(), x = event.clientX - box.left, y = event.clientY - box.top;
    if (x < 0 || y < 0 || x > box.width || y > box.height) { leave(); return; }
    ptr = { x: x * W / box.width, y: y * H / box.height };
    if (effect === 'lucian-226') { root.style.setProperty('--mx', `${ptr.x}px`); root.style.setProperty('--my', `${ptr.y}px`); }
    if (effect === 'lucian-363') {
      const now = performance.now();
      if (event.type === 'pointermove' && now - lastAdd < 110) return;
      lastAdd = now; state.waves.push({ ...ptr, t: now, a: event.type === 'pointerdown' ? 1.6 : .55 });
      if (state.waves.length > 14) state.waves.shift();
    }
  }
  function leave() { ptr = null; root.style.setProperty('--mx', '-200px'); root.style.setProperty('--my', '-200px'); }
  function pointerOut(event) { if (!event.relatedTarget) leave(); }
  function visibility() { leave(); run(); }
  function motion() { leave(); if (state) state.waves = []; run(); }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(root);
  const intersectionObserver = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; run(); });
  intersectionObserver.observe(root);
  window.addEventListener('resize', resize, { passive: true });
  window.addEventListener('pointermove', pointer, { passive: true });
  if (effect === 'lucian-363') window.addEventListener('pointerdown', pointer, { passive: true });
  window.addEventListener('pointerout', pointerOut, { passive: true });
  window.addEventListener('blur', leave);
  document.addEventListener('visibilitychange', visibility);
  media.addEventListener('change', motion);
  resize();
  return () => {
    disposed = true; stop(); resizeObserver.disconnect(); intersectionObserver.disconnect();
    window.removeEventListener('resize', resize); window.removeEventListener('pointermove', pointer); window.removeEventListener('pointerdown', pointer);
    window.removeEventListener('pointerout', pointerOut); window.removeEventListener('blur', leave);
    document.removeEventListener('visibilitychange', visibility); media.removeEventListener('change', motion); leave();
  };
}
