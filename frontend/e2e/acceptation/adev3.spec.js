// ADEV114 — acceptation en direct de la contre-visite ADEV du 04/11/2026 (ADEV106-ADEV112 ; ADEV111 et ADEV113 sans
// étape : API seulement / test seul). Données posées par l'API (devis « niveau 2 » et calepinage posés au shell Django,
// comme un devis envoyé avant le 27/10 et un pan dessiné), nettoyées en fin d'étape. /proposition = apps/web servie EN
// LOCAL (`E2E_WEB_BASE`, PUBLIC_API_BASE=http://localhost), jamais la prod.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { catalogueCi, retablirCatalogueApresTout, leadCi, devisAuto, pdfTexte as pdfTexteCi } from './_ci.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, API_DJANGO as API } from '../helpers.js'

// `ACCEPTATION_COUVRE` (ids séparés par des virgules) : le sous-ensemble rejoué avec `-g` — un enregistrement PASS ne couvre
// que des tâches dont TOUTES les étapes passent ; les étapes en échec sont rejouées à part (enregistrement FAIL = trace).
const TOUTES = ['ADEV106', 'ADEV107', 'ADEV108', 'ADEV109', 'ADEV110', 'ADEV112']
const etape = groupe('ADEV', process.env.ACCEPTATION_COUVRE ? process.env.ACCEPTATION_COUVRE.split(',') : TOUTES)
fermerDjangoApresTout()
retablirCatalogueApresTout()
const T = { timeout: 180_000 }
test.describe.configure({ timeout: 900_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const lire = async (r, id) => lireJson(await r.get(`${API}/ventes/devis/${id}/`, T), 'devis')
const web = () => {
  const w = process.env.E2E_WEB_BASE
  expect(w, 'E2E_WEB_BASE absent : apps/web non servie').toBeTruthy()
  expect(w, 'jamais la prod').toMatch(/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?/)
  return w.replace(/\/$/, '')
}
async function nettoyer(r, { devis = [], leads = [], produits = [] }) {
  for (const id of devis) {
    const sup = await r.delete(`${API}/ventes/devis/${id}/`, T).catch(() => null)
    if (!sup || !sup.ok()) await r.patch(`${API}/ventes/devis/${id}/`, { ...T, data: { is_active: false } }).catch(() => null)
  }
  for (const id of leads) await r.delete(`${API}/crm/leads/${id}/`, T).catch(() => null)
  for (const id of produits) await r.delete(`${API}/stock/produits/${id}/`, T).catch(() => null)
}
const produit = async (r, nom, prix) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: prix, prix_achat: '321.09' } }), nom)
const ligne = (p, q, pu, ordre, extra = {}) => ({ produit: p.id, designation: p.nom, quantite: q, prix_unitaire: pu, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre, ...extra })

// ── (1) ADEV106 — générateur C&I ouvert depuis un lead pro à 4 000 kWh/mois, kWh annuel corrigé à 96 000 ─────────
etape('P1.kwh_annuel_corrige', ['ADEV106'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `ADEV106 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`,
    type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', raccordement: 'triphase',
    type_toiture: 'bac_acier', conso_mensuelle_kwh: '4000', contrat_electricite: 'bt_patente',
  } }), 'lead C&I')
  try {
    await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
    const champ = page.locator('#gen-ci-kwh-annuel')
    await expect(champ, 'champ « Consommation annuelle (kWh) » du générateur C&I').toBeVisible({ timeout: 90_000 })
    const attendu = page.waitForResponse(async (x) => {
      if (!/\/ventes\/etude-ci\/preview\/$/.test(new URL(x.url()).pathname) || x.request().method() !== 'POST') return false
      try { return Number(JSON.parse(x.request().postData() || '{}')?.consommation?.kwh_annuel) === 96000 } catch { return false }
    }, { timeout: 120_000 })
    await champ.fill('96000')
    const rep = await attendu
    expect(rep.status()).toBe(200)
    const corps = await rep.json()
    const kwh = corps.entrees_resolues?.kwh_annuel
    expect(kwh?.provenance?.origine, `kWh annuel retenu depuis la saisie (${JSON.stringify(Object.keys(corps.entrees_resolues || {}))})`).toBe('saisie')
    const somme = (corps.bilan?.par_mois || []).reduce((s, x) => s + Number(x.consommation_kwh || 0), 0)
    expect(Math.abs(somme - 96000), `bilan = ${somme} kWh`).toBeLessThanOrEqual(24)
    // Persistance : rechargement de l'écran ⇒ le lead n'a pas été réécrit (aperçu sans écriture).
    // (Réouverture dans un nouvel onglet : l'écran garde la saisie non enregistrée par `beforeunload`.)
    const p2 = await page.context().newPage()
    await p2.goto(`/ventes/devis/nouveau?lead=${lead.id}`, { waitUntil: 'domcontentloaded' })
    await expect(p2.locator('#gen-ci-kwh-annuel')).toBeVisible({ timeout: 90_000 })
    await p2.close()
    const relu = await lireJson(await r.get(`${API}/crm/leads/${lead.id}/`, T), 'lead relu')
    expect(Number(relu.conso_mensuelle_kwh)).toBe(4000)
  } finally {
    await nettoyer(r, { leads: [lead.id] })
  }
})

