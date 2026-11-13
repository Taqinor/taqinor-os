// Complément ÉCRAN des preuves en direct AMSG (audit PF8 « messages envoyés aux clients », dossier
// docs/audits/2026-11-11-parcours-PF8.md). La relecture adverse des lots amsg/amsg2 a refusé des tâches dont la
// clause « Preuve en direct » nomme un ÉCRAN jamais affirmé, ou dont un volet du « fini quand » manquait :
// chaque étape ci-dessous joue le geste À L'ÉCRAN sous le rôle du registre (connexion UI), AFFIRME ce que la
// clause nomme (aperçu, refus, titre de fiche, statut de ligne), recharge puis réaffirme. AUCUN envoi réel : e-mail
// au backend du réglage (console), WhatsApp jamais vers un fournisseur (`window.open` intercepté : on lit le lien
// wa.me que l'écran ouvrirait). AMSG29 (0 écran) : le volet WhatsApp du « fini quand » joué par le vrai beat dans le
// shell Django, transaction ANNULÉE. AMSG6 ÉCARTÉE : l'assistant exige un fournisseur LLM réel (service FastAPI et
// clé absents de la pile) — aucune carte de résultat ne peut naître sans lui. AMSG56 : DÉFAUT PRODUIT (aucun écran
// ERP n'affiche une livraison ni ses tâches) — étape non écrite, voir le rapport.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG4', 'AMSG5', 'AMSG11', 'AMSG12', 'AMSG15', 'AMSG29'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  window.open = (u) => { window.__waOuvert = String(u); return null }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const contextesUi = []
const apres = []
test.afterEach(async () => {
  for (const c of contextesUi.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const courriel = (m) => `amsg-${m}-${Math.floor(Math.random() * 1e6)}@example.invalid`
const SOC = `U.objects.get(username='demo_admin').company_id`

/** Sonde HÔTE (`docs/audits/sondes/AMSG/<c>.py`) ; {ok, res|err}. Bouchons périmés ⇒ nommée, jamais comptée. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AMSG', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}
function sondeOuNommee(constat) {
  const s = sondeHote(constat)
  if (!s.ok) console.log(`[AMSG] sonde ${constat} non exécutable (bouchons périmés, non comptée) : ${s.err}`)
  else expect(s.res.repro, `sonde ${constat} : ${J(s.res.observe)}`).toBe(false)
}

const compteRole = (nom, nomRole, prenom = 'Essai') => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), ...(u.viewport ? { viewport: u.viewport } : {}),
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
const montrer = async (page) => { await page.close().catch(() => undefined) }
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(marque()), ...extra },
}), `lead ${nom}`)
const poserLead = (id, champs) => py(`from apps.crm.models import Lead
M = getattr(Lead, 'all_objects', Lead.objects)
sortie(M.filter(pk=${Number(id)}).update(**json.loads(${J(J(champs))})))`)
let PRODUIT = null
async function devisBrouillon(request, leadId) {
  PRODUIT ??= await lireJson(await request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Onduleur AMSG3 ${marque()}`, prix_vente: '10000.00', prix_achat: '4321.09' },
  }), 'produit')
  return lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: leadId,
      lignes: [{ produit: PRODUIT.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
}
const envoyer = async (request, id) => lireJson(await request.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi du devis')
const devisRelu = async (request, id) => lireJson(await request.get(`${API}/ventes/devis/${id}/`, T), 'devis relu')
async function nettoyer(request, { leads = [], devis = [] }) {
  for (const id of devis) await request.delete(`${API}/ventes/devis/${id}/`, T).catch(() => null)
  for (const id of leads) await request.delete(`${API}/crm/leads/${id}/`, T).catch(() => null)
}
async function avecGabarit(cle, champs, corps) {
  const avant = await py(`from apps.parametres.models_messages import MessageTemplate as M
co = U.objects.get(username='demo_admin').company_id
t = M.objects.filter(company_id=co, cle=${J(cle)}).first()
avant = None if t is None else dict(corps_fr=t.corps_fr, corps_darija=t.corps_darija)
t = t or M(company_id=co, cle=${J(cle)})
for k, v in json.loads(${J(J(champs))}).items(): setattr(t, k, v)
t.save()
sortie(avant)`)
  try {
    return await corps()
  } finally {
    await py(`from apps.parametres.models_messages import MessageTemplate as M
co = U.objects.get(username='demo_admin').company_id
avant = json.loads(${J(J(avant))})
t = M.objects.filter(company_id=co, cle=${J(cle)}).first()
if avant is None:
    t and t.delete()
else:
    for k, v in avant.items(): setattr(t, k, v)
    t.save()
sortie(1)`)
  }
}

/** Fiche du lead → section « Visite technique » → « Autre rendez-vous (RDV général) » ouvert. */
async function ouvrirRdv(p, leadId) {
  await p.goto(`/crm/leads/${leadId}`)
  await p.locator('nav[aria-label="Sections du lead"]').getByRole('button', { name: 'Visite technique' }).click({ timeout: 60_000 })
  const resume = p.getByText('Autre rendez-vous (RDV général)')
  await resume.click()
  await expect(p.getByText('Visites planifiées').first(), 'liste des rendez-vous à venir').toBeVisible({ timeout: 30_000 })
}
/** Fiche identité anonymisée (titre, plus de nom d'origine, aucun lien tél/e-mail). */
async function ficheAnonyme(p, pk, nomOrigine) {
  await p.goto(`/crm/leads/${pk}`)
  await expect(p.getByRole('heading', { level: 1, name: 'Lead — Anonymisé' }), `lead #${pk} : « Lead — Anonymisé »`).toBeVisible({ timeout: 60_000 })
  await expect(p.locator('body'), `lead #${pk} : plus « ${nomOrigine} »`).not.toContainText(nomOrigine)
  await expect(p.locator('a[href^="tel:"], a[href^="mailto:"]'), `lead #${pk} : ni téléphone ni e-mail`).toHaveCount(0)
}

// ═══ PF8.2 — AMSG4 : Clients → fiche → « Anonymiser » (admin), puis la fiche du lead lié : identité effacée ═══
etape('PF8.2.anonymiser_client_ecran', ['AMSG4'], async ({ page }) => {
  sondeOuNommee('C-AMSG-004')
  const m = marque()
  const nomLead = `AMSG4 Benali ${m}`
  const nomClient = `AMSG4 Client ${m}`
  const lie = await nouveauLead(page.request, nomLead, { whatsapp: telephoneMobileUnique() })
  const autre = await nouveauLead(page.request, `AMSG4 Temoin ${m}`)
  const c = await py(`from apps.crm.models import Client, Lead
co = ${SOC}
c1 = Client.objects.create(company_id=co, nom=${J(nomClient)}, email='amsg4-client-${m}@example.invalid', telephone='${telephoneMobileUnique()}')
c2 = Client.objects.create(company_id=co, nom='AMSG4 Autre ${m}')
Lead.objects.filter(pk=${lie.id}).update(client=c1)
Lead.objects.filter(pk=${autre.id}).update(client=c2)
sortie(dict(c1=c1.id, c2=c2.id))`)
  try {
    // Administrateur (demo_admin, rôle livré « Administrateur ») : Clients → fiche du client → « Anonymiser (RGPD) ».
    await page.goto('/crm')
    await page.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nomClient)
    await page.getByRole('row').filter({ hasText: nomClient }).first().click({ timeout: 60_000 })
    await expect(page.getByText(`Fiche client — ${nomClient}`)).toBeVisible({ timeout: 30_000 })
    await page.getByRole('button', { name: 'Anonymiser (RGPD)' }).click()
    const dlg = page.getByRole('alertdialog')
    await expect(dlg).toContainText('Anonymiser ce client ?')
    await dlg.getByRole('button', { name: 'Anonymiser définitivement' }).click()
    await expect(toast(page, 'Client anonymisé (données personnelles effacées)')).toBeVisible({ timeout: 30_000 })
    // Puis la fiche du lead lié : identité effacée ; le lead d'un autre client intact.
    await ficheAnonyme(page, lie.id, nomLead)
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: 'Lead — Anonymisé' }), 'après rechargement : toujours anonymisé').toBeVisible({ timeout: 60_000 })
    await page.goto(`/crm/leads/${autre.id}`)
    await expect(page.getByRole('heading', { level: 1, name: `Lead — AMSG4 Temoin ${m}` }), 'témoin : le lead d\'un autre client est intact').toBeVisible({ timeout: 60_000 })
    const base = await py(`from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
l = Lead.all_objects.get(pk=${lie.id})
sortie(dict(lie=[l.nom, l.email, l.telephone, l.whatsapp], a_faire=RelanceEtape.objects.filter(lead_id=${lie.id}, statut='a_faire').count()))`)
    expect(base.lie, 'en base : nom anonymisé, sans e-mail, téléphone ni WhatsApp').toEqual(['Anonymisé', null, null, null])
    expect(base.a_faire, 'en base : aucune touche à faire (cadence arrêtée)').toBe(0)
    await ficheAnonyme(page, lie.id, nomLead)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await nettoyer(page.request, { leads: [lie.id, autre.id] })
    })
  }
})

