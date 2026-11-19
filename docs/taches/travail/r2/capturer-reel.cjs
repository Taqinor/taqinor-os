// capturer-reel.cjs — capture le module Tâches sur l'écran RÉEL (pile locale r2), 4 vues par écran.
// Usage : node capturer-reel.cjs <compte> <dossier de sortie> [filtre d'écran (sous-chaînes séparées par ,)]
// Env : BASE (défaut http://127.0.0.1:5180), TACHES_DEMO_PASSWORD (sinon lu dans scratchpad/r2/env.local),
//       COMPTE_VIDE (défaut revide : compte semé --vide pour « aujourdhui-vide »).
// Aucune écriture durable : les écrans ouvrent des feuilles/menus sans valider ; la saisie n'est jamais envoyée.
const fs = require('fs')
const path = require('path')
const { chromium } = require('C:/dev/taqinor-os/frontend/node_modules/playwright')

const [compte, sortie, filtre] = process.argv.slice(2)
if (!compte || !sortie) { console.error('Usage : node capturer-reel.cjs <compte> <sortie> [filtre]'); process.exit(2) }
const BASE = process.env.BASE || 'http://127.0.0.1:5180'
const ENV_LOCAL = 'C:/Users/kasri/AppData/Local/Temp/claude/75bbe857427ccce5/b797bc27-f912-4ba8-a54b-d982221d7224/scratchpad/r2/env.local'
const MDP = process.env.TACHES_DEMO_PASSWORD
  || (fs.readFileSync(ENV_LOCAL, 'utf8').match(/^TACHES_DEMO_PASSWORD=(.*)$/m) || [])[1]
const COMPTE_VIDE = process.env.COMPTE_VIDE || 'revide'
const MAQ = 'docs/taches/maquettes/'
const filtres = filtre ? filtre.split(',') : null
const garde = (nom) => !filtres || filtres.some((f) => nom.includes(f))

// [appareil, thème, viewport, colorScheme, mobile]
const VUES = [
  ['iphone', 'clair', { width: 390, height: 844 }, 'light', true],
  ['iphone', 'sombre', { width: 390, height: 844 }, 'dark', true],
  ['bureau', 'clair', { width: 1440, height: 900 }, 'light', false],
  ['bureau', 'sombre', { width: 1440, height: 900 }, 'dark', false],
]
const COLLAGE = 'Salon Solaire Expo\nRéserver le stand\nImprimer les kakémonos\nPréparer la démo onduleur hybride'

const rest = async (p, ms = 700) => { await p.waitForLoadState('networkidle').catch(() => {}); await p.waitForTimeout(ms) }
const aller = async (p, url) => {
  await p.goto(BASE + url)
  await p.locator('.tch[data-ecran]').first().waitFor({ timeout: 20000 })
  await rest(p)
}
const esc = async (p) => { await p.keyboard.press('Escape').catch(() => {}); await p.waitForTimeout(250) }
const premiereLigne = (p) => p.locator('[data-ligne^="tache:"]').first()
const ajouter = (p) => p.getByRole('button', { name: 'Ajouter une tâche', exact: true }).first()
const ouvrirFiche = async (p) => {
  await aller(p, '/taches/aujourdhui')
  const l = premiereLigne(p); await l.waitFor()
  await l.locator('.titre').first().click()
  const f = p.locator('[data-fiche]').first(); await f.waitFor({ timeout: 8000 }); await rest(p)
  return f
}
const defiler = (p) => p.evaluate(() => {
  for (const e of document.querySelectorAll('*')) {
    if (e.scrollHeight > e.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(e).overflowY)) e.scrollTop = e.scrollHeight
  }
  window.scrollTo(0, 1e6)
})
const premierProjet = async (p) => {
  await aller(p, '/taches/projets')
  await p.locator('[data-projet] .ep-ouvrir').first().click()
  await p.waitForURL(/\/taches\/projets\/\d+/)
  await p.locator('.tch[data-ecran]').first().waitFor(); await rest(p)
}

