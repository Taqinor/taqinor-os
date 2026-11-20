// aerr16 : preuves en direct ÉCRAN du groupe AERR, lot 16, des trois tâches livrées sur dev-all-2011c le 20/11/2026 :
// AERR187 (fiche produit /stock et « Nouvelle réception fournisseur ») et AERR188 (formulaire « Nouvelle facture ») — leur bouton
// « Annuler » du pied passe désormais par `confirmLeaveIfDirty` : saisie ⇒ la boîte de l'application « Quitter sans enregistrer ? »
// (« Rester » garde fiche et saisie, « Quitter » ferme), formulaire intact ⇒ fermeture directe sans demande, aucune écriture ;
// AERR189 (liste des leads, « Planifier une relance » depuis la carte kanban) — la fenêtre reste montée : date et objet tapés
// sont gardés après une fermeture accidentelle (Échap) puis réouverture sur le même lead, vides sur un autre lead, rien n'est
// écrit en base par la fermeture ; « Enregistrer » pose ensuite la relance et ferme la fenêtre.
// Chaque étape joue le geste sous un compte d'essai du rôle SYSTÈME « Directeur » (« Commercial » pour les leads),
// session posée par la vraie route /token/ (patron aerr15.spec.js), relit la base par le shell Django, recharge et réaffirme.
// Tout dialogue natif est un incident de l'oracle 4 (la demande est la boîte de l'application). Données propres créées par le
// shell Django et retirées en fin d'étape (base jetable du runner). Aucun envoi réel.
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, listeDe, telephoneMobileUnique } from '../helpers.js'

