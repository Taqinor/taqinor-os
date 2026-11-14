// Preuve en direct d'AERR155 (C-AERR-VER2-106, PLAN_AUDIT_TRANSVERSE.md) : sortir d'un formulaire modifié ouvre la boîte
// de l'APPLICATION « Quitter sans enregistrer ? » (`frontend/src/ui/useDirtyGuard.js::confirmLeaveIfDirty` → `ui/confirm`),
// jamais un dialogue natif. La clause demande de REJOUER les étapes AERR27 (/sav, fiche modifiée, Échap), AERR37
// (réception fournisseur et BCF), AERR38 (recette de pompage) et PF12.9b-AERR108-creation (lead en création, lien du
// doublon) : chaque étape ci-dessous rejoue le même geste que l'étape d'origine (aerr.spec.js, aerr2.spec.js), sous le
// même rôle LIVRÉ du registre (Responsable, Administrateur ; Commercial pour le lead, comme la clause le nomme), et
// affirme : la boîte maison s'ouvre (titre, « Rester », « Quitter ») ; « Rester » garde la saisie ; « Quitter » ferme
// sans rien écrire (base relue par le shell Django, écran rechargé) ; l'oracle 4 n'excuse AUCUN dialogue natif.
// Données propres créées par le shell Django et retirées après l'étape (base jetable du runner).
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, telephoneMobileUnique, uiLoginJusquAuxApps } from '../helpers.js'

