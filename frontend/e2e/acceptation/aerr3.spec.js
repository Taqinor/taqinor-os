// Preuves en direct ÉCRAN du groupe AERR (parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran »,
// dossier docs/audits/2026-11-11-parcours-PF12.md) : AERR1, 3, 4, 6, 7 (écrans d'argent), AERR2, 5, 9, 11 (devis),
// AERR12 (générateur, plan calepinage). Chaque étape joue le geste À L'ÉCRAN sous un compte d'un rôle LIVRÉ du registre
// (`permissions_registre.py`, relu par son nom dans la société démo ; l'argent sous « Commercial », qui porte `encaisser`),
// PROVOQUE vraiment l'échec (route Playwright déclarée AVANT par `suivi.attendre`, ou refus réel du serveur), AFFIRME ce
// que la clause nomme (avis, saisie gardée, message sous le champ, confirmation qui nomme), relit la base par l'API, recharge
// et réaffirme ; l'étape finit sur l'écran affirmé (capture). Données propres créées par les vraies routes (lead, devis
// envoyé, accepté, facturé) ; une facture à numéro légal ne se supprime jamais : elle reste sur la base jetable du runner.
// AERR114 n'est pas jouée ici : « Suppr » sous une boîte exige l'atelier (fond de carte, clés refusées hors taqinor.ma).
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('AERR', ['AERR1', 'AERR2', 'AERR3', 'AERR4', 'AERR5', 'AERR6', 'AERR7', 'AERR9', 'AERR11', 'AERR12'])
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
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[AERR] ${type} : ${description}`)
}

/** Rejoue une sonde HÔTE (`docs/audits/sondes/AERR/<c>.py`, sans Django ni base) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AERR', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeFausse(constat) {
  const s = sondeHote(constat)
  expect(s.ok, `sonde ${constat} exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde ${constat} : ${J(s.res.observe)}`).toBe(false)
}
/** Sonde dont le détecteur compte un motif que la tâche GARDE à dessein (relecture totale, fête au clic) :
 *  rejouée et NOMMÉE dans le rapport, jamais comptée — la preuve est l'écran. */
function sondeNommee(constat, testInfo) {
  const s = sondeHote(constat)
  note(testInfo, `sonde ${constat} (nommée, non comptée)`, s.ok ? `repro=${s.res.repro} ${J(s.res.observe).slice(0, 400)}` : `non exécutée : ${s.err}`)
}

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo ; {id, porte: encaisser ?}. */
const compteDuRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'porte': 'encaisser' in (r.permissions or []), 'systeme': r.est_systeme})`)

/** Écran sous le compte `nom` : contexte neuf (accueil et visites vus, SW bloqué), observé ; la page demo_admin est
 *  refermée (la capture montre l'écran du rôle). `api` = requêtes de CE compte (même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  ouverts.push(ctx)
  // Pré-chargement matinal de la tournée (NTMOB28, `PrechargementTournee.jsx`, monté par Layout sur tout écran avant
  // midi) marqué « fait aujourd'hui » : pour un rôle sans lecture des interventions il appelle `ma-tournee` en 403
  // (défaut antérieur, hors des Files des tâches AERR, rapporté à part) — il n'est pas l'objet de ces étapes.
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p: suivi.surveiller(await ctx.newPage()), api: ctx.request, ctx }
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
/** Vente acceptée (demo_admin) puis facturée « complete » par `cree` (créateur = le rôle joué) ; 10 000 HT = 12 000 TTC.
 *  L'acceptation pose un acompte automatique BROUILLON (référence provisoire) : il est remplacé (`remplacer_brouillons`). */
async function factureDe(cree, admin, m, { emettre }) {
  const d = await devisDe(cree, admin, m, { envoye: true })
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR' } }), 'accepter')
  const rep = await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut, ttc: Number(rep.facture.total_ttc) }
}
const factureLue = async (api, id) => lireJson(await api.get(`${API}/ventes/factures/${id}/`, T), 'facture relue')

/** Route tenue : chaque requête qui passe attend `lacher()`, puis `issue(route)` (abort par défaut). */
function porte() {
  let lacher
  let signaler
  const ouverte = new Promise((r) => { lacher = r })
  const arrivee = new Promise((r) => { signaler = r })
  return {
    arrivee, lacher: () => lacher(),
    gestion: (issue = (route) => route.abort('failed')) => async (route) => { signaler(); await ouverte; await issue(route) },
  }
}
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })
const valeurMad = (texte) => Number(String(texte).replace(/\D/g, '')) / 100
const tuile = (p, libelle) => p.getByText(libelle, { exact: true }).first().locator('xpath=../..').locator('.num')
const kpis = async (api) => lireJson(await api.get(`${API}/ventes/factures/kpis/`, T), 'kpis')

