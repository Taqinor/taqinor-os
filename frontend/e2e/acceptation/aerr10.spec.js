// Preuves en direct ÉCRAN du groupe AERR, vague 6 (runner GitHub, essai du 16/11/2026) : les tâches « code livré, preuve
// en direct due » AERR1 (Note de débit et Encaissements — l'écran Factures est déjà joué par aerr3, Remises par aerr6),
// AERR69 (palette ⌘K), AERR114 (confirmations nommées des suppressions : gabarit, relevé, pose réelle), AERR120 (fiche
// lead pleine page : « Signé » refusé) et AERR132 (fiche produit à stock négatif).
// Chaque étape joue le geste À L'ÉCRAN sous un compte d'un rôle LIVRÉ (relu par son nom dans la société démo, connexion par
// /token/ comme aerr3.spec.js), PROVOQUE le refus ou la panne (route Playwright déclarée AVANT par `suivi.attendre`),
// AFFIRME ce que la clause nomme, relit la base (API / shell Django) et recharge. Données propres créées par les vraies
// routes ou le shell Django ; une facture à numéro légal reste sur la base jetable du runner.
// AERR114 : la clause « Suppr tapé sous une boîte posée sur l'atelier n'appelle aucune action » exige le constructeur 3D
// (carte MapTiler, absente du runner : `builderApi.raccourcis` vide ⇒ aucun gestionnaire à appeler, preuve vide) — NON
// jouée ici ; les trois confirmations nommées (gabarit, pose réelle, relevé) le sont.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique, listeDe, STAGE_LABELS, uniq } from '../helpers.js'

const etape = groupe('AERR', ['AERR1', 'AERR69', 'AERR114', 'AERR120', 'AERR132'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
const apres = []
test.afterEach(async () => {
  for (const c of ouverts.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const pad = (n) => String(n).padStart(2, '0')
const isoJour = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie(u.id)`)

/** Écran sous le compte `nom` : contexte neuf (accueil et visites vus, SW bloqué), observé ; la page demo_admin est
 *  refermée (la capture montre l'écran du rôle). `api` = requêtes de CE compte (même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
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
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p: suivi.surveiller(await ctx.newPage()), api: ctx.request, ctx }
}

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
/** Compteur de requêtes (méthode(s) + chemin) observées par la page. */
function compteur(p, methodes, cheminOk) {
  const c = { n: 0, corps: [], urls: [] }
  p.on('request', (r) => {
    if (!methodes.includes(r.method())) return
    const u = new URL(r.url())
    if (!cheminOk(u.pathname, u)) return
    c.n += 1
    c.urls.push(`${r.method()} ${u.pathname}${u.search}`)
    c.corps.push(r.postData() || '')
  })
  return c
}

/** Leads de la société démo, propriétaire `owner` ; `liste` = champs du modèle. Renvoie leurs pk. */
const creerLeads = (owner, liste) => py(`from apps.crm.models import Lead
out = []
for d in json.loads(${J(J(liste))}):
    out.append(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **d).pk)
sortie(out)`)
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
try:
    from apps.ventes.models import Devis
    Devis.all_objects.filter(lead_id__in=${J(pks)}).delete() if hasattr(Devis, 'all_objects') else Devis.objects.filter(lead_id__in=${J(pks)}).delete()
except Exception as exc:
    print('devis', exc)
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
const etapeLead = (lead) => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${lead}).stage)`)

// ═══ AERR69 — palette ⌘K : « Changer le stage » ⇒ toast nommé + « Annuler » ; vers « Signé » une boîte nommée d'abord ═══
async function lancerChangerStage(p) {
  await p.keyboard.press('Control+k')
  const champ = p.getByRole('textbox', { name: 'Recherche rapide' })
  await expect(champ, 'palette ouverte').toBeVisible({ timeout: 30_000 })
  await champ.fill('Changer le stage')
  await p.getByText('Changer le stage du lead sélectionné').first().click()
}
etape('PF12.69-AERR69', ['AERR69'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr69_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [A, B, C] = await creerLeads(cr, [
    { nom: `Karim B. ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
    { nom: `Relance ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'FOLLOW_UP' },
    { nom: `Panne ${m}`, prenom: '', telephone: telephoneMobileUnique(), stage: 'CONTACTED' },
  ])
  apres.push(() => supprimerLeads([A, B, C]))
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const patchsDe = (id) => compteur(p, ['PATCH'], (ch) => ch === `${API}/crm/leads/${id}/`)
  const ouvrirFiche = async (id, nomLead) => {
    await p.goto(`/crm/leads?lead=${id}`)
    await expect(p.getByText(nomLead).first(), `fiche de ${nomLead} affichée`).toBeVisible({ timeout: 60_000 })
  }

  // (1) Lead CONTACTED : un PATCH {stage: QUOTE_SENT}, toast « <nom> → Devis envoyé » + « Annuler » qui le remet en CONTACTED.
  const pa = patchsDe(A)
  await ouvrirFiche(A, `Karim B. ${m}`)
  await lancerChangerStage(p)
  const t = toast(p, `Karim B. ${m} → ${STAGE_LABELS.QUOTE_SENT}`).first()
  await expect(t, 'toast nommé « <nom du lead> → Devis envoyé »').toBeVisible({ timeout: 30_000 })
  await expect(t.getByRole('button', { name: 'Annuler' }), 'toast avec « Annuler »').toBeVisible()
  await expect.poll(() => pa.n, { timeout: 15_000 }).toBe(1)
  expect(JSON.parse(pa.corps[0]), 'PATCH de l\'avancée').toEqual({ stage: 'QUOTE_SENT' })
  expect(await etapeLead(A), 'base : avancé en QUOTE_SENT').toBe('QUOTE_SENT')
  const retour = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${A}/`) && r.request().postData() !== pa.corps[0], T)
  // « Annuler » cliqué À LA SOURIS (fiche ouverte en fenêtre modale : sa couche modale pose `pointer-events:none` sur le
  // toast, le clic tombe sur la couche). Constaté au run 43978374413 : s'il est bloqué, l'étape le DIT (défaut) puis
  // déclenche le bouton par son gestionnaire pour juger le reste de la clause (appel inverse, base).
  let clicBloque = false
  await t.getByRole('button', { name: 'Annuler' }).click({ timeout: 2500 }).catch(() => { clicBloque = true })
  if (clicBloque) {
    testInfo.annotations.push({ type: 'défaut AERR69', description: '« Annuler » du toast non cliquable à la souris : la couche de la fiche ouverte (modale) intercepte le clic' })
    await t.getByRole('button', { name: 'Annuler' }).dispatchEvent('click')
  }
  const rep = await retour
  expect(JSON.parse(rep.request().postData()), '« Annuler » PATCHe l\'étape d\'origine').toMatchObject({ stage: 'CONTACTED' })
  expect(rep.status(), `« Annuler » accepté par le serveur (reçu ${rep.status()} ${(await rep.text()).slice(0, 200)})`).toBeLessThan(300)
  await expect.poll(() => etapeLead(A), { timeout: 30_000, message: 'base : retour en CONTACTED' }).toBe('CONTACTED')
  const relu = await lireJson(await api.get(`${API}/crm/leads/${A}/`, T), 'lead relu')
  expect(relu.stage, 'persistance : le lead relu est en CONTACTED').toBe('CONTACTED')

  // (2) Lead en Relance : une boîte nommée AVANT tout passage en « Signé » ; « Annuler » ⇒ aucun PATCH.
  const pb = patchsDe(B)
  await ouvrirFiche(B, `Relance ${m}`)
  await lancerChangerStage(p)
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte nommée avant « Signé »').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText(`Passer « Relance ${m} » en « ${STAGE_LABELS.SIGNED} » ?`)
  expect(pb.n, 'la boîte précède tout PATCH').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1500)
  expect(pb.n, '« Annuler » : aucun PATCH').toBe(0)
  expect(await etapeLead(B), 'base : le lead reste en FOLLOW_UP').toBe('FOLLOW_UP')

  // (3) Échec serveur : UN SEUL toast (celui de l'intercepteur global).
  suivi.attendre(new RegExp(`/api/django/crm/leads/${C}/$`), 500)
  await p.route((u) => u.pathname === `${API}/crm/leads/${C}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: J({ detail: 'panne injectée AERR69' }) })
    : route.fallback()))
  const pc = patchsDe(C)
  await ouvrirFiche(C, `Panne ${m}`)
  await lancerChangerStage(p)
  await expect.poll(() => pc.n, { timeout: 30_000 }).toBeGreaterThanOrEqual(1)
  await expect(p.locator('[data-sonner-toast]').first(), 'l\'échec est dit').toBeVisible({ timeout: 15_000 })
  await p.waitForTimeout(2500)
  expect(await p.locator('[data-sonner-toast]').count(), 'un seul message pour un échec (aucun toast qui double celui de l\'intercepteur)').toBe(1)
  expect(await etapeLead(C), 'base : rien d\'écrit sur échec').toBe('CONTACTED')
  expect(clicBloque, '« Annuler » du toast est cliquable à la souris sur la fiche ouverte (`?lead=<id>`)').toBe(false)
})