const G = 'AERR'
const etape = groupe(G, ['AERR155'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const DEMANDE = 'Quitter sans enregistrer ?'
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const contextes = []
const apres = []
test.afterEach(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

/** Compte d'essai du rôle LIVRÉ `nomRole` (rôle système de la société démo) ; renvoie son id. */
const compteRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
assert r.est_systeme, 'rôle non système'
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.first_name = 'Essai'; u.last_name = ${J(nomRole)}; u.save(update_fields=['first_name', 'last_name'])
sortie(u.id)`)

/** Écran du compte `nom` (contexte neuf, SW bloqué, accueil et visites vus), observé par les oracles ; la page
 *  demo_admin de l'étape est refermée (la capture montre CET écran). `ui` : connexion par l'ÉCRAN de connexion
 *  (patron aerr2.spec.js), sinon par /token/ (patron aerr.spec.js). `dem.repondre()` répond dans la boîte maison
 *  « Quitter sans enregistrer ? » ; tout dialogue natif est un incident de l'oracle 4. */
async function ecran(page, suivi, testInfo, nom, { ui = false } = {}) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  contextes.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  if (!ui) await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const p = suivi.surveiller(await ctx.newPage())
  const boite = p.getByRole('alertdialog').filter({ hasText: DEMANDE })
  const dem = { vues: 0, prochaine: null, boite }
  dem.repondre = async () => {
    if (dem.prochaine && await boite.isVisible()) {
      // La boîte de l'application, ses deux réponses.
      await expect(boite.getByRole('button', { name: 'Rester', exact: true }), 'boîte maison : « Rester »').toBeVisible()
      await expect(boite.getByRole('button', { name: 'Quitter', exact: true }), 'boîte maison : « Quitter »').toBeVisible()
      await boite.getByRole('button', { name: dem.prochaine === 'quitter' ? 'Quitter' : 'Rester', exact: true }).click()
      await expect(boite, 'boîte maison refermée').toHaveCount(0)
      dem.prochaine = null
      dem.vues += 1
    }
    return dem.vues
  }
  p.removeAllListeners('dialog')
  p.on('dialog', async (d) => {
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif inattendu ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
  if (ui) await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p, dem }
}

/** Capture PENDANT que l'écran affirmé est visible (en plus de la capture de fin d'étape). */
async function capturer(p, id, n) {
  const chemin = join(RACINE, cheminCapture(G, `${id}-${n}`))
  mkdirSync(dirname(chemin), { recursive: true })
  await p.screenshot({ path: chemin, type: 'jpeg', quality: 60 })
}
const auRepos = (p) => p.waitForLoadState('networkidle').catch(() => undefined)

// ══════════════ SAV — rejeu de PF12.1-AERR27 (Responsable, /sav, fiche modifiée, Échap) ══════════════
const ticketsDe = (m, specs) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
ids = []
for s in ${J(specs)}:
    t = Ticket.objects.create(company_id=${SOC}, client=cl, reference=s['ref'], priorite=s['priorite'],
        description=s['description'], instructions=s.get('instructions', ''))
    ids.append(t.pk)
sortie(dict(client=cl.pk, tickets=ids))`)
const champsTicket = (pks) => py(`from apps.sav.models import Ticket
sortie([[t.priorite, t.description, t.instructions] for t in (Ticket.objects.get(pk=pk) for pk in ${J(pks)})])`)
const retirerTickets = (ids) => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
for pk in ${J(ids.tickets)}:
    try: Ticket.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)
async function listeTickets(p, m) {
  await p.goto('/sav')
  await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(`AERR Client ${m}`, { timeout: 60_000 })
  const ligne = (ref) => p.getByRole('row').filter({ hasText: ref })
  const fiche = p.locator('aside[aria-label^="Détail du ticket"]')
  const champ = {
    description: fiche.locator('label:text-is("Description") + div textarea'),
    technicien: fiche.locator('label:text-is("Technicien responsable") + button'),
  }
  return { ligne, fiche, champ }
}

etape('PF12.1-AERR155-sav', ['AERR155'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-155-${m}`
  const S2 = `SAV-255-${m}`
  const ids = await ticketsDe(m, [
    { ref: S1, priorite: 'normale', description: `Onduleur ${m}` },
    { ref: S2, priorite: 'normale', description: `Câble ${m}` },
  ])
  apres.push(() => retirerTickets(ids))
  const nom = `aerr155re_${m}`
  await compteRole(nom, 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const { ligne, fiche, champ } = await listeTickets(p, m)
  await expect(ligne(S2)).toBeVisible({ timeout: 60_000 })
  await ligne(S1).getByText(S1).click()
  await expect(fiche).toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  const retouche = `Onduleur ${m} — retouche non enregistrée`
  await champ.description.fill(retouche)
  // 1) « Annuler ce ticket ? » ouverte, Échap : seule cette boîte se ferme, aucune demande.
  await fiche.getByRole('button', { name: 'Annuler le ticket' }).click()
  const annul = p.getByRole('alertdialog')
  await expect(annul).toContainText('Annuler ce ticket ?')
  await p.keyboard.press('Escape')
  await expect(annul, 'Échap ferme la boîte').toBeHidden()
  await expect(fiche, 'la fiche reste ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.description, 'saisie intacte').toHaveValue(retouche)
  await expect(dem.boite, 'aucune demande : la fiche n\'a pas été visée').toHaveCount(0)
  // 2) Liste Technicien ouverte, « k » puis « j », Échap : sélection inchangée, aucune demande.
  await champ.technicien.click()
  const liste = p.getByRole('listbox')
  await expect(liste, 'liste Technicien ouverte').toBeVisible()
  await p.keyboard.press('k')
  await p.keyboard.press('j')
  await expect(fiche, 'k / j dans la liste : même ticket').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await p.keyboard.press('Escape')
  await expect(liste, 'Échap ferme la liste').toBeHidden()
  await expect(champ.description).toHaveValue(retouche)
  await expect(dem.boite, 'aucune demande pendant la liste').toHaveCount(0)
  // 3) Fiche modifiée, Échap : la boîte de l'application ; « Rester » garde fiche et saisie.
  await fiche.getByRole('button', { name: "Rapport d'intervention (PDF)" }).focus()
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect(dem.boite, 'Échap sur la fiche modifiée : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await capturer(p, 'PF12.1-AERR155-sav', 1)
  await expect.poll(() => dem.repondre(), { message: 'Échap : la boîte maison est posée' }).toBe(1)
  await expect(fiche, 'rester : fiche ouverte').toHaveAttribute('aria-label', `Détail du ticket ${S1}`)
  await expect(champ.description, 'rester : saisie gardée').toHaveValue(retouche)
  // « Quitter » : la fiche se ferme, rien n'est écrit.
  await fiche.getByRole('button', { name: "Rapport d'intervention (PDF)" }).focus()
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre(), { message: 'Échap : la boîte maison est posée (2)' }).toBe(2)
  await expect(fiche, 'quitter : fiche fermée').toHaveCount(0)
  expect(await champsTicket([ids.tickets[0]]), 'base : description non écrite').toEqual([['normale', `Onduleur ${m}`, '']])
  await p.reload()
  const l2 = await listeTickets(p, m)
  await l2.ligne(S1).getByText(S1).click({ timeout: 60_000 })
  await expect(l2.champ.description, 'après rechargement : description d\'origine').toHaveValue(`Onduleur ${m}`)
  await auRepos(p)
})

// ══════════════ Chantiers — rejeu de PF12.2-AERR38 (Responsable, recette de pompage) ══════════════
const chantierDe = (m, prefixe) => py(`from apps.crm.models import Client
from apps.installations.models import Installation
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`${prefixe}-${m}`)}, client=cl, type_installation='agricole')
sortie(dict(client=cl.pk, inst=i.pk))`)
const retirerChantier = (ids) => py(`from apps.crm.models import Client
from apps.installations.models import Installation
try: Installation.objects.filter(pk=${ids.inst}).delete()
except Exception as exc: print('nettoyage chantier', exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`)

etape('PF12.2-AERR155-recette', ['AERR155'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await chantierDe(m, 'AERR155')
  apres.push(() => retirerChantier(ids))
  const r = page.request
  const ouverte = await r.post(`${API}/installations/chantiers/${ids.inst}/recette-pompage/`, { ...T, data: {} })
  expect(ouverte.status(), `fiche de recette ouverte : ${(await ouverte.text()).slice(0, 200)}`).toBeLessThan(300)
  const nom = `aerr155rp_${m}`
  await compteRole(nom, 'Responsable')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const recette = p.getByRole('dialog', { name: 'Recette de pompage (IEC 62253)' })
  const debit = recette.locator('#recette-pompage-debit_mesure_m3h')
  const ouvrir = async () => {
    await p.goto(`/chantiers?id=${ids.inst}`)
    await p.getByRole('tab', { name: /Jalons/ }).click({ timeout: 60_000 })
    await expect(p.getByTestId('ch6-recette')).toBeVisible({ timeout: 30_000 })
    await p.getByRole('button', { name: /fiche de recette/ }).first().click()
    await expect(recette).toBeVisible({ timeout: 30_000 })
    await expect(debit).toBeVisible()
  }
  await ouvrir()
  await p.keyboard.press('Escape')
  await expect(recette, 'sans saisie : fermeture directe').toBeHidden()
  await expect(dem.boite, 'sans saisie : aucune demande').toHaveCount(0)
  await ouvrir()
  await debit.fill('12.5')
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect(dem.boite, 'Échap : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await capturer(p, 'PF12.2-AERR155-recette', 1)
  await expect.poll(() => dem.repondre(), { message: 'Échap : boîte maison posée' }).toBe(1)
  await expect(recette, 'rester : fiche ouverte').toBeVisible()
  await expect(debit, 'rester : mesure intacte').toHaveValue('12.5')
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect.poll(() => dem.repondre(), { message: 'clic extérieur : boîte maison posée' }).toBe(2)
  await expect(recette, 'rester (clic extérieur) : fiche ouverte').toBeVisible()
  await expect(debit).toHaveValue('12.5')
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre()).toBe(3)
  await expect(recette, 'quitter : fiche fermée').toBeHidden()
  const lue = await (await r.get(`${API}/installations/chantiers/${ids.inst}/recette-pompage/`, T)).json()
  expect(lue.record?.debit_mesure_m3h ?? null, 'base : aucune mesure enregistrée').toBeNull()
  await p.reload()
  await ouvrir()
  await expect(debit, 'rechargé, fiche rouverte : mesure non enregistrée').toHaveValue('')
  await p.keyboard.press('Escape')
  await auRepos(p)
})

// ══════════════ Stock — rejeu de PF12.3-AERR37 (Administrateur, réception fournisseur et BCF) ══════════════
const achatsDe = (m, bcfs) => py(`from decimal import Decimal
from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`AERR Fournisseur ${m}`)})
prods = [Produit.objects.create(company_id=${SOC}, nom='AERR article %s ${m}' % n, prix_vente=100, prix_achat=60) for n in ('A', 'B')]
bs = []
for s in ${J(bcfs)}:
    b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference=s['ref'], fournisseur=f, statut=s['statut'], date_commande=timezone.localdate())
    for pr, q in zip(prods, s['quantites']):
        LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=q, prix_achat_unitaire=Decimal('60'))
    bs.append(b.pk)