// ═══ PF12.3 — AERR1 : Ventes → Factures, encaisser pendant que la relecture de la liste est tenue puis coupée ═══
etape('PF12.3-AERR1-ecran', ['AERR1'], async ({ page, suivi, testInfo }) => {
  sondeNommee('C-AERR-001', testInfo)
  const admin = page.context().request
  const m = marque()
  const nom = `aerr1co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte, 'le rôle Commercial porte encaisser').toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const fs = []
  for (let i = 0; i < 3; i += 1) fs.push(await factureDe(api, admin, `${m}f${i}`, { emettre: true }))
  expect(fs.map((f) => f.statut), 'Given : 3 factures émises').toEqual(['emise', 'emise', 'emise'])
  const ligne = (f) => p.locator(`#facture-row-${f.id}`)
  await p.goto('/ventes/factures')
  for (const f of fs) await expect(ligne(f), `${f.reference} affichée`).toBeVisible({ timeout: 90_000 })

  const LISTE = /\/api\/django\/ventes\/factures\/\?/
  suivi.attendre(LISTE, 'reseau')
  const g = porte()
  await p.route(LISTE, g.gestion())
  await ligne(fs[0]).getByRole('button', { name: 'Encaisser', exact: true }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${fs[0].reference}` })
  await expect(dlg, 'boîte Paiement ouverte').toBeVisible({ timeout: 30_000 })
  const autre = dlg.getByRole('switch', { name: 'Créer un autre' })
  await autre.click()
  await expect(autre, '« Créer un autre » allumé').toHaveAttribute('aria-checked', 'true')
  await dlg.locator('#pay-montant').fill('1000')
  await dlg.locator('#pay-ref').fill(`AERR1-A-${m}`)
  const paie = p.waitForResponse((x) => x.request().method() === 'POST' && /\/enregistrer-paiement\/$/.test(new URL(x.url()).pathname), T)
  await dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  expect((await paie).status(), 'paiement enregistré').toBeLessThan(300)
  await g.arrivee // la relecture de la liste est partie et TENUE
  await expect(dlg.locator('#pay-montant'), '« Créer un autre » : champs vidés, boîte ouverte').toHaveValue('')
  await dlg.locator('#pay-montant').fill('500')
  await dlg.locator('#pay-ref').fill(`AERR1-B-${m}`)
  for (const f of fs) await expect(ligne(f), `relecture EN COURS : ${f.reference} reste affichée`).toBeVisible()
  g.lacher() // la relecture est rejetée (réseau coupé)
  const avis = p.getByTestId('factures-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  await expect(avis.getByRole('button', { name: 'Réessayer' }), 'avis avec « Réessayer »').toBeVisible()
  for (const f of fs) await expect(ligne(f), `relecture RATÉE : ${f.reference} reste affichée`).toBeVisible()
  await expect(p.getByText('Erreur de chargement'), 'jamais l\'écran plein d\'erreur').toHaveCount(0)
  await expect(dlg, 'la boîte Paiement reste montée').toBeVisible()
  await expect(dlg.locator('#pay-montant'), 'saisie du 2ᵉ paiement gardée').toHaveValue('500')
  await expect(dlg.locator('#pay-ref')).toHaveValue(`AERR1-B-${m}`)
  // Persistance (le geste, pas la relecture) : le 1er paiement est en base.
  expect(Number((await factureLue(api, fs[0].id)).montant_paye), 'persistance : 1 000 payés sur la facture').toBe(1000)
  // Réessayer → liste relue ; recharger → mêmes lignes.
  await dlg.getByRole('button', { name: 'Annuler' }).click()
  await p.unroute(LISTE)
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'Réessayer : avis retiré').toBeHidden({ timeout: 30_000 })
  await p.reload()
  for (const f of fs) await expect(ligne(f), `après rechargement : ${f.reference}`).toBeVisible({ timeout: 90_000 })
  // Réaffirmé sur l'écran rechargé, et l'étape finit sur l'écran affirmé (capture).
  await p.route(LISTE, (route) => route.abort('failed'))
  await ligne(fs[1]).getByRole('button', { name: 'Encaisser', exact: true }).click()
  const dlg2 = p.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${fs[1].reference}` })
  await expect(dlg2).toBeVisible({ timeout: 30_000 })
  const autre2 = dlg2.getByRole('switch', { name: 'Créer un autre' })
  if ((await autre2.getAttribute('aria-checked')) !== 'true') await autre2.click()
  await expect(autre2).toHaveAttribute('aria-checked', 'true')
  await dlg2.locator('#pay-montant').fill('200')
  const paie2 = p.waitForResponse((x) => x.request().method() === 'POST' && /\/enregistrer-paiement\/$/.test(new URL(x.url()).pathname), T)
  await dlg2.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  expect((await paie2).status()).toBeLessThan(300)
  await expect(avis, 'rechargé : relecture ratée ⇒ avis').toBeVisible({ timeout: 30_000 })
  await dlg2.locator('#pay-montant').fill('300')
  for (const f of fs) await expect(ligne(f)).toBeVisible()
  await expect(dlg2, 'boîte montée').toBeVisible()
  await expect(dlg2.locator('#pay-montant')).toHaveValue('300')
})

// ═══ PF12.3 — AERR2 : Ventes → Devis, supprimer un brouillon pendant que la relecture est tenue puis coupée ═══
etape('PF12.3-AERR2-ecran', ['AERR2'], async ({ page, suivi, testInfo }) => {
  sondeNommee('C-AERR-002', testInfo)
  const admin = page.context().request
  const m = marque()
  const nom = `aerr2ad_${m}`
  await compteDuRole(nom, 'Administrateur') // « Supprimer » d'un devis : palier admin (canDelete)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const b1 = await devisDe(api, admin, `${m}b1`)
  const b2 = await devisDe(api, admin, `${m}b2`)
  const e3 = await devisDe(api, admin, `${m}e3`, { envoye: true })
  const b4 = await devisDe(api, admin, `${m}b4`)
  expect([b1.statut, b2.statut, e3.statut, b4.statut], 'Given').toEqual(['brouillon', 'brouillon', 'envoye', 'brouillon'])
  const ligne = (d) => p.locator(`#devis-row-${d.id}`)
  const supprimer = async (d) => {
    await ligne(d).getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
    await p.getByRole('menuitem', { name: 'Supprimer' }).click()
    const conf = p.getByRole('alertdialog')
    await expect(conf).toContainText(`Supprimer le devis ${d.reference} ?`)
    const del = p.waitForResponse((x) => x.request().method() === 'DELETE' && new RegExp(`/ventes/devis/${d.id}/$`).test(new URL(x.url()).pathname), T)
    await conf.getByRole('button', { name: 'Supprimer' }).click()
    expect((await del).status(), `suppression de ${d.reference}`).toBeLessThan(300)
    // Le menu « Plus d'actions » reste ouvert derrière la confirmation (onSelect + preventDefault) : Échap le ferme.
    await expect(conf).toBeHidden()
    if (await p.getByRole('menu').count()) await p.keyboard.press('Escape')
    await expect(p.getByRole('menu')).toHaveCount(0)
  }
  await p.goto('/ventes/devis')
  for (const d of [b1, b2, e3, b4]) await expect(ligne(d)).toBeVisible({ timeout: 90_000 })

  const LISTE = /\/api\/django\/ventes\/devis\/\?/
  suivi.attendre(LISTE, 'reseau')
  const g = porte()
  await p.route(LISTE, g.gestion())
  await supprimer(b1)
  await g.arrivee
  for (const d of [b2, e3]) await expect(ligne(d), `relecture EN COURS : ${d.reference} reste`).toBeVisible()
  // Une boîte ouverte pendant la relecture : la modale d'acceptation du devis envoyé, saisie en cours.
  await ligne(e3).getByRole('button', { name: 'Accepter', exact: true }).click()
  const acc = p.getByRole('dialog').filter({ hasText: `Accepter le devis — ${e3.reference}` })
  await expect(acc).toBeVisible()
  await acc.locator('#accept-nom').fill('Karim Alaoui')
  g.lacher()
  const avis = p.getByTestId('devis-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  await expect(avis.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  for (const d of [b2, e3, b4]) await expect(ligne(d), `relecture RATÉE : ${d.reference} reste`).toBeVisible()
  await expect(acc, 'la modale d\'acceptation reste montée').toBeVisible()
  await expect(acc.locator('#accept-nom'), 'sa saisie est gardée').toHaveValue('Karim Alaoui')
  // Persistance : le brouillon est supprimé en base (la relecture ratée n'y change rien).
  expect((await api.get(`${API}/ventes/devis/${b1.id}/`, T)).status(), 'persistance : brouillon supprimé').toBe(404)
  await acc.getByRole('button', { name: 'Annuler' }).click()
  await p.unroute(LISTE)
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'Réessayer : avis retiré').toBeHidden({ timeout: 30_000 })
  await expect(ligne(b1), 'liste relue : le supprimé est parti').toHaveCount(0)
  await p.reload()
  for (const d of [b2, e3, b4]) await expect(ligne(d), `après rechargement : ${d.reference}`).toBeVisible({ timeout: 90_000 })
  await expect(ligne(b1)).toHaveCount(0)
  // Réaffirmé sur l'écran rechargé ; l'étape finit sur l'écran affirmé.
  await p.route(LISTE, (route) => route.abort('failed'))
  await supprimer(b4)
  await expect(avis, 'rechargé : relecture ratée ⇒ avis').toBeVisible({ timeout: 30_000 })
  for (const d of [b2, e3]) await expect(ligne(d)).toBeVisible()
})