// ═══ PF8.2 — AMSG5 : Paramètres › Confidentialité, demande d'effacement par e-mail, puis la fiche sœur ═══
etape('PF8.2.effacement_fiche_soeur_ecran', ['AMSG5'], async ({ page }) => {
  sondeOuNommee('C-AMSG-005')
  const m = marque()
  const email = `amsg5-${m}@example.invalid`
  const chiffres = telephoneMobileUnique().slice(-9)
  const tel = `+212${chiffres}`
  const autrement = `0${chiffres.slice(0, 1)} ${chiffres.slice(1, 3)} ${chiffres.slice(3, 5)} ${chiffres.slice(5, 7)} ${chiffres.slice(7)}`
  const f = await py(`from authentication.models import Company
from apps.crm.models import Client, Lead
co = ${SOC}
cl = Client.objects.create(company_id=co, nom='AMSG5 Client ${m}')
site = Lead.objects.create(company_id=co, nom='AMSG5 Site ${m}', email=${J(email)}, telephone=${J(tel)}, client=cl)
meta = Lead.objects.create(company_id=co, nom='AMSG5 Meta ${m}', telephone=${J(autrement)})
autre_co = Company.objects.create(nom='AMSG5 Autre ${m}', slug='amsg5e-autre-${m}')
ailleurs = Lead.objects.create(company=autre_co, nom='AMSG5 Ailleurs ${m}', telephone=${J(tel)})
sortie(dict(client=cl.id, site=site.id, meta=meta.id, ailleurs=ailleurs.id, autre_co=autre_co.id, meme_cle=site.phone_normalise == meta.phone_normalise))`)
  try {
    expect(f.meme_cle, 'précondition : la fiche Meta porte le même téléphone écrit autrement').toBe(true)
    // Administrateur (demo_admin, `dsr_traiter`) : Paramètres › Confidentialité → nouvelle demande « Effacement ».
    await page.goto('/parametres?onglet=confidentialite')
    const carte = page.getByText('Demandes de personnes concernées').first()
      .locator('xpath=ancestor::*[.//input[@placeholder="Email ou téléphone de la personne concernée"]][1]')
    await expect(carte, 'bloc « Demandes de personnes concernées »').toBeVisible({ timeout: 60_000 })
    await carte.getByPlaceholder('Email ou téléphone de la personne concernée').fill(email)
    await carte.getByRole('combobox').click()
    await page.getByRole('option', { name: 'Effacement' }).click()
    await carte.getByRole('button', { name: 'Soumettre' }).click()
    const ligne = page.getByTestId('dsr-row').filter({ hasText: email })
    await expect(ligne, 'demande reçue').toContainText('Reçue', { timeout: 30_000 })
    await ligne.getByRole('button', { name: 'Traiter' }).click()
    const dlg = page.getByRole('alertdialog')
    await expect(dlg).toContainText(`Effacer les données de ${email} ?`)
    await dlg.getByRole('button', { name: 'Effacer' }).click()
    await expect(ligne, 'demande traitée').toContainText('Traitée', { timeout: 60_000 })
    // Persistance de l'écran : recharger, la demande reste « Traitée ».
    await page.reload()
    await expect(page.getByTestId('dsr-row').filter({ hasText: email }), 'après rechargement : « Traitée »').toContainText('Traitée', { timeout: 60_000 })
    // Lecture de la fiche sœur (même téléphone, sans e-mail) : identité effacée ; la fiche site aussi.
    await ficheAnonyme(page, f.meta, `AMSG5 Meta ${m}`)
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: 'Lead — Anonymisé' }), 'fiche sœur après rechargement').toBeVisible({ timeout: 60_000 })
    await ficheAnonyme(page, f.site, `AMSG5 Site ${m}`)
    const base = await py(`from apps.crm.models import Client, Lead
M = Lead.all_objects
sortie(dict(meta=[M.get(pk=${f.meta}).nom, M.get(pk=${f.meta}).telephone], ailleurs=[M.get(pk=${f.ailleurs}).nom, M.get(pk=${f.ailleurs}).telephone],
  client=Client.objects.get(pk=${f.client}).is_anonymized))`)
    expect(base.meta, 'en base : fiche sœur anonymisée, sans contact').toEqual(['Anonymisé', null])
    expect(base.client, 'en base : client lié anonymisé').toBe(true)
    expect(base.ailleurs, 'en base : fiche de l\'autre société intacte').toEqual([`AMSG5 Ailleurs ${m}`, tel])
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await py(`from authentication.models import Company
from core.models import DataSubjectRequest
DataSubjectRequest.objects.filter(subject_identifier=${J(email)}).delete()
Company.objects.filter(pk=${f.autre_co}).delete()
sortie(1)`).catch(() => undefined)
    })
  }
})

