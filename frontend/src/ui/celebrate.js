// Fête « affaire signée » — le seul moment célébré de toute l'app (devis
// envoyé → accepté). Demande du fondateur (08/10/2026) : remplacer l'ancien
// burst de 14 points (VX40) par une VRAIE fête de plus de 30 secondes, qui
// cumule et dépasse ce que font les logiciels de référence :
//   • Odoo CRM      — le « rainbow man » quand une opportunité est gagnée
//                     (ici : couronne + soleil rayonnant, côté carte React) ;
//   • Salesforce    — les confettis du Path sur « Closed Won » ;
//   • Vtiger        — la pluie de confettis à la signature ;
//   • Monday.com    — les canons à confettis ;
//   • Asana         — les créatures qui traversent l'écran (licorne…).
// Plus : feux d'artifice (fusées, pivoines, saules dorés, anneaux, cœurs,
// crépitements), pluie d'émojis, grand final, et un son synthétisé (fanfare,
// détonations, applaudissements) — le tout sans aucune dépendance (canvas +
// Web Audio).
//
// Toujours : rien n'est posé sous `prefers-reduced-motion: reduce` (la carte
// React reste affichée, statique) ; une seule fête à la fois ; tout se nettoie
// à `stop()` (canvas retiré, audio fermé, boucle arrêtée).

export const PARTY_ID = 'deal-signed-party'
export const PARTY_DURATION_MS = 35000
const SPAWN_UNTIL_MS = 32000 // dernières 3 s : on laisse retomber
const MAX_PARTICLES = 2600

const CONFETTI_COLORS = ['#f5c542', '#ffd76a', '#e8a33d', '#3fa9f5', '#ff5fa2', '#7ce38b', '#b18cff', '#ffffff']
const FIREWORK_HUES = [45, 50, 200, 330, 280, 140, 15, 0]
const EMOJIS = ['👑', '💎', '🎉', '🥂', '☀️', '💰', '⭐', '🌟', '🎊', '✨']
const CREATURES = [
  { glyph: '🦄', rainbow: true },
  { glyph: '🚀', sparks: true },
  { glyph: '🦄', rainbow: true },
  { glyph: '🐬', sparks: true },
  { glyph: '🦋', rainbow: true },
]

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const rand = (a, b) => a + Math.random() * (b - a)
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)]

