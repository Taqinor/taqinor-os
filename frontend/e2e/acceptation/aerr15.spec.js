// aerr15 : preuves en direct ÉCRAN du groupe AERR, lot 15, des six tâches livrées sur dev-all-aerr le 20/11/2026 :
// AERR181 (fiche chantier), AERR182 (fiche équipement), AERR183 (fiche BCF) — leur bouton « Fermer » passe désormais par
// `confirmLeaveIfDirty` : fiche modifiée ⇒ la boîte de l'application « Quitter sans enregistrer ? » (« Rester » garde la
// saisie, « Quitter » ferme), fiche intacte ⇒ fermeture directe sans demande, aucune écriture dans tous les cas ;
// AERR184 (ticket SAV, fenêtre à 1 000 px = panneau étroit) — une note tapée puis Échap ouvre la demande, « Rester » garde la note ;
// AERR185 (GED) — « Révoquer » un partage (/ged/retention › Partages) et « Retirer ce droit » (panneau Détails d'un document)
// ouvrent une confirmation qui NOMME la cible ; « Annuler » ⇒ AUCUN appel (relu en base), « Confirmer » ⇒ UN appel ;
// AERR186 (fenêtre « Journaliser un appel » d'un lead) — issue + note gardées après une fermeture accidentelle avant journalisation,
// vides après journalisation (un seul appel en base, garde d'AERR156 intacte).
// Chaque étape joue le geste sous un compte d'essai du rôle SYSTÈME « Directeur » (« Commercial » pour le lead, comme la clause),
// session posée par la vraie route /token/ (patron aerr8.spec.js), relit la base par le shell Django, recharge et réaffirme.
// Tout dialogue natif est un incident de l'oracle 4 (la demande est la boîte de l'application). Données propres créées par le
// shell Django ou l'API et retirées en fin d'étape (base jetable du runner). Aucun envoi réel.
import { test, expect } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { RACINE, cheminCapture } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi, listeDe, telephoneMobileUnique, lireJson } from '../helpers.js'

const G = 'AERR'
const etape = groupe(G, ['AERR181', 'AERR182', 'AERR183', 'AERR184', 'AERR185', 'AERR186'])
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

/** Le geste commun d'AERR181/182/183 : « Fermer » d'une fiche (dialogue ou panneau) modifiée.
 *  1) fiche intacte ⇒ « Fermer » ferme sans demande ; 2) saisie ⇒ la boîte de l'application, « Rester » garde fiche et valeur ;
 *  3) « Fermer » puis « Quitter » ⇒ fiche fermée ; aucune écriture ; base inchangée ; rechargé, fiche rouverte ⇒ valeur d'origine. */