// ═══ PF8.1 — AMSG11 : fiche d'un lead darija → rendez-vous planifié → « Confirmer par WhatsApp » : aperçu en darija ═══
etape('PF8.1.confirmation_rdv_darija_ecran', ['AMSG11'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `amsg11cr_${m}`
  const cr = await compteRole(nom, 'Commercial responsable', 'Yassine')
  const darija = await nouveauLead(page.request, `AMSG11 Darija ${m}`)
  const fr = await nouveauLead(page.request, `AMSG11 Francais ${m}`)
  try {
    await poserLead(darija.id, { owner_id: cr, langue_preferee: 'darija' })
    await poserLead(fr.id, { owner_id: cr, langue_preferee: 'fr' })
    const rdv = await py(`from apps.crm.models import Appointment, Lead
import zoneinfo
from apps.crm.cadence_messages import _date_visite_francais
res = {}
for k, i in (('darija', ${darija.id}), ('fr', ${fr.id})):
    l = Lead.objects.get(pk=i)
    a = Appointment.objects.create(company_id=l.company_id, lead=l, scheduled_at=timezone.now() + datetime.timedelta(days=2))
    res[k] = dict(id=a.id, jour=_date_visite_francais(a.scheduled_at.astimezone(zoneinfo.ZoneInfo('Africa/Casablanca')).date()))
sortie(res)`)
    const p = await ecran(page, suivi, testInfo, nom)
    const apercu = p.locator('.lw-booker-wa-preview-text')
    const confirmer = async (leadId) => {
      await ouvrirRdv(p, leadId)
      await p.getByRole('button', { name: 'Confirmer par WhatsApp' }).first().click()
      await expect(p.getByText('Aperçu du message WhatsApp').first(), 'aperçu affiché').toBeVisible({ timeout: 30_000 })
      return apercu
    }
    const verifierDarija = async (quand) => {
      const a = await confirmer(darija.id)
      await expect(a, `${quand} : corps darija du gabarit visite_confirmation`).toContainText('الزيارة التقنية')
      await expect(a, `${quand} : date du rendez-vous`).toContainText(rdv.darija.jour)
      await expect(a, `${quand} : {conseiller} = responsable du lead`).toContainText('Yassine')
      await expect(a, `${quand} : plus la chaîne française codée`).not.toContainText('je confirme notre rendez-vous')
    }
    await verifierDarija('aperçu')
    // L'aperçu est ce qui part : « Ouvrir WhatsApp » ouvre wa.me avec ce même texte.
    const texte = await apercu.innerText()
    await p.getByRole('button', { name: 'Ouvrir WhatsApp' }).click()
    await expect.poll(() => p.evaluate(() => window.__waOuvert || ''), { timeout: 30_000 }).toMatch(/^https:\/\/wa\.me\//)
    const ouvert = await p.evaluate(() => window.__waOuvert)
    expect(decodeURIComponent(ouvert.split('text=')[1] || '').trim(), 'wa.me porte le texte de l\'aperçu').toBe(texte.trim())
    // Persistance : recharger, l'aperçu est le même.
    await p.reload()
    await verifierDarija('après rechargement')
    // Lead français : le texte personnalisé par la société est celui de l'aperçu.
    await avecGabarit('visite_confirmation', { corps_fr: `Texte maison AMSG11 ${m} : visite {date_visite}.` }, async () => {
      const a = await confirmer(fr.id)
      await expect(a, 'texte personnalisé par la société').toContainText(`Texte maison AMSG11 ${m} : visite `)
      await expect(a).toContainText(rdv.fr.jour)
    })
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await nettoyer(page.request, { leads: [darija.id, fr.id] })
    })
  }
})

