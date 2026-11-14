// Preuves en direct ÉCRAN du groupe AERR, lot 6 (contre-visites du 14/11 : C-AERR-VER1-100, C-AERR-VER2-100,
// C-AERR-VER2-101) : AERR133 (Factures › Notes de débit, liste de A jamais sous B), AERR150 (Remises d'encaissement,
// lignes gardées pendant la relecture qui suit « Clôturer » / « Déclarer »), AERR149 (Lots / multi-sites créés DEPUIS
// le générateur sans soumettre son formulaire) — l'étape rejoue aussi celle d'AERR11 retirée d'aerr3.spec.js au commit
// 99e450b1e (défaut produit corrigé par AERR149), comme sa clause « Preuve en direct » le demande.
// Chaque étape joue le geste À L'ÉCRAN sous un compte du rôle LIVRÉ « Directeur » (registre `permissions_registre.py`,
// rôle système relu par son nom dans la société démo), connecté par le VRAI écran de connexion ; l'échec est PROVOQUÉ
// (route Playwright déclarée AVANT par `suivi.attendre`) ; l'étape relit la base par l'API, recharge et réaffirme.
// Données propres créées par les vraies routes ; une facture à numéro légal ne se supprime jamais : elle reste sur la
// base jetable du runner. Aucun envoi réel (le runner n'a ni worker Celery ni passerelle de messages).
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, listeDe } from '../helpers.js'