sortie(dict(f=f.pk, prods=[p.pk for p in prods], bcfs=bs))`)
const retirerAchats = (ids) => py(`from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur
for qs in (BonCommandeFournisseur.objects.filter(pk__in=${J(ids.bcfs)}), Produit.objects.filter(pk__in=${J(ids.prods)}),
           Fournisseur.objects.filter(pk=${ids.f})):
    try: qs.delete()
    except Exception as exc: print('nettoyage achats', exc)`)

etape('PF12.3-AERR155-reception', ['AERR155'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `BCF-AERR155-${m}`
  const ids = await achatsDe(m, [{ ref, statut: 'envoye', quantites: [2, 3] }])
  apres.push(() => retirerAchats(ids))
  const nom = `aerr155ad_${m}`
  await compteRole(nom, 'Administrateur')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const dlg = p.getByRole('dialog').filter({ hasText: 'Nouvelle réception fournisseur' })
  await p.goto('/stock/receptions-fournisseur')
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click({ timeout: 60_000 })
  await expect(dlg).toBeVisible()
  await p.mouse.click(8, 8)
  await expect(dlg, 'non modifié : fermeture directe').toBeHidden()
  await expect(dem.boite, 'non modifié : aucune demande').toHaveCount(0)
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click()
  await dlg.locator('#rec-bon').click()
  await p.getByPlaceholder('Référence ou fournisseur…').fill(ref)
  await p.getByRole('option', { name: new RegExp(ref) }).click()
  const lignes = dlg.locator('tbody tr')
  await expect(lignes, '2 lignes à réceptionner').toHaveCount(2, { timeout: 30_000 })
  await dlg.getByRole('button', { name: `N° de série / lot — AERR article A ${m}` }).click()
  await dlg.getByRole('button', { name: `N° de série / lot — AERR article B ${m}` }).click()
  const series = dlg.locator('textarea[id^="rec-series-"]')
  await expect(series).toHaveCount(2)
  await series.nth(0).fill(`SNA1-${m}\nSNA2-${m}`)
  await series.nth(1).fill(`SNB1-${m}`)
  await dlg.locator('#rec-note').fill(`Réception partielle ${m}`)
  const saisie = async (quand) => {
    await expect(dlg, `${quand} : boîte ouverte`).toBeVisible()
    await expect(dlg.locator('#rec-bon'), `${quand} : BCF choisi`).toContainText(ref)
    await expect(lignes, `${quand} : 2 lignes`).toHaveCount(2)
    await expect(series.nth(0), `${quand} : séries ligne A`).toHaveValue(`SNA1-${m}\nSNA2-${m}`)
    await expect(series.nth(1), `${quand} : série ligne B`).toHaveValue(`SNB1-${m}`)
    await expect(dlg.locator('#rec-note'), `${quand} : note`).toHaveValue(`Réception partielle ${m}`)
  }
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect(dem.boite, 'clic sur le fond : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await capturer(p, 'PF12.3-AERR155-reception', 1)
  await expect.poll(() => dem.repondre(), { message: 'clic sur le fond : boîte maison posée' }).toBe(1)
  await saisie('rester (clic extérieur)')
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre(), { message: 'Échap : boîte maison posée' }).toBe(2)
  await saisie('rester (Échap)')
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre()).toBe(3)
  await expect(dlg, 'quitter : boîte fermée').toBeHidden()
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.get(pk=${ids.bcfs[0]})
sortie([b.statut, sum(l.quantite_recue for l in b.lignes.all())])`), 'base : rien réceptionné').toEqual(['envoye', 0])
  await p.reload()
  await p.getByRole('button', { name: 'Nouvelle réception' }).first().click({ timeout: 60_000 })
  await expect(dlg.locator('#rec-note'), 'après rechargement : formulaire vierge').toHaveValue('')
  await p.mouse.click(8, 8)
  await expect(dlg).toBeHidden()
  await auRepos(p)
})