// ── Son : tout est synthétisé (aucun fichier audio) ─────────────────────────
function createSound() {
  const Ctx = typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext)
  if (!Ctx) return null
  let ctx
  try { ctx = new Ctx() } catch { return null }
  const master = ctx.createGain()
  master.gain.value = 0.22
  master.connect(ctx.destination)
  let muted = false

  const noiseBuffer = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate)
  const data = noiseBuffer.getChannelData(0)
  for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1

  function noise(at, dur, { freq = 800, q = 0.7, gain = 0.6, type = 'lowpass' } = {}) {
    const src = ctx.createBufferSource()
    src.buffer = noiseBuffer
    const f = ctx.createBiquadFilter()
    f.type = type
    f.frequency.value = freq
    f.Q.value = q
    const g = ctx.createGain()
    g.gain.setValueAtTime(gain, at)
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur)
    src.connect(f); f.connect(g); g.connect(master)
    src.start(at, Math.random()); src.stop(at + dur + 0.05)
  }

  function tone(at, freq, dur, { type = 'sawtooth', gain = 0.12, slideTo } = {}) {
    const o = ctx.createOscillator()
    o.type = type
    o.frequency.setValueAtTime(freq, at)
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, at + dur)
    const f = ctx.createBiquadFilter()
    f.type = 'lowpass'
    f.frequency.value = 2400
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.0001, at)
    g.gain.exponentialRampToValueAtTime(gain, at + 0.03)
    g.gain.setValueAtTime(gain, at + Math.max(0.04, dur - 0.08))
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur)
    o.connect(f); f.connect(g); g.connect(master)
    o.start(at); o.stop(at + dur + 0.05)
  }

  return {
    ctx,
    get muted() { return muted },
    setMuted(m) {
      muted = !!m
      master.gain.setTargetAtTime(muted ? 0 : 0.22, ctx.currentTime, 0.05)
    },
    resume() { if (ctx.state === 'suspended') ctx.resume().catch(() => {}) },
    // Fanfare d'ouverture : « ta-da-da-daaaa » cuivré (do-mi-sol-do).
    fanfare() {
      const t = ctx.currentTime + 0.05
      const notes = [[523.25, 0, 0.16], [659.25, 0.16, 0.16], [783.99, 0.32, 0.16], [1046.5, 0.5, 1.1]]
      notes.forEach(([f, d, dur]) => {
        tone(t + d, f, dur, { gain: 0.1 })
        tone(t + d, f / 2, dur, { type: 'square', gain: 0.04 })
      })
      // accord final tenu
      ;[523.25, 659.25, 783.99].forEach((f) => tone(t + 0.5, f, 1.2, { type: 'triangle', gain: 0.06 }))
    },
    launch() {
      const t = ctx.currentTime
      tone(t, rand(500, 800), rand(0.7, 1.1), { type: 'sine', gain: 0.025, slideTo: rand(1600, 2400) })
    },
    boom(big = false) {
      const t = ctx.currentTime
      noise(t, big ? 1.4 : 0.9, { freq: big ? 350 : 600, gain: big ? 0.9 : 0.55 })
      tone(t, big ? 90 : 120, 0.5, { type: 'sine', gain: big ? 0.35 : 0.2, slideTo: 40 })
    },
    crackle() {
      const t = ctx.currentTime
      for (let i = 0; i < 10; i += 1) {
        noise(t + 0.25 + Math.random() * 0.6, 0.03, { freq: 4000, type: 'highpass', gain: 0.25 })
      }
    },
    cannon() {
      const t = ctx.currentTime
      noise(t, 0.35, { freq: 1500, gain: 0.5, type: 'bandpass', q: 0.5 })
    },
    applause(seconds = 5) {
      const t = ctx.currentTime
      const claps = Math.round(seconds * 28)
      for (let i = 0; i < claps; i += 1) {
        const at = t + Math.random() * seconds
        const fade = 1 - (at - t) / seconds
        noise(at, 0.05, { freq: rand(1200, 2600), type: 'bandpass', q: 1.2, gain: 0.35 * fade + 0.05 })
      }
    },
    close() { try { ctx.close() } catch { /* déjà fermé */ } },
  }
}

// ── Particules ──────────────────────────────────────────────────────────────
function makeConfetti(x, y, angle, speed) {
  return {
    kind: 'confetti', x, y,
    vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
    w: rand(7, 13), h: rand(4, 8), rot: rand(0, Math.PI * 2), vr: rand(-0.25, 0.25),
    flip: rand(0, Math.PI * 2), vflip: rand(0.08, 0.2), wobble: rand(0, 10),
    color: pick(CONFETTI_COLORS), life: 0, maxLife: rand(260, 420), drag: 0.985, g: 0.12,
  }
}

function makeSpark(x, y, vx, vy, hue, opts = {}) {
  return {
    kind: 'spark', x, y, px: x, py: y, vx, vy, hue,
    light: opts.light ?? rand(55, 75), life: 0, maxLife: opts.maxLife ?? rand(55, 90),
    drag: opts.drag ?? 0.975, g: opts.g ?? 0.045, size: opts.size ?? rand(1.6, 2.6),
    crackle: !!opts.crackle, willow: !!opts.willow,
  }
}

function makeEmoji(w) {
  return {
    kind: 'emoji', glyph: pick(EMOJIS), x: rand(0, w), y: -40,
    vx: rand(-0.6, 0.6), vy: rand(1.2, 2.6), rot: rand(-0.4, 0.4), vr: rand(-0.03, 0.03),
    size: rand(22, 42), life: 0, maxLife: 900, drag: 1, g: 0.008,
  }
}