const etape = groupe('AERR', ['AERR133', 'AERR150', 'AERR149', 'AERR11'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

/** Rejoue une sonde HÔTE (`docs/audits/sondes/AERR/<c>.py`, sans Django ni base) : exécutée, `repro` faux. */
function sondeFausse(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  expect(ligne, `sonde ${constat} exécutée : ${(r.stderr || '').slice(-300)}`).toBeTruthy()
  const res = JSON.parse(ligne.slice(3))
  console.log(`[AERR] sonde ${constat} : ${J(res).slice(0, 500)}`)
  expect(res.repro, `sonde ${constat} : ${J(res.observe)}`).toBe(false)
}

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {id, porte}. */
const compteDuRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'porte': 'encaisser' in (r.permissions or [])})`)

/** Écran sous le compte `nom` : contexte neuf (SW bloqué), connexion par l'ÉCRAN de connexion, visites guidées
 *  marquées vues ; la page demo_admin est refermée (la capture montre l'écran du rôle). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  const p = suivi.surveiller(await ctx.newPage())
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p, api: ctx.request, ctx }
}

const LEAD_CI = {
  type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', raccordement: 'triphase',
  type_toiture: 'bac_acier', conso_mensuelle_kwh: '10000', contrat_electricite: 'bt_patente',
}
/** Lead + produit + devis (porté par `cree`) ; `envoye` ⇒ lien client émis (vraie route share-link). */
async function devisDe(cree, admin, m, { ci = false, envoye = false, ht = '10000.00' } = {}) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `AERR ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aerr-${m}@example.invalid`, ...(ci ? LEAD_CI : {}),
  } }), 'lead')
  const p = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AERR ${m}`, prix_vente: ht, prix_achat: '1.00' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: l.id, ...(ci ? { mode_installation: 'commercial' } : {}),
    lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: ht, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  } }), 'devis')
  if (envoye) await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await cree.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { id: d.id, reference: relu.reference, statut: relu.statut, leadId: l.id }
}
/** Vente acceptée (demo_admin) puis facturée « complete » et émise par `cree`. */
async function factureDe(cree, admin, m) {
  const d = await devisDe(cree, admin, m, { envoye: true })
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR' } }), 'accepter')
  const rep = await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre: true, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut }
}

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)`. */
function porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}

// ═══ AERR133 — Factures › « Note de débit » : la boîte ouverte sur A (notes lues) puis sur B (lecture en 500) ═══
etape('PF12.3-AERR133', ['AERR133'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-VER1-100')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr133di_${m}`
  await compteDuRole(nom, 'Directeur')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const A = await factureDe(api, admin, `${m}a`)
  const B = await factureDe(api, admin, `${m}b`)
  expect([A.statut, B.statut], 'Given : deux factures émises').toEqual(['emise', 'emise'])
  const nd = await lireJson(await api.post(`${API}/ventes/factures/${A.id}/creer-note-debit/`, { ...T, data: {
    motif: `AERR133 ${m}`, montant: '100', taux_tva: '20', idempotency_key: `aerr133-${m}`,
  } }), 'note de débit sur A')
  expect(nd.reference, 'Given : la note de débit de A a une référence').toBeTruthy()
  const ndsB = listeDe(await lireJson(await api.get(`${API}/ventes/notes-debit/?facture=${B.id}`, T), 'notes de B'))
  expect(ndsB.length, 'Given : B n\'a aucune note de débit').toBe(0)

  const LECTURE_B = new RegExp(`/api/django/ventes/notes-debit/\\?.*facture=${B.id}(&|$)`)
  const ligne = (f) => p.locator(`#facture-row-${f.id}`)
  const boite = (f) => p.getByRole('dialog').filter({ hasText: `Notes de débit — ${f.reference}` })
  const ouvrir = async (f) => {
    // État d'accessibilité de la ligne avant le clic (diagnostic : une couche modale mal refermée la rend aria-hidden).
    const etat = await ligne(f).evaluate((el) => ({
      cachee: Boolean(el.closest('[aria-hidden="true"]')), inerte: Boolean(el.closest('[inert]')),
      pointeurs: getComputedStyle(document.body).pointerEvents,
      boutons: [...el.querySelectorAll('button')].map((b) => b.textContent.trim()).filter(Boolean),
    })).catch((e) => ({ erreur: String(e).slice(0, 200) }))
    console.log(`[AERR133] ligne ${f.reference} avant « Actions » : ${J(etat)}`)
    const bouton = ligne(f).locator('button', { hasText: 'Actions' })
    if (etat.pointeurs === 'none') {
      // DÉFAUT ANTÉRIEUR, hors des Files d'AERR133 (FactureRow.jsx : « Note de débit » ouvre la boîte sans refermer le
      // menu de la ligne) : la boîte refermée, la page reste inerte au pointeur (body pointer-events:none, aria-hidden).
      // Nommé dans le rapport ; la ligne suivante est ouverte au CLAVIER (Tab/Entrée), geste réel d'un utilisateur.
      testInfo.annotations.push({ type: 'défaut antérieur', description: `page inerte au pointeur après la boîte de ${A.reference} : ${J(etat)}` })
      await bouton.focus()
      await p.keyboard.press('Enter')
    } else {
      await bouton.click()
    }
    await p.getByRole('menuitem', { name: 'Note de débit' }).click()
    await expect(boite(f), `boîte ouverte sur ${f.reference}`).toBeVisible({ timeout: 30_000 })
  }
  // « Note de débit » ouvre la boîte SANS refermer le menu de la ligne (`onSelect` + `preventDefault`) : Échap ferme la
  // boîte, puis le menu resté ouvert derrière elle.
  const fermer = async (f) => {
    await boite(f).getByRole('button', { name: 'Fermer' }).click()
    await expect(boite(f), `boîte de ${f.reference} refermée`).toBeHidden({ timeout: 30_000 })
    if (await p.getByRole('menu').isVisible()) await p.keyboard.press('Escape')
    await expect(p.getByRole('menu'), 'menu de ligne refermé').toHaveCount(0)
  }
  const jouer = async (passe) => {
    await p.goto('/ventes/factures')
    for (const f of [A, B]) await expect(ligne(f), `${passe}${f.reference} affichée`).toBeVisible({ timeout: 90_000 })
    await ouvrir(A)
    await expect(boite(A).getByText(nd.reference), `${passe}A : sa note ${nd.reference} est lue`).toBeVisible({ timeout: 30_000 })
    await expect(boite(A).getByRole('button', { name: 'PDF' }), `${passe}A : bouton PDF de sa note`).toBeVisible()
    await fermer(A)
    await p.route(LECTURE_B, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"panne injectée AERR133"}' }))
    const lu = p.waitForResponse((x) => LECTURE_B.test(x.url()), T)
    await ouvrir(B)
    expect((await lu).status(), `${passe}B : la lecture est bien rejetée (500 injecté)`).toBe(500)
    const b = boite(B)
    await expect(b.getByText('Notes de débit indisponibles.'), `${passe}B : « Notes de débit indisponibles »`).toBeVisible({ timeout: 30_000 })
    await expect(b.getByRole('button', { name: 'Réessayer' }), `${passe}B : « Réessayer »`).toBeVisible()
    await expect(b.getByText(nd.reference), `${passe}B : aucune note de A`).toHaveCount(0)
    await expect(b.getByRole('button', { name: 'Annuler' }), `${passe}B : aucun « Annuler »`).toHaveCount(0)
    await expect(b.getByRole('button', { name: 'PDF' }), `${passe}B : aucun « PDF »`).toHaveCount(0)
    await expect(b.getByText('Aucune note de débit sur cette facture.'), `${passe}B : l'échec n'est pas dit « aucune note »`).toHaveCount(0)
    return b
  }
  suivi.attendre(LECTURE_B, 500)
  const b = await jouer('')
  // Réessayer, panne levée : la vraie lecture de B ⇒ « aucune note » (B n'en a pas), toujours rien de A.
  await p.unroute(LECTURE_B)
  await b.getByRole('button', { name: 'Réessayer' }).click()
  await expect(b.getByText('Aucune note de débit sur cette facture.'), 'Réessayer : B relue, aucune note').toBeVisible({ timeout: 30_000 })
  await expect(b.getByText(nd.reference), 'Réessayer : toujours aucune note de A').toHaveCount(0)
  // Persistance (lecture) : la note est sur A, aucune sur B.
  expect(listeDe(await lireJson(await api.get(`${API}/ventes/notes-debit/?facture=${A.id}`, T), 'notes de A')).map((x) => x.reference), 'base : la note est sur A').toContain(nd.reference)
  expect(listeDe(await lireJson(await api.get(`${API}/ventes/notes-debit/?facture=${B.id}`, T), 'notes de B')).length, 'base : aucune note sur B').toBe(0)
  await fermer(B)
  // Rechargé : même parcours, même verdict ; l'étape finit sur la boîte de B en échec (capture).
  await p.reload()
  await jouer('rechargé : ')
})