// ═══ AERR132 — fiche produit à stock négatif : changer le prix s'enregistre, rien sous « Quantité en stock » ═══
etape('PF12.132-AERR132', ['AERR132'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr132_${m}`
  await compteRole(nom, 'Directeur')
  const prod = await py(`from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='Câble 6 mm² AERR132 ${m}', prix_vente=12)
Produit.objects.filter(pk=p.pk).update(quantite_stock=-3)
sortie(p.pk)`)
  apres.push(() => py(`from apps.stock.models import Produit
try: Produit.objects.filter(pk=${prod}).delete()
except Exception as exc: print('nettoyage produit', exc)`))
  const lu = () => py(`from apps.stock.models import Produit
p = Produit.objects.get(pk=${prod}); sortie([str(p.prix_vente), p.quantite_stock])`)
  expect(await lu(), 'Given : prix 12, stock -3').toEqual(['12.00', -3])
  const { p } = await ecran(page, suivi, testInfo, nom)
  const envois = compteur(p, ['PATCH', 'PUT'], (ch) => ch === `${API}/stock/produits/${prod}/`)
  await p.goto('/stock')
  await p.getByPlaceholder('Chercher partout…').fill(`AERR132 ${m}`, { timeout: 60_000 })
  const ligne = p.getByRole('row').filter({ hasText: `AERR132 ${m}` })
  await expect(ligne, 'la fiche à stock -3 est listée').toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
  await p.getByRole('menuitem', { name: 'Éditer' }).click()
  const form = p.getByRole('dialog').filter({ has: p.locator('#pf-vente') })
  await expect(form, 'fiche ouverte en édition').toBeVisible({ timeout: 30_000 })
  await expect(form.locator('#pf-qte'), 'quantité en stock grisée à -3').toBeDisabled()
  await expect(form.locator('#pf-qte')).toHaveValue('-3')
  await form.locator('#pf-vente').fill('13')
  await form.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(form, 'la fiche se ferme (enregistrée)').toBeHidden({ timeout: 30_000 })
  await expect.poll(() => envois.n, { timeout: 15_000, message: 'updateProduit appelé' }).toBe(1)
  const corps = JSON.parse(envois.corps[0])
  expect(corps.prix_vente, 'le prix de vente part à 13').toMatch(/^13(\.0+)?$/)
  expect(Object.keys(corps), 'sans quantite_stock').not.toContain('quantite_stock')
  expect(await lu(), 'persistance : prix 13, stock -3 inchangé').toEqual(['13.00', -3])
  await p.reload()
  await p.getByPlaceholder('Chercher partout…').fill(`AERR132 ${m}`, { timeout: 60_000 })
  await expect(p.getByRole('row').filter({ hasText: `AERR132 ${m}` }), 'après rechargement : la fiche est listée').toBeVisible({ timeout: 60_000 })
})

// ═══ AERR114 — confirmations nommées : gabarit (Réglages), relevé terrain, pose réelle (atelier) ═══
etape('PF12.114-AERR114-gabarit', ['AERR114'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr114g_${m}`
  await compteRole(nom, 'Administrateur')
  const intitule = `Bac acier 2 pans ${m}`
  const gab = await py(`from apps.calepinage.models import GabaritDossierReglementaire as G
g = G.objects.create(company_id=${SOC}, pays='ma', code='bac-acier-${m}', intitule=${J(intitule)}, pieces_attendues=[], champs=[])
sortie(g.pk)`)
  apres.push(() => py(`from apps.calepinage.models import GabaritDossierReglementaire as G
G.objects.filter(pk=${gab}).delete()`))
  const existe = () => py(`from apps.calepinage.models import GabaritDossierReglementaire as G
sortie(G.objects.filter(pk=${gab}).exists())`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  const natifs = []
  p.on('dialog', (d) => natifs.push(d.type()))
  const suppressions = compteur(p, ['DELETE'], (ch) => ch === `${API}/calepinage/gabarits-dossiers/${gab}/`)
  await p.goto('/calepinage/reglages/gabarits')
  const ligne = p.getByTestId(`acal242-gabarit-${gab}`)
  await expect(ligne, 'le gabarit est listé').toBeVisible({ timeout: 90_000 })
  await ligne.getByTestId(`acal242-supprimer-${gab}`).click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte maison qui nomme le gabarit').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText(`Supprimer le gabarit « ${intitule} » ?`)
  expect(suppressions.n, 'la boîte précède tout appel').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1000)
  expect(suppressions.n, '« Annuler » : aucun gabarits.supprimer').toBe(0)
  expect(await existe(), 'persistance : le gabarit est toujours en base').toBe(true)
  await p.reload()
  await expect(p.getByTestId(`acal242-gabarit-${gab}`), 'après rechargement : gabarit présent').toBeVisible({ timeout: 90_000 })
  // Confirmé : l'appel part, une seule fois.
  await p.getByTestId(`acal242-supprimer-${gab}`).click()
  await expect(p.getByRole('alertdialog')).toContainText(`Supprimer le gabarit « ${intitule} » ?`)
  await p.getByRole('alertdialog').getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect.poll(() => suppressions.n, { timeout: 15_000 }).toBe(1)
  await expect.poll(existe, { timeout: 15_000, message: 'base : gabarit supprimé' }).toBe(false)
  await expect(p.getByTestId(`acal242-gabarit-${gab}`)).toHaveCount(0)
  expect(natifs, 'aucune boîte native (window.confirm)').toEqual([])
})