// ── (2) ADEV108 — simulation bancable d'un devis ENVOYÉ : trace « corrigé après envoi — étude » + jeton avancé ──────
etape('P2.simulation_envoye', ['ADEV108'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADEV108 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '1500' } }), 'lead')
  const pan = await produit(r, `Panneau mono 550W ADEV108 ${m}`, '1000.00')
  const ond = await produit(r, `Onduleur réseau 6kW ADEV108 ${m}`, '9000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, '12', '1000.00', 0), ligne(ond, '1', '9000.00', 1)] } }), 'devis')
  try {
    // Calepinage exploitable (un pan sud dessiné) + GPS du lead, comme après l'outil 3D.
    await py(`from apps.ventes.models import Devis
from apps.crm.models import Lead
Lead.objects.filter(pk=${lead.id}).update(gps_lat=33.5731, gps_lng=-7.5898)
d = Devis.objects.get(pk=${d.id})
lay = dict(d.roof_layout or {}); lay['_pans_geometry'] = [{'label': 'Pan Sud', 'kwc': 6.6, 'inclinaison_deg': 30, 'azimut_deg': 180}]
Devis.objects.filter(pk=d.pk).update(roof_layout=lay)
sortie(1)`)
    await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
    const avant = await lire(r, d.id)
    expect(avant.statut).toBe('envoye')
    const histAvant = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'historique'))
    await page.goto(`/ventes/devis?devis=${d.id}`)
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
    await page.getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
    await page.getByRole('menuitem', { name: 'Étude bancable' }).click()
    const lancer = page.getByRole('button', { name: /Lancer la simulation/ })
    await expect(lancer).toBeVisible({ timeout: 30_000 })
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && /\/simuler\/$/.test(new URL(x.url()).pathname)),
      lancer.click(),
    ])
    expect(rep.status(), await rep.text()).toBe(202)
    // La carte se remplit quand la tâche (file interactive) a rangé la simulation.
    await expect(page.getByRole('button', { name: /Recalculer l'étude/ })).toBeVisible({ timeout: 240_000 })
    const apres = await lire(r, d.id)
    expect(apres.statut, 'statut inchangé').toBe('envoye')
    expect(apres.etude_params?.simulation, 'simulation rangée').toBeTruthy()
    expect(new Date(apres.updated_at) > new Date(avant.updated_at), `jeton avancé (${avant.updated_at} → ${apres.updated_at})`).toBe(true)
    const hist = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'historique'))
    const nouvelles = hist.filter((h) => !histAvant.some((x) => x.id === h.id))
    const trace = nouvelles.find((h) => /Corrigé après envoi/.test(`${h.body || ''} ${h.field_label || ''}`) && /étude/.test(`${h.body || ''} ${h.new_value || ''}`))
    expect(trace, `ligne « corrigé après envoi — étude » (${JSON.stringify(nouvelles.map((h) => h.body))})`).toBeTruthy()
    expect(JSON.stringify(trace), 'au nom de l\'utilisateur').toMatch(/demo_admin|Demo|Admin/i)
    // Persistance : relecture ⇒ même trace, même simulation.
    await page.reload({ waitUntil: 'domcontentloaded' })
    const relu = await lire(r, d.id)
    expect(relu.etude_params?.simulation).toEqual(apres.etude_params?.simulation)
    const hist2 = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'historique'))
    expect(hist2.filter((h) => h.id === trace.id)).toHaveLength(1)
  } finally {
    await nettoyer(r, { devis: [d.id], leads: [lead.id], produits: [pan.id, ond.id] })
  }
})

