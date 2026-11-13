// Acceptation en direct — groupe ASOC (facturation, run 99392c, lane W10B) : preuve due d'ASOC107 — profil réglé
// 2 % / 10 j : consolider deux devis acceptés du même client DEPUIS la liste des factures (« Consolider des devis »),
// rouvrir la facture et son PDF ⇒ mention d'escompte ; retenue et exigible inchangés. Le profil de la société de
// demo_admin est rétabli en fin d'étape. Devis montés par les vraies routes (atomic, share-link, accepter) — patron
// atot.spec.js ; PDF par `telecharger-pdf` (texte extrait par pdfjs).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, telephoneMobileUnique, textePdf, uniq, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ASOC', ['ASOC107'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 480_000 })
test.use({ viewport: { width: 1600, height: 1000 } })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify

const LIGNES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12500.00', tva: '20.00' },
  { d: 'Installation', q: '1', pu: '5000.00', tva: '20.00' },
]
/** Devis (atomic) envoyé puis accepté par les routes ; `client` fourni ⇒ même client. */
async function devisAccepte(request, client = null) {
  let leadId = null
  if (!client) {
    leadId = (await lireJson(await request.post(`${API}/crm/leads/`, {
      ...T, data: { nom: uniq('ASOC107 Client'), ville: 'Casablanca', telephone: telephoneMobileUnique() },
    }), 'lead')).id
  }
  const lignes = []
  for (const [i, l] of LIGNES.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, { ...T, data: { nom: `${l.d} ASOC107 ${Date.now()}-${i}`, prix_vente: l.pu } }), 'produit')
    lignes.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
  }
  const d = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lignes, ...(leadId ? { lead: leadId } : { client }) },
  }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await request.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ASOC107' } }), 'acceptation')
  return lireJson(await request.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
}

etape('P.consolidee_escompte_profil', ['ASOC107'], async ({ page }) => {
  const r = page.request
  const avant = await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.get(company=U.objects.get(username='demo_admin').company)
v = dict(pct=None if p.escompte_pct_defaut is None else str(p.escompte_pct_defaut), jours=p.escompte_jours_defaut)
p.escompte_pct_defaut = 2; p.escompte_jours_defaut = 10; p.save()
sortie(v)`)
  try {
    const d1 = await devisAccepte(r)
    const d2 = await devisAccepte(r, d1.client)
    expect([d1.statut, d2.statut], 'deux devis acceptés').toEqual(['accepte', 'accepte'])
    // Écran : Ventes › Factures → « Consolider des devis » → cocher les deux → « Consolider (2) ».
    await page.goto('/ventes/factures')
    await page.getByRole('button', { name: 'Consolider des devis' }).click({ timeout: 60_000 })
    const dlg = page.getByRole('dialog').filter({ hasText: 'Consolider des devis' })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    for (const d of [d1, d2]) await dlg.getByRole('checkbox', { name: `Sélectionner le devis ${d.reference}` }).click({ timeout: 60_000 })
    const rep = page.waitForResponse((q) => q.request().method() === 'POST' && /\/ventes\/factures\/consolider\/?$/.test(new URL(q.url()).pathname), T)
    await dlg.getByRole('button', { name: /^Consolider \(2\)/ }).click()
    const reponse = await rep
    expect(reponse.status(), `consolider (${(await reponse.text()).slice(0, 300)})`).toBe(201)
    const cree = await reponse.json()
    // Persistance : la facture relue porte l'escompte du profil (2 % / 10 j) ; retenue et exigible = ceux d'une
    // consolidée sans escompte (escompte = mention, jamais une baisse du total).
    const f = await lireJson(await r.get(`${API}/ventes/factures/${cree.id}/`, T), 'facture relue')
    expect([Number(f.escompte_pct), f.escompte_jours], `escompte repris du profil (${J({ p: f.escompte_pct, j: f.escompte_jours })})`).toEqual([2, 10])
    const ttc = Number(d1.total_ttc) + Number(d2.total_ttc)
    expect(Math.abs(Number(f.total_ttc) - ttc), `TTC consolidée = Σ devis (${f.total_ttc} vs ${ttc})`).toBeLessThan(0.01)
    // Rouvrir la facture à l'écran (recherche par référence) puis son PDF ⇒ mention d'escompte.
    await page.reload()
    await page.getByPlaceholder('Référence, client').fill(f.reference)
    await expect(page.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 60_000 })
    const pdf = await r.get(`${API}/ventes/factures/${f.id}/telecharger-pdf/`, T)
    expect(pdf.status(), `PDF de la facture (${pdf.status()})`).toBe(200)
    const texte = (await textePdf(await pdf.body())).replace(/\s+/g, ' ')
    expect(texte, 'PDF : « Escompte 2 % si règlement sous 10 jours »').toMatch(/Escompte 2(?:[.,]0+)? ?% si règlement sous 10 jours/)
  } finally {
    await py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.get(company=U.objects.get(username='demo_admin').company)
avant = json.loads(${J(J(avant))})
p.escompte_pct_defaut = avant['pct']; p.escompte_jours_defaut = avant['jours']; p.save()
sortie(1)`)
  }
})