// ═══ PF12.3 — AERR3 : tuiles d'argent relues après l'encaissement groupé, sans recharger ═══
etape('PF12.3-AERR3-ecran', ['AERR3'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-003')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr3co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte).toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const f = await factureDe(api, admin, `${m}f`, { emettre: true })
  const g2 = await factureDe(api, admin, `${m}g`, { emettre: true })
  expect([f.statut, f.ttc, g2.statut, g2.ttc], 'Given : deux factures émises de 12 000 MAD impayées').toEqual(['emise', 12000, 'emise', 12000])
  const KPIS = /\/api\/django\/ventes\/factures\/kpis\/$/
  const lireTuiles = async () => ({
    encaisse: valeurMad(await tuile(p, 'Encaissé ce mois').innerText()),
    du: valeurMad(await tuile(p, 'Total dû').innerText()),
    retard: valeurMad(await tuile(p, 'En retard').innerText()),
  })
  const servies = (k) => ({ encaisse: Number(k.encaisse_mois), du: Number(k.total_du), retard: Number(k.total_en_retard) })
  const encaisserGroupe = async (fa) => {
    await p.getByRole('checkbox', { name: `Sélectionner la facture ${fa.reference}` }).click()
    await p.getByRole('region', { name: 'Actions factures en masse' }).getByRole('button', { name: 'Encaissement groupé' }).click()
    const dlg = p.getByRole('dialog').filter({ has: p.locator('#eg-montant') })
    await expect(dlg.locator('#eg-montant'), 'montant prérempli : le reste dû').toHaveValue('12000')
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && /\/encaissement-groupe\/$/.test(new URL(x.url()).pathname), T)
    await dlg.getByRole('button', { name: 'Encaisser', exact: true }).click()
    expect((await rep).status(), 'encaissement groupé').toBeLessThan(300)
    await expect(dlg).toBeHidden({ timeout: 30_000 })
  }
  await p.goto('/ventes/factures')
  await expect(p.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 90_000 })
  const k0 = servies(await kpis(api))
  await expect.poll(lireTuiles, { timeout: 30_000, message: 'tuiles au montage = serveur' }).toEqual(k0)

  const relue = p.waitForResponse((x) => KPIS.test(x.url()) && x.request().method() === 'GET', T)
  await encaisserGroupe(f)
  await relue
  const k1 = servies(await kpis(api))
  expect(k1.encaisse, 'serveur : encaissé ce mois + 12 000').toBe(k0.encaisse + 12000)
  await expect.poll(lireTuiles, { timeout: 30_000, message: 'après le geste, SANS recharger : tuiles = nouvelles valeurs servies' }).toEqual(k1)
  await expect(p.getByText('Indicateurs pas à jour — la relecture a échoué.')).toHaveCount(0)

  // Relecture des tuiles ratée : anciennes valeurs + mention « pas à jour ».
  suivi.attendre(KPIS, 'reseau')
  await p.route(KPIS, (route) => route.abort('failed'))
  await encaisserGroupe(g2)
  await expect(p.getByText('Indicateurs pas à jour — la relecture a échoué.'), 'mention « pas à jour »').toBeVisible({ timeout: 30_000 })
  const k2 = servies(await kpis(api))
  expect(k2.encaisse, 'serveur : 2ᵉ encaissement compté').toBe(k1.encaisse + 12000)
  expect(await lireTuiles(), 'échec de relecture : les anciennes valeurs restent').toEqual(k1)
  // Persistance : recharger ⇒ le serveur fait foi.
  expect((await factureLue(api, f.id)).statut, 'persistance : facture soldée').toBe('payee')
  await p.unroute(KPIS)
  await p.reload()
  await expect(p.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 90_000 })
  await expect.poll(lireTuiles, { timeout: 30_000, message: 'rechargé : tuiles = serveur' }).toEqual(k2)
  await expect(p.getByText('Indicateurs pas à jour — la relecture a échoué.')).toHaveCount(0)
})