// [nom, maquette (ou null), compte vide ?, async (p) => ouvre l'état]
const ECRANS = [
  ['aujourdhui-matin', 'ecran-aujourdhui-matin.html', false, async (p) => { await aller(p, '/taches/aujourdhui') }],
  ['aujourdhui-matin-bas', 'ecran-aujourdhui-matin-bas.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await defiler(p); await p.waitForTimeout(400) }],
  ['saisie-vide', 'ecran-saisie.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await ajouter(p).click()
    await p.getByRole('dialog', { name: 'Ajouter une tâche' }).waitFor(); await rest(p) }],
  ['saisie-phrase', 'ecran-saisie-nouveau.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await ajouter(p).click()
    const d = p.getByRole('dialog', { name: 'Ajouter une tâche' }); await d.waitFor()
    await d.getByRole('textbox', { name: 'Ajouter une tâche', exact: true }).fill('Appeler le fournisseur demain 10h #Salon')
    await rest(p, 900) }],
  ['saisie-coller-liste', 'ecran-saisie-liste.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await ajouter(p).click()
    const d = p.getByRole('dialog', { name: 'Ajouter une tâche' }); await d.waitFor()
    await d.getByRole('textbox', { name: 'Ajouter une tâche', exact: true }).fill(COLLAGE)
    await rest(p, 900) }],
  ['fiche-tache', 'ecran-fiche.html', false, async (p) => { await ouvrirFiche(p) }],
  ['fiche-tache-plus', 'ecran-fiche-plus.html', false, async (p) => {
    const f = await ouvrirFiche(p)
    await f.getByRole('button', { name: 'Plus', exact: true }).click(); await rest(p) }],
  ['menu-ligne', null, false, async (p) => {
    await aller(p, '/taches/aujourdhui'); const l = premiereLigne(p); await l.waitFor(); await l.hover()
    await l.getByRole('button', { name: /^Actions pour « / }).click({ force: true, timeout: 8000 }); await rest(p, 500) }],
  ['alleger-ma-journee', null, false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await p.getByRole('button', { name: "Plus d'actions" }).click()
    await p.getByRole('menuitem', { name: 'Alléger ma journée' }).click()
    await p.getByRole('dialog', { name: 'Alléger ma journée' }).waitFor(); await rest(p) }],
  ['bilan-du-soir', 'ecran-bilan.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui?ouvrir=bilan')
    await p.getByRole('dialog', { name: 'Bilan du soir' }).waitFor({ timeout: 10000 }); await rest(p) }],
  ['a-trier', 'ecran-a-trier.html', false, async (p) => { await aller(p, '/taches/a-trier') }],
  ['recherche', 'recherche.html', false, async (p) => { await aller(p, '/taches/recherche?q=devis'); await rest(p, 900) }],
  ['supprimees', 'supprimees.html', false, async (p) => { await aller(p, '/taches/supprimees') }],
  ['projets', 'projets-liste.html', false, async (p) => { await aller(p, '/taches/projets') }],
  ['projet', 'projet-liste.html', false, async (p) => { await premierProjet(p) }],
  ['projet-tableau', 'projet-tableau.html', false, async (p) => {
    await premierProjet(p)
    await p.goto(p.url().split('?')[0] + '?vue=tableau'); await p.locator('.tch[data-ecran]').first().waitFor(); await rest(p) }],
  ['planifier-le-projet', 'projet-planifier.html', false, async (p) => {
    // « Site web » est « À planifier » (jamais planifié, cf. seed_taches_demo) : le rituel s'y ouvre.
    await aller(p, '/taches/projets')
    await p.locator('[data-projet]').filter({ hasText: 'Site web' }).locator('.ep-ouvrir').first().click()
    await p.waitForURL(/\/taches\/projets\/\d+/)
    await p.goto(p.url().split('?')[0] + '?planifier=1')  // le rituel s'ouvre par ?planifier=1 (PlanifierProjet.jsx)
    await p.getByRole('region', { name: 'Planifier le projet' }).waitFor({ timeout: 10000 }); await rest(p) }],
  ['revue', 'revue-semaine.html', false, async (p) => { await aller(p, '/taches/revue') }],
  ['agenda-jour', 'agenda-jour.html', false, async (p) => {
    await aller(p, '/taches/agenda'); await p.getByRole('radio', { name: 'Jour', exact: true }).click(); await rest(p) }],
  ['agenda-semaine', 'agenda-semaine.html', false, async (p) => {
    await aller(p, '/taches/agenda'); await p.getByRole('radio', { name: 'Semaine', exact: true }).click(); await rest(p) }],
  ['agenda-mois', 'agenda-mois.html', false, async (p) => {
    await aller(p, '/taches/agenda'); await p.getByRole('radio', { name: 'Mois', exact: true }).click(); await rest(p) }],
  ['agenda-a-venir', 'agenda-a-venir.html', false, async (p) => {
    await aller(p, '/taches/agenda'); await p.getByRole('radio', { name: /^À venir/ }).click(); await rest(p) }],
  ['planifier-ma-semaine', 'agenda-semaine-planifier.html', false, async (p) => {
    // Le bouton de la Revue n'apparaît qu'après avoir décidé chaque projet (geste qui écrit) : on ouvre l'écran direct.
    await aller(p, '/taches/agenda?placer=1'); await rest(p, 900) }],
  ['mon-rythme', 'rythme.html', false, async (p) => { await aller(p, '/taches/rythme') }],
  ['reglages-liste', 'reglages.html', false, async (p) => { await aller(p, '/taches/reglages') }],
  ['reglages-vie-privee', 'reglages-vie-privee.html', false, async (p) => { await aller(p, '/taches/reglages/vie-privee') }],
  ['reglages-mon-iphone', 'mon-iphone.html', false, async (p) => { await aller(p, '/taches/reglages/iphone') }],
  ['reglages-notifications', 'reglages-notifications.html', false, async (p) => { await aller(p, '/taches/reglages/notifications') }],
  ['reglages-donnees', 'reglages-donnees.html', false, async (p) => { await aller(p, '/taches/reglages/donnees') }],
  ['copilote-depuis-taches', 'copilote.html', false, async (p) => {
    await aller(p, '/taches/aujourdhui'); await p.getByRole('button', { name: /Copilote/ }).first().click()
    await p.waitForTimeout(1500); await rest(p) }],
  ['aujourdhui-vide', 'ecran-aujourdhui-vide.html', true, async (p) => { await aller(p, '/taches/aujourdhui') }],
]