// ═══ PF8.2 — AMSG15 : rendez-vous marqué absent → « Confirmer par WhatsApp » : message de refus ═══
etape('PF8.2.confirmation_rdv_absent_ecran', ['AMSG15'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `amsg15cr_${m}`
  const cr = await compteRole(nom, 'Commercial responsable')
  const lead = await nouveauLead(page.request, `AMSG15 ${m}`)
  try {
    await poserLead(lead.id, { owner_id: cr })
    const rdv = await py(`from apps.crm.models import Appointment, Lead
l = Lead.objects.get(pk=${lead.id}); n = timezone.now(); D = datetime.timedelta
cree = lambda statut, delta: Appointment.objects.create(company_id=l.company_id, lead=l, statut=statut, scheduled_at=n + delta).id
sortie(dict(no_show=cree('no_show', D(days=2)), annule=cree('annule', D(days=3)), effectue=cree('effectue', D(days=4))))`)
    const p = await ecran(page, suivi, testInfo, nom)
    suivi.attendre(/\/api\/django\/crm\/appointments\/\d+\/confirmer-whatsapp\/$/, 409)
    const MSG = 'Rendez-vous annulé, effectué, manqué ou passé : rien à confirmer.'
    const refus = async (quand) => {
      await ouvrirRdv(p, lead.id)
      const boutons = p.getByRole('button', { name: 'Confirmer par WhatsApp' })
      // Annulé et effectué : pas de ligne (bouton absent) ; le rendez-vous « absent » reste listé.
      await expect(boutons, `${quand} : seul le rendez-vous absent offre « Confirmer par WhatsApp »`).toHaveCount(1)
      await boutons.click()
      await expect(toast(p, MSG), `${quand} : message de refus affiché`).toBeVisible({ timeout: 30_000 })
      await expect(p.locator('.lw-booker-wa-preview-text'), `${quand} : aucun aperçu`).toHaveCount(0)
    }
    await refus('premier essai')
    await p.reload()
    await refus('après rechargement')
    // API seulement pour annulé et effectué (bouton absent à l'écran) : 409 nommé, aucun wa_url.
    for (const cas of ['annule', 'effectue']) {
      const r = await p.request.post(`${API}/crm/appointments/${rdv[cas]}/confirmer-whatsapp/`, T)
      const corps = await r.json().catch(() => ({}))
      expect([r.status(), corps.detail, corps.wa_url], `${cas} : 409 nommé sans wa_url`).toEqual([409, MSG, undefined])
    }
    const statuts = await py(`from apps.crm.models import Appointment
sortie(sorted(Appointment.objects.filter(lead_id=${lead.id}).values_list('statut', flat=True)))`)
    expect(statuts, 'rien n\'est écrit (statuts inchangés)').toEqual(['annule', 'effectue', 'no_show'])
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await nettoyer(page.request, { leads: [lead.id] })
    })
  }
})