// ═══ PF12.3 — AERR4 : Ventes → Relances, lecture coupée puis deux bascules rapides de file ═══
etape('PF12.3-AERR4-ecran', ['AERR4'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-004')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr4co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte).toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const fs = [await factureDe(api, admin, `${m}a`, { emettre: true }), await factureDe(api, admin, `${m}b`, { emettre: true })]
  const file = await lireJson(await api.get(`${API}/ventes/relances/`, T), 'file servie')
  expect(fs.every((f) => file.some((r) => r.id === f.id)), 'Given : les 2 impayées sont dans « Toutes »').toBe(true)
  expect((await lireJson(await api.get(`${API}/ventes/relances/?mes_relances=1`, T), 'mes relances')).length, '« Mes relances » servie vide').toBe(0)
  const table = p.getByRole('table', { name: 'Factures à relancer' })
  const ligne = (f) => table.getByRole('row').filter({ hasText: f.reference })
  const FESTIF = 'Aucune facture impayée'
  const TOUTES = /\/api\/django\/ventes\/relances\/$/
  const MES = /\/api\/django\/ventes\/relances\/\?mes_relances=1/

  // Lecture rejetée au chargement : erreur + Réessayer, jamais l'état festif.
  suivi.attendre(TOUTES, 'reseau')
  await p.route(TOUTES, (route) => route.abort('failed'))
  await p.goto('/ventes/relances')
  const erreur = p.getByTestId('relances-erreur')
  await expect(erreur, 'erreur de lecture affichée').toBeVisible({ timeout: 60_000 })
  await expect(erreur).toContainText('Impossible de charger la file de relances.')
  await expect(erreur.getByRole('button', { name: 'Réessayer' })).toBeVisible()
  await expect(p.getByText(FESTIF), 'jamais « Aucune facture impayée » sur une panne').toHaveCount(0)
  await p.unroute(TOUTES)
  await erreur.getByRole('button', { name: 'Réessayer' }).click()
  for (const f of fs) await expect(ligne(f), `Réessayer : ${f.reference}`).toBeVisible({ timeout: 60_000 })
  await expect(erreur).toBeHidden()

  // Deux bascules : « Mes relances » (réponse TENUE, arrive en dernier) puis « Toutes ».
  const g = porte()
  await p.route(MES, g.gestion((route) => route.continue()))
  const choisir = async (libelle) => {
    await p.getByRole('combobox', { name: 'Filtrer la file de relance' }).click()
    await p.getByRole('option', { name: libelle, exact: true }).click()
  }
  await choisir('Mes relances')
  await g.arrivee
  for (const f of fs) await expect(ligne(f), `relecture EN COURS : ${f.reference} reste affichée`).toBeVisible()
  const toutes = p.waitForResponse((x) => TOUTES.test(x.url()), T)
  await choisir('Toutes les factures')
  expect((await toutes).status()).toBe(200)
  const tardive = p.waitForResponse((x) => MES.test(x.url()), T)
  g.lacher()
  expect((await tardive).status(), 'la réponse « Mes relances » arrive en dernier').toBe(200)
  await expect(p.getByRole('combobox', { name: 'Filtrer la file de relance' })).toContainText('Toutes les factures')
  for (const f of fs) await expect(ligne(f), `seule la dernière demandée s'affiche : ${f.reference}`).toBeVisible()
  await expect(p.getByText('Aucune relance qui vous soit assignée'), 'la réponse tardive est ignorée').toHaveCount(0)
  await p.unroute(MES)
  // Persistance : recharger ⇒ la file servie.
  await p.reload()
  for (const f of fs) await expect(ligne(f), `rechargé : ${f.reference}`).toBeVisible({ timeout: 60_000 })
  await expect(p.getByText(FESTIF)).toHaveCount(0)
})

// ═══ PF12.2 — AERR5 : accepter un devis C&I avec un ICE faux (refus RÉEL du serveur) ═══
etape('PF12.2-AERR5-ecran', ['AERR5'], async ({ page, suivi, testInfo }) => {
  sondeNommee('C-AERR-005', testInfo)
  const admin = page.context().request
  const m = marque()
  const nom = `aerr5co_${m}`
  await compteDuRole(nom, 'Commercial')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const d = await devisDe(api, admin, `${m}ci`, { ci: true, envoye: true })
  expect(d.statut, 'Given : devis C&I envoyé').toBe('envoye')
  const ACCEPTER = new RegExp(`/api/django/ventes/devis/${d.id}/accepter/$`)
  suivi.attendre(ACCEPTER, 400)
  const ligne = p.locator(`#devis-row-${d.id}`)
  const ICE = '1234567890123456' // 16 chiffres : refusé par validate_ice_ma
  const acc = p.getByRole('dialog').filter({ hasText: `Accepter le devis — ${d.reference}` })
  const remplir = async () => {
    await ligne.getByRole('button', { name: 'Accepter', exact: true }).click()
    await expect(acc).toBeVisible()
    await expect(acc.getByTestId('identite-entreprise'), 'bloc entreprise d\'un C&I').toBeVisible()
    await acc.locator('#accept-nom').fill('Karim Alaoui')
    await acc.locator('#accept-raison-sociale').fill(`Boulangerie AERR ${m}`)
    await acc.locator('#accept-qualite').fill('Gérant')
    await acc.locator('#accept-ice').fill(ICE)
    return acc.locator('#accept-date').inputValue()
  }
  const garde = async (date) => {
    await expect(acc, 'modale du MÊME devis rouverte').toBeVisible({ timeout: 30_000 })
    await expect(acc.locator('#accept-nom')).toHaveValue('Karim Alaoui')
    await expect(acc.locator('#accept-date')).toHaveValue(date)
    await expect(acc.locator('#accept-raison-sociale')).toHaveValue(`Boulangerie AERR ${m}`)
    await expect(acc.locator('#accept-qualite')).toHaveValue('Gérant')
    await expect(acc.locator('#accept-ice')).toHaveValue(ICE)
  }
  const confirmer = async () => {
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && ACCEPTER.test(x.url()), T)
    await acc.getByRole('button', { name: "Confirmer l'acceptation" }).click()
    return rep
  }
  await p.goto('/ventes/devis')
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  const date = await remplir()
  const r1 = await confirmer()
  expect(r1.status(), 'refus RÉEL du serveur').toBe(400)
  const corps = await r1.json()
  expect(corps.champ, 'le serveur nomme le champ').toBe('entreprise.ice')
  await garde(date)
  const sousIce = acc.locator('#accept-ice').locator('xpath=..')
  await expect(sousIce, 'le message est sous le champ ICE').toContainText(corps.detail)
  // Persistance : rien d'accepté ; recharger et réaffirmer.
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut, 'persistance : toujours envoyé').toBe('envoye')
  await acc.getByRole('button', { name: 'Annuler' }).click()
  await p.reload()
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  const date2 = await remplir()
  expect((await confirmer()).status()).toBe(400)
  await garde(date2)
  await expect(sousIce, 'rechargé : message sous ICE').toContainText(corps.detail)
  // « Date invalide » (réponse injectée, forme servie par devis_cycle.accepter) : sous la date, saisie gardée.
  await p.route(ACCEPTER, (route) => route.fulfill({ status: 400, contentType: 'application/json', body: J({ detail: 'Date invalide (attendu AAAA-MM-JJ).' }) }))
  expect((await confirmer()).status()).toBe(400)
  await garde(date2)
  await expect(acc.locator('#accept-date').locator('xpath=..'), '« Date invalide » sous la date').toContainText('Date invalide (attendu AAAA-MM-JJ).')
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).statut).toBe('envoye')
})