async function scenarioFermer(p, boite, id, { ouvrir, fiche, champ, saisie, ecritures, relireBase, affichageInitial }) {
  const fermer = () => fiche.locator('button:text-is("Fermer")').click()
  const avant = await relireBase()
  await ouvrir()
  await fermer()
  await expect(fiche, 'sans saisie : « Fermer » ferme la fiche').toBeHidden({ timeout: 15_000 })
  await expect(boite, 'sans saisie : aucune demande').toHaveCount(0)
  await ouvrir()
  await champ.fill(saisie)
  await fermer()
  await expect(boite, '« Fermer » sur la fiche modifiée : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await expect(boite.getByRole('button', { name: 'Rester', exact: true }), 'boîte maison : « Rester »').toBeVisible()
  await expect(boite.getByRole('button', { name: 'Quitter', exact: true }), 'boîte maison : « Quitter »').toBeVisible()
  await expect(fiche, 'la demande est posée, la fiche reste ouverte').toBeVisible()
  await cliche(p, id, 'demande')
  await boite.getByRole('button', { name: 'Rester', exact: true }).click()
  await expect(boite, 'boîte refermée').toHaveCount(0)
  await expect(fiche, 'rester : fiche ouverte').toBeVisible()
  await expect(champ, 'rester : valeur tapée gardée').toHaveValue(saisie)
  await fermer()
  await expect(boite, 'second « Fermer » : la demande revient').toBeVisible({ timeout: 15_000 })
  await boite.getByRole('button', { name: 'Quitter', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await expect(fiche, 'quitter : fiche fermée').toBeHidden({ timeout: 15_000 })
  expect(ecritures, 'aucune écriture envoyée').toEqual([])
  expect(await relireBase(), 'base : inchangée').toEqual(avant)
  await p.reload()
  await ouvrir()
  await expect(champ, 'rechargé, fiche rouverte : saisie non enregistrée').toHaveValue(affichageInitial)
  await auRepos(p)
}

// ══════════════════════════════ Chantiers — AERR181 ══════════════════════════════

etape('S2-AERR181-chantier-fermer', ['AERR181'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ids = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`AERR181-${m}`)}, client=cl)
sortie(dict(client=cl.pk, inst=i.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
try: Installation.objects.filter(pk=${ids.inst}).delete()
except Exception as exc: print('nettoyage chantier', exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`))
  const di = await compteRole('aerr181di', 'Directeur')
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, new RegExp(`/api/django/installations/chantiers/${ids.inst}/(\\?.*)?$`))
  // Rôle lu en CSS : la boîte « Quitter sans enregistrer ? » pose aria-hidden sur la fiche, que getByRole(dialog) ignorerait.
  const horaires = p.locator('#ch-horaires')
  const fiche = p.locator('[role="dialog"]').filter({ has: horaires })
  await scenarioFermer(p, boite, 'S2-AERR181', {
    ouvrir: async () => {
      await p.goto(`/chantiers?id=${ids.inst}`)
      await expect(horaires, 'fiche chantier ouverte (Aperçu › Horaires d\'accès)').toBeVisible({ timeout: 60_000 })
    },
    fiche, champ: horaires, saisie: `8h-17h ${m}`, ecritures, affichageInitial: '',
    relireBase: () => py(`from apps.installations.models import Installation
sortie(Installation.objects.get(pk=${ids.inst}).horaires_acces)`),
  })
})

// ══════════════════════════════ SAV — AERR182 (équipement), AERR184 (ticket, panneau étroit) ══════════════════════════════

etape('S2-AERR182-equipement-fermer', ['AERR182'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const serie = `SN182-${m}`
  const ids = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
i = Installation.objects.create(company_id=${SOC}, reference=${J(`AERR182-${m}`)}, client=cl)
pr = Produit.objects.create(company_id=${SOC}, nom=${J(`Onduleur AERR182 ${m}`)}, prix_vente=100)
e = Equipement.objects.create(company_id=${SOC}, produit=pr, installation=i, numero_serie=${J(serie)})
sortie(dict(client=cl.pk, inst=i.pk, produit=pr.pk, eq=e.pk))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
Equipement.objects.filter(pk=${ids.eq}).delete()
Installation.objects.filter(pk=${ids.inst}).delete()
Produit.objects.filter(pk=${ids.produit}).delete()
Client.objects.filter(pk=${ids.client}).delete()`))
  const di = await compteRole('aerr182di', 'Directeur')
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, /\/api\/django\/sav\/equipements\//)
  const fiche = p.locator('[role="dialog"]').filter({ hasText: 'Équipement —' })
  await scenarioFermer(p, boite, 'S2-AERR182', {
    ouvrir: async () => {
      await p.goto('/equipements')
      await p.getByPlaceholder('Rechercher (série, produit, chantier, client)…').fill(`AERR182 ${m}`, { timeout: 60_000 })
      const ligne = p.getByRole('row').filter({ hasText: serie })
      await expect(ligne, 'équipement listé').toBeVisible({ timeout: 60_000 })
      await ligne.getByText(serie).click()
      await expect(fiche, 'fiche équipement ouverte').toBeVisible({ timeout: 30_000 })
    },
    fiche, champ: fiche.locator('label:text-is("Note") + textarea'), saisie: `Note AERR182 ${m}`, ecritures, affichageInitial: '',
    relireBase: () => py(`from apps.sav.models import Equipement
e = Equipement.objects.get(pk=${ids.eq})
sortie([e.note or '', e.numero_serie])`),
  })
})

etape('S2-AERR184-ticket-panneau-etroit', ['AERR184'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const S1 = `SAV-184A-${m}`
  const S2 = `SAV-184B-${m}`
  const ids = await py(`from apps.crm.models import Client
from apps.sav.models import Ticket
cl = Client.objects.create(company_id=${SOC}, nom=${J(`AERR Client ${m}`)})
ts = [Ticket.objects.create(company_id=${SOC}, client=cl, reference=r, priorite='normale', description='Onduleur ${m}').pk for r in (${J(S1)}, ${J(S2)})]
sortie(dict(client=cl.pk, tickets=ts))`)
  apres.push(() => py(`from apps.crm.models import Client
from apps.sav.models import Ticket
for pk in ${J(ids.tickets)}:
    try: Ticket.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
try: Client.objects.filter(pk=${ids.client}).delete()
except Exception as exc: print('nettoyage client', exc)`))
  const notesEnBase = () => py(`from apps.sav.models import Ticket
t = Ticket.objects.get(pk=${ids.tickets[0]})
try:
    from apps.sav.models import TicketActivity
    n = TicketActivity.objects.filter(ticket=t, kind='note').count()
except Exception:
    n = None
sortie(n)`)
  const di = await compteRole('aerr184di', 'Directeur')
  // Fenêtre à 1 000 px : sous 1 280 px la fiche du ticket est le panneau étroit (Sheet), pas la vue scindée.
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom, { width: 1000, height: 800 })
  const ecritures = compter(p, null, /\/api\/django\/sav\/tickets\//)
  const panneau = p.locator('[role="dialog"]').filter({ has: p.getByPlaceholder('Écrire une note…') })
  const note = panneau.getByPlaceholder('Écrire une note…')
  const ouvrir = async () => {
    await p.goto('/sav')
    await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(`AERR Client ${m}`, { timeout: 60_000 })
    await expect(p.getByText(S2).first(), 'SAV-184B listé').toBeVisible({ timeout: 60_000 })
    await p.getByText(S1).first().click()
    await expect(panneau, `panneau du ticket ${S1} ouvert`).toBeVisible({ timeout: 30_000 })
    await expect(panneau).toContainText(S1)
    await expect(p.locator('aside[aria-label^="Détail du ticket"]'), 'à 1 000 px : pas de vue scindée').toHaveCount(0)
  }
  const nAvant = await notesEnBase()
  // Sans brouillon : Échap ferme sans demande.
  await ouvrir()
  await p.keyboard.press('Escape')
  await expect(panneau, 'sans brouillon : Échap ferme le panneau').toBeHidden({ timeout: 15_000 })
  await expect(boite, 'sans brouillon : aucune demande').toHaveCount(0)
  // Note tapée sans l'envoyer puis Échap : la demande ; « Rester » garde panneau et note.
  await ouvrir()
  const texte = `Pièce remplacée sur site ${m}`
  await note.fill(texte)
  await p.keyboard.press('Escape')
  await expect(boite, 'Échap sur le panneau avec note : boîte « Quitter sans enregistrer ? »').toBeVisible({ timeout: 15_000 })
  await cliche(p, 'S2-AERR184', 'demande')
  await boite.getByRole('button', { name: 'Rester', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await expect(panneau, 'rester : panneau ouvert').toBeVisible()
  await expect(note, 'rester : note gardée').toHaveValue(texte)
  // « Quitter » : panneau fermé, la note n'est écrite nulle part.
  await p.keyboard.press('Escape')
  await expect(boite, 'seconde demande').toBeVisible({ timeout: 15_000 })
  await boite.getByRole('button', { name: 'Quitter', exact: true }).click()
  await expect(panneau, 'quitter : panneau fermé').toBeHidden({ timeout: 15_000 })
  expect(ecritures.filter((x) => /\/(noter|notes?|note)\//.test(x)), 'aucune note envoyée').toEqual([])
  expect(await notesEnBase(), 'base : aucune note ajoutée').toEqual(nAvant)
  await p.reload()
  await ouvrir()
  await expect(note, 'rechargé, panneau rouvert : champ note vide').toHaveValue('')
  await auRepos(p)
})

// ══════════════════════════════ Stock — AERR183 (BCF brouillon) ══════════════════════════════

etape('S2-AERR183-bcf-fermer', ['AERR183'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const ref = `BCF-AERR183-${m}`
  const ids = await py(`from decimal import Decimal
from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`AERR Fournisseur ${m}`)})
prods = [Produit.objects.create(company_id=${SOC}, nom='AERR article %s ${m}' % n, prix_vente=100, prix_achat=60) for n in ('A', 'B')]
b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference=${J(ref)}, fournisseur=f, statut='brouillon', date_commande=timezone.localdate())
for pr, q in zip(prods, (2, 3)):
    LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=q, prix_achat_unitaire=Decimal('60'))
sortie(dict(f=f.pk, prods=[p.pk for p in prods], bcf=b.pk))`)
  apres.push(() => py(`from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur
for qs in (BonCommandeFournisseur.objects.filter(pk=${ids.bcf}), Produit.objects.filter(pk__in=${J(ids.prods)}),
           Fournisseur.objects.filter(pk=${ids.f})):
    try: qs.delete()
    except Exception as exc: print('nettoyage achats', exc)`))
  const di = await compteRole('aerr183di', 'Directeur')
  const { p, boite } = await ecran(page, suivi, testInfo, di.nom)
  const ecritures = compter(p, null, /\/api\/django\/[^?]*(bons-commande|commande-fournisseur)[^?]*(\?.*)?$/i)
  const noteChamp = p.locator('#bcf-note')
  const fiche = p.locator('[role="dialog"]').filter({ has: noteChamp })
  await scenarioFermer(p, boite, 'S2-AERR183', {
    ouvrir: async () => {
      await p.goto('/stock/bons-commande-fournisseur')
      await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(ref, { timeout: 60_000 })
      await p.getByRole('row').filter({ hasText: ref }).getByText(ref).click({ timeout: 60_000 })
      await expect(fiche, 'fiche du BCF brouillon ouverte').toBeVisible({ timeout: 30_000 })
    },
    fiche, champ: noteChamp, saisie: `Livraison quai 2 ${m}`, ecritures, affichageInitial: '',
    relireBase: () => py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.get(pk=${ids.bcf})
sortie([b.statut, b.note or '', [(l.produit_id, l.quantite) for l in b.lignes.order_by('id')]])`),
  })
})

// ══════════════════════════════ GED — AERR185 ══════════════════════════════

etape('S2-AERR185-ged-revoquer-retirer', ['AERR185'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const di = await compteRole('aerr185di', 'Directeur')
  const cible = await compteRole('aerr185ci', 'Commercial')
  const r = page.request
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab AERR185 ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos AERR185 ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Contrat AERR185 ${m}`, folder: dos.id } }), 'document')
  apres.push(() => py(`from apps.ged.models import Cabinet
try: Cabinet.objects.filter(pk=${cab.id}).delete()
except Exception as exc: print('nettoyage', exc)`))
  const ids = await py(`from apps.ged.models import AclGed, PartageGed
from apps.roles.models import Role
d = U.objects.get(username=${J(di.nom)})
role = Role.objects.get(company_id=${SOC}, nom='Directeur', est_systeme=True)
PartageGed.objects.filter(document_id=${doc.id}).delete()
AclGed.objects.filter(document_id=${doc.id}).delete()
pa = PartageGed.objects.create(company_id=${SOC}, document_id=${doc.id}, created_by=d)
# le rôle Directeur garde l'accès au document ; l'entrée « porteur » à retirer est celle du compte d'essai
AclGed.objects.create(company_id=${SOC}, document_id=${doc.id}, role=role, niveau='gestion', created_by=d)
ac = AclGed.objects.create(company_id=${SOC}, document_id=${doc.id}, utilisateur=U.objects.get(username=${J(cible.nom)}), niveau='lecture', created_by=d)
sortie(dict(partage=pa.pk, acl=ac.pk))`)
  const partageActif = () => py(`from apps.ged.models import PartageGed
sortie(PartageGed.objects.get(pk=${ids.partage}).actif)`)
  const aclExiste = () => py(`from apps.ged.models import AclGed
sortie(AclGed.objects.filter(pk=${ids.acl}).exists())`)
  const { p } = await ecran(page, suivi, testInfo, di.nom)
  const revocations = compter(p, 'POST', new RegExp(`/api/django/ged/partages/${ids.partage}/revoquer/$`))
  const retraits = compter(p, 'DELETE', new RegExp(`/api/django/ged/acls/${ids.acl}/$`))
  const boite = p.getByRole('alertdialog')

  // ── 1) /ged/retention › Partages : « Révoquer » ⇒ confirmation nommée ; Annuler ⇒ aucun appel ; Révoquer ⇒ un appel.
  const ligne = p.getByRole('row').filter({ hasText: doc.nom })
  const ouvrirPartages = async () => {
    await p.goto('/ged/retention')
    await p.getByRole('tab', { name: 'Partages' }).click({ timeout: 60_000 })
    await expect(ligne, 'partage listé').toBeVisible({ timeout: 60_000 })
    await expect(ligne, 'partage actif').toContainText('Actif')
  }
  const demanderRevocation = async () => {
    await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
    await p.getByRole('menuitem', { name: 'Révoquer' }).click()
    await expect(boite, 'confirmation nommée (le document du partage)').toContainText(`Révoquer le partage de « ${doc.nom} » ?`, { timeout: 15_000 })
    await expect(boite, 'effet nommé').toContainText('Le lien public cessera de fonctionner.')
  }
  await ouvrirPartages()
  await demanderRevocation()
  await cliche(p, 'S2-AERR185', 'revoquer')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1_000)
  expect(revocations.length, 'Annuler : aucun appel de révocation').toBe(0)
  expect(await partageActif(), 'base : partage toujours actif').toBe(true)
  await expect(ligne, 'écran : toujours « Actif »').toContainText('Actif')
  await p.reload()
  await ouvrirPartages()
  await expect(ligne, 'rechargé : partage toujours actif').toContainText('Actif')
  await demanderRevocation()
  await boite.getByRole('button', { name: 'Révoquer', exact: true }).click()
  await expect(toast(p, 'Partage révoqué.').first(), 'Confirmer : partage révoqué').toBeVisible({ timeout: 30_000 })
  expect(revocations.length, 'Confirmer : exactement un appel').toBe(1)
  expect(await partageActif(), 'base : partage révoqué').toBe(false)

  // ── 2) /ged › Détails du document › Accès : « Retirer ce droit » ⇒ confirmation nommée ; Annuler ⇒ aucun appel ; Retirer ⇒ un appel.
  const ouvrirDroits = async () => {
    await p.goto('/ged')
    const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
    await expect(p.getByRole('tree', { name: 'Dossiers' }).or(choix).first()).toBeVisible({ timeout: 60_000 })
    if (await choix.count()) {
      await choix.click()
      await p.getByRole('option', { name: cab.nom, exact: true }).click()
    }
    await p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
    await p.getByRole('button', { name: `Détails de ${doc.nom}` }).click({ timeout: 60_000 })
    await p.getByRole('tab', { name: /Accès/ }).click({ timeout: 30_000 })
    await expect(p.getByTestId('ged-acl-entries'), 'droits listés').toContainText(cible.nom, { timeout: 30_000 })
  }
  const entree = () => p.getByTestId('ged-acl-entries').locator('li').filter({ hasText: cible.nom })
  await ouvrirDroits()
  await entree().getByRole('button', { name: 'Retirer ce droit' }).click()
  await expect(boite, 'confirmation nommée (le porteur)').toContainText(`Retirer le droit de « ${cible.nom} » ?`, { timeout: 15_000 })
  await expect(boite, 'effet nommé').toContainText('Cette entrée de droits sera retirée du document.')
  await cliche(p, 'S2-AERR185', 'droit')
  await boite.getByRole('button', { name: 'Annuler', exact: true }).click()
  await expect(boite).toHaveCount(0)
  await p.waitForTimeout(1_000)
  expect(retraits.length, 'Annuler : aucun appel de retrait').toBe(0)
  expect(await aclExiste(), 'base : droit toujours présent').toBe(true)
  await expect(entree(), 'écran : droit toujours listé').toBeVisible()
  await p.reload()
  await ouvrirDroits()
  await expect(entree(), 'rechargé : droit toujours listé').toBeVisible()
  await entree().getByRole('button', { name: 'Retirer ce droit' }).click()
  await expect(boite).toContainText(`Retirer le droit de « ${cible.nom} » ?`, { timeout: 15_000 })
  await boite.getByRole('button', { name: 'Retirer', exact: true }).click()
  await expect(entree(), 'Confirmer : droit retiré de la liste').toHaveCount(0, { timeout: 30_000 })
  expect(retraits.length, 'Confirmer : exactement un appel').toBe(1)
  expect(await aclExiste(), 'base : droit supprimé').toBe(false)
})

// ══════════════════════════════ CRM — AERR186 ══════════════════════════════

etape('S2-AERR186-appel-saisie-gardee', ['AERR186'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteRole('aerr186co', 'Commercial')
  const [a, b] = await py(`from apps.crm.models import Lead
sortie([Lead.objects.create(company_id=${SOC}, owner_id=${co.id}, nom=n, prenom='Essai', telephone=t, stage='NEW').pk
        for n, t in ((${J(`AERR186A ${m}`)}, ${J(telephoneMobileUnique())}), (${J(`AERR186B ${m}`)}, ${J(telephoneMobileUnique())}))])`)
  apres.push(() => py(`from apps.crm.models import Lead
for pk in ${J([a, b])}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`))
  const appelsEnBase = (pk) => py(`from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(lead_id=${pk}, kind='appel').count())`)
  const { p } = await ecran(page, suivi, testInfo, co.nom)
  const journauxA = compter(p, 'POST', new RegExp(`/api/django/crm/leads/${a}/log-interaction/$`))
  const rail = p.getByTestId('lw-context-rail')
  const pop = p.getByRole('dialog').filter({ hasText: 'Journaliser un appel' })
  const note = pop.getByPlaceholder('Note (facultative)…')
  const actifs = pop.locator('.clp-outcome-btn-active')
  const ouvrir = async (lead) => {
    await p.goto(`/crm/leads/${lead}`)
    await expect(rail).toBeVisible({ timeout: 60_000 })
    await rouvrir()
  }
  const rouvrir = async () => {
    await rail.getByRole('button', { name: 'Journaliser', exact: true }).click()
    await expect(pop, 'fenêtre « Journaliser un appel » ouverte').toBeVisible({ timeout: 30_000 })
  }
  const texte = `rappeler le soir ${m}`
  await ouvrir(a)
  await expect(actifs, 'fenêtre neuve : aucune issue choisie').toHaveCount(0)
  await pop.getByRole('group', { name: "Résultat de l'appel" }).getByRole('button', { name: 'À rappeler' }).click()
  await expect(actifs, 'issue « À rappeler » choisie').toHaveCount(1)
  await note.fill(texte)
  // Fermeture accidentelle AVANT journalisation (Échap), puis réouverture sur le même lead : issue et note gardées.
  await p.keyboard.press('Escape')
  await expect(pop, 'fenêtre fermée').toBeHidden({ timeout: 15_000 })
  await rouvrir()
  await expect(note, 'A rouvert : note gardée').toHaveValue(texte)
  await expect(actifs, 'A rouvert : issue gardée').toHaveCount(1)
  await expect(actifs.first(), 'A rouvert : « À rappeler » reste active').toContainText('À rappeler')
  await cliche(p, 'S2-AERR186', 'saisie-gardee')
  expect(journauxA.length, 'rien n\'est journalisé par la fermeture').toBe(0)
  expect(await appelsEnBase(a), 'base : aucun appel journalisé').toBe(0)
  // Autre lead : fenêtre vide (la saisie de A ne fuit pas sur B).
  await ouvrir(b)
  await expect(note, 'lead B : note vide').toHaveValue('')
  await expect(actifs, 'lead B : aucune issue').toHaveCount(0)
  await p.keyboard.press('Escape')
  await expect(pop).toBeHidden({ timeout: 15_000 })
  // Journalisation sur A, fermeture, réouverture : fenêtre vide, aucun second appel (garde d'AERR156).
  await ouvrir(a)
  await pop.getByRole('group', { name: "Résultat de l'appel" }).getByRole('button', { name: 'Non joint' }).click()
  await pop.getByRole('button', { name: 'Demain', exact: true }).click()
  await note.fill(`appel journalisé ${m}`)
  await pop.getByRole('button', { name: 'Enregistrer', exact: true }).click()
  await expect(toast(p, 'Appel journalisé').first(), 'appel journalisé').toBeVisible({ timeout: 30_000 })
  await expect.poll(() => appelsEnBase(a), { message: 'base : un appel sur A' }).toBe(1)
  if (await pop.isVisible()) await p.keyboard.press('Escape')
  await expect(pop, 'fenêtre fermée après journalisation').toBeHidden({ timeout: 15_000 })
  await rouvrir()
  await expect(note, 'après journalisation : note vide').toHaveValue('')
  await expect(actifs, 'après journalisation : aucune issue').toHaveCount(0)
  await cliche(p, 'S2-AERR186', 'apres-journalisation')
  expect(journauxA.length, 'un seul appel journalisé côté réseau').toBe(1)
  expect(await appelsEnBase(a), 'base : toujours UN appel (garde d\'AERR156)').toBe(1)
  // Persistance : rechargé, le journal du lead A ne porte qu'un appel.
  await p.reload()
  await expect(rail).toBeVisible({ timeout: 60_000 })
  const histo = await p.request.get(`${API}/crm/leads/${a}/historique/`, T)
  expect(histo.status()).toBe(200)
  expect((J(await histo.json()).match(/"kind":\s*"appel"/g) || []).length, 'historique relu : un seul appel').toBe(1)
  await auRepos(p)
})