async function calepinageDe(request, m) {
  const lead = await lireJson(await request.post(`${API}/crm/leads/`, { ...T, data: {
    nom: uniq(`AERR114 ${m}`), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800',
  } }), 'lead')
  const cal = await lireJson(await request.post(`${API}/calepinage/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq('AERR114') } }), 'calepinage')
  // Amorce : le 1er design-context d'un calepinage neuf est lent (~30 s) — lu une fois ici (délai 120 s).
  await lireJson(await request.get(`${API}/calepinage/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  return { lead, cal }
}
const ongletOuvert = (p) => expect(p.getByTestId('cal-onglet-panneau')).toBeVisible({ timeout: 240_000 })

etape('PF12.114-AERR114-releve', ['AERR114'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr114r_${m}`
  await compteRole(nom, 'Administrateur')
  const admin = page.context().request
  const { lead, cal } = await calepinageDe(admin, m)
  apres.push(() => supprimerLeads([lead.id]))
  const cree = await lireJson(await admin.post(`${API}/calepinage/calepinages/${cal.id}/releve/`, { ...T, data: {
    releve_le: '2026-11-01', notes: `AERR114 ${m}`,
    chaines: [{ nom: 'Pignon nord', total_mesure: 12.4, cotes: [{ nom: 'a', valeur: 5.2 }, { nom: 'b', valeur: 7.2 }] }],
  } }), 'relevé posé')
  const releveId = cree.releve?.id
  expect(releveId, 'Given : un relevé du 2026-11-01').toBeTruthy()
  const releves = async () => (await lireJson(await admin.get(`${API}/calepinage/calepinages/${cal.id}/releve/`, T), 'relevés')).releves ?? []
  const { p } = await ecran(page, suivi, testInfo, nom)
  const natifs = []
  p.on('dialog', (d) => natifs.push(d.type()))
  const suppressions = compteur(p, ['DELETE'], (ch) => ch === `${API}/calepinage/calepinages/${cal.id}/releve/${releveId}/`)
  await p.goto(`/calepinage/${cal.id}?onglet=releve`)
  await ongletOuvert(p)
  await expect(p.getByTestId('cal-releve-panel')).toBeVisible({ timeout: 60_000 })
  const jour = await p.locator('#cal-releve-releve_le').inputValue()
  expect(jour, 'le relevé courant est affiché (date du 01/11)').toBe('2026-11-01')
  await p.getByTestId('cal-releve-supprimer').click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte maison qui nomme le relevé').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText(`Supprimer le relevé du ${jour} ?`)
  expect(suppressions.n, 'la boîte précède tout appel').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1000)
  expect(suppressions.n, '« Annuler » : aucune suppression').toBe(0)
  expect((await releves()).length, 'persistance : relevé toujours en base').toBe(1)
  await p.reload()
  await ongletOuvert(p)
  await expect(p.getByTestId('cal-releve-supprimer'), 'après rechargement : relevé présent').toBeVisible({ timeout: 90_000 })
  await p.getByTestId('cal-releve-supprimer').click()
  await expect(p.getByRole('alertdialog')).toContainText(`Supprimer le relevé du ${jour} ?`)
  await p.getByRole('alertdialog').getByRole('button', { name: 'Supprimer', exact: true }).click()
  await expect.poll(() => suppressions.n, { timeout: 15_000 }).toBe(1)
  await expect(p.getByTestId('cal-releve-message')).toContainText('Relevé supprimé.', { timeout: 30_000 })
  expect((await releves()).length, 'base : relevé supprimé').toBe(0)
  expect(natifs, 'aucun window.confirm natif').toEqual([])
})

etape('PF12.114-AERR114-pose', ['AERR114'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr114p_${m}`
  await compteRole(nom, 'Administrateur')
  const admin = page.context().request
  const { lead, cal } = await calepinageDe(admin, m)
  apres.push(() => supprimerLeads([lead.id]))
  const zone = `pan-sud-${m}`
  await py(`from apps.calepinage.models import PoseReelle
PoseReelle.objects.create(company_id=${SOC}, calepinage_id=${cal.id}, pan='Sud', zone_id=${J(zone)}, modules_poses=8,
    releve_le=timezone.localdate(), modules_prevus=10)
sortie(1)`)
  const existe = () => py(`from apps.calepinage.models import PoseReelle
sortie(PoseReelle.objects.filter(calepinage_id=${cal.id}, zone_id=${J(zone)}).exists())`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  const natifs = []
  p.on('dialog', (d) => natifs.push(d.type()))
  const suppressions = compteur(p, ['DELETE'], (ch) => ch.startsWith(`${API}/calepinage/calepinages/${cal.id}/pose-reelle/`))
  await p.goto(`/calepinage/${cal.id}?onglet=pose-reelle`)
  await ongletOuvert(p)
  const retirer = p.getByTestId(`cal-pose-retirer-${zone}`)
  await expect(retirer, 'la ligne du pan « Sud » (orphelin) propose « Retirer »').toBeVisible({ timeout: 90_000 })
  await retirer.click()
  const boite = p.getByRole('alertdialog')
  await expect(boite, 'boîte maison qui nomme le pan').toBeVisible({ timeout: 30_000 })
  await expect(boite).toContainText('Retirer le relevé du pan Sud ?')
  expect(suppressions.n, 'la boîte précède tout appel').toBe(0)
  await boite.getByRole('button', { name: 'Annuler' }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1000)
  expect(suppressions.n, '« Annuler » : aucun appel de retrait').toBe(0)
  expect(await existe(), 'persistance : le relevé du pan est toujours en base').toBe(true)
  await p.reload()
  await ongletOuvert(p)
  await expect(p.getByTestId(`cal-pose-retirer-${zone}`), 'après rechargement : ligne présente').toBeVisible({ timeout: 90_000 })
  await p.getByTestId(`cal-pose-retirer-${zone}`).click()
  await expect(p.getByRole('alertdialog')).toContainText('Retirer le relevé du pan Sud ?')
  await p.getByRole('alertdialog').getByRole('button', { name: 'Retirer', exact: true }).click()
  await expect.poll(() => suppressions.n, { timeout: 15_000 }).toBe(1)
  await expect.poll(existe, { timeout: 30_000, message: 'base : relevé du pan retiré' }).toBe(false)
  await expect(p.getByTestId(`cal-pose-ligne-${zone}`)).toHaveCount(0, { timeout: 30_000 })
  expect(natifs, 'aucun window.confirm natif').toEqual([])
})

// ═══ AERR120 — /crm/leads/<id> : « Signé » refusé (400 {date} puis 400 {nom}) ⇒ dialogue rouvert pré-rempli, message sous son champ ═══
etape('PF12.120-AERR120', ['AERR120'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr120_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR120 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'QUOTE_SENT' }])
  apres.push(() => supprimerLeads([lead]))
  const devis = await py(`from decimal import Decimal
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
l = Lead.objects.get(pk=${lead})
cl = Client.objects.create(company_id=l.company_id, nom='AERR120 ${m}', prenom='Essai')
p = Produit.objects.filter(company_id=l.company_id).first()
d = Devis.objects.create(company_id=l.company_id, reference='DEV-AERR120-${m}', client=cl, lead=l, statut='envoye', created_by_id=${cr},
    mode_installation='commercial', etude_params={'scenario': 'Les deux (Sans + Avec)'})
for desig, qte, pu in (('Onduleur réseau 10kW', '1', '12000'), ('Onduleur hybride 5kW', '1', '24000'), ('Panneau mono 550W', '14', '1100'),
                       ('Batterie 5 kWh', '1', '14000'), ('Structures acier', '14', '375'), ('Installation', '1', '4000')):
    LigneDevis.objects.create(devis=d, produit=p, designation=desig, quantite=Decimal(qte), prix_unitaire=Decimal(pu))
sortie(dict(id=d.pk, client=cl.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
Client.objects.filter(pk=${devis.client}).delete()`))
  const etat = () => py(`from apps.ventes.models import Devis
from apps.crm.models import Lead
sortie([Devis.objects.get(pk=${devis.id}).statut, Lead.objects.get(pk=${lead}).stage])`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  const ACCEPTER = new RegExp(`/api/django/ventes/devis/${devis.id}/accepter/$`)
  const refus = (corps) => async (route) => {
    if (route.request().method() === 'POST') await route.fulfill({ status: 400, contentType: 'application/json', body: J(corps) })
    else await route.fallback()
  }
  suivi.attendre(ACCEPTER, 400)
  await p.goto(`/crm/leads/${lead}`)
  await p.getByTitle("Changer l'étape du lead").click({ timeout: 60_000 })
  await p.getByRole('menuitem', { name: new RegExp(STAGE_LABELS.SIGNED) }).click()
  const heading = p.getByRole('heading', { name: /Passer en « Signé »/ })
  const dlg = p.getByRole('dialog').filter({ has: heading })
  await expect(dlg, 'dialogue « Signé » ouvert').toBeVisible({ timeout: 30_000 })
  const hier = new Date(); hier.setDate(hier.getDate() - 1)
  await dlg.locator('#sd-nom').fill('K. Alami')
  await dlg.locator('#sd-date').fill(isoJour(hier))
  const ICE = '001234567000089'
  await expect(dlg.getByTestId('identite-entreprise'), 'bloc entreprise (devis commercial)').toBeVisible()
  await dlg.locator('#sd-raison-sociale').fill(`Boulangerie ${m}`)
  await dlg.locator('#sd-qualite').fill('Gérant')
  await dlg.locator('#sd-ice').fill(ICE)
  const radios = dlg.locator('input[name="sd-option"]')
  const avecOption = (await radios.count()) > 0
  let optionChoisie = ''
  if (avecOption) {
    await radios.nth(0).check()
    optionChoisie = await radios.nth(0).getAttribute('value')
  }
  console.log(`[AERR120] choix d'option affiché : ${avecOption ? `oui (${optionChoisie})` : 'non (devis à une option)'}`)

  const garde = async (quoi) => {
    const rouvert = p.getByRole('dialog').filter({ has: heading })
    await expect(rouvert, `${quoi} : le dialogue « Signé » réapparaît`).toBeVisible({ timeout: 30_000 })
    await expect(p, `${quoi} : la page reste la fiche du lead`).toHaveURL(new RegExp(`/crm/leads/${lead}$`))
    await expect(rouvert.locator('#sd-nom'), `${quoi} : signataire gardé`).toHaveValue('K. Alami')
    await expect(rouvert.locator('#sd-date'), `${quoi} : date gardée`).toHaveValue(isoJour(hier))
    await expect(rouvert.locator('#sd-raison-sociale'), `${quoi} : raison sociale gardée`).toHaveValue(`Boulangerie ${m}`)
    await expect(rouvert.locator('#sd-qualite'), `${quoi} : qualité gardée`).toHaveValue('Gérant')
    await expect(rouvert.locator('#sd-ice'), `${quoi} : ICE gardé`).toHaveValue(ICE)
    if (avecOption) await expect(rouvert.locator(`input[name="sd-option"][value="${optionChoisie}"]`), `${quoi} : option gardée`).toBeChecked()
    return rouvert
  }
  // (1) 400 {date: […]} ⇒ « Date invalide. » sous « Date d'acceptation ».
  await p.route(ACCEPTER, refus({ date: ['Date invalide.'] }))
  const r1 = p.waitForResponse((r) => ACCEPTER.test(r.url()), T)
  await dlg.getByRole('button', { name: /Confirmer l.acceptation/ }).click()
  expect((await r1).status()).toBe(400)
  const apresDate = await garde('refus {date}')
  await expect(apresDate.locator('#sd-date + p.form-error'), '« Date invalide. » sous « Date d\'acceptation »').toHaveText('Date invalide.', { timeout: 15_000 })
  expect(await etat(), 'refus : rien n\'est accepté').toEqual(['envoye', 'QUOTE_SENT'])
  // (2) 400 {nom: […]} ⇒ le message reste sous « Signataire » (ACVI68 inchangé).
  await p.unroute(ACCEPTER)
  await p.route(ACCEPTER, refus({ nom: ['Nom invalide.'] }))
  const r2 = p.waitForResponse((r) => ACCEPTER.test(r.url()), T)
  await apresDate.getByRole('button', { name: /Confirmer l.acceptation/ }).click()
  expect((await r2).status()).toBe(400)
  const apresNom = await garde('refus {nom}')
  await expect(apresNom.locator('#sd-nom + p.form-error'), '« Nom invalide. » sous « Signataire »').toHaveText('Nom invalide.', { timeout: 15_000 })
  expect(await etat(), 'refus : rien n\'est accepté').toEqual(['envoye', 'QUOTE_SENT'])
  // Persistance : rechargée, la fiche est toujours « Devis envoyé ».
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(p.getByTitle("Changer l'étape du lead"), 'après rechargement : toujours « Devis envoyé »').toContainText(STAGE_LABELS.QUOTE_SENT, { timeout: 60_000 })
})