async function seConnecter(browser, utilisateur, [, , viewport, scheme, mobile]) {
  const ctx = await browser.newContext({
    viewport, colorScheme: scheme, locale: 'fr-FR', timezoneId: 'Africa/Casablanca', deviceScaleFactor: 2,
    isMobile: mobile, hasTouch: mobile,
  })
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('taqinor-theme', t)
      localStorage.setItem('taqinor-pwa-install-dismissed', '1')
      localStorage.setItem('taqinor:welcome:seen:v1', '1')
    } catch { /* mode privé */ }
  }, scheme)
  const p = await ctx.newPage()
  await p.goto(BASE + '/login')
  await p.getByPlaceholder('Entrez votre identifiant').fill(utilisateur)
  await p.locator('input[type="password"]').fill(MDP)
  await p.getByRole('button', { name: 'Se connecter →' }).click()
  await p.waitForURL((u) => !/\/login/.test(u.pathname), { timeout: 30000 })
  // Assistant de démarrage et visites guidées fermés, comme e2e/auth.setup.js (sinon ils recouvrent l'écran).
  try {
    const pr = await p.request.get('/api/django/onboarding/progress/')
    for (const it of ((await pr.json()).items ?? [])) {
      if (it.key === 'assistant_demarrage' && !it.fait) await p.request.post(`/api/django/onboarding/progress/${it.id}/ignorer/`)
    }
    for (const v of await (await p.request.get('/api/django/onboarding/tours/')).json()) {
      if (!v.vu) await p.request.post(`/api/django/onboarding/tours/${v.tour_key}/vu/`)
    }
  } catch { /* non bloquant */ }
  return { ctx, p }
}