/**
 * celebrateDealSigned — lance LA fête (≥ 30 s). Renvoie un contrôleur
 * `{ stop, setMuted, muted, done }` ou `null` (reduced-motion / déjà en cours
 * / pas de DOM). À appeler UNIQUEMENT au point de confirmation de
 * l'acceptation d'un devis (via <DealSignedCelebration>).
 */
export function celebrateDealSigned({ durationMs = PARTY_DURATION_MS, sound = true, muted = false, mount } = {}) {
  if (typeof document === 'undefined') return null
  if (prefersReducedMotion()) return null
  if (document.getElementById(PARTY_ID)) return null

  const container = document.createElement('div')
  container.id = PARTY_ID
  container.setAttribute('aria-hidden', 'true')
  // Monté DANS la scène de la carte (par-dessus, clics traversants) si `mount`,
  // sinon par-dessus toute la page.
  container.style.cssText = mount
    ? 'position:absolute;inset:0;pointer-events:none;z-index:20'
    : 'position:fixed;inset:0;pointer-events:none;z-index:var(--z-toast, 9999)'
  const canvas = document.createElement('canvas')
  canvas.style.cssText = 'width:100%;height:100%;display:block'
  container.appendChild(canvas)
  ;(mount || document.body).appendChild(container)

  let ctx = null
  try { ctx = canvas.getContext('2d') } catch { ctx = null }

  const audio = sound ? createSound() : null
  if (audio) { audio.setMuted(muted); audio.resume() }

  let W = 0
  let H = 0
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    W = window.innerWidth
    H = window.innerHeight
    canvas.width = Math.round(W * dpr)
    canvas.height = Math.round(H * dpr)
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  window.addEventListener('resize', resize)

  const particles = []
  const rockets = []
  const creatures = []
  const add = (p) => { if (particles.length < MAX_PARTICLES) particles.push(p) }

  // Canon à confettis (Monday / Salesforce) depuis un coin bas.
  function cannon(side, power = 1) {
    const x = side === 'left' ? -10 : W + 10
    const base = side === 'left' ? -Math.PI / 3 : -2 * Math.PI / 3
    for (let i = 0; i < 110 * power; i += 1) {
      add(makeConfetti(x, H * 0.85, base + rand(-0.35, 0.35), rand(9, 19) * Math.sqrt(H / 800)))
    }
    audio?.cannon()
  }

  // Canon central vers le haut (ouverture / final).
  function centerBlast(count = 220) {
    for (let i = 0; i < count; i += 1) {
      add(makeConfetti(W / 2 + rand(-40, 40), H * 0.55, -Math.PI / 2 + rand(-1.1, 1.1), rand(6, 17)))
    }
  }

  const SHAPES = ['peony', 'peony', 'willow', 'ring', 'crossette', 'heart', 'double']
  function rocket(shape = pick(SHAPES), x = rand(W * 0.12, W * 0.88)) {
    const targetY = rand(H * 0.1, H * 0.42)
    const vy = -Math.sqrt(2 * 0.12 * (H - targetY)) * rand(0.98, 1.04)
    rockets.push({ x, y: H + 5, px: x, py: H + 5, vx: rand(-1.2, 1.2), vy, hue: pick(FIREWORK_HUES), shape, t: 0 })
    audio?.launch()
  }

  function explode(r) {
    const { x, y, hue, shape } = r
    const big = shape === 'double' || shape === 'heart'
    audio?.boom(big)
    if (shape === 'peony' || shape === 'double') {
      const n = shape === 'double' ? 140 : 100
      for (let i = 0; i < n; i += 1) {
        const a = rand(0, Math.PI * 2)
        const s = rand(1.5, 7.5)
        add(makeSpark(x, y, Math.cos(a) * s, Math.sin(a) * s, hue + rand(-12, 12)))
      }
      if (shape === 'double') {
        const hue2 = pick(FIREWORK_HUES)
        for (let i = 0; i < 70; i += 1) {
          const a = (i / 70) * Math.PI * 2
          add(makeSpark(x, y, Math.cos(a) * 3, Math.sin(a) * 3, hue2, { light: 85 }))
        }
      }
    } else if (shape === 'willow') {
      for (let i = 0; i < 110; i += 1) {
        const a = rand(0, Math.PI * 2)
        const s = rand(1, 5.5)
        add(makeSpark(x, y, Math.cos(a) * s, Math.sin(a) * s, 44, {
          light: rand(55, 70), maxLife: rand(130, 190), drag: 0.982, g: 0.03, willow: true, size: rand(1.4, 2.2),
        }))
      }
    } else if (shape === 'ring') {
      const tilt = rand(0.3, 1)
      for (let i = 0; i < 90; i += 1) {
        const a = (i / 90) * Math.PI * 2
        add(makeSpark(x, y, Math.cos(a) * 6, Math.sin(a) * 6 * tilt, hue, { maxLife: 75 }))
      }
    } else if (shape === 'crossette') {
      for (let i = 0; i < 80; i += 1) {
        const a = rand(0, Math.PI * 2)
        const s = rand(2, 6.5)
        add(makeSpark(x, y, Math.cos(a) * s, Math.sin(a) * s, hue, { crackle: true }))
      }
      audio?.crackle()
    } else if (shape === 'heart') {
      // Cœur pour la reine : x = 16 sin³t, y = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t
      for (let i = 0; i < 120; i += 1) {
        const t = (i / 120) * Math.PI * 2
        const hx = 16 * Math.sin(t) ** 3
        const hy = -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t))
        add(makeSpark(x, y, hx * 0.38, hy * 0.38, 340, { light: 70, g: 0.02, drag: 0.965, maxLife: 95 }))
      }
    }
    // Flash de détonation
    add({ kind: 'flash', x, y, life: 0, maxLife: 10, hue, size: big ? 120 : 80 })
  }

  function creature() {
    const c = CREATURES[creatures.length % CREATURES.length]
    const ltr = Math.random() < 0.5
    creatures.push({
      ...c, x: ltr ? -90 : W + 90, y: rand(H * 0.15, H * 0.6), dir: ltr ? 1 : -1,
      speed: rand(4.5, 6.5), phase: rand(0, 6), trail: [],
    })
  }

  // ── Chorégraphie (ms depuis le début) ─────────────────────────────────────
  const timeline = []
  const at = (ms, fn) => timeline.push({ ms, fn })
  at(0, () => { audio?.fanfare(); cannon('left', 1.3); cannon('right', 1.3); centerBlast(260) })
  at(300, () => { rocket('double', W * 0.3); rocket('double', W * 0.7) })
  at(900, () => audio?.applause(6))
  at(1200, () => rocket('heart', W / 2))
  for (let s = 4; s < 30; s += 4.5) {
    at(s * 1000, () => { cannon('left'); cannon('right') })
  }
  for (let s = 3; s < 30; s += 6.5) at(s * 1000, creature)
  // Salve au milieu (10 s) et cœurs (20 s)
  at(10000, () => { for (let i = 0; i < 7; i += 1) rocket(pick(SHAPES), (W * (i + 1)) / 8) })
  at(20000, () => { rocket('heart', W * 0.25); rocket('heart', W * 0.75) })
  at(20500, () => rocket('heart', W / 2))
  // GRAND FINAL 26 → 31 s
  for (let i = 0; i < 34; i += 1) at(26000 + i * 150, () => rocket())
  at(28000, () => audio?.applause(6))
  at(30500, () => { cannon('left', 1.6); cannon('right', 1.6); centerBlast(320) })
  at(31000, () => { rocket('double', W * 0.2); rocket('double', W * 0.5); rocket('double', W * 0.8) })
  timeline.sort((a, b) => a.ms - b.ms)

  let last = performance.now()
  let elapsed = 0
  let nextRocket = 1800
  let nextEmoji = 0
  let tlIndex = 0
  let raf = 0
  let stopped = false
  let resolveDone
  const done = new Promise((r) => { resolveDone = r })

  function step(p, k) {
    p.life += k
    if (p.kind === 'flash') return
    p.vx *= p.drag ** k
    p.vy = p.vy * p.drag ** k + p.g * k
    if (p.kind === 'confetti') {
      p.wobble += 0.1 * k
      p.x += (p.vx + Math.sin(p.wobble) * 0.6) * k
      p.y += p.vy * k
      if (p.vy > 2.2) p.vy = 2.2 + (p.vy - 2.2) * 0.9 // vitesse terminale : ça flotte
      p.rot += p.vr * k
      p.flip += p.vflip * k
    } else {
      if (p.kind === 'spark') { p.px = p.x; p.py = p.y }
      p.x += p.vx * k
      p.y += p.vy * k
      if (p.kind === 'emoji') p.rot += p.vr * k
      if (p.crackle && p.life > p.maxLife * 0.55 && !p.cracked) {
        p.cracked = true
        for (let i = 0; i < 4; i += 1) {
          add(makeSpark(p.x, p.y, rand(-2, 2), rand(-2, 2), 50, { light: 90, maxLife: 18, size: 1.3 }))
        }
      }
    }
  }

  function draw(p) {
    const fade = Math.max(0, 1 - p.life / p.maxLife)
    if (p.kind === 'confetti') {
      ctx.save()
      ctx.globalAlpha = Math.min(1, fade * 3)
      ctx.translate(p.x, p.y)
      ctx.rotate(p.rot)
      ctx.scale(1, Math.cos(p.flip))
      ctx.fillStyle = p.color
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h)
      ctx.restore()
    } else if (p.kind === 'spark') {
      ctx.globalAlpha = p.willow ? fade : fade ** 0.7
      ctx.strokeStyle = `hsl(${p.hue},100%,${p.light}%)`
      ctx.lineWidth = p.size
      ctx.beginPath()
      ctx.moveTo(p.px - p.vx * (p.willow ? 3 : 1.5), p.py - p.vy * (p.willow ? 3 : 1.5))
      ctx.lineTo(p.x, p.y)
      ctx.stroke()
      if (Math.random() < 0.08) { // scintillement
        ctx.fillStyle = '#fff'
        ctx.fillRect(p.x - 1, p.y - 1, 2, 2)
      }
    } else if (p.kind === 'flash') {
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size)
      g.addColorStop(0, `hsla(${p.hue},100%,90%,${0.7 * fade})`)
      g.addColorStop(1, `hsla(${p.hue},100%,60%,0)`)
      ctx.globalAlpha = 1
      ctx.fillStyle = g
      ctx.fillRect(p.x - p.size, p.y - p.size, p.size * 2, p.size * 2)
    } else if (p.kind === 'emoji') {
      ctx.save()
      ctx.globalAlpha = Math.min(1, fade * 4)
      ctx.translate(p.x, p.y)
      ctx.rotate(p.rot)
      ctx.font = `${p.size}px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(p.glyph, 0, 0)
      ctx.restore()
    }
  }

  function frame(now) {
    if (stopped) return
    // Temps de fête EFFECTIVEMENT affiché : onglet caché = fête en pause
    // (jamais un final « sauté » parce que la page était en arrière-plan).
    const dt = Math.min(50, now - last)
    elapsed += dt
    const k = dt / 16.67 // pas normalisé à 60 fps
    last = now

    while (tlIndex < timeline.length && timeline[tlIndex].ms <= elapsed) {
      timeline[tlIndex].fn()
      tlIndex += 1
    }
    if (elapsed < SPAWN_UNTIL_MS) {
      if (elapsed >= nextRocket) {
        rocket()
        nextRocket = elapsed + rand(450, 1100)
      }
      if (elapsed >= nextEmoji) {
        particles.push(makeEmoji(W))
        nextEmoji = elapsed + rand(160, 420)
      }
      // pluie d'or continue
      if (Math.random() < 0.5 * k) {
        add({ ...makeConfetti(rand(0, W), -10, Math.PI / 2, rand(1, 3)), color: pick(['#f5c542', '#ffd76a', '#ffffff']) })
      }
    }

    // fusées
    for (let i = rockets.length - 1; i >= 0; i -= 1) {
      const r = rockets[i]
      r.px = r.x; r.py = r.y
      r.x += r.vx * k
      r.y += r.vy * k
      r.vy += 0.12 * k
      r.t += k
      if (Math.random() < 0.6) {
        add(makeSpark(r.x, r.y, rand(-0.4, 0.4), rand(0.5, 1.5), 40, { light: 70, maxLife: 22, g: 0.02, size: 1.4 }))
      }
      if (r.vy >= -0.6) { explode(r); rockets.splice(i, 1) }
    }

    // créatures (Asana)
    for (let i = creatures.length - 1; i >= 0; i -= 1) {
      const c = creatures[i]
      c.x += c.speed * c.dir * k
      c.phase += 0.08 * k
      const y = c.y + Math.sin(c.phase) * 28
      c.trail.push({ x: c.x - 30 * c.dir, y: y + 8 })
      if (c.trail.length > 46) c.trail.shift()
      if (c.sparks && Math.random() < 0.7) {
        add(makeSpark(c.x - 34 * c.dir, y + 6, rand(-1, 1) - c.dir * 1.5, rand(-1, 1), pick([40, 15, 50]), { maxLife: 35 }))
      }
      c.drawY = y
      if ((c.dir > 0 && c.x > W + 120) || (c.dir < 0 && c.x < -120)) creatures.splice(i, 1)
    }

    for (let i = particles.length - 1; i >= 0; i -= 1) {
      const p = particles[i]
      step(p, k)
      if (p.life >= p.maxLife || p.y > H + 60 || p.x < -80 || p.x > W + 80) particles.splice(i, 1)
    }

    if (ctx) {
      ctx.clearRect(0, 0, W, H)
      ctx.globalCompositeOperation = 'source-over'
      for (const p of particles) if (p.kind === 'confetti' || p.kind === 'emoji') draw(p)
      ctx.globalCompositeOperation = 'lighter'
      for (const p of particles) if (p.kind === 'spark' || p.kind === 'flash') draw(p)
      ctx.lineCap = 'round'
      for (const r of rockets) {
        ctx.globalAlpha = 1
        ctx.strokeStyle = `hsl(${r.hue},100%,80%)`
        ctx.lineWidth = 2.5
        ctx.beginPath(); ctx.moveTo(r.px, r.py + 6); ctx.lineTo(r.x, r.y); ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
      for (const c of creatures) {
        if (c.rainbow) {
          const bands = ['#ff3b3b', '#ff9f1a', '#ffe14d', '#3ddc84', '#3fa9f5', '#9b5cff']
          bands.forEach((col, b) => {
            ctx.globalAlpha = 0.75
            ctx.strokeStyle = col
            ctx.lineWidth = 5
            ctx.beginPath()
            c.trail.forEach((pt, j) => {
              const yy = pt.y - 15 + b * 5
              if (j === 0) ctx.moveTo(pt.x, yy); else ctx.lineTo(pt.x, yy)
            })
            ctx.stroke()
          })
        }
        ctx.save()
        ctx.globalAlpha = 1
        ctx.translate(c.x, c.drawY)
        if (c.dir < 0) ctx.scale(-1, 1)
        ctx.font = '72px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        // les émojis regardent à gauche par défaut : on retourne pour aller à droite
        ctx.scale(-1, 1)
        ctx.fillText(c.glyph, 0, 0)
        ctx.restore()
      }
      ctx.globalAlpha = 1
    }

    if (elapsed >= durationMs && !particles.length && !rockets.length) { stop(); return }
    if (elapsed >= durationMs + 4000) { stop(); return }
    raf = window.requestAnimationFrame(frame)
  }

  function stop() {
    if (stopped) return
    stopped = true
    if (raf) window.cancelAnimationFrame(raf)
    window.removeEventListener('resize', resize)
    container.remove()
    audio?.close()
    resolveDone()
  }

  if (typeof window.requestAnimationFrame === 'function') {
    raf = window.requestAnimationFrame(frame)
  }

  return {
    stop,
    done,
    get muted() { return audio ? audio.muted : true },
    setMuted(m) { audio?.setMuted(m) },
    hasSound: !!audio,
  }
}

export default celebrateDealSigned