// ═══ AERR150 — Remises d'encaissement : « Clôturer » puis « Déclarer », relecture retenue puis rejetée ═══
etape('PF12.3-AERR150', ['AERR150'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr150di_${m}`
  expect((await compteDuRole(nom, 'Directeur')).porte, 'le rôle Directeur porte encaisser').toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const jour = new Date().toISOString().slice(0, 10)
  const remise = async (montant) => lireJson(await api.post(`${API}/ventes/remises-encaissement/`, { ...T, data: {
    date_collecte: jour, montant_declare: montant, note: `AERR150 ${m}`, lignes: [],
  } }), 'remise déclarée')
  const R1 = await remise('120.00')
  const R2 = await remise('80.00')
  expect([R1.statut, R2.statut], 'Given : deux remises ouvertes').toEqual(['ouverte', 'ouverte'])
  const LISTE = /\/api\/django\/ventes\/remises-encaissement\/\?/
  const ligne = (r) => p.getByRole('row').filter({ hasText: new RegExp(`${r.reference}(?![0-9])`) })
  const squelette = p.locator('.skeleton-shimmer')
  const avis = p.getByTestId('remises-pas-a-jour')
  await p.goto('/ventes/remises-encaissement')
  for (const r of [R1, R2]) await expect(ligne(r), `${r.reference} listée`).toBeVisible({ timeout: 90_000 })

  // « Clôturer » R1 : la relecture qui suit est TENUE (les lignes restent, aucun squelette) puis REJETÉE (500).
  suivi.attendre(LISTE, 500)
  const g = porte()
  await p.route(LISTE, g.gestion((route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"panne injectée AERR150"}' })))
  await ligne(R1).getByRole('button', { name: 'Clôturer' }).click()
  const conf = p.getByRole('alertdialog')
  await expect(conf, 'confirmation de clôture').toContainText(`Clôturer la remise ${R1.reference}`)
  const clot = p.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/remises-encaissement/${R1.id}/cloturer/$`).test(new URL(x.url()).pathname), T)
  await conf.getByRole('button', { name: 'Clôturer' }).click()
  expect((await clot).status(), 'clôture servie').toBeLessThan(300)
  await g.arrivee // la relecture est partie et TENUE
  for (const r of [R1, R2]) await expect(ligne(r), `relecture EN COURS : ${r.reference} reste à l'écran`).toBeVisible()
  await expect(squelette, 'relecture EN COURS : aucun squelette').toHaveCount(0)
  g.lacher()
  await expect(avis, 'relecture REJETÉE : avis').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour — la dernière relecture a échoué.')
  await expect(avis.getByRole('button', { name: 'Réessayer' }), 'avis avec « Réessayer »').toBeVisible()
  for (const r of [R1, R2]) await expect(ligne(r), `relecture REJETÉE : ${r.reference} reste à l'écran`).toBeVisible()
  await expect(squelette).toHaveCount(0)
  // Persistance : R1 clôturée en base.
  const relue = async (r) => lireJson(await api.get(`${API}/ventes/remises-encaissement/${r.id}/`, T), 'remise relue')
  expect((await relue(R1)).statut, 'base : R1 clôturée').toBe('cloturee')
  expect((await relue(R2)).statut, 'base : R2 toujours ouverte').toBe('ouverte')
  await p.unroute(LISTE)
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'Réessayer : avis retiré').toBeHidden({ timeout: 30_000 })
  await expect(ligne(R1).getByRole('button', { name: 'Clôturer' }), 'Réessayer : R1 relue clôturée').toHaveCount(0)

  // « Déclarer » une remise : la relecture qui suit est TENUE (lignes, pas de squelette) puis servie.
  const g2 = porte()
  await p.route(LISTE, g2.gestion((route) => route.continue()))
  await p.getByRole('button', { name: 'Déclarer une remise' }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: 'Déclarer une remise d\'encaissement' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#remise-montant').fill('55')
  await dlg.locator('#remise-note').fill(`AERR150 déclarée ${m}`)
  const decl = p.waitForResponse((x) => x.request().method() === 'POST' && /\/remises-encaissement\/$/.test(new URL(x.url()).pathname), T)
  await dlg.getByRole('button', { name: 'Déclarer', exact: true }).click()
  const R3 = await (await decl).json()
  await g2.arrivee
  for (const r of [R1, R2]) await expect(ligne(r), `après Déclarer, relecture EN COURS : ${r.reference} reste`).toBeVisible()
  await expect(squelette, 'après Déclarer, relecture EN COURS : aucun squelette').toHaveCount(0)
  g2.lacher()
  await expect(ligne(R3), `relecture servie : ${R3.reference} listée`).toBeVisible({ timeout: 30_000 })
  suivi.verifie(5)
  await p.unroute(LISTE)
  // Rechargé : le premier chargement garde son squelette (puis les lignes) ; R1 clôturée, R2 ouverte.
  await p.reload()
  for (const r of [R1, R2, R3]) await expect(ligne(r), `rechargé : ${r.reference}`).toBeVisible({ timeout: 90_000 })
  await expect(ligne(R1).getByRole('button', { name: 'Clôturer' }), 'rechargé : R1 sans « Clôturer »').toHaveCount(0)
  await expect(ligne(R2).getByRole('button', { name: 'Clôturer' }), 'rechargé : R2 clôturable').toBeVisible()
  // Réaffirmé sur l'écran rechargé : clôture de R2, relecture rejetée ⇒ lignes + avis (l'étape finit dessus).
  await p.route(LISTE, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"panne injectée AERR150"}' }))
  await ligne(R2).getByRole('button', { name: 'Clôturer' }).click()
  await conf.getByRole('button', { name: 'Clôturer' }).click()
  await expect(avis, 'rechargé : relecture rejetée ⇒ avis').toBeVisible({ timeout: 30_000 })
  for (const r of [R1, R2, R3]) await expect(ligne(r), `rechargé, relecture rejetée : ${r.reference}`).toBeVisible()
  await expect(squelette).toHaveCount(0)
  expect((await relue(R2)).statut, 'base : R2 clôturée').toBe('cloturee')
})

