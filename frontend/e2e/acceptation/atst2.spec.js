// Preuves en direct du groupe ATST (audit PF7 « tests qui ne prouvent rien », dossier docs/audits/2026-11-11-parcours-PF7.md),
// lot 2 (vague 6, runner GitHub, 16/11/2026) : ATST56 (la composition par défaut du générateur n'est pas une saisie) et
// ATST23 (le prix catalogue barré et le prix remisé de chaque ligne du document premium et une-page, sur le HTML rendu
// par le moteur — rejeu du geste de la classe NON taguée `TestHtmlRemiseParLigne`, contre un devis RÉEL de la base).
// ATST54 (servir apps/web dans l'e2e par fusion) n'est pas jouée ici : sa preuve est le rapport Playwright du check requis
// `e2e` de la PR et du nocturne (YAML de ci.yml / release-verify.yml, jamais ce runner).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ATST', ['ATST56', 'ATST23'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const CLE = 'taqinor:draft:devis:new'
const LIGNES = 'table.lines-table tbody tr[data-line-key]'
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

/** Onglet observé comme `suivi.surveiller` (oracles 1-3), SAUF le dialogue `beforeunload` : c'est précisément ce que
 *  l'étape compte (la confirmation du navigateur à la fermeture). Tout AUTRE dialogue natif reste un incident (oracle 4). */
function ongletObserve(onglet, suivi, origine, vus) {
  onglet.on('response', (r) => {
    const s = r.status()
    if (s >= 400 && r.url().startsWith(origine)) {
      suivi.incidents.push({ oracle: s >= 500 ? '1' : '2', texte: `${r.request().method()} ${r.url()} → ${s}` })
    }
  })
  onglet.on('console', (msg) => {
    if (msg.type() === 'error') suivi.incidents.push({ oracle: '3', texte: `console.error : ${msg.text()}` })
  })
  onglet.on('pageerror', (e) => suivi.incidents.push({ oracle: '3', texte: `pageerror : ${e.message}` }))
  onglet.on('dialog', async (d) => {
    if (d.type() === 'beforeunload') {
      vus.push(d.type())
      await d.accept().catch(() => undefined) // « Quitter » : l'onglet se ferme
      return
    }
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
}

// ═══ ATST56 — générateur vierge sur /ventes/devis/nouveau : ni garde de sortie ni brouillon ; une ligne par défaut modifiée les arme ═══
etape('PF7.4-ATST56', ['ATST56'], async ({ page, context, suivi, testInfo }) => {
  const origine = new URL(testInfo.project.use.baseURL).origin
  // Given : aucun brouillon de création dans ce navigateur.
  await page.goto('/dashboard')
  await page.evaluate((k) => window.localStorage.removeItem(k), CLE)

  // (1) Monté vierge, composition par défaut posée, RIEN saisi : la clé reste absente, la fermeture n'est pas gardée.
  const vus1 = []
  const vierge = await context.newPage()
  ongletObserve(vierge, suivi, origine, vus1)
  await vierge.goto('/ventes/devis/nouveau')
  await expect(vierge.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await expect(vierge.locator(LIGNES).first(), 'la composition par défaut est posée (lignes `compose`)').toBeVisible({ timeout: 60_000 })
  const nbParDefaut = await vierge.locator(LIGNES).count()
  expect(nbParDefaut, 'composition par défaut : plusieurs lignes').toBeGreaterThan(1)
  await vierge.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await vierge.waitForTimeout(2_500) // 1,7 s de composition comme ATST27, plus la marge de l'écriture du brouillon
  const ecrite = await vierge.evaluate((k) => window.localStorage.getItem(k), CLE)
  console.log(`[ATST56] ${nbParDefaut} lignes par défaut ; clé ${CLE} après composition : ${ecrite ? 'ÉCRITE' : 'absente'}`)
  expect(ecrite, `la clé ${CLE} reste absente après la composition par défaut`).toBeNull()
  await vierge.close({ runBeforeUnload: true })
  await expect.poll(() => vierge.isClosed(), { timeout: 15_000, message: 'l\'onglet vierge se ferme sans confirmation' }).toBe(true)
  expect(vus1.length, 'aucun beforeunload demandé à la fermeture d\'un générateur vierge').toBe(0)

  // Persistance : rouvert, aucun brouillon n'est proposé.
  await page.goto('/ventes/devis/nouveau')
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator(LIGNES).first()).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(2_500)
  await expect(page.getByTestId('draft-restore-banner'), 'rouvert : aucun « Reprendre le brouillon » proposé').toHaveCount(0)
  expect(await page.evaluate((k) => window.localStorage.getItem(k), CLE), 'rouvert : la clé est toujours absente').toBeNull()

  // (2) Contrôle : modifier une ligne PAR DÉFAUT arme la garde et écrit le brouillon.
  const vus2 = []
  const touche = await context.newPage()
  ongletObserve(touche, suivi, origine, vus2)
  await touche.goto('/ventes/devis/nouveau')
  await expect(touche.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await expect(touche.locator(LIGNES).first()).toBeVisible({ timeout: 60_000 })
  await touche.waitForTimeout(2_500)
  const designation = `ATST56 modifiée ${marque()}`
  const champ = touche.locator(LIGNES).first().locator('td[data-label="Désignation"] input')
  await champ.click()
  await champ.fill(designation)
  await expect(champ).toHaveValue(designation)
  await expect.poll(async () => touche.evaluate((k) => {
    try { return (JSON.parse(window.localStorage.getItem(k) || 'null')?.data?.lines || []).map((l) => l.designation) } catch { return [] }
  }, CLE), { timeout: 20_000, message: 'brouillon écrit avec la désignation modifiée d\'une ligne par défaut' }).toContain(designation)
  await touche.close({ runBeforeUnload: true })
  await expect.poll(() => vus2.length, { timeout: 15_000, message: 'beforeunload demandé après la modification d\'une ligne par défaut' }).toBeGreaterThan(0)
  await expect.poll(() => touche.isClosed(), { timeout: 15_000 }).toBe(true)
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByTestId('draft-restore-banner'), 'rouvert : le brouillon de la ligne modifiée est proposé').toBeVisible({ timeout: 30_000 })
  await page.evaluate((k) => window.localStorage.removeItem(k), CLE)
})

// ═══ ATST23 — le prix catalogue barré et le prix remisé de chaque ligne, sur le HTML rendu par le moteur (premium et une-page) ═══
const LIGNES_DEVIS = [
  ['Onduleur réseau 10kW', '1', '12000'], ['Onduleur hybride 5kW', '1', '24000'], ['Panneau mono 550W', '14', '1100'],
  ['Batterie 5 kWh', '1', '14000'], ['Structures acier', '14', '375'], ['Installation', '1', '4000'], ['Transport', '1', '1000'],
]
async function devisRemise(r, produits, remise, m, etiquette) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ATST23 ${etiquette} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `atst23${etiquette}${m}@example.invalid` } }), 'lead')
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: remise, lead: lead.id,
    lignes: LIGNES_DEVIS.map(([desig, qte, pu], i) => ({ produit: produits[i].id, designation: desig, quantite: qte, prix_unitaire: pu, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: i })),
  } }), 'devis')
  return devis.id
}
etape('PF7.3-ATST23', ['ATST23'], async ({ page }) => {
  const r = page.request
  const m = marque()
  // Chaque produit porte un prix d'achat marqué 9876,54 : il ne doit JAMAIS apparaître dans le document client.
  const produits = []
  for (const [desig, , pu] of LIGNES_DEVIS) {
    produits.push(await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `${desig} ATST23 ${m}`, prix_vente: pu, prix_achat: '9876.54' } }), `produit ${desig}`))
  }
  const premium5 = await devisRemise(r, produits, '5', m, 'p5')
  const une5 = await devisRemise(r, produits, '5', m, 'u5')
  const nulle = await devisRemise(r, produits, '0', m, 'r0')
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J([premium5, nulle])}).update(etude_params={'scenario': 'Les deux (Sans + Avec)'})
sortie(1)`)
  const res = await py(`import re