// ═══ PF12.1 — AERR6 : modifier l'échéance d'une facture émise, refus 400 par champ ═══
etape('PF12.1-AERR6-ecran', ['AERR6'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-006')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr6co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte).toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const f = await factureDe(api, admin, `${m}f`, { emettre: true })
  const avant = (await factureLue(api, f.id)).date_echeance
  expect(f.statut === 'emise' && !!avant, 'Given : facture émise avec échéance').toBe(true)
  const nouvelle = new Date(Date.parse(`${avant}T12:00:00Z`) + 15 * 86_400_000).toISOString().slice(0, 10)
  const PATCH = new RegExp(`/api/django/ventes/factures/${f.id}/$`)
  suivi.attendre(PATCH, 400)
  let corpsRefus = null
  await p.route(PATCH, (route) => (route.request().method() === 'PATCH' && corpsRefus
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J(corpsRefus) })
    : route.continue()))
  const ouvrir = async () => {
    await p.goto(`/ventes/factures?id=${f.id}`)
    await expect(p.locator('#fc-echeance'), 'formulaire de la facture émise ouvert').toBeVisible({ timeout: 90_000 })
    await expect(p.locator('#fc-echeance')).toHaveValue(avant)
  }
  const mettreAJour = async (corps) => {
    corpsRefus = corps
    const rep = p.waitForResponse((x) => x.request().method() === 'PATCH' && PATCH.test(x.url()), T)
    await p.getByRole('button', { name: 'Mettre à jour' }).click()
    expect((await rep).status()).toBe(400)
  }
  const sousEcheance = async () => {
    await expect(p.locator('#fc-echeance-error'), 'message sous « Date d\'échéance »').toContainText('Période verrouillée.', { timeout: 30_000 })
    await expect(p.locator('#fc-echeance'), 'champ marqué').toHaveAttribute('aria-invalid', 'true')
    await expect(p.locator('#fc-echeance'), 'saisie gardée, formulaire ouvert').toHaveValue(nouvelle)
  }
  await ouvrir()
  await p.locator('#fc-echeance').fill(nouvelle)
  await mettreAJour({ date_echeance: ['Période verrouillée.'] })
  await sousEcheance()
  // Clé hors formulaire : au bandeau, avec le nom du champ.
  await mettreAJour({ reference_externe: ['Refusée par le serveur.'] })
  await expect(p.getByRole('alert').filter({ hasText: 'reference_externe : Refusée par le serveur.' }), 'bandeau nommant le champ').toBeVisible({ timeout: 30_000 })
  await expect(p.locator('#fc-echeance')).toHaveValue(nouvelle)
  // Persistance : rien n'a été écrit ; recharger et réaffirmer.
  expect((await factureLue(api, f.id)).date_echeance, 'persistance : échéance inchangée en base').toBe(avant)
  corpsRefus = null
  // « Annuler » du formulaire (ferme sans question ; la garde de sortie tombe avec lui) puis recharger.
  await p.getByRole('dialog').filter({ has: p.locator('#fc-echeance') }).getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(p.locator('#fc-echeance')).toHaveCount(0)
  await ouvrir()
  await p.locator('#fc-echeance').fill(nouvelle)
  await mettreAJour({ date_echeance: ['Période verrouillée.'] })
  await sousEcheance()
})