// ═══ AERR149 (+ AERR11) — générateur en Édition complète : « Créer le lot » et Entrée ne soumettent pas gen-form ═══
/** Générateur ouvert sur `d` (Édition complète). */
async function ouvrirGenerateur(p, d, { ci }) {
  await p.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(p.locator('#gen-form')).toBeVisible({ timeout: 90_000 })
  if (ci) await expect(p.getByTestId('ci-profil'), 'générateur C&I').toBeVisible({ timeout: 90_000 })
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
}
const PRIX = (p) => p.locator('td[data-label="Prix unit. TTC"] input').first()
/** Prix de la 1ʳᵉ ligne modifié jusqu'à « Modifications non enregistrées » (le `dirty` qui arme la garde). */
async function modifierPrix(p, d) {
  const cle = `taqinor:draft:devis:edit:${d.id}`
  let n = 0
  await expect(async () => {
    n += 1
    await PRIX(p).fill(String(15000 + n))
    await expect(p.getByTestId('gen-barre-non-enregistre')).toBeVisible({ timeout: 4_000 })
  }, 'saisie modifiée (« Modifications non enregistrées »)').toPass({ timeout: 60_000 })
  await expect.poll(() => p.evaluate((k) => localStorage.getItem(k), cle), { timeout: 10_000 }).not.toBeNull().catch(() => undefined)
  return { valeur: String(15000 + n), cle, brouillon: await lireBrouillon(p, cle) }
}
const lireBrouillon = (p, cle) => p.evaluate((k) => {
  const v = localStorage.getItem(k)
  if (v === null) return null
  try { return JSON.stringify(JSON.parse(v).data ?? null) } catch { return v }
}, cle)