// ── (3) ADEV112 — aperçu PDF d'un devis commercial incomplet : liste puis panneau du lead ─────────────────────────
async function devisIncomplet(r) {
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADEV112 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'commercial', categorie_commerciale: 'bureau' } }), 'lead')
  const pan = await produit(r, `Panneau mono 550W ADEV112 ${m}`, '1000.00')
  const ond = await produit(r, `Onduleur réseau 10kW ADEV112 ${m}`, '9000.00')
  // Nomenclature trop longue pour la page équipements commerciale : refus NOMMÉ du rendu C&I (409, ADEV88).
  const lignes = [ligne(pan, '40', '1000.00', 0), ligne(ond, '1', '9000.00', 1),
    ...Array.from({ length: 150 }, (_, i) => ligne(pan, '1', '10.00', 2 + i, { designation: `Accessoire de fixation et de câblage numéro ${i} pour structure toiture bac acier` }))]
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'commercial', lignes } }), 'devis commercial')
  const direct = await r.get(`${API}/ventes/devis/${d.id}/proposal/`, T)
  expect(direct.status()).toBe(409)
  const detail = (await direct.json()).detail
  expect(detail).toMatch(/^Devis commercial incomplet : /)
  return { lead, d, detail, produits: [pan.id, ond.id] }
}

etape('P3.apercu_409_liste', ['ADEV112'], async ({ page, suivi }) => {
  const r = page.request
  const x = await devisIncomplet(r)
  suivi.attendre(new RegExp(`/ventes/devis/${x.d.id}/proposal/`), 409)
  try {
    // Liste des devis → « Plus d'actions » → « Aperçu du PDF ».
    await page.goto('/ventes/devis')
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(x.d.reference, { timeout: 60_000 })
    await page.getByRole('button', { name: `Plus d'actions — ${x.d.reference}` }).click()
    await page.getByRole('menuitem', { name: 'Aperçu du PDF' }).click()
    await expect(page.getByText(x.detail).first(), 'liste : le detail du 409 affiché tel quel').toBeVisible({ timeout: 120_000 })
    await expect(page.getByText('Aperçu du PDF indisponible.')).toHaveCount(0)
    // Persistance : rouvert, même verdict (aucun état gardé).
    expect((await r.get(`${API}/ventes/devis/${x.d.id}/proposal/`, T)).status()).toBe(409)
  } finally {
    await nettoyer(r, { devis: [x.d.id], leads: [x.lead.id], produits: x.produits })
  }
})

