// ADCG — second lot, tour 2 (runner GitHub) : ADCG55 seulement, contre le site RÉEL déployé (https://taqinor.ma).
// Une page locale du runner porte `<iframe src="https://taqinor.ma/embed/estimation">` ; Chromium doit charger le vrai
// widget dans le cadre, et refuser `<iframe src="https://taqinor.ma/devis/mon-toit">`. Aucun stub.
// Deux pages locales : en HTTPS (certificat auto-signé, c'est la forme d'un site partenaire : `frame-ancestors https:`)
// et en HTTP simple (127.0.0.1), la seconde à titre d'information consignée.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import http from 'node:http'
import https from 'node:https'
import { groupe } from './_oracles.js'

const etape = groupe('ADCG', ['ADCG55'])
test.describe.configure({ timeout: 300_000 })

const SITE = 'https://taqinor.ma'
const PAGE = (src, id) => `<!doctype html><meta charset="utf-8"><title>Site partenaire local</title>
<h1>Site partenaire (page locale du runner)</h1>
<iframe id="${id}" title="${id}" src="${src}" width="700" height="500"></iframe>`

function ecouter(serveur) {
  return new Promise((ok) => serveur.listen(0, '127.0.0.1', () => ok(serveur.address().port)))
}

etape('PF3.web.ADCG55-embed-site-reel', ['ADCG55'], async ({ page, context }) => {
  // Certificat auto-signé pour la page « partenaire » HTTPS locale.
  const dossier = mkdtempSync(join(tmpdir(), 'adcg55-'))
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', join(dossier, 'k.pem'), '-out', join(dossier, 'c.pem'),
    '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], { stdio: 'ignore' })
  const corps = { '/embed': PAGE(`${SITE}/embed/estimation`, 'embed'), '/devis': PAGE(`${SITE}/devis/mon-toit`, 'devis') }
  const repondre = (req, res) => {
    const c = corps[req.url.split('?')[0]] || corps['/embed']
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end(c)
  }
  const sHttps = https.createServer({ key: readFileSync(join(dossier, 'k.pem')), cert: readFileSync(join(dossier, 'c.pem')) }, repondre)
  const sHttp = http.createServer(repondre)
  const portHttps = await ecouter(sHttps)
  const portHttp = await ecouter(sHttp)
  try {
    // En-têtes RÉELS du site déployé (lecture directe, aucune interception).
    const reel = await fetch(`${SITE}/embed/estimation`, { redirect: 'follow' })
    const csp = reel.headers.get('content-security-policy') || ''
    console.log(`[ADCG55] site réel /embed/estimation : HTTP ${reel.status} ; CSP frame-ancestors = ${(csp.match(/frame-ancestors[^;]*/) || ['(absent)'])[0]} ; X-Frame-Options = ${reel.headers.get('x-frame-options')}`)
    const reelAutre = await fetch(`${SITE}/devis/mon-toit`, { redirect: 'follow' })
    console.log(`[ADCG55] site réel /devis/mon-toit : HTTP ${reelAutre.status} ; CSP frame-ancestors = ${((reelAutre.headers.get('content-security-policy') || '').match(/frame-ancestors[^;]*/) || ['(absent)'])[0]} ; XFO = ${reelAutre.headers.get('x-frame-options')}`)
    expect(csp, 'site réel : /embed/estimation sert `frame-ancestors https:`').toContain('frame-ancestors https:')
    expect(reel.headers.get('x-frame-options'), 'site réel : /embed/estimation sans X-Frame-Options').toBeNull()
    expect(reelAutre.headers.get('x-frame-options'), 'site réel : /devis/mon-toit garde DENY').toBe('DENY')

    // Page partenaire HTTPS locale : le VRAI widget se charge dans le cadre.
    const ctx = await page.context().browser().newContext({ ignoreHTTPSErrors: true })
    const p = await ctx.newPage()
    const console1 = []
    p.on('console', (m) => console1.push(`${m.type()}: ${m.text()}`))
    await p.goto(`https://127.0.0.1:${portHttps}/embed`)
    const cadre = await (async () => {
      for (let i = 0; i < 60; i += 1) {
        const f = p.frames().find((x) => x.url().startsWith(`${SITE}/embed/estimation`))
        if (f) return f
        await p.waitForTimeout(1000)
      }
      return null
    })()
    expect(cadre, `le cadre charge https://taqinor.ma/embed/estimation (frames : ${p.frames().map((f) => f.url()).join(' | ')})`).toBeTruthy()
    await cadre.waitForLoadState('load', { timeout: 60_000 })
    const texte = (await cadre.locator('body').innerText({ timeout: 30_000 })).trim()
    console.log(`[ADCG55] contenu du widget dans le cadre (${texte.length} car.) : ${texte.slice(0, 200).replace(/\s+/g, ' ')}`)
    expect(texte.length, 'le widget réel affiche du contenu dans le cadre').toBeGreaterThan(20)
    expect(await cadre.locator('form, input, button').count(), 'le widget réel porte ses champs / boutons').toBeGreaterThan(0)
    expect(console1.join('\n'), 'aucune erreur frame-ancestors / X-Frame-Options en console').not.toMatch(/frame-ancestors|X-Frame-Options/i)
    await p.screenshot({ path: join(dossier, 'embed.png') }).catch(() => undefined)

    // Témoin : /devis/mon-toit dans un cadre est BLOQUÉ.
    const p2 = await ctx.newPage()
    const console2 = []
    p2.on('console', (m) => console2.push(`${m.type()}: ${m.text()}`))
    await p2.goto(`https://127.0.0.1:${portHttps}/devis`)
    await p2.waitForTimeout(8000)
    const f2 = p2.frames().filter((x) => x !== p2.mainFrame())
    const urls2 = f2.map((x) => x.url())
    console.log(`[ADCG55] témoin /devis/mon-toit : frames=${urls2.join(' | ')} ; console=${console2.join(' | ').slice(0, 400)}`)
    for (const f of f2) {
      expect(f.url().startsWith(`${SITE}/devis/mon-toit`) && (await f.locator('body').innerText().catch(() => '')).trim().length > 20,
        '/devis/mon-toit ne se charge PAS dans le cadre').toBe(false)
    }
    expect(console2.join('\n'), 'le navigateur nomme le refus du cadre').toMatch(/frame-ancestors|X-Frame-Options|Refused to display/i)

    // Information : la même page en HTTP simple (hors forme d'un site partenaire HTTPS).
    const p3 = await ctx.newPage()
    await p3.goto(`http://127.0.0.1:${portHttp}/embed`)
    await p3.waitForTimeout(8000)
    const f3 = p3.frames().find((x) => x.url().startsWith(`${SITE}/embed/estimation`))
    const t3 = f3 ? (await f3.locator('body').innerText().catch(() => '')).trim().length : 0
    console.log(`[ADCG55] information : parent HTTP simple → cadre widget ${f3 ? `chargé (${t3} car.)` : 'absent/bloqué'}`)
    await ctx.close()
  } finally {
    sHttps.close(); sHttp.close()
  }
  // Page surveillée par les oracles : une page neutre (le contenu du site réel est jugé ci-dessus).
  await page.goto('about:blank')
})