// ═══ AERR1 (suite) — Factures : la boîte « Note de débit » reste montée pendant une relecture qui échoue ═══
async function devisDe(cree, admin, m, { envoye = false, ht = '10000.00' } = {}) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `AERR ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aerr-${m}@example.invalid`,
  } }), 'lead')
  const p = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AERR ${m}`, prix_vente: ht, prix_achat: '1.00' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: l.id,
    lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: ht, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  } }), 'devis')
  if (envoye) await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return { id: d.id, leadId: l.id }
}
/** Vente acceptée par demo_admin puis facturée « complète » et émise par `cree`. */
async function factureDe(cree, admin, m) {
  const d = await devisDe(cree, admin, m, { envoye: true })
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR' } }), 'accepter')
  const rep = await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre: true, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut }
}

etape('PF12.1-AERR1-note-debit', ['AERR1'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const nom = `aerr1nd_${m}`
  await compteRole(nom, 'Directeur')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const A = await factureDe(api, admin, `${m}a`)
  const B = await factureDe(api, admin, `${m}b`)
  expect([A.statut, B.statut], 'Given : deux factures émises').toEqual(['emise', 'emise'])
  const ligne = (f) => p.locator(`#facture-row-${f.id}`)
  const boite = p.getByRole('dialog').filter({ hasText: `Notes de débit — ${A.reference}` })
  await p.goto('/ventes/factures')
  for (const f of [A, B]) await expect(ligne(f), `${f.reference} affichée`).toBeVisible({ timeout: 90_000 })
  await ligne(A).locator('button', { hasText: 'Actions' }).click()
  await p.getByRole('menuitem', { name: 'Note de débit' }).click()
  await expect(boite, 'boîte « Note de débit » ouverte sur A').toBeVisible({ timeout: 30_000 })

  const LISTE = /\/api\/django\/ventes\/factures\/\?/
  suivi.attendre(LISTE, 'reseau')
  const g = porte()
  await p.route(LISTE, g.gestion())
  await boite.locator('#nd-motif').fill(`AERR1 ${m}`)
  await boite.locator('#nd-montant').fill('100')
  const creation = p.waitForResponse((x) => x.request().method() === 'POST' && /\/creer-note-debit\/$/.test(new URL(x.url()).pathname), T)
  await boite.getByRole('button', { name: 'Créer la note de débit' }).click()
  expect((await creation).status(), 'note de débit créée').toBeLessThan(300)
  await g.arrivee // la relecture de la liste est partie et TENUE
  for (const f of [A, B]) await expect(ligne(f), `relecture EN COURS : ${f.reference} reste affichée`).toBeVisible()
  await expect(boite, 'relecture EN COURS : la boîte reste montée').toBeVisible()
  g.lacher() // la relecture est rejetée (réseau coupé)
  const avis = p.getByTestId('factures-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  await expect(avis.locator('button', { hasText: 'Réessayer' }), 'avis avec « Réessayer »').toBeVisible()
  for (const f of [A, B]) await expect(ligne(f), `relecture RATÉE : ${f.reference} reste affichée`).toBeVisible()
  await expect(p.getByText('Erreur de chargement'), 'jamais l\'écran plein d\'erreur').toHaveCount(0)
  await expect(boite, 'relecture RATÉE : la boîte « Note de débit » reste montée').toBeVisible()
  // Persistance : la note est en base (le geste a réussi, seule la relecture a échoué).
  const notes = listeDe(await lireJson(await api.get(`${API}/ventes/notes-debit/?facture=${A.id}`, T), 'notes de A'))
  expect(notes.length, 'base : la note de débit de A existe').toBe(1)
  await expect(boite.getByText(notes[0].reference), 'la note créée est listée dans la boîte').toBeVisible({ timeout: 30_000 })
  // Réessayer → liste relue ; recharger → mêmes lignes.
  await boite.getByRole('button', { name: 'Fermer' }).click()
  await expect(boite).toBeHidden({ timeout: 30_000 })
  if (await p.getByRole('menu').count()) await p.keyboard.press('Escape')
  await p.unroute(LISTE)
  await avis.locator('button', { hasText: 'Réessayer' }).click()
  await expect(avis, 'Réessayer : avis retiré').toBeHidden({ timeout: 30_000 })
  await p.reload()
  for (const f of [A, B]) await expect(ligne(f), `après rechargement : ${f.reference}`).toBeVisible({ timeout: 90_000 })
})