// ═══ PF12.4 — AERR7 : actions de masse sur les factures, confirmation qui dit le nombre et les références ═══
etape('PF12.4-AERR7-ecran', ['AERR7'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-007')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr7co_${m}`
  expect((await compteDuRole(nom, 'Commercial')).porte).toBe(true)
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const fs = [await factureDe(api, admin, `${m}a`, { emettre: false }), await factureDe(api, admin, `${m}b`, { emettre: false })]
  expect(fs.map((f) => f.statut), 'Given : deux brouillons').toEqual(['brouillon', 'brouillon'])
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && /\/ventes\/factures\/bulk\/$/.test(new URL(q.url()).pathname)) envois.push(q.postDataJSON()) })
  const barre = p.getByRole('region', { name: 'Actions factures en masse' })
  const conf = p.getByRole('alertdialog')
  const cocher = async (liste) => {
    for (const f of liste) await p.getByRole('checkbox', { name: `Sélectionner la facture ${f.reference}` }).check()
    await expect(barre).toContainText('2 factures sélectionnées')
  }
  const demander = async (bouton, titre, liste) => {
    await barre.getByRole('button', { name: bouton, exact: true }).click()
    await expect(conf, `« ${bouton} » demande`).toBeVisible()
    await expect(conf).toContainText(titre)
    await expect(conf, 'la boîte nomme les références').toContainText(liste.map((f) => f.reference).join(', '))
  }
  await p.goto('/ventes/factures')
  for (const f of fs) await expect(p.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 90_000 })
  await cocher(fs)
  for (const [bouton, titre] of [['Envoyer par email', 'Envoyer 2 factures par e-mail ?'], ['Relancer', 'Relancer 2 factures ?'], ['Émettre', 'Émettre 2 factures ?']]) {
    await demander(bouton, titre, fs)
    await conf.getByRole('button', { name: 'Annuler' }).click()
    await expect(conf).toBeHidden()
    expect(envois, `« Annuler » sur « ${bouton} » : aucun appel bulkFactures`).toEqual([])
    await expect(barre, 'sélection gardée').toContainText('2 factures sélectionnées')
  }
  await demander('Émettre', 'Émettre 2 factures ?', fs)
  const rep = p.waitForResponse((x) => x.request().method() === 'POST' && /\/ventes\/factures\/bulk\/$/.test(new URL(x.url()).pathname), T)
  await conf.getByRole('button', { name: 'Confirmer' }).click()
  expect((await rep).status()).toBe(200)
  expect(envois, '« Confirmer » ⇒ bulkFactures(emettre, les 2 ids)').toEqual([{ action: 'emettre', ids: fs.map((f) => f.id) }])
  await expect(toast(p, 'Émettre : 2 facture(s) traitée(s).')).toBeVisible({ timeout: 30_000 })
  // Persistance : les deux sont émises en base, sous un numéro légal (jamais supprimable).
  const emises = []
  for (const f of fs) emises.push(await factureLue(api, f.id))
  expect(emises.map((f) => f.statut), 'persistance : émises').toEqual(['emise', 'emise'])
  expect(emises.every((f) => !f.reference.startsWith('BROUILLON-')), 'numéro légal attribué').toBe(true)
  await p.reload()
  for (const f of emises) await expect(p.locator(`#facture-row-${f.id}`), `rechargé : ${f.reference}`).toContainText(f.reference, { timeout: 90_000 })
  // « Générer le PDF » (sans effet client) part sans question.
  await cocher(emises)
  const pdf = p.waitForResponse((x) => x.request().method() === 'POST' && /\/ventes\/factures\/bulk\/$/.test(new URL(x.url()).pathname), T)
  await barre.getByRole('button', { name: 'Générer le PDF', exact: true }).click()
  expect((await pdf).status()).toBe(200)
  await expect(conf, '« Générer le PDF » : aucune question').toHaveCount(0)
  expect(envois[1], 'appel direct').toEqual({ action: 'generer-pdf', ids: emises.map((f) => f.id) })
  // L'étape finit sur l'écran affirmé : la question nommée de « Envoyer par email » (références légales).
  if (!(await barre.isVisible())) await cocher(emises)
  await demander('Envoyer par email', 'Envoyer 2 factures par e-mail ?', emises)
  expect(envois.length, 'rien n\'est parti sans « Confirmer »').toBe(2)
})

// ═══ PF12.1 — AERR9 : « Copier le lien » quand le presse-papier refuse ═══
etape('PF12.1-AERR9-ecran', ['AERR9'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-009')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr9co_${m}`
  await compteDuRole(nom, 'Commercial')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const d1 = await devisDe(api, admin, `${m}d1`)
  const d2 = await devisDe(api, admin, `${m}d2`)
  expect([d1.statut, d2.statut], 'Given : deux brouillons').toEqual(['brouillon', 'brouillon'])
  // Presse-papier piloté : `refus` rejette writeText (NotAllowedError), `ok` le résout et garde le texte copié.
  const pressePapier = (mode) => p.evaluate((x) => {
    const writeText = x === 'refus'
      ? () => Promise.reject(new DOMException('Écriture refusée', 'NotAllowedError'))
      : (t) => { window.__copie = t; return Promise.resolve() }
    if (navigator.clipboard) Object.defineProperty(navigator.clipboard, 'writeText', { value: writeText, configurable: true })
    else Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  }, mode)
  // Menus ouverts au CLAVIER : les avis d'échec (20 s, coin bas-droit) recouvrent le bouton « ⋯ » des lignes.
  const menu = async (d, item) => {
    await p.locator(`#devis-row-${d.id}`).getByRole('button', { name: `Plus d'actions — ${d.reference}` }).press('Enter')
    await p.getByRole('menuitem', { name: item }).press('Enter')
  }
  const lienServi = async (d, item) => {
    const rep = p.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/devis/${d.id}/share-link/$`).test(new URL(x.url()).pathname), T)
    await menu(d, item)
    const r = await rep
    expect(r.status()).toBeLessThan(300)
    return r.json()
  }
  const SUCCES = 'Lien copié — devis marqué envoyé.'
  await p.goto('/ventes/devis')
  await expect(p.locator(`#devis-row-${d1.id}`)).toBeVisible({ timeout: 90_000 })
  // Témoin : writeText résolu ⇒ succès actuel, et le presse-papier a bien reçu l'URL.
  await pressePapier('ok')
  const s2 = await lienServi(d2, /Copier le lien de la proposition/)
  await expect(toast(p, SUCCES), 'témoin : copie réussie annoncée').toBeVisible({ timeout: 30_000 })
  expect(await p.evaluate(() => window.__copie), 'le presse-papier a reçu le lien').toContain(s2.path)
  await expect(toast(p, SUCCES)).toBeHidden({ timeout: 30_000 })
  // writeText rejeté : jamais « Lien copié », l'URL publique est montrée, et le devis est dit envoyé.
  await pressePapier('refus')
  const s1 = await lienServi(d1, /Copier le lien de la proposition/)
  const echec = toast(p, 'Copie impossible — devis marqué envoyé.')
  await expect(echec, 'message d\'échec').toBeVisible({ timeout: 30_000 })
  await expect(echec, 'il porte l\'URL publique complète').toContainText(s1.path)
  await expect(toast(p, SUCCES), 'aucun « Lien copié »').toHaveCount(0)
  // Persistance : le devis est bien envoyé ; recharger et réaffirmer.
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d1.id}/`, T), 'devis relu')).statut, 'persistance : envoyé').toBe('envoye')
  await p.reload()
  await expect(p.locator(`#devis-row-${d1.id}`).getByRole('button', { name: 'Accepter', exact: true }), 'rechargé : la ligne est « envoyé »').toBeVisible({ timeout: 90_000 })
  await pressePapier('refus')
  // Lien interne et aperçu interne : même règle.
  await menu(d1, 'Lien interne')
  const interne = toast(p, 'Copie impossible — copiez le lien ci-dessous.')
  await expect(interne, 'lien interne : échec dit').toBeVisible({ timeout: 30_000 })
  await expect(interne).toContainText(`/ventes/devis?devis=${d1.id}`)
  await expect(toast(p, 'Lien interne du devis copié.')).toHaveCount(0)
  const s3 = await lienServi(d1, /Copier l.aperçu interne/)
  const apercu = toast(p, 'Copie impossible — aperçu interne ci-dessous')
  await expect(apercu, 'aperçu interne : échec dit').toBeVisible({ timeout: 30_000 })
  await expect(apercu).toContainText(s3.path_interne)
  await expect(toast(p, 'Aperçu interne copié')).toHaveCount(0)
  await expect(toast(p, SUCCES)).toHaveCount(0)
})