// ═══ PF8.2 — AMSG12 : fiche → Suivi commercial → « Envoyer le résumé à un associé » (texte personnalisé) : rempli ═══
etape('PF8.2.resume_associe_ecran', ['AMSG12'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `amsg12cr_${m}`
  const cr = await compteRole(nom, 'Commercial responsable', 'Rachid')
  const nomLead = `Alaoui${m}`
  const lead = await nouveauLead(page.request, nomLead)
  try {
    await poserLead(lead.id, { owner_id: cr, civilite: 'M.', ville: '', contact_secondaire_nom: 'Hassan (associé)', contact_secondaire_telephone: '0661223344' })
    const d = await devisBrouillon(page.request, lead.id)
    await envoyer(page.request, d.id)
    const avant = await devisRelu(page.request, d.id)
    const p = await ecran(page, suivi, testInfo, nom)
    await avecGabarit('resume_associe', {
      corps_fr: 'Bonjour, à la demande de {civilite} {nom}, voici le résumé de la proposition {reference} : {lien}. Ville : {ville}. — {conseiller}',
    }, async () => {
      const partager = async (quand) => {
        await p.evaluate(() => { window.__waOuvert = '' })
        await p.goto(`/crm/leads/${lead.id}`)
        await p.locator('nav[aria-label="Sections du lead"]').getByRole('button', { name: 'Suivi commercial' }).click({ timeout: 60_000 })
        const bloc = p.getByTestId('resume-associe')
        await expect(bloc, `${quand} : bloc « résumé à un associé »`).toBeVisible({ timeout: 30_000 })
        await bloc.getByLabel('Le client a demandé ou accepté ce partage').check()
        await bloc.getByRole('button', { name: 'Envoyer le résumé à un associé' }).click()
        await expect.poll(() => p.evaluate(() => window.__waOuvert || ''), { timeout: 30_000 }).toMatch(/^https:\/\/wa\.me\/212661223344/)
        const msg = decodeURIComponent((await p.evaluate(() => window.__waOuvert)).split('text=')[1] || '')
        expect(msg, `${quand} : civilité et nom`).toContain(`à la demande de M. ${nomLead}`)
        expect(msg, `${quand} : référence du devis`).toContain(`proposition ${avant.reference} : `)
        expect(msg, `${quand} : lien de la proposition`).toContain('/proposition/')
        expect(msg, `${quand} : phrase « Ville : » omise`).not.toContain('Ville :')
        expect(msg, `${quand} : aucune accolade`).not.toMatch(/[{}]/)
        expect(msg, `${quand} : signé du conseiller`).toContain('Rachid')
        await expect(bloc.getByTestId('resume-associe-refus'), `${quand} : aucun refus affiché`).toHaveCount(0)
      }
      await partager('premier envoi')
      await p.reload()
      await partager('après rechargement')
    })
    const apres = await devisRelu(page.request, d.id)
    expect([apres.statut, apres.date_envoi], 'devis : statut et date d\'envoi inchangés').toEqual([avant.statut, avant.date_envoi])
    await montrer(page)
  } finally {
    // Nettoyage APRÈS la capture et la clôture des écrans (afterEach) : un écran encore ouvert relirait
    // des données retirées (404 tardifs hors de l'étape).
    apres.push(async () => {
    await nettoyer(page.request, { leads: [lead.id] })
    })
  }
})