// ═══ AERR1 (suite) — Encaissements : annuler une saisie pendant que la relecture est tenue puis coupée ═══
etape('PF12.1-AERR1-encaissements', ['AERR1'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const nom = `aerr1en_${m}`
  await compteRole(nom, 'Directeur')
  const { p, api } = await ecran(page, suivi, testInfo, nom)
  const A = await factureDe(api, admin, `${m}a`)
  const B = await factureDe(api, admin, `${m}b`)
  const jour = isoJour(new Date())
  for (const f of [A, B]) {
    await lireJson(await api.post(`${API}/ventes/factures/${f.id}/enregistrer-paiement/`, { ...T, data: { montant: 1000, date_paiement: jour, mode: 'virement' } }), `paiement ${f.reference}`)
  }
  const table = p.getByRole('table', { name: 'Encaissements' })
  const ligne = (f) => table.getByRole('row').filter({ hasText: f.reference })
  await p.goto('/ventes/paiements')
  for (const f of [A, B]) await expect(ligne(f), `${f.reference} : encaissement listé`).toBeVisible({ timeout: 90_000 })
  const LISTE = /\/api\/django\/ventes\/paiements\/\?/
  suivi.attendre(LISTE, 'reseau')
  const g = porte()
  await p.route(LISTE, g.gestion())
  await ligne(A).getByRole('button', { name: /Annuler \(erreur de saisie\)/ }).click()
  const dlg = p.getByRole('dialog').filter({ hasText: 'Annuler la saisie du paiement' })
  await expect(dlg, 'boîte « Annuler la saisie » ouverte').toBeVisible({ timeout: 30_000 })
  await dlg.locator('#annul-motif').fill(`AERR1 saisie ${m}`)
  const annul = p.waitForResponse((x) => x.request().method() === 'POST' && /\/annuler-saisie\/$/.test(new URL(x.url()).pathname), T)
  await dlg.getByRole('button', { name: 'Annuler la saisie', exact: true }).click()
  expect((await annul).status(), 'saisie annulée').toBeLessThan(300)
  await g.arrivee // la relecture est partie et TENUE
  for (const f of [A, B]) await expect(ligne(f), `relecture EN COURS : ${f.reference} reste affichée`).toBeVisible()
  await expect(p.locator('.skeleton-shimmer'), 'relecture EN COURS : aucun squelette').toHaveCount(0)
  g.lacher()
  const avis = p.getByTestId('paiements-pas-a-jour')
  await expect(avis, 'avis « Liste pas à jour »').toBeVisible({ timeout: 30_000 })
  await expect(avis).toContainText('Liste pas à jour')
  await expect(avis.getByRole('button', { name: 'Réessayer' }), 'avis avec « Réessayer »').toBeVisible()
  for (const f of [A, B]) await expect(ligne(f), `relecture RATÉE : ${f.reference} reste affichée`).toBeVisible()
  await expect(p.getByText('Impossible de charger les encaissements'), 'jamais l\'écran plein d\'erreur').toHaveCount(0)
  // Persistance : la saisie est bien annulée en base.
  const pa = listeDe(await lireJson(await api.get(`${API}/ventes/paiements/?page_size=200`, T), 'paiements')).find((x) => x.facture === A.id)
  expect(pa?.statut, 'base : le paiement de A est annulé (saisie)').toBe('annule_saisie')
  await p.unroute(LISTE)
  await avis.getByRole('button', { name: 'Réessayer' }).click()
  await expect(avis, 'Réessayer : avis retiré').toBeHidden({ timeout: 30_000 })
  await expect(ligne(A), 'Réessayer : A relue « Annulé (saisie) »').toContainText('Annulé (saisie)', { timeout: 30_000 })
  await p.reload()
  for (const f of [A, B]) await expect(ligne(f), `après rechargement : ${f.reference}`).toBeVisible({ timeout: 90_000 })
})