etape('PF12.2-AERR149', ['AERR149', 'AERR11'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-011')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr149di_${m}`
  await compteDuRole(nom, 'Directeur')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const d = await devisDe(api, admin, `${m}ci`, { ci: true })
  expect(d.statut, 'Given : un devis brouillon').toBe('brouillon')
  const lignesAvant = (await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire])
  const posts = []
  const ecritures = [] // toute autre écriture sur le devis, et toute navigation de document, pendant les gestes
  p.on('request', (q) => {
    const chemin = new URL(q.url()).pathname
    if (q.method() === 'POST' && new RegExp(`/ventes/devis/${d.id}/lots/$`).test(chemin)) posts.push(q.postDataJSON())
    else if (q.method() !== 'GET' && chemin.includes(`/ventes/devis/${d.id}/`)) ecritures.push(`${q.method()} ${chemin}`)
    if (q.isNavigationRequest() && q.frame() === p.mainFrame()) ecritures.push(`navigation ${q.url()}`)
  })
  const carte = p.getByTestId('lots-multi-sites')
  const conf = p.getByRole('alertdialog')
  const PERTE = 'Créer le lot recharge le devis : vos modifications non enregistrées seront perdues.'
  const ouvrirLots = async () => {
    const bascule = carte.getByRole('button', { name: 'Afficher' })
    if (await bascule.isVisible()) await bascule.click()
    await expect(carte.getByTestId('lot-formulaire')).toBeVisible({ timeout: 30_000 })
  }
  const lotsPost = (x) => x.request().method() === 'POST' && new RegExp(`/ventes/devis/${d.id}/lots/$`).test(new URL(x.url()).pathname)
  await ouvrirGenerateur(p, d, { ci: true })
  await ouvrirLots()
  const url = p.url()
  expect(url, 'générateur en Édition complète').toContain(`edit=${d.id}`)
  expect(await carte.locator('form').count(), 'le panneau des lots n\'est plus un <form> imbriqué').toBe(0)
  expect(await p.locator('#gen-form form').count(), 'aucun formulaire imbriqué dans gen-form').toBe(0)

  // 1) Saisie NON modifiée, clic « Créer le lot » : un POST lots/, aucune question, aucune soumission, URL inchangée.
  ecritures.length = 0
  await carte.locator('#lot-nom').fill(`Bâtiment B ${m}`)
  const r1 = p.waitForResponse(lotsPost, T)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  expect((await r1).status(), `clic : lot créé ; écritures/navigations : ${J(ecritures)}`).toBeLessThan(300)
  await expect(conf, 'clic, saisie non modifiée : aucune question').toHaveCount(0)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  expect(p.url(), 'clic : URL inchangée').toBe(url)
  expect(ecritures, 'clic : ni soumission du générateur ni navigation').toEqual([])
  await ouvrirLots()
  await expect(carte, 'clic : lot listé').toContainText(`Bâtiment B ${m}`, { timeout: 30_000 })
  suivi.verifie(5)

  // 2) Saisie NON modifiée, Entrée dans « Nom du lot » : un POST lots/, rien d'autre.
  ecritures.length = 0
  await carte.locator('#lot-nom').fill(`Bâtiment C ${m}`)
  const r2 = p.waitForResponse(lotsPost, T)
  await carte.locator('#lot-nom').press('Enter')
  expect((await r2).status(), `Entrée : lot créé ; écritures/navigations : ${J(ecritures)}`).toBeLessThan(300)
  await expect(conf, 'Entrée, saisie non modifiée : aucune question').toHaveCount(0)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  expect(p.url(), 'Entrée : URL inchangée').toBe(url)
  expect(ecritures, 'Entrée : ni soumission du générateur ni navigation').toEqual([])
  await ouvrirLots()
  await expect(carte, 'Entrée : lot listé').toContainText(`Bâtiment C ${m}`, { timeout: 30_000 })
  expect(posts.map((x) => x.nom_lot), 'deux créations').toEqual([`Bâtiment B ${m}`, `Bâtiment C ${m}`])

  // 3) Saisie MODIFIÉE : « Créer le lot » puis Entrée ⇒ la demande d'AERR11 d'abord ; « Annuler » garde tout.
  const { valeur, cle, brouillon } = await modifierPrix(p, d)
  for (const geste of ['clic', 'Entrée']) {
    ecritures.length = 0
    await carte.locator('#lot-nom').fill(`Lot annulé ${geste} ${m}`)
    if (geste === 'clic') await carte.getByRole('button', { name: 'Créer le lot' }).click()
    else await carte.locator('#lot-nom').press('Enter')
    await expect(conf, `${geste}, saisie modifiée : confirmation maison`).toBeVisible({ timeout: 30_000 })
    await expect(conf).toContainText(PERTE)
    await conf.getByRole('button', { name: 'Annuler' }).click()
    await expect(conf).toBeHidden()
    expect(posts.length, `${geste} + « Annuler » : aucun creerLotDevis`).toBe(2)
    expect(ecritures, `${geste} + « Annuler » : ni écriture ni navigation`).toEqual([])
    expect(p.url(), `${geste} + « Annuler » : URL inchangée`).toBe(url)
    await expect(PRIX(p), `${geste} + « Annuler » : saisie intacte`).toHaveValue(valeur)
    await expect(p.getByTestId('gen-barre-non-enregistre'), 'toujours « Modifications non enregistrées »').toBeVisible()
    expect(await lireBrouillon(p, cle), `brouillon de secours intact (${brouillon ? 'présent' : 'absent'} avant le geste)`).toBe(brouillon)
  }
  // « Créer le lot » confirmé : un POST, le devis est rechargé (la saisie non enregistrée est perdue, comme annoncé).
  await carte.locator('#lot-nom').fill(`Lot confirmé ${m}`)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  const r3 = p.waitForResponse(lotsPost, T)
  await conf.getByRole('button', { name: 'Créer le lot' }).click()
  expect((await r3).status(), 'confirmé : lot créé').toBeLessThan(300)
  await expect(PRIX(p), 'devis rechargé depuis le serveur').not.toHaveValue(valeur, { timeout: 60_000 })
  expect(p.url(), 'confirmé : URL inchangée').toBe(url)
  const NOMS = [`Bâtiment B ${m}`, `Bâtiment C ${m}`, `Lot confirmé ${m}`]
  expect(posts.map((x) => x.nom_lot), 'trois créations, jamais les lots annulés').toEqual(NOMS)

  // Persistance : GET lots/ ⇒ les trois lots ; les lignes du devis inchangées ; recharger ⇒ listés.
  const lots = await lireJson(await api.get(`${API}/ventes/devis/${d.id}/lots/`, T), 'lots')
  expect(lots.lots.map((l) => l.nom_lot).sort(), 'persistance : lots en base').toEqual([...NOMS].sort())
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire]), 'lignes inchangées').toEqual(lignesAvant)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await p.reload()
  await expect(p.locator('#gen-form')).toBeVisible({ timeout: 90_000 })
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await ouvrirLots()
  for (const n of NOMS) await expect(carte, `rechargé : ${n}`).toContainText(n, { timeout: 30_000 })
  // Réaffirmé sur l'écran rechargé : Entrée sans saisie modifiée ⇒ POST direct ; saisie modifiée ⇒ question (fin).
  ecritures.length = 0
  await carte.locator('#lot-nom').fill(`Bâtiment D ${m}`)
  const r4 = p.waitForResponse(lotsPost, T)
  await carte.locator('#lot-nom').press('Enter')
  expect((await r4).status(), 'rechargé, Entrée : lot créé').toBeLessThan(300)
  await expect(conf, 'rechargé : aucune question').toHaveCount(0)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  expect(ecritures, 'rechargé, Entrée : ni soumission ni navigation').toEqual([])
  await ouvrirLots()
  await expect(carte, 'rechargé, Entrée : lot listé').toContainText(`Bâtiment D ${m}`, { timeout: 30_000 })
  // Le devis est relu après la création (QJR548) : la saisie ne se modifie qu'une fois cette relecture finie.
  await p.waitForTimeout(3_000)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  const fin = await modifierPrix(p, d)
  await p.waitForTimeout(1_500)
  await expect(PRIX(p), 'rechargé : saisie modifiée tenue').toHaveValue(fin.valeur)
  await expect(p.getByTestId('gen-barre-non-enregistre'), 'rechargé : « Modifications non enregistrées »').toBeVisible()
  await carte.locator('#lot-nom').fill(`Lot final ${m}`)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  await expect(conf, 'rechargé, saisie modifiée : question').toContainText(PERTE)
  expect(posts.length, 'rien n\'est parti après la question').toBe(4)
})