// REGEN=1 : ne capture rien, reconstruit index.md d'après les PNG déjà présents dans <sortie>.
function ecrireIndex(lignes) {
  const par = {}
  for (const [nom, app, th, statut, detail, maq] of lignes) (par[nom] ||= { maq, vues: [] }).vues.push({ app, th, statut, detail })
  let md = `# Captures du module Tâches — pile locale r2 (compte ${compte})\n\nGénéré le ${new Date().toISOString()} par capturer-reel.cjs.\n\n`
  md += '| Écran | Maquette | iPhone clair | iPhone sombre | Bureau clair | Bureau sombre |\n|---|---|---|---|---|---|\n'
  const cell = (v) => (!v ? '—' : v.statut === 'OK' ? `[${v.detail}](${v.detail})` : `NON CAPTURÉ (${v.detail.replace(/\|/g, '/')})`)
  for (const nom of Object.keys(par)) {
    const g = (a, t) => par[nom].vues.find((v) => v.app === a && v.th === t)
    const m = par[nom].maq ? `${MAQ}${par[nom].maq}` : 'aucune maquette dédiée'
    md += `| ${nom} | ${m} | ${cell(g('iphone', 'clair'))} | ${cell(g('iphone', 'sombre'))} | ${cell(g('bureau', 'clair'))} | ${cell(g('bureau', 'sombre'))} |\n`
  }
  fs.writeFileSync(path.join(sortie, 'index.md'), md)
}
if (process.env.REGEN === '1') {
  const l = []
  for (const [nom, maq] of ECRANS) for (const [a, t] of VUES) {
    const f = `${nom}-${a}-${t}.png`
    l.push([nom, a, t, fs.existsSync(path.join(sortie, f)) ? 'OK' : 'NON CAPTURÉ', fs.existsSync(path.join(sortie, f)) ? f : 'voir le journal de capture', maq])
  }
  ecrireIndex(l); console.log('index reconstruit'); process.exit(0)
}

;(async () => {
  fs.mkdirSync(sortie, { recursive: true })
  const browser = await chromium.launch()
  const lignes = []
  for (const vue of VUES) {
    const [appareil, theme] = vue
    for (const vide of [false, true]) {
      const aFaire = ECRANS.filter((e) => e[2] === vide && garde(e[0]))
      if (!aFaire.length) continue
      let session
      try { session = await seConnecter(browser, vide ? COMPTE_VIDE : compte, vue) } catch (e) {
        for (const e2 of aFaire) lignes.push([e2[0], appareil, theme, 'ECHEC', `connexion impossible : ${String(e.message).split('\n')[0]}`, e2[1]])
        continue
      }
      const { ctx, p } = session
      const erreurs = []
      p.on('pageerror', (e) => erreurs.push(String(e.message).slice(0, 120)))
      for (const [nom, maq, , etat] of aFaire) {
        const fichier = `${nom}-${appareil}-${theme}.png`
        try {
          await etat(p)
          await p.screenshot({ path: path.join(sortie, fichier) })
          lignes.push([nom, appareil, theme, 'OK', fichier, maq])
          console.log('OK  ', fichier)
        } catch (e) {
          const raison = String(e.message).split('\n')[0].slice(0, 200)
          try { await p.screenshot({ path: path.join(sortie, 'echec-' + fichier) }) } catch { /* */ }
          lignes.push([nom, appareil, theme, 'NON CAPTURÉ', raison, maq])
          console.log('FAIL', fichier, raison)
        }
        await esc(p)
      }
      if (erreurs.length) console.log(`pageerror ${appareil}/${theme}:`, [...new Set(erreurs)].slice(0, 5))
      await ctx.close()
    }
  }
  await browser.close()
  const par = {}
  for (const [nom, app, th, statut, detail, maq] of lignes) (par[nom] ||= { maq, vues: [] }).vues.push({ app, th, statut, detail })
  let md = `# Captures du module Tâches — pile locale r2 (compte ${compte})\n\nGénéré le ${new Date().toISOString()} par capturer-reel.cjs.\n\n`
  md += '| Écran | Maquette | iPhone clair | iPhone sombre | Bureau clair | Bureau sombre |\n|---|---|---|---|---|---|\n'
  const cell = (v) => (!v ? '—' : v.statut === 'OK' ? `[${v.detail}](${v.detail})` : `NON CAPTURÉ (${v.detail.replace(/\|/g, '/')})`)
  for (const nom of Object.keys(par)) {
    const g = (a, t) => par[nom].vues.find((v) => v.app === a && v.th === t)
    const m = par[nom].maq ? `${MAQ}${par[nom].maq}` : 'aucune maquette dédiée'
    md += `| ${nom} | ${m} | ${cell(g('iphone', 'clair'))} | ${cell(g('iphone', 'sombre'))} | ${cell(g('bureau', 'clair'))} | ${cell(g('bureau', 'sombre'))} |\n`
  }
  fs.writeFileSync(path.join(sortie, 'index.md'), md)
  const n = lignes.filter((l) => l[3] === 'OK').length
  console.log(`\n${n} captures, ${lignes.length - n} non capturées. Index : ${path.join(sortie, 'index.md')}`)
})()