etape('PF12.3-AERR155-bcf', ['AERR155'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `BCF-AERR155B-${m}`
  const ids = await achatsDe(m, [{ ref, statut: 'brouillon', quantites: [2, 3] }])
  apres.push(() => retirerAchats(ids))
  const nom = `aerr155bc_${m}`
  await compteRole(nom, 'Administrateur')
  const { p, dem } = await ecran(page, suivi, testInfo, nom)
  const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-note') })
  const ouvrir = async () => {
    await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(ref, { timeout: 60_000 })
    await p.getByRole('row').filter({ hasText: ref }).getByText(ref).click({ timeout: 60_000 })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
  }
  await p.goto('/stock/bons-commande-fournisseur')
  await ouvrir()
  await p.keyboard.press('Escape')
  await expect(dlg, 'non modifié : fermeture directe').toBeHidden()
  await expect(dem.boite).toHaveCount(0)
  await ouvrir()
  await dlg.locator('#bcf-note').fill(`Livraison quai 2 ${m}`)
  dem.prochaine = 'rester'
  await p.mouse.click(8, 8)
  await expect(dem.boite, 'clic extérieur : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await capturer(p, 'PF12.3-AERR155-bcf', 1)
  await expect.poll(() => dem.repondre(), { message: 'clic extérieur : boîte maison posée' }).toBe(1)
  await expect(dlg, 'rester : boîte ouverte').toBeVisible()
  await expect(dlg.locator('#bcf-note'), 'rester : saisie gardée').toHaveValue(`Livraison quai 2 ${m}`)
  dem.prochaine = 'rester'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre(), { message: 'Échap : boîte maison posée' }).toBe(2)
  await expect(dlg.locator('#bcf-note')).toHaveValue(`Livraison quai 2 ${m}`)
  dem.prochaine = 'quitter'
  await p.keyboard.press('Escape')
  await expect.poll(() => dem.repondre()).toBe(3)
  await expect(dlg).toBeHidden()
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
sortie(BonCommandeFournisseur.objects.get(pk=${ids.bcfs[0]}).note)`), 'base : note non écrite').toBeNull()
  await p.reload()
  await ouvrir()
  await expect(dlg.locator('#bcf-note'), 'après rechargement : note vide').toHaveValue('')
  await p.keyboard.press('Escape')
  await auRepos(p)
})

// ══════════════ CRM — rejeu de PF12.9b-AERR108-creation (Commercial, lead en création, lien du doublon) ══════════════
const creerLead = (owner, d) => py(`from apps.crm.models import Lead
sortie(Lead.objects.create(company_id=${SOC}, owner_id=${owner}, **json.loads(${J(J(d))})).pk)`)
const supprimerLeads = (noms) => py(`from apps.crm.models import Lead
for l in Lead.all_objects.filter(nom__in=${J(noms)}):
    try: l.delete()
    except Exception as exc: print('nettoyage', l.pk, exc)`)
const nbLeads = (n) => py(`from apps.crm.models import Lead
sortie(Lead.all_objects.filter(nom=${J(n)}).count())`)

etape('PF12.9b-AERR155-creation', ['AERR155'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `aerr155co_${m}`
  const co = await compteRole(nom, 'Commercial')
  const tel = telephoneMobileUnique()
  const doublon = `AERR155C ${m}`
  const nouveau = `AERR155C nouveau ${m}`
  const a = await creerLead(co, { nom: doublon, prenom: 'Essai', telephone: tel, stage: 'NEW' })
  apres.push(() => supprimerLeads([doublon, nouveau]))
  const { p, dem } = await ecran(page, suivi, testInfo, nom, { ui: true })
  const lectures = []
  p.on('request', (q) => { if (q.method() === 'GET' && new URL(q.url()).pathname === `${API}/crm/leads/${a}/`) lectures.push(q.url()) })
  await p.goto('/crm/leads?new=1')
  const fiche = p.getByRole('dialog').filter({ has: p.getByRole('heading', { name: 'Nouveau lead' }) })
  await expect(fiche).toBeVisible({ timeout: 60_000 })
  await fiche.locator('#lf-nom').fill(nouveau)
  await fiche.locator('#lf-telephone').fill(tel)
  const lien = fiche.locator('.lw-dup-warning .lw-dup-link').filter({ hasText: doublon })
  await expect(lien, 'doublon signalé en création').toBeVisible({ timeout: 30_000 })
  // Lien du doublon : la boîte de l'application ; « Rester » garde la fiche en création, le doublon n'est pas lu.
  dem.prochaine = 'rester'
  await lien.click()
  await expect(dem.boite, 'lien du doublon : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await capturer(p, 'PF12.9b-AERR155-creation', 1)
  await expect.poll(() => dem.repondre(), { message: 'lien du doublon : boîte maison posée' }).toBe(1)
  await expect(fiche, 'rester : la fiche en création reste').toBeVisible()
  await expect(fiche.locator('#lf-nom'), 'rester : saisie gardée').toHaveValue(nouveau)
  expect(lectures.length, 'rester : le doublon n\'est pas lu').toBe(0)
  expect(await nbLeads(nouveau), 'rester : rien n\'est créé').toBe(0)
  // « Quitter » : la fiche bascule sur le doublon, la saisie en création n'est écrite nulle part.
  dem.prochaine = 'quitter'
  await lien.click()
  await expect.poll(() => dem.repondre(), { message: 'lien du doublon : boîte maison posée (2)' }).toBe(2)
  await expect(p.getByRole('heading', { name: new RegExp(doublon) }).first(), 'quitter : le doublon est ouvert').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => lectures.length, { message: 'quitter : le doublon est lu', timeout: 30_000 }).toBeGreaterThan(0)
  expect(await nbLeads(nouveau), 'quitter : rien n\'est créé').toBe(0)
  await p.reload()
  await auRepos(p)
  expect(await nbLeads(nouveau), 'rechargé : toujours rien créé').toBe(0)
  await auRepos(p)
})
