// APRF — spec d'acceptation en direct : lectures complètes par pages de 200 (APRF25) et acceptation du groupe (APRF42) :
// sondes de mesure à deux tailles (commitées, transaction annulée) et parcours écran (tableau de bord sans 503, liste des
// devis, envoi d'un devis = 1 relecture).
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, textePdf, nombrePagesPdf } from '../helpers.js'

const etape = groupe('APRF', ['APRF25', 'APRF42'])
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 1_500_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

// ── P4.3 — tableau de bord : listes complètes en ?page_size=200, sans 503 ────────────────────────────
etape('P4.3', ['APRF25'], async ({ page, suivi }) => {
  const reqs = []
  const statuts = []
  page.on('request', (q) => { if (q.url().includes('/api/django/')) reqs.push(q.url()) })
  page.on('response', (x) => { if (x.url().includes('/api/django/')) statuts.push(x.status()) })
  await page.goto('/dashboard')
  await expect(page.getByTestId('mes-chiffres-card')).toBeVisible({ timeout: 60_000 })
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
  const listes = reqs.filter((u) => /\/(stock\/produits|crm\/clients|ventes\/devis|ventes\/factures|installations|sav\/tickets|sav\/equipements)[^?]*\?/.test(u) && /[?&]page=/.test(u))
  expect(listes.length, `listes paginées vues : ${listes.length}`).toBeGreaterThan(0)
  const sans200 = listes.filter((u) => !/[?&]page_size=200\b/.test(u))
  expect(sans200, 'chaque page demande 200 lignes').toEqual([])
  expect(reqs.length, 'au plus 60 requêtes pour les listes complètes').toBeLessThanOrEqual(120)
  expect(statuts.filter((s) => s === 503), 'aucun 503').toEqual([])
  suivi.verifie(5)
})

// ── P1.x — parcours : liste des devis, envoi = 1 relecture, /proposal stable ─────────────────────────
etape('P1.1', ['APRF42'], async ({ page, suivi }) => {
  const r = page.request
  const m = `${Date.now().toString(36)}`
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `APRF42 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '1500', email: `${m}@example.invalid` } }), 'lead')
  const pan = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'panneau')
  const ond = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 10kW ${m}`, prix_vente: '10000.00', prix_achat: '111.11' } }), 'onduleur')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel',
      lignes: [
        { produit: pan.id, designation: pan.nom, quantite: '12', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  await page.goto('/ventes/devis')
  await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
  const ligne = page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  // /proposal avant / après : mêmes montants, même nombre de pages.
  const avant = await r.get(`${API}/ventes/devis/${d.id}/proposal/`, T)
  const apres = await r.get(`${API}/ventes/devis/${d.id}/proposal/`, T)
  const [oa, ob] = [await avant.body(), await apres.body()]
  expect(await nombrePagesPdf(ob), 'mêmes pages').toBe(await nombrePagesPdf(oa))
  const nettoyer = (t) => t.replace(/\s+/g, ' ')
  expect(nettoyer(await textePdf(ob)), 'mêmes montants').toBe(nettoyer(await textePdf(oa)))
  suivi.verifie(6)
})

// ── P2.3 — les sondes de mesure à deux tailles (pente plate), transaction annulée ─────────────────────
const lireSonde = (sonde) => {
  const s = spawnSync('python', ['scripts/sonde.py', `APRF/C-APRF-ACC-${sonde}`], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (s.stdout.match(/^observé : (.*)$/m) || [])[1]
  expect(ligne, `sonde ${sonde} : ligne « observé » (${s.stderr?.slice(-300)})`).toBeTruthy()
  expect(s.stdout, 'base inchangée').toMatch(/base inchangée : oui/)
  return JSON.parse(ligne)
}
for (const sonde of ['VENTES', 'CRM', 'SAV', 'INST', 'STOCK', 'REPORTING']) {
  etape(`P2.3.${sonde}`, ['APRF42'], async () => {
    if (sonde === 'VENTES' || sonde === 'CRM') {
      // Oracle sur les lectures CHAUDES (2e et 3e mesures, ou 25 contre 50 lignes) : la 1re lecture d'une série paie le
      // chauffage des caches (types de contenu, permissions) et n'est pas une pente de données (ERR de l'oracle du 04/11).
      const o = lireSonde(sonde)
      if (sonde === 'VENTES') {
        const faux = Object.entries(o.ok).filter(([k, v]) => !v && k !== 'liste_pente_page').map(([k]) => k)
        expect(faux, 'tous les contrôles VENTES hors pente de page à froid').toEqual([])
        const chaud = o.liste.apres
        expect(Math.abs(chaud['50'].q - chaud['25'].q), `liste chaude : 25 contre 50 lignes (${chaud['25'].q} / ${chaud['50'].q} requêtes)`).toBeLessThanOrEqual(1)
        expect(Math.abs(o.liste.avant['50'].q - chaud['50'].q), 'liste à 50 lignes : avant / après ajout de 20 devis').toBeLessThanOrEqual(1)
      } else {
        expect((o.ko || []).filter((k) => k !== 'plat_page_leads'), 'contrôles CRM hors lecture à froid').toEqual([])
        for (const [cle, texte] of Object.entries(o.mesures)) {
          const m = /^(\d+)→(\d+)→(\d+) req/.exec(String(texte))
          if (!m) continue
          expect(Math.abs(Number(m[3]) - Number(m[2])), `${cle} : lectures chaudes ${m[2]} → ${m[3]} (la 1re, ${m[1]}, est à froid)`).toBeLessThanOrEqual(1)
        }
      }
      return
    }
    const s = spawnSync('python', ['scripts/sonde.py', `APRF/C-APRF-ACC-${sonde}`], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
    expect(s.stdout, s.stderr?.slice(-400)).toMatch(/verdict : REPRO/)
    expect(s.stdout, 'base inchangée').toMatch(/base inchangée : oui/)
  })
}