etape('P3.apercu_409_panneau_lead', ['ADEV112'], async ({ page, suivi }) => {
  const r = page.request
  const x = await devisIncomplet(r)
  suivi.attendre(new RegExp(`/ventes/devis/${x.d.id}/proposal/`), 409)
  try {
    // Panneau devis du lead → « Aperçu interne ».
    await page.goto(`/crm/leads/${x.lead.id}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await page.getByRole('button', { name: /Aperçu interne/ }).first().click()
    await expect(page.getByText(x.detail).first(), 'panneau du lead : le detail du 409 affiché').toBeVisible({ timeout: 120_000 })
    await expect(page.getByText(/Request failed with status code 409/)).toHaveCount(0)
  } finally {
    await nettoyer(r, { devis: [x.d.id], leads: [x.lead.id], produits: x.produits })
  }
})

/** Devis résidentiel à DEUX options (lignes variantées), niveau de règles 2 (devis envoyé avant le 27/10), lien envoyé. */
async function devisDeuxOptions(r, tag, { email = true } = {}) {
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `${tag} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), ...(email ? { email: `${m}@example.invalid` } : {}), type_installation: 'residentiel', facture_hiver: '1500', facture_ete: '1200' } }), 'lead')
  const pan = await produit(r, `Panneau mono 550W ${tag} ${m}`, '1000.00')
  const hyb = await produit(r, `Onduleur hybride 6kW ${tag} ${m}`, '12000.00')
  const bat = await produit(r, `Batterie lithium 5kWh ${tag} ${m}`, '15000.00')
  const res = await produit(r, `Onduleur réseau injection 6kW ${tag} ${m}`, '9000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [
    ligne(pan, '10', '1000.00', 0), ligne(hyb, '1', '12000.00', 1, { variante: 'avec' }), ligne(bat, '1', '15000.00', 2, { variante: 'avec' }), ligne(res, '1', '9000.00', 3, { variante: 'sans' }),
  ] } }), 'devis deux options')
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${d.id}).update(regles_calcul=2)
sortie(1)`)
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return { lead, d, jeton: lien.token, produits: [pan.id, hyb.id, bat.id, res.id] }
}

// ── (4) ADEV107 — /proposition niveau 2 : le cumul 25 ans suit l'option cochée (et après une bascule de taille) ────
const couleurs = []
etape('P4.cumul_suit_option', ['ADEV107'], async ({ page, suivi }) => {
  const base = web()
  const r = page.request
  const x = await devisDeuxOptions(r, 'ADEV107')
  try {
    const pub = await lireJson(await r.get(`${API}/public/proposal/${x.jeton}/data/`, T), 'données publiques')
    const cumul = pub.economies_cumul_25_ans || {}
    expect(Object.keys(cumul).sort(), 'cumul servi pour les deux options').toEqual(['avec_batterie', 'sans_batterie'])
    expect(pub.gain_net_25_ans ?? null, 'niveau 2 : pas de gain net').toBeNull()
    const fmt = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
    const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '')
    const mens = (opt) => Math.round((opt === 'avec_batterie' ? pub.quote.eco_a_ann : pub.quote.eco_s_ann) / 12)
    const p2 = suivi.surveiller(await page.context().newPage())
    const rep = await p2.goto(`${base}/proposition/${x.jeton}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    expect(rep.status()).toBe(200)
    const carte = p2.locator('[data-detail-cumul-value]')
    await expect(carte).toBeVisible({ timeout: 60_000 })
    const sous = p2.locator('[data-detail-cumul-sous]')
    const reco = (await carte.getAttribute('data-figure-option')) === 'avec' ? 'avec_batterie' : 'sans_batterie'
    const autre = reco === 'avec_batterie' ? 'sans_batterie' : 'avec_batterie'
    expect(plat(await carte.innerText())).toContain(plat(fmt(cumul[reco])))
    const couleurAvant = await sous.locator('.text-brass-300').count()
    // Bascule d'option dans le bloc de signature.
    await p2.locator(`input[name="option"][value="${autre}"]`).first().check({ force: true })
    await expect(carte).toHaveAttribute('data-figure-option', autre === 'avec_batterie' ? 'avec' : 'sans', { timeout: 10_000 })
    expect(plat(await carte.innerText()), 'le cumul suit l\'option cochée').toContain(plat(fmt(cumul[autre])))
    expect(plat(await sous.innerText()), 'la mensualité suit l\'option cochée').toContain(plat(fmt(mens(autre))))
    const couleurApres = await sous.locator('.text-brass-300').count()
    // Retour : la valeur de départ revient.
    await p2.locator(`input[name="option"][value="${reco}"]`).first().check({ force: true })
    await expect(carte).toHaveAttribute('data-figure-option', reco === 'avec_batterie' ? 'avec' : 'sans', { timeout: 10_000 })
    expect(plat(await carte.innerText())).toContain(plat(fmt(cumul[reco])))
    // Persistance : rechargement ⇒ la carte revient à l'option recommandée (rendu client, rien n'est écrit).
    await p2.reload({ waitUntil: 'domcontentloaded' })
    await expect(p2.locator('[data-detail-cumul-value]')).toHaveAttribute('data-figure-option', reco === 'avec_batterie' ? 'avec' : 'sans', { timeout: 60_000 })
    couleurs.push([couleurAvant, couleurApres])
  } finally {
    await nettoyer(r, { devis: [x.d.id], leads: [x.lead.id], produits: x.produits })
  }
})

