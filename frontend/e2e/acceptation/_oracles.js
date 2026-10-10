// AMET90 — harnais des specs d'acceptation : une ÉTAPE = un test Playwright qui
// observe les oracles qa-explorer 1-10 (numérotation de `_format.md`) sur
// chaque page qu'il ouvre, capture l'écran final et s'inscrit dans
// l'enregistrement du groupe (`_enregistrement.js`), PASS ou FAIL.
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test, expect } from '@playwright/test'
import { ORACLES, RACINE, cheminCapture, ecrire } from './_enregistrement.js'
import { TITRE_ECRAN_ERREUR } from '../helpers.js'

/** Observe une page : 1 (≥ 500), 2 (4xx), 3 (console.error / pageerror /
 *  rejet non géré), 4 (dialogue natif). `attendus` = [{ url: RegExp, statut }]
 *  : les SEULS échecs que l'étape injecte elle-même (jamais un joker). */
export class Suivi {
  constructor(origine) {
    this.origine = origine
    this.incidents = []
    this.pages = []
    this.verifies = new Set()
    this.attendus = []
  }

  attendre(url, statut) { this.attendus.push({ url, statut }) }

  // `statut` null = message console d'un échec réseau (seule l'URL compte).
  _attendu(url, statut) {
    return this.attendus.some((a) => a.url.test(url)
      && (statut === null || a.statut === undefined || a.statut === statut))
  }

  surveiller(page) {
    this.pages.push(page)
    page.on('response', (r) => {
      const s = r.status()
      if (s < 400 || !r.url().startsWith(this.origine) || this._attendu(r.url(), s)) return
      this.incidents.push({ oracle: s >= 500 ? '1' : '2', texte: `${r.request().method()} ${r.url()} → ${s}` })
    })
    page.on('console', (m) => {
      if (m.type() !== 'error') return
      // « Failed to load resource » d'un échec INJECTÉ par l'étape : attendu.
      if (/^Failed to load resource/.test(m.text()) && this._attendu(m.location()?.url || '', null)) return
      this.incidents.push({ oracle: '3', texte: `console.error : ${m.text()}` })
    })
    page.on('pageerror', (e) => this.incidents.push({ oracle: '3', texte: `pageerror : ${e.message}` }))
    page.on('dialog', async (d) => {
      this.incidents.push({ oracle: '4', texte: `dialogue natif ${d.type()} : ${d.message()}` })
      await d.dismiss().catch(() => undefined)
    })
    return page
  }

  /** Marque un oracle à vérification explicite (5 : liste après création…). */
  verifie(oracle) { this.verifies.add(String(oracle)) }

  async oracles() {
    const o = Object.fromEntries(ORACLES.map((k) => [k, 'NA']))
    for (const k of ['1', '2', '3', '4']) o[k] = 'PASS'
    for (const k of this.verifies) o[k] = 'PASS'
    o['8'] = 'PASS'
    for (const p of this.pages.filter((x) => !x.isClosed())) {
      if (await p.getByText(TITRE_ECRAN_ERREUR).count().catch(() => 0)) {
        this.incidents.push({ oracle: '8', texte: `écran cassé sur ${p.url()}` })
      }
    }
    for (const i of this.incidents) o[i.oracle] = 'FAIL'
    return o
  }
}

/** Fabrique d'étapes d'un groupe : `etape(id, taches, corps, options)` déclare
 *  un test ; `afterAll` écrit l'enregistrement (même si une étape a échoué : un
 *  FAIL reste une trace, il ne couvre rien).
 *  `options.ecart = { base: 'FAIL', raison }` — ÉCART ACCEPTÉ (`_format.md`) :
 *  l'étape échouait déjà à la base (`base_verdict`), ses tâches vont dans
 *  `couvre_avec_ecart` (et restent dans `couvre`). Seuls ses ORACLES peuvent
 *  alors échouer sans faire tomber le test ; une assertion de son corps qui
 *  échoue le fait toujours tomber. */
export function groupe(nom, couvre) {
  const etapes = []
  const ecarts = new Set()
  test.afterAll(() => {
    const sortie = ecrire({
      groupe: nom, couvre: [...new Set([...couvre, ...ecarts])], couvreAvecEcart: [...ecarts], etapes,
    })
    console.log(`[acceptation] ${sortie.verdict} — ${sortie.md}`)
  })
  return function etape(id, taches, corps, { ecart = null } = {}) {
    if (ecart && (ecart.base !== 'FAIL' || !String(ecart.raison || '').trim())) {
      throw new Error(`étape ${id} : un écart accepté exige { base: 'FAIL', raison }`)
    }
    if (ecart) taches.forEach((t) => ecarts.add(t))
    test(`${id} — ${taches.join(', ')}`, async ({ page, context }, testInfo) => {
      const suivi = new Suivi(new URL(testInfo.project.use.baseURL).origin)
      suivi.surveiller(page)
      let erreur = null
      try {
        await corps({ page, context, suivi, testInfo })
      } catch (e) {
        erreur = e
      }
      const oracles = await suivi.oracles()
      const trace = cheminCapture(nom, id)
      const absolu = join(RACINE, trace)
      mkdirSync(dirname(absolu), { recursive: true })
      const ouverte = suivi.pages.find((p) => !p.isClosed())
      if (ouverte) await ouverte.screenshot({ path: absolu, type: 'jpeg', quality: 60 }).catch(() => undefined)
      const ok = !erreur && !Object.values(oracles).includes('FAIL')
      etapes.push({
        id, taches, verdict: ok ? 'PASS' : 'FAIL', base_verdict: ecart ? ecart.base : null, trace, oracles,
        notes: [ecart ? `écart accepté (base FAIL) : ${ecart.raison}` : '',
          // eslint-disable-next-line no-control-regex -- couleurs ANSI de `expect`
          erreur ? `erreur : ${String(erreur.message).replace(/\u001b\[[0-9;]*m/g, '').split('\n')[0]}` : '',
          ...suivi.incidents.map((i) => `oracle ${i.oracle} — ${i.texte}`)].filter(Boolean).join(' ; '),
      })
      if (erreur) throw erreur
      if (ecart) {
        testInfo.annotations.push({ type: 'écart accepté', description: ecart.raison })
        return
      }
      expect(suivi.incidents, 'oracles durs 1-4 et 8').toEqual([])
    })
  }
}