/** Générateur ouvert sur `d` (Édition complète). */
async function ouvrirGenerateur(p, d, { ci }) {
  await p.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(p.locator('#gen-form')).toBeVisible({ timeout: 90_000 })
  if (ci) await expect(p.getByTestId('ci-profil'), 'générateur C&I').toBeVisible({ timeout: 90_000 })
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
}
const PRIX = (p) => p.locator('td[data-label="Prix unit. TTC"] input').first()
/** Prix de la 1ʳᵉ ligne modifié jusqu'à ce que l'écran se dise « Modifications non enregistrées » (le `dirty` qui arme
 *  la garde) — une frappe dans la fenêtre de référence (QJR581, 1,5 s après le chargement) ne compte pas : on refrappe. */
async function modifierPrix(p, d) {
  const cle = `taqinor:draft:devis:edit:${d.id}`
  let n = 0
  await expect(async () => {
    n += 1
    await PRIX(p).fill(String(15000 + n))
    await expect(p.getByTestId('gen-barre-non-enregistre')).toBeVisible({ timeout: 4_000 })
  }, 'saisie modifiée (« Modifications non enregistrées »)').toPass({ timeout: 60_000 })
  // Brouillon de secours (autosave débouncé 800 ms) : lu tel quel pour vérifier qu'« Annuler » le laisse intact.
  await expect.poll(() => p.evaluate((k) => localStorage.getItem(k), cle), { timeout: 10_000 }).not.toBeNull().catch(() => undefined)
  return { valeur: String(15000 + n), cle, brouillon: await lireBrouillon(p, cle) }
}
/** Contenu (`data`) du brouillon de secours, sans son horodatage ; null s'il n'existe pas. */
const lireBrouillon = (p, cle) => p.evaluate((k) => {
  const v = localStorage.getItem(k)
  if (v === null) return null
  try { return JSON.stringify(JSON.parse(v).data ?? null) } catch { return v }
}, cle)

// ═══ PF12.2 — AERR11 : « Créer le lot » sur un générateur à saisie modifiée ═══
etape('PF12.2-AERR11-ecran', ['AERR11'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-011')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr11co_${m}`
  await compteDuRole(nom, 'Commercial')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const d = await devisDe(api, admin, `${m}ci`, { ci: true })
  const lignesAvant = (await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire])
  const posts = []
  const ecritures = [] // toute autre écriture sur le devis pendant les gestes « Créer le lot »
  p.on('request', (q) => {
    const chemin = new URL(q.url()).pathname
    if (q.method() === 'POST' && new RegExp(`/ventes/devis/${d.id}/lots/$`).test(chemin)) posts.push(q.postDataJSON())
    else if (q.method() !== 'GET' && chemin.includes(`/ventes/devis/${d.id}/`)) ecritures.push(`${q.method()} ${chemin}`)
  })
  p.on('framenavigated', (f) => { if (f === p.mainFrame()) ecritures.push(`navigation ${f.url()}`) })
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
  // Témoin d'abord (saisie NON modifiée) : création directe, sans question, sans navigation.
  ecritures.length = 0
  await carte.locator('#lot-nom').fill(`Lot initial ${m}`)
  const cree0 = p.waitForResponse(lotsPost, { timeout: 30_000 })
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  const r0 = await cree0.catch(() => null)
  expect(Boolean(r0) && r0.status() < 300, `saisie non modifiée : « Créer le lot » crée le lot ; écritures/navigations du clic : ${J(ecritures)}`).toBe(true)
  await expect(conf, 'témoin : aucune question').toHaveCount(0)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await ouvrirLots()
  const { valeur, cle, brouillon } = await modifierPrix(p, d)
  ecritures.length = 0
  await carte.locator('#lot-nom').fill(`Lot annulé ${m}`)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  await expect(conf, 'confirmation maison').toBeVisible().catch((e) => {
    throw new Error(`pas de confirmation après « Créer le lot » ; écritures/navigations du clic : ${J(ecritures)} ; ${e.message.split('\n')[0]}`)
  })
  await expect(conf).toContainText(PERTE)
  await conf.getByRole('button', { name: 'Annuler' }).click()
  await expect(conf).toBeHidden()
  expect(posts, '« Annuler » : aucun creerLotDevis').toEqual([])
  expect(ecritures, 'le clic n\'a rien écrit d\'autre (ni enregistrement du générateur, ni navigation)').toEqual([])
  await expect(PRIX(p), 'saisie intacte').toHaveValue(valeur)
  await expect(p.getByTestId('gen-barre-non-enregistre'), 'toujours « Modifications non enregistrées »').toBeVisible()
  expect(await lireBrouillon(p, cle), `brouillon de secours intact (${brouillon ? 'présent' : 'absent'} avant le geste)`).toBe(brouillon)
  await expect(carte.locator('#lot-nom')).toHaveValue(`Lot annulé ${m}`)
  // « Créer le lot » confirmé : un POST, le devis est rechargé (la saisie non enregistrée est perdue, comme annoncé).
  await carte.locator('#lot-nom').fill(`Lot confirmé ${m}`)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  const cree1 = p.waitForResponse(lotsPost, T)
  await conf.getByRole('button', { name: 'Créer le lot' }).click()
  expect((await cree1).status()).toBeLessThan(300)
  await expect(PRIX(p), 'devis rechargé depuis le serveur').not.toHaveValue(valeur, { timeout: 60_000 })
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  // Témoin : saisie NON modifiée ⇒ aucune question.
  await ouvrirLots()
  await carte.locator('#lot-nom').fill(`Lot témoin ${m}`)
  const cree2 = p.waitForResponse(lotsPost, T)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  expect((await cree2).status(), 'saisie non modifiée : création directe').toBeLessThan(300)
  await expect(conf, 'aucune question').toHaveCount(0)
  expect(posts.map((x) => x.nom_lot), 'trois créations seulement (jamais le lot annulé)').toEqual([`Lot initial ${m}`, `Lot confirmé ${m}`, `Lot témoin ${m}`])
  // Persistance : les lots servis ; les lignes du devis inchangées.
  const lots = await lireJson(await api.get(`${API}/ventes/devis/${d.id}/lots/`, T), 'lots')
  expect(lots.lots.map((l) => l.nom_lot).sort(), 'persistance : lots en base').toEqual([`Lot initial ${m}`, `Lot confirmé ${m}`, `Lot témoin ${m}`].sort())
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire]), 'lignes inchangées').toEqual(lignesAvant)
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await p.reload()
  await expect(p.locator('#gen-form')).toBeVisible({ timeout: 90_000 })
  await p.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await ouvrirLots()
  for (const n of [`Lot initial ${m}`, `Lot confirmé ${m}`, `Lot témoin ${m}`]) await expect(carte, `rechargé : ${n}`).toContainText(n)
  // Réaffirmé sur l'écran rechargé ; l'étape finit sur la question affichée.
  await modifierPrix(p, d)
  await carte.locator('#lot-nom').fill(`Lot final ${m}`)
  await carte.getByRole('button', { name: 'Créer le lot' }).click()
  await expect(conf).toContainText(PERTE)
  expect(posts.length, 'rien n\'est parti').toBe(3)
})