const G = 'AERR'
const etape = groupe(G, ['AERR187', 'AERR188', 'AERR189'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const DEMANDE = 'Quitter sans enregistrer ?' // AERR155 — boîte maison de `confirmLeaveIfDirty`
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const contextes = []
const apres = []
const comptes = []
test.afterEach(async () => {
  for (const c of contextes.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
  const noms = comptes.splice(0)
  if (noms.length) await py(`U.objects.filter(username__in=${J(noms)}).update(is_active=False)`).catch(() => undefined)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte })
const auRepos = (p) => p.waitForLoadState('networkidle').catch(() => undefined)

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {nom, id}. Désactivé en fin d'étape. */
async function compteRole(prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
assert r.est_systeme, 'rôle non système'
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.first_name = 'Essai'; u.last_name = ${J(nomRole)}; u.save(update_fields=['first_name', 'last_name'])
sortie(u.id)`)
  comptes.push(nom)
  return { nom, id }
}

/** Écran du compte `nom` : contexte neuf (accueil et visites guidées vus, SW bloqué), session par la vraie route /token/,
 *  observé par les oracles ; la page demo_admin de l'étape est refermée (la capture montre CET écran). */
async function ecran(page, suivi, testInfo, nom, viewport = { width: 1600, height: 1000 }) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport,
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
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of listeDe(await visites.json())) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  p.removeAllListeners('dialog')
  p.on('dialog', async (d) => {
    suivi.incidents.push({ oracle: '4', texte: `dialogue natif inattendu ${d.type()} : ${d.message()}` })
    await d.dismiss().catch(() => undefined)
  })
  return { p, ctx, boite: p.getByRole('alertdialog').filter({ hasText: DEMANDE }) }
}

/** Requêtes de méthode `methode` (ou toute méthode d'écriture si `null`) d'URL `re` parties de la page. */
function compter(p, methode, re) {
  const vues = []
  p.on('request', (r) => {
    const ok = methode ? r.method() === methode : r.method() !== 'GET' && r.method() !== 'HEAD' && r.method() !== 'OPTIONS'
    if (ok && re.test(r.url())) vues.push(`${r.method()} ${r.url()}`)
  })
  return vues
}

/** Capture PENDANT que l'écran affirmé est visible (en plus de la capture de fin d'étape). */
async function cliche(p, id, moment) {
  const chemin = join(RACINE, cheminCapture(G, `${id}-${moment}`))
  mkdirSync(dirname(chemin), { recursive: true })
  await p.screenshot({ path: chemin, type: 'jpeg', quality: 60 })
}

/** Le geste commun d'AERR187/188 : « Annuler » du pied d'un formulaire de création.
 *  1) formulaire intact ⇒ « Annuler » ferme sans demande ; 2) saisie ⇒ la boîte de l'application, « Rester » garde formulaire
 *  et saisie ; 3) « Annuler » puis « Quitter » ⇒ formulaire fermé ; aucune écriture envoyée ; rouvert : saisie perdue (neuf). */
async function scenarioAnnuler(p, boite, id, { ouvrir, fiche, saisir, verifierSaisie, verifierNeuf, ecritures }) {
  // Rôle lu en CSS : la boîte « Quitter sans enregistrer ? » pose aria-hidden sur le formulaire, que getByRole ignorerait.
  const annuler = () => fiche.locator('button:text-is("Annuler")').click()
  await ouvrir()
  await annuler()
  await expect(fiche, 'sans saisie : « Annuler » ferme le formulaire').toBeHidden({ timeout: 15_000 })
  await expect(boite, 'sans saisie : aucune demande').toHaveCount(0)
  await ouvrir()
  await saisir()
  await annuler()
  await expect(boite, '« Annuler » sur le formulaire modifié : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await expect(boite.getByRole('button', { name: 'Rester', exact: true }), 'boîte maison : « Rester »').toBeVisible()
  await expect(boite.getByRole('button', { name: 'Quitter', exact: true }), 'boîte maison : « Quitter »').toBeVisible()
  await expect(fiche, 'la demande est posée, le formulaire reste ouvert').toBeVisible()
  await cliche(p, id, 'demande')
  await boite.getByRole('button', { name: 'Rester', exact: true }).click()
  await expect(boite, 'boîte refermée').toHaveCount(0)
  await expect(fiche, 'rester : formulaire ouvert').toBeVisible()
  await verifierSaisie()
  await annuler()
  await expect(boite, 'second « Annuler » : la demande revient').toBeVisible({ timeout: 15_000 })
  await boite.getByRole('button', { name: 'Quitter', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await expect(fiche, 'quitter : formulaire fermé').toBeHidden({ timeout: 15_000 })
  expect(ecritures, 'aucune écriture envoyée').toEqual([])
  await p.reload()
  await ouvrir()
  await verifierNeuf()
  await auRepos(p)
}

// ══════════════════════════════ Stock — AERR187 (fiche produit, nouvelle réception) ══════════════════════════════

etape('S2-AERR187-produit-annuler', ['AERR187'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `Produit AERR187 ${m}`
  const di = await compteRole('aerr187di', 'Directeur')
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, /\/api\/django\/stock\/produits\//)
  const champ = p.locator('#pf-nom')
  const fiche = p.locator('[role="dialog"]').filter({ has: champ })
  const produitsEnBase = () => py(`from apps.stock.models import Produit
sortie(Produit.objects.filter(company_id=${SOC}, nom__icontains='AERR187 ${m}').count())`)
  apres.push(() => py(`from apps.stock.models import Produit
try: Produit.objects.filter(company_id=${SOC}, nom__icontains='AERR187 ${m}').delete()
except Exception as exc: print('nettoyage produit', exc)`))
  await scenarioAnnuler(p, boite, 'S2-AERR187-produit', {
    ouvrir: async () => {
      await p.goto('/stock')
      await p.getByRole('button', { name: 'Nouveau produit' }).first().click({ timeout: 60_000 })
      await expect(champ, 'fiche « Nouveau produit » ouverte').toBeVisible({ timeout: 30_000 })
    },
    fiche,
    saisir: async () => { await champ.fill(nom) },
    verifierSaisie: async () => { await expect(champ, 'rester : nom tapé gardé').toHaveValue(nom) },
    verifierNeuf: async () => { await expect(champ, 'rechargé, fiche rouverte : nom vide').toHaveValue('') },
    ecritures,
  })
  expect(await produitsEnBase(), 'base : aucun produit créé').toBe(0)
})

etape('S2-AERR187-reception-annuler', ['AERR187'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from decimal import Decimal
from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`AERR Fournisseur ${m}`)})
pr = Produit.objects.create(company_id=${SOC}, nom=${J(`AERR article ${m}`)}, prix_vente=100, prix_achat=60)
b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference=${J(`BCF-AERR187-${m}`)}, fournisseur=f, statut='envoye', date_commande=timezone.localdate())
LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=2, prix_achat_unitaire=Decimal('60'))
sortie(dict(f=f.pk, prod=pr.pk, bcf=b.pk))`)
  apres.push(() => py(`from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur
for qs in (BonCommandeFournisseur.objects.filter(pk=${ids.bcf}), Produit.objects.filter(pk=${ids.prod}),
           Fournisseur.objects.filter(pk=${ids.f})):
    try: qs.delete()
    except Exception as exc: print('nettoyage achats', exc)`))
  const di = await compteRole('aerr187re', 'Directeur')
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, /\/api\/django\/stock\/receptions-fournisseur\//)
  const champ = p.locator('#rec-note')
  const fiche = p.locator('[role="dialog"]').filter({ has: champ })
  const saisie = `Livraison quai 3 ${m}`
  await scenarioAnnuler(p, boite, 'S2-AERR187-reception', {
    ouvrir: async () => {
      await p.goto('/stock/receptions-fournisseur')
      const nouvelle = p.getByRole('button', { name: 'Nouvelle réception' }).first()
      await expect(nouvelle, 'bon envoyé recevable : bouton actif').toBeEnabled({ timeout: 60_000 })
      await nouvelle.click()
      await expect(fiche, 'dialogue « Nouvelle réception fournisseur » ouvert').toBeVisible({ timeout: 30_000 })
      await expect(fiche).toContainText('Nouvelle réception fournisseur')
    },
    fiche,
    saisir: async () => { await champ.fill(saisie) }, // la règle « sale » est `bonId || note.trim()`
    verifierSaisie: async () => { await expect(champ, 'rester : note gardée').toHaveValue(saisie) },
    verifierNeuf: async () => { await expect(champ, 'rechargé, dialogue rouvert : note vide').toHaveValue('') },
    ecritures,
  })
  expect(await py(`from apps.achats.models import ReceptionFournisseur
sortie(ReceptionFournisseur.objects.filter(bon_commande_id=${ids.bcf}).count())`), 'base : aucune réception créée').toBe(0)
})

// ══════════════════════════════ Ventes — AERR188 (nouvelle facture) ══════════════════════════════

etape('S2-AERR188-facture-annuler', ['AERR188'], async ({ page, suivi, testInfo }) => {
  const di = await compteRole('aerr188di', 'Directeur')
  const nbFactures = () => py(`from apps.ventes.models import Facture
sortie(Facture.objects.filter(company_id=${SOC}).count())`)
  const avant = await nbFactures()
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, /\/api\/django\/ventes\/factures\//)
  const fiche = p.locator('[role="dialog"]').filter({ hasText: 'Créer la facture' })
  const remise = fiche.locator('tr[data-line-key] td[data-label="Rem. %"] input')
  await scenarioAnnuler(p, boite, 'S2-AERR188', {
    ouvrir: async () => {
      await p.goto('/ventes/factures')
      await p.getByRole('button', { name: 'Nouvelle facture' }).first().click({ timeout: 60_000 })
      await expect(fiche, 'formulaire « Nouvelle facture » ouvert').toBeVisible({ timeout: 30_000 })
    },
    fiche,
    saisir: async () => {
      await fiche.getByRole('button', { name: 'Ajouter une ligne' }).click()
      await expect(remise, 'ligne ajoutée').toBeVisible({ timeout: 15_000 })
      await remise.fill('7')
    },
    verifierSaisie: async () => { await expect(remise, 'rester : ligne et remise gardées').toHaveValue('7') },
    verifierNeuf: async () => { await expect(fiche.locator('tr[data-line-key]'), 'rechargé, formulaire rouvert : aucune ligne tapée').toHaveCount(0) },
    ecritures,
  })
  expect(await nbFactures(), 'base : aucune facture créée').toBe(avant)
})

// ══════════════════════════════ CRM — AERR189 (« Planifier une relance », liste des leads) ══════════════════════════════

etape('S2-AERR189-relance-saisie-gardee', ['AERR189'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr189co', 'Commercial')
  const nomA = `AERR189A ${m}`
  const nomB = `AERR189B ${m}`
  const [a, b] = await py(`from apps.crm.models import Lead
sortie([Lead.objects.create(company_id=${SOC}, owner_id=${co.id}, nom=n, prenom='Essai', telephone=t, stage='NEW').pk
        for n, t in ((${J(nomA)}, ${J(telephoneMobileUnique())}), (${J(nomB)}, ${J(telephoneMobileUnique())}))])`)
  apres.push(() => py(`from apps.crm.models import Lead
for pk in ${J([a, b])}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`))
  const relanceEnBase = (pk) => py(`from apps.crm.models import Lead
r = Lead.objects.get(pk=${pk}).relance_date
sortie(str(r) if r else None)`)
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const ecrituresA = compter(p, null, new RegExp(`/api/django/crm/leads/${a}/`))
  const pop = p.getByRole('dialog').filter({ hasText: 'Planifier une relance' })
  const date = (pk) => p.locator(`#clp-date-${pk}`)
  const objet = (pk) => p.locator(`#clp-objet-${pk}`)
  const ouvrir = async (nomLead, pk) => {
    await p.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nomLead)}`)
    const carte = p.locator('article.kb-card', { hasText: nomLead }).first()
    await expect(carte, `carte du lead ${nomLead}`).toBeVisible({ timeout: 60_000 })
    await carte.getByRole('button', { name: /^Actions du lead/ }).click()
    await p.getByRole('menuitem', { name: 'Planifier une relance' }).click()
    await expect(pop, 'fenêtre « Planifier une relance » ouverte').toBeVisible({ timeout: 30_000 })
    await expect(date(pk), 'fenêtre du bon lead').toBeVisible()
  }
  // Rouvre par le même menu SANS recharger (la fenêtre reste montée, c'est la clause d'AERR189).
  const rouvrir = async (nomLead) => {
    const carte = p.locator('article.kb-card', { hasText: nomLead }).first()
    await carte.getByRole('button', { name: /^Actions du lead/ }).click()
    await p.getByRole('menuitem', { name: 'Planifier une relance' }).click()
    await expect(pop, 'fenêtre rouverte').toBeVisible({ timeout: 30_000 })
  }
  const texteObjet = `Rappeler après le devis ${m}`
  await ouvrir(nomA, a)
  await expect(date(a), 'fenêtre neuve : aucune date').toContainText('jj/mm/aaaa')
  await expect(objet(a), 'fenêtre neuve : objet vide').toHaveValue('')
  await pop.getByRole('button', { name: 'Demain', exact: true }).click()
  await expect(date(a), 'date choisie (raccourci « Demain »)').not.toContainText('jj/mm/aaaa')
  const dateTexte = ((await date(a).innerText()).trim())
  await objet(a).fill(texteObjet)
  // Fermeture accidentelle AVANT enregistrement (Échap, focus dans le champ objet), puis réouverture sur le même lead.
  await p.keyboard.press('Escape')
  await expect(pop, 'fenêtre fermée').toBeHidden({ timeout: 15_000 })
  await rouvrir(nomA)
  await expect(date(a), 'A rouvert : date gardée').toHaveText(dateTexte)
  await expect(objet(a), 'A rouvert : objet gardé').toHaveValue(texteObjet)
  await cliche(p, 'S2-AERR189', 'saisie-gardee')
  expect(ecrituresA, 'aucune écriture envoyée par la fermeture').toEqual([])
  expect(await relanceEnBase(a), 'base : aucune relance posée sur A').toBeNull()
  // Autre lead (sans recharger) : fenêtre vide, la saisie de A ne fuit pas sur B.
  await p.keyboard.press('Escape')
  await expect(pop).toBeHidden({ timeout: 15_000 })
  await rouvrir(nomB)
  await expect(date(b), 'lead B : date vide').toContainText('jj/mm/aaaa')
  await expect(objet(b), 'lead B : objet vide').toHaveValue('')
  await p.keyboard.press('Escape')
  await expect(pop).toBeHidden({ timeout: 15_000 })
  expect(await relanceEnBase(b), 'base : aucune relance posée sur B').toBeNull()
  // Enregistrer sur A (fenêtre neuve après le passage par B) : la relance est posée, la fenêtre se ferme.
  await rouvrir(nomA)
  await pop.getByRole('button', { name: 'Demain', exact: true }).click()
  await pop.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  await expect(toast(p, 'Relance planifiée.').first(), 'relance planifiée').toBeVisible({ timeout: 30_000 })
  await expect(pop, 'fenêtre fermée après enregistrement').toBeHidden({ timeout: 15_000 })
  await expect.poll(() => relanceEnBase(a), { message: 'base : relance posée sur A' }).not.toBeNull()
  await auRepos(p)
})