// La mensualité « ≈ N MAD/mois » est mise en valeur (span .text-brass-300) au rendu serveur : elle doit le rester
// après une bascule d'option (risque signalé par le constructeur : la bascule réécrit le texte des spans fr/en/ar).
etape('P4.couleur_mensualite', ['ADEV107'], async () => {
  expect(couleurs.length, 'étape P4.cumul_suit_option jouée avant').toBeGreaterThan(0)
  const [avant, apres] = couleurs[0]
  expect(avant, 'mensualité en valeur au rendu serveur').toBeGreaterThan(0)
  expect(apres, `mensualité : mise en valeur (.text-brass-300) gardée après bascule (${avant} → ${apres})`).toBe(avant)
})

etape('P4.bascule_taille_puis_option', ['ADEV107'], async ({ page, suivi }) => {
  const base = web()
  const r = page.request
  const x = await devisDeuxOptions(r, 'ADEV107T')
  try {
    const pub = await lireJson(await r.get(`${API}/public/proposal/${x.jeton}/data/`, T), 'données publiques')
    const offres = pub.offres_tailles
    expect(offres, 'offres_tailles servies (Éco/Max) — sans elles la bascule de taille n\'existe pas').toBeTruthy()
    const p2 = suivi.surveiller(await page.context().newPage())
    await p2.goto(`${base}/proposition/${x.jeton}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    const carte = p2.locator('[data-detail-cumul-value]')
    await expect(carte).toBeVisible({ timeout: 60_000 })
    const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '')
    const reco = (await carte.getAttribute('data-figure-option')) === 'avec' ? 'avec_batterie' : 'sans_batterie'
    const autre = reco === 'avec_batterie' ? 'sans_batterie' : 'avec_batterie'
    const valeurReco = plat(await carte.innerText())
    // Bascule de taille (Éco ou Max) : la carte prend le cumul de la taille chargée.
    const bouton = p2.locator('[data-taille-carte]:not([aria-current="true"])').first()
    await expect(bouton, 'carte de taille Éco/Max').toBeAttached({ timeout: 30_000 })
    await bouton.scrollIntoViewIfNeeded()
    await bouton.click({ position: { x: 12, y: 12 } })
    await expect.poll(async () => plat(await carte.innerText()), { timeout: 60_000 }).not.toBe(valeurReco)
    const valeurTaille = plat(await carte.innerText())
    // Puis bascule d'option : la carte ne doit pas revenir au cumul de la taille RECOMMANDÉE de l'autre option sans le dire.
    await p2.locator(`input[name="option"][value="${autre}"]`).first().check({ force: true })
    const cumulAutreReco = String(Math.round(pub.economies_cumul_25_ans[autre]))
    const apres = plat(await carte.innerText())
    test.info().annotations.push({ type: 'taille puis option', description: `reco ${valeurReco} → taille ${valeurTaille} → option ${autre} ${apres} (cumul recommandé de ${autre} = ${cumulAutreReco})` })
    expect(apres, `après une bascule de taille, la bascule d'option n'affiche pas le cumul de la taille recommandée (${valeurReco} → ${valeurTaille} → ${apres})`).not.toContain(cumulAutreReco)
  } finally {
    await nettoyer(r, { devis: [x.d.id], leads: [x.lead.id], produits: x.produits })
  }
})

// ── (5) ADEV109 — signature d'un devis sans canal de code : 409 `aucun_canal` affiché en FR ────────────────────────
etape('P5.signature_sans_canal', ['ADEV109'], async ({ page, suivi }) => {
  const base = web()
  const r = page.request
  const x = await devisDeuxOptions(r, 'ADEV109')
  try {
    // Le client perd ses canaux (ni WhatsApp ni e-mail) ; OTP de signature actif sur la pile (ESIGN_OTP_ENABLED=1).
    const clientId = (await lire(r, x.d.id)).client
    await py(`from apps.crm.models import Client
Client.objects.filter(pk=${clientId}).update(email=None, telephone='')
sortie(1)`)
    const brut = await r.post(`${API}/ventes/proposal/${x.jeton}/otp/`, { ...T, data: {} })
    expect(brut.status(), await brut.text()).toBe(409)
    const corps = await brut.json()
    expect(corps.code).toBe('aucun_canal')
    const p2 = suivi.surveiller(await page.context().newPage())
    suivi.attendre(/\/api\/proposition-otp/, 409)
    suivi.attendre(/\/otp\/?$/, 409)
    suivi.attendre(/\/api\/proposition-accept/, 403)
    suivi.attendre(/\/accept\/?$/, 403)
    await p2.goto(`${base}/proposition/${x.jeton}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    const form = p2.locator('#sign-form')
    const cta = p2.getByRole('link', { name: 'Signer en ligne' }).or(p2.getByRole('button', { name: 'Signer en ligne' })).first()
    if (await cta.count()) await cta.click()
    await expect(form).toBeVisible({ timeout: 60_000 })
    await form.locator('#sign-nom').fill('Tijani Kharbachi')
    for (const c of await form.locator('input[type="checkbox"]:visible').all()) await c.check()
    const pad = form.locator('#sign-pad')
    const b = await pad.boundingBox()
    await p2.mouse.move(b.x + 20, b.y + b.height / 2)
    await p2.mouse.down()
    await p2.mouse.move(b.x + b.width / 2, b.y + 10, { steps: 8 })
    await p2.mouse.move(b.x + b.width - 20, b.y + b.height / 2, { steps: 8 })
    await p2.mouse.up()
    await form.locator('#sign-submit').click()
    const statut = p2.locator('#sign-otp-status')
    await expect(statut, 'le detail servi du 409, en FR').toContainText("Aucun moyen d'envoyer le code : contactez votre conseiller.", { timeout: 60_000 })
    await expect(statut).not.toContainText('Impossible d\'envoyer le code pour le moment')
    // Persistance : devis toujours envoyé (aucune signature).
    expect((await lire(r, x.d.id)).statut).toBe('envoye')
  } finally {
    await nettoyer(r, { devis: [x.d.id], leads: [x.lead.id], produits: x.produits })
  }
})

// ── (6) ADEV110 — PDF C&I d'une étude à relevé partiel (3 mois) : la mention « estimation sur 3 mois relevés » ──────
etape('P6.pdf_releve_partiel', ['ADEV110'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const lead = await leadCi(r, `ADEV110 ${m}`, { conso_mensuelle_kwh: null, releve_conso: { mois: [{ mois: '2026-06', kwh: '3000' }, { mois: '2026-07', kwh: '4000' }, { mois: '2026-08', kwh: '5000' }] } })
  let devisId = null
  try {
    const d = await devisAuto(r, lead.id)
    devisId = d.id || d.devis?.id
    const lu = await lire(r, devisId)
    const hyp = (lu.etude_params?.etude_ci?.hypotheses || []).find((h) => h.cle === 'consommation')
    expect(hyp?.source, `hypothèse de consommation de l'étude (${JSON.stringify(hyp)})`).toBe('relevé partiel (3 mois)')
    // Servi : synthese_ci.hypotheses du lien public porte consommation_estimee (lecteur /proposition).
    const lien = await lireJson(await r.post(`${API}/ventes/devis/${devisId}/share-link/`, { ...T, data: { envoi: true } }), 'lien')
    const pub = await lireJson(await r.get(`${API}/public/proposal/${lien.token}/data/`, T), 'données publiques')
    const servie = (pub.synthese_ci?.hypotheses || []).find((h) => h.cle === 'consommation_estimee')
    expect(servie?.textes?.fr, 'servi à /proposition').toContain('estimation sur 3 mois relevés')
    // PDF lu (/proposal, chemin unique) : la mention doit être imprimée.
    const texte = await pdfTexteCi(r, devisId)
    expect(texte, 'PDF C&I : mention « estimation sur 3 mois relevés » imprimée').toMatch(/estimation sur 3 mois relev/)
  } finally {
    await nettoyer(r, { devis: devisId ? [devisId] : [], leads: [lead.id] })
  }
})