// ═══ PF12.2 — AERR12 : « Ajouter le BOQ électrique » sur un générateur à saisie modifiée ═══
etape('PF12.2-AERR12-ecran', ['AERR12'], async ({ page, suivi, testInfo }) => {
  sondeFausse('C-AERR-011')
  const admin = page.context().request
  const m = marque()
  const nom = `aerr12co_${m}`
  await compteDuRole(nom, 'Commercial')
  const ecr = await ecran(page, suivi, testInfo, nom)
  const { api, ctx } = ecr
  let { p } = ecr
  const d = await devisDe(api, admin, `${m}r`)
  const lignesAvant = (await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire])
  const BOQ = new RegExp(`/api/django/ventes/devis/${d.id}/ajouter-boq-electrique/$`)
  suivi.attendre(BOQ, 409) // témoin sans conception électrique : refus d'état servi tel quel
  const posts = []
  const compter = (q) => { if (q.method() === 'POST' && BOQ.test(q.url())) posts.push(q.url()) }
  p.on('request', compter)
  const bloc = () => p.getByTestId('ajouter-boq-electrique')
  const conf = () => p.getByRole('alertdialog')
  const PERTE = 'L’ajout recharge le devis : vos modifications non enregistrées seront perdues.'
  await ouvrirGenerateur(p, d, { ci: false })
  // Témoin : saisie non modifiée ⇒ aucune question, l'appel part (409 « pas encore de conception électrique »).
  const t = p.waitForResponse((x) => x.request().method() === 'POST' && BOQ.test(x.url()), T)
  await bloc().getByRole('button', { name: 'Ajouter le BOQ électrique' }).click()
  expect((await t).status()).toBe(409)
  await expect(conf(), 'témoin : aucune question').toHaveCount(0)
  await expect(bloc().getByRole('alert'), 'refus servi affiché').toContainText('conception électrique')
  expect(posts.length).toBe(1)
  // Saisie modifiée ⇒ confirmation qui dit la perte ; « Annuler » n'envoie rien.
  const { valeur, cle, brouillon } = await modifierPrix(p, d)
  await bloc().getByRole('button', { name: 'Ajouter le BOQ électrique' }).click()
  await expect(conf(), 'confirmation maison').toBeVisible()
  await expect(conf()).toContainText(PERTE)
  await conf().getByRole('button', { name: 'Annuler' }).click()
  await expect(conf()).toBeHidden()
  expect(posts.length, '« Annuler » : aucun ajouterBoqElectrique').toBe(1)
  await expect(PRIX(p), 'saisie intacte').toHaveValue(valeur)
  await expect(p.getByTestId('gen-barre-non-enregistre'), 'toujours « Modifications non enregistrées »').toBeVisible()
  expect(await lireBrouillon(p, cle), `brouillon de secours intact (${brouillon ? 'présent' : 'absent'} avant le geste)`).toBe(brouillon)
  // Persistance : rien d'écrit en base.
  expect((await lireJson(await api.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).lignes.map((l) => [l.id, l.prix_unitaire]), 'persistance : lignes inchangées').toEqual(lignesAvant)
  // Recharger : la saisie modifiée arme la garde de sortie (beforeunload) ; l'onglet est refermé sans elle et le
  // générateur rouvert dans un onglet neuf du même compte, puis tout est réaffirmé.
  await p.close({ runBeforeUnload: false })
  p = suivi.surveiller(await ctx.newPage())
  p.on('request', compter)
  await ouvrirGenerateur(p, d, { ci: false })
  await modifierPrix(p, d)
  await bloc().getByRole('button', { name: 'Ajouter le BOQ électrique' }).click()
  await expect(conf(), 'rechargé : confirmation maison').toContainText(PERTE)
  expect(posts.length, 'rien n\'est parti').toBe(1)
})