// ═══ AERR117 (suite) — un refus ne produit qu'UN message (réassignation, type de client, mois de clôture) ; 400 {notes} du RDV ═══
const unSeulMessage = async (p, quoi) => {
  await expect(p.locator('[data-sonner-toast]').first(), `${quoi} : le refus est dit`).toBeVisible({ timeout: 20_000 })
  await p.waitForTimeout(2500)
  expect(await p.locator('[data-sonner-toast]').count(), `${quoi} : un seul message (aucun toast générique en plus de celui de l'intercepteur)`).toBe(1)
}

etape('PF12.117b-reassignation', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117a_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const cible = `aerr117c_${m}`
  const idCible = await compteRole(cible, 'Commercial')
  const [lead] = await creerLeads(cr, [{ nom: `AERR117R ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const proprietaire = () => py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${lead}).owner_id)`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  suivi.attendre(new RegExp(`/api/django/crm/leads/${lead}/$`), 400)
  await p.route((u) => u.pathname === `${API}/crm/leads/${lead}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ owner: ['Réassignation refusée (AERR117).'] }) })
    : route.fallback()))
  await p.goto(`/crm/leads?view=liste&q=${m}`)
  const ligne = p.locator('tr.lv-row').filter({ hasText: `AERR117R ${m}` })
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.locator('.ap-trigger').click()
  const demande = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${lead}/`), T)
  await p.locator('.ap-item').filter({ hasText: cible }).click()
  const rep = await demande
  expect(rep.status(), 'réassignation refusée (400 injecté)').toBe(400)
  expect(JSON.parse(rep.request().postData()), 'PATCH {owner: <cible>}').toEqual({ owner: idCible })
  await unSeulMessage(p, 'réassignation refusée')
  expect(await proprietaire(), 'base : le responsable n\'a pas changé').toBe(cr)
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(p.locator('tr.lv-row').filter({ hasText: `AERR117R ${m}` }), 'après rechargement : lead listé').toBeVisible({ timeout: 60_000 })
})

etape('PF12.117c-type-client', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117t_${m}`
  await compteRole(nom, 'Directeur')
  const client = await py(`from apps.crm.models import Client
c = Client.objects.create(company_id=${SOC}, nom='AERR117T ${m}', prenom='Essai')
sortie(c.pk)`)
  apres.push(() => py(`from apps.crm.models import Client
Client.objects.filter(pk=${client}).delete()`))
  const typeEnBase = () => py(`from apps.crm.models import Client
sortie(Client.objects.get(pk=${client}).type_client)`)
  const avant = await typeEnBase()
  const { p } = await ecran(page, suivi, testInfo, nom)
  suivi.attendre(new RegExp(`/api/django/crm/clients/${client}/$`), 400)
  await p.route((u) => u.pathname === `${API}/crm/clients/${client}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ type_client: ['Type refusé (AERR117).'] }) })
    : route.fallback()))
  await p.goto('/crm')
  await p.getByPlaceholder(/Rechercher nom, email/).fill(`AERR117T ${m}`, { timeout: 60_000 })
  const ligne = p.getByRole('row').filter({ hasText: `AERR117T ${m}` })
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  const actuel = (await ligne.locator('.ct-type-btn').innerText()).trim()
  const autreType = /entreprise/i.test(actuel) ? 'Particulier' : 'Entreprise'
  await ligne.getByTitle('Changer le type de client').click()
  const demande = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/clients/${client}/`), T)
  await ligne.locator('.ct-type-opt').filter({ hasText: autreType }).click()
  expect((await demande).status(), 'changement de type refusé (400 injecté)').toBe(400)
  await unSeulMessage(p, 'type de client refusé')
  expect(await typeEnBase(), 'base : le type n\'a pas changé').toBe(avant)
})

etape('PF12.117d-mois-cloture', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117m_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const d = new Date(); d.setMonth(d.getMonth() + 1, 15)
  const [lead] = await creerLeads(cr, [{ nom: `AERR117M ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'QUOTE_SENT', date_cloture_prevue: isoJour(d) }])
  apres.push(() => supprimerLeads([lead]))
  const dateEnBase = () => py(`from apps.crm.models import Lead
sortie(str(Lead.objects.get(pk=${lead}).date_cloture_prevue))`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  suivi.attendre(new RegExp(`/api/django/crm/leads/${lead}/$`), 400)
  await p.route((u) => u.pathname === `${API}/crm/leads/${lead}/`, (route) => (route.request().method() === 'PATCH'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ date_cloture_prevue: ['Mois refusé (AERR117).'] }) })
    : route.fallback()))
  await p.goto(`/crm/leads?view=prevision&q=${m}`)
  const selecteur = p.locator(`#fv-month-${lead}`)
  await expect(selecteur, 'le lead est sur le tableau de prévision').toBeVisible({ timeout: 60_000 })
  const origine = await selecteur.inputValue()
  const autre = await selecteur.locator('option').evaluateAll((os, o) => os.map((x) => x.value).find((v) => v !== o), origine)
  expect(autre, 'un autre mois est proposé').toBeTruthy()
  const demande = p.waitForResponse((r) => r.request().method() === 'PATCH' && r.url().endsWith(`/crm/leads/${lead}/`), T)
  await selecteur.selectOption(autre)
  expect((await demande).status(), 'changement de mois refusé (400 injecté)').toBe(400)
  await unSeulMessage(p, 'mois de clôture refusé')
  await expect(selecteur, 'le sélecteur revient au mois d\'origine').toHaveValue(origine, { timeout: 15_000 })
  expect(await dateEnBase(), 'base : date de clôture inchangée').toBe(isoJour(d))
})