from apps.ventes.models import Devis
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.builder import build_quote_data
BARRE = 'text-decoration:line-through;white-space:nowrap;">'
SEP = '[\\u00a0\\u202f ]'
def nb(txt): return SEP.join(re.escape(x) for x in txt.split(' '))
def rendre(pk, opts=None): return G.render_html_for(build_quote_data(Devis.objects.get(pk=pk), opts))
def cellule(html, cat, rem):
    return bool(re.search(re.escape(BARRE) + nb(cat) + r'</span>\\s*<span style="white-space:nowrap;">' + nb(rem) + '</span>', html))
def verdict(html):
    bas = html.lower()
    return dict(
        c4000=cellule(html, '4 000,00', '3 800,00'), c1100=cellule(html, '1 100,00', '1 045,00'), c15400=cellule(html, '15 400,00', '14 630,00'),
        barre=BARRE in html, sous_total='Sous-total HT' in html, remise_5=('Remise (5' in html),
        phrase='appliquée sur chaque ligne' in html, remise_de_5=bool(re.search('Remise de 5' + SEP + '%', html)),
        total_ttc='Total TTC' in html,
        achat_chiffre=bool(re.search(r'9(&#8239;|&nbsp;|\\u00a0|\\u202f| )?876', bas)),
        achat_mot=bool(re.search(r'\\bachat\\b', bas)))
sortie(dict(
    premium5=verdict(rendre(${premium5})),
    onepage5=verdict(rendre(${une5}, {'pdf_mode': 'onepage'})),
    premium0=verdict(rendre(${nulle})),
    onepage0=verdict(rendre(${nulle}, {'pdf_mode': 'onepage'}))))`)
  console.log(`[ATST23] ${J(res)}`)
  for (const [nom, v] of [['premium', res.premium5], ['une page', res.onepage5]]) {
    expect(v.c4000, `${nom} à 5 % : « 4 000,00 » barré puis « 3 800,00 » dans la même cellule`).toBe(true)
    expect(v.c1100, `${nom} à 5 % : P.U. du panneau « 1 100,00 » barré puis « 1 045,00 »`).toBe(true)
    expect(v.c15400, `${nom} à 5 % : total du panneau « 15 400,00 » barré puis « 14 630,00 »`).toBe(true)
    expect(v.sous_total && v.remise_5, `${nom} à 5 % : la chaîne Sous-total HT → Remise (5 …) est intacte`).toBe(true)
    expect(v.phrase, `${nom} à 5 % : la phrase « appliquée sur chaque ligne »`).toBe(true)
    expect(v.remise_de_5, `${nom} à 5 % : « Remise de 5 % »`).toBe(true)
    expect(v.achat_chiffre, `${nom} à 5 % : aucun marqueur du prix d'achat 9 876`).toBe(false)
    expect(v.achat_mot, `${nom} à 5 % : le mot « achat » n'est pas imprimé`).toBe(false)
  }
  expect(res.premium5.total_ttc, 'premium à 5 % : « Total TTC » présent').toBe(true)
  for (const [nom, v] of [['premium', res.premium0], ['une page', res.onepage0]]) {
    expect(v.barre, `${nom} à 0 % : aucun prix barré`).toBe(false)
    expect(v.phrase, `${nom} à 0 % : aucune phrase « appliquée sur chaque ligne »`).toBe(false)
  }
})