// ═══ PF8.3 — AMSG29 (0 écran) : un niveau au canal WhatsApp remet son brouillon au responsable ═══
etape('PF8.3-AMSG29-whatsapp', ['AMSG29'], async () => {
  const s = sondeHote('C-AMSG-008')
  expect(s.ok, `sonde C-AMSG-008 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, 'sonde C-AMSG-008 : repro faux (volet e-mail)').toBe(false)
  const m = marque()
  // Le VRAI beat `relance_reminders`, backend du réglage (console), société d'essai, transaction ANNULÉE.
  const r = await py(`from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from authentication.models import Company
from apps.crm.models import Client
from apps.records.models import Activity
from apps.ventes.models import EmailLog, Facture, FollowupLevel, RelanceLog
from apps.ventes.scheduled import casablanca_today, relance_reminders
m = ${J(m)}
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG29W ' + m, slug='amsg29w-' + m)
    resp = U.objects.create_user(username='amsg29resp_' + m, password='x', role_legacy='responsable', company=co)
    FollowupLevel.objects.create(company=co, ordre=0, nom='Rappel WA', delai_jours=0, canal=FollowupLevel.Canal.WHATSAPP)
    today = casablanca_today()
    def fac(cl, suf):
        f = Facture.objects.create(company=co, reference='FAC-AMSG29W-' + m + suf, client=cl, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'), montant_ttc=Decimal('5000'), prochaine_relance=today)
        Facture.objects.filter(pk=f.pk).update(created_by=resp)
        return f
    f = fac(Client.objects.create(company=co, nom='Canal', prenom='AMSG29', email='amsg29w' + m + '@example.invalid', telephone='+212600000056', adresse='Casablanca'), 'A')
    g = fac(Client.objects.create(company=co, nom='SansTel', prenom='AMSG29', email='amsg29s' + m + '@example.invalid', telephone='', adresse='Casablanca'), 'B')
    res['backend'] = getattr(settings, 'EMAIL_BACKEND_REEL', settings.EMAIL_BACKEND)
    res['retour'] = relance_reminders()
    ct = ContentType.objects.get_for_model(Facture)
    res['taches'] = [[a.assigned_to_id == resp.pk, a.note, a.summary, a.done] for a in Activity.objects.filter(content_type=ct, object_id=f.pk)]
    res['logs'] = list(RelanceLog.objects.filter(facture=f).values_list('canal', 'niveau'))
    res['sans_tel'] = [RelanceLog.objects.filter(facture=g).count(), Activity.objects.filter(content_type=ct, object_id=g.pk).count()]
    res['emaillog'] = EmailLog.objects.filter(company=co).count()
    transaction.set_rollback(True)
res['rien_laisse'] = not Company.objects.filter(slug='amsg29w-' + m).exists()
sortie(res)`)
  expect(r.backend, 'backend réel = console (aucun e-mail ne part)').toBe('django.core.mail.backends.console.EmailBackend')
  expect(r.taches, 'une tâche (brouillon WhatsApp) sur la facture').toHaveLength(1)
  const [auResponsable, note, resume, faite] = r.taches[0]
  expect(auResponsable, 'brouillon remis AU RESPONSABLE (assigné)').toBe(true)
  expect(note, 'le brouillon porte le lien wa.me du client').toContain('https://wa.me/212600000056?text=')
  expect(resume, 'libellé de la tâche').toContain('Relance WhatsApp à envoyer')
  expect(faite, 'tâche à faire').toBe(false)
  expect(r.logs, 'PUIS la RelanceLog du niveau WhatsApp').toEqual([['whatsapp', 0]])
  expect(r.retour, 'le beat compte la relance remise').toBeGreaterThanOrEqual(1)
  expect(r.sans_tel, 'brouillon impossible (téléphone absent) : niveau gardé, aucune tâche').toEqual([0, 0])
  expect(r.emaillog, 'aucun EmailLog').toBe(0)
  expect(r.rien_laisse, 'transaction annulée').toBe(true)
})