etape('PF12.117e-rdv-notes', ['AERR117'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr117v_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const [lead] = await creerLeads(cr, [{ nom: `AERR117V ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), stage: 'NEW' }])
  apres.push(() => supprimerLeads([lead]))
  const nbRdv = () => py(`from apps.crm.models import Appointment
sortie(Appointment.objects.filter(lead_id=${lead}).count())`)
  const { p } = await ecran(page, suivi, testInfo, nom)
  const APPT = /\/api\/django\/crm\/appointments\/$/
  suivi.attendre(APPT, 400)
  await p.route(APPT, (route) => (route.request().method() === 'POST'
    ? route.fulfill({ status: 400, contentType: 'application/json', body: J({ notes: ['Notes trop longues (AERR117).'] }) })
    : route.fallback()))
  await p.goto(`/crm/leads/${lead}`)
  await p.getByRole('navigation', { name: 'Sections du lead' }).getByRole('button', { name: /Visite technique/ }).click({ timeout: 60_000 })
  await p.locator('summary').filter({ hasText: 'Autre rendez-vous' }).click()
  await p.getByRole('button', { name: '+ Planifier une visite' }).first().click({ timeout: 60_000 })
  const futur = new Date(); futur.setDate(futur.getDate() + 10)
  await p.locator('#appt-scheduled-at').fill(`${isoJour(futur)}T10:00`)
  await p.locator('#appt-notes').fill('Visite AERR117')
  await p.getByRole('button', { name: 'Confirmer', exact: true }).click()
  const erreur = p.locator('#appt-error')
  await expect(erreur, '400 {notes} nommé dans le formulaire du RDV').toHaveText('Notes : Notes trop longues (AERR117).', { timeout: 20_000 })
  await expect(p.locator('#appt-notes'), 'la saisie des notes est gardée').toHaveValue('Visite AERR117')
  expect(await nbRdv(), 'base : aucun RDV créé sur refus').toBe(0)
})
