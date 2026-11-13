// AMSG — preuves en direct du parcours PF8 « messages envoyés aux clients » (dossier
// docs/audits/2026-11-11-parcours-PF8.md), au format de `_format.md`. AUCUN envoi réel : e-mail en
// backend console, WhatsApp jamais vers un fournisseur — chaque étape lit ce que l'ERP PRÉPARE (texte,
// lien wa.me, numéro), JOURNALISE ou REFUSE, par les vraies routes. Le shell Django (`_django.js`) ne
// pose que ce qu'aucun geste ne peut poser (drapeaux perdu/archivé, statut d'un rendez-vous passé,
// gabarit société, compte désactivé, passage du beat des rappels) et relit la base.
// Données propres à chaque étape (noms marqués) ; les réglages PARTAGÉS de la société démo (gabarits,
// responsable par défaut) sont rétablis en `finally`.
import { test, expect, request as pwRequest } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, connexionApi, assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG1', 'AMSG2', 'AMSG4', 'AMSG5', 'AMSG6', 'AMSG11', 'AMSG12', 'AMSG13', 'AMSG14', 'AMSG15', 'AMSG16', 'AMSG37'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const courriel = (m) => `amsg-${m}-${Math.floor(Math.random() * 1e6)}@example.invalid`

// ── société démo, rôles, comptes d'essai ────────────────────────────────────────────────────────
let DEMO = null
const demo = async () => {
  DEMO ??= await py(`from apps.roles.models import Role
a = U.objects.get(username='demo_admin')
co = a.company_id
sortie(dict(co=co, admin=a.id, commercial=Role.objects.get(company_id=co, nom='Commercial').pk,
            directeur=Role.objects.get(company_id=co, nom='Directeur').pk))`)
  return DEMO
}
const sessions = new Map()
/** Compte d'essai (rôle réel de la société démo, prénom fixé) + contexte API connecté. */
async function session(testInfo, nom, role, prenom) {
  const dej = sessions.get(nom)
  if (dej && Date.now() - dej.quand < 20 * 60_000) return dej
  const d = await demo()
  const id = await py(`u = compte(${J(nom)}, role=${d[role]}, societe=${d.co})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  const s = { ctx, id, nom, prenom, quand: Date.now() }
  sessions.set(nom, s)
  return s
}
test.afterAll(async () => { for (const s of sessions.values()) await s.ctx.dispose().catch(() => undefined) })
const commercial = (testInfo) => session(testInfo, 'amsg_commercial', 'commercial', 'Salma')
const directeur = (testInfo) => session(testInfo, 'amsg_directeur', 'directeur', 'Karim')

// ── sonde hôte du dossier, rejouée sur l'arbre (vrai code, bouchons, sans Django) ────────────────────
function sonde(constat) {
  const sortie = execFileSync(process.env.E2E_PYTHON || 'python', ['-X', 'utf8', `docs/audits/sondes/AMSG/${constat}.py`],
    { cwd: RACINE, encoding: 'utf8', timeout: 120_000 })
  return JSON.parse(sortie)
}

// ── données ─────────────────────────────────────────────────────────────────────────────────────
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(marque()), ...extra },
}), `lead ${nom}`)
/** Champs du lead posés en base (ce qu'aucun geste unitaire ne pose : perdu, archivé, responsable…). */
const poserLead = (id, champs) => py(`from apps.crm.models import Lead
M = getattr(Lead, 'all_objects', Lead.objects)
sortie(M.filter(pk=${Number(id)}).update(**json.loads(${J(J(champs))})))`)
let PRODUIT = null
async function devisBrouillon(request, leadId) {
  PRODUIT ??= await lireJson(await request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Onduleur AMSG ${marque()}`, prix_vente: '10000.00', prix_achat: '4321.09' },
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
/** Gabarit société posé le temps d'un corps, puis rétabli (ligne d'origine ou absence). */
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
/** Touche de cadence À FAIRE posée sur un lead (template_cle, devis éventuel). */
const touche = (leadId, cle, { devis = null, cadence = 'apres_devis', ordre = 5 } = {}) => py(`from apps.crm.models_cadence import RelanceEtape
from apps.crm.models import Lead
l = Lead.objects.get(pk=${Number(leadId)})
sortie(RelanceEtape.objects.create(company_id=l.company_id, lead=l, cadence=${J(cadence)}, ordre=${ordre}, due_date=timezone.localdate(),
    due_at=timezone.now(), canal='whatsapp', libelle='Message AMSG', template_cle=${J(cle)}, devis_id=${devis == null ? 'None' : Number(devis)}).id)`)
const messageTouche = async (request, id) => lireJson(await request.get(`${API}/crm/relance-etapes/${id}/message/`, T), `message de la touche ${id}`)

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.2 — AMSG1 : « Envoyer un questionnaire » refusé (409 nommé) pour un lead opposé, perdu, archivé
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2.questionnaire_fiche_close', ['AMSG1'], async ({ page, suivi, testInfo }) => {
  const s = sonde('C-AMSG-001')
  expect(s.repro, `sonde C-AMSG-001 rejouée : repro False (${J(s.observe?.fiches_closes_servies)})`).toBe(false)
  const com = await commercial(testInfo)
  const m = marque()
  const leads = {}
  for (const cas of ['oppose', 'perdu', 'archive', 'temoin']) leads[cas] = await nouveauLead(page.request, `AMSG1 ${cas} ${m}`)
  try {
    for (const l of Object.values(leads)) await poserLead(l.id, { owner_id: com.id })
    await poserLead(leads.oppose.id, { ne_plus_contacter: true })
    await poserLead(leads.perdu.id, { perdu: true })
    await poserLead(leads.archive.id, { is_archived: true })
    const attendu = { oppose: 'Message refusé : ne plus contacter.', perdu: 'Message refusé : perdu/archivé.', archive: 'Message refusé : perdu/archivé.' }
    for (const [cas, detail] of Object.entries(attendu)) {
      const r = await com.ctx.post(`${API}/crm/leads/${leads[cas].id}/questionnaire-lien/`, { ...T, data: {} })
      const corps = await r.json().catch(() => ({}))
      expect(r.status(), `${cas} : 409 (${J(corps)})`).toBe(409)
      expect(corps.detail, cas).toBe(detail)
      expect(corps.url, `${cas} : aucun lien`).toBeUndefined()
    }
    const t = await lireJson(await com.ctx.post(`${API}/crm/leads/${leads.temoin.id}/questionnaire-lien/`, { ...T, data: {} }), 'témoin')
    expect(t.url, 'témoin contactable : lien rendu comme avant').toBeTruthy()
    // Persistance : relire en base — 0 lien frappé, aucune note « Lien questionnaire … » pour les trois.
    const base = await py(`from apps.crm.models import QuestionnaireLien, LeadActivity
ids = ${J([leads.oppose.id, leads.perdu.id, leads.archive.id])}
sortie(dict(liens=QuestionnaireLien.objects.filter(lead_id__in=ids).count(),
            notes=LeadActivity.objects.filter(lead_id__in=ids, body__contains='Lien questionnaire').count(),
            temoin=QuestionnaireLien.objects.filter(lead_id=${leads.temoin.id}).count()))`)
    expect(base, 'en base : aucun lien ni note pour les fiches closes ; un lien pour le témoin').toEqual({ liens: 0, notes: 0, temoin: 1 })
    // Écran : fiche du lead opposé → « Plus d'actions » → « Envoyer un questionnaire » : refus, aucun bouton WhatsApp.
    suivi.attendre(/\/crm\/leads\/\d+\/questionnaire-lien\/?$/, 409)
    await page.goto(`/crm/leads/${leads.oppose.id}`)
    await page.getByRole('button', { name: "Plus d'actions", exact: true }).first().click()
    await page.getByRole('menuitem', { name: 'Envoyer un questionnaire' }).click()
    const dialogue = page.getByRole('dialog', { name: 'Envoyer un questionnaire' })
    await expect(dialogue).toContainText('Message refusé : ne plus contacter.', { timeout: 30_000 })
    await expect(dialogue.getByRole('button', { name: /WhatsApp/ })).toHaveCount(0)
    await expect(dialogue.getByRole('link', { name: /WhatsApp/ })).toHaveCount(0)
  } finally {
    await nettoyer(page.request, { leads: Object.values(leads).map((l) => l.id) })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.1 — AMSG2 : « Relances du jour » sans brouillon ni numéro pour un devis d'un lead opposé/perdu/archivé
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.1.relances_du_jour_fiche_close', ['AMSG2'], async ({ page, suivi, testInfo }) => {
  const s = sonde('C-AMSG-002')
  expect(s.repro, 'sonde C-AMSG-002 rejouée : repro False').toBe(false)
  const com = await commercial(testInfo)
  const m = marque()
  const leads = {}
  const devis = {}
  for (const cas of ['oppose', 'perdu', 'archive', 'temoin']) {
    leads[cas] = await nouveauLead(page.request, `AMSG2 ${cas} ${m}`, { whatsapp: telephoneMobileUnique() })
    devis[cas] = await devisBrouillon(page.request, leads[cas].id)
    await envoyer(page.request, devis[cas].id)
    devis[cas] = await devisRelu(page.request, devis[cas].id)
  }
  const ctxUi = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })
  try {
    // Le commercial responsable : ses leads, ses devis (portée ADEV64 : auteur ou responsable du lead).
    const ids = Object.values(devis).map((d) => d.id)
    for (const l of Object.values(leads)) await poserLead(l.id, { owner_id: com.id })
    await py(`from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors_cadence import marquer_declencheur
Devis.objects.filter(pk__in=${J(ids)}).update(created_by_id=${com.id})
for l in ShareLink.objects.filter(devis_id__in=${J(ids)}):
    marquer_declencheur(l, 'not_opened_24h'); l.save(update_fields=['engagement_triggers_fired'])
sortie(1)`)
    await poserLead(leads.oppose.id, { ne_plus_contacter: true })
    await poserLead(leads.perdu.id, { perdu: true })
    await poserLead(leads.archive.id, { is_archived: true })
    const b = await lireJson(await com.ctx.get(`${API}/ventes/devis/action-requise/`, T), 'Relances du jour')
    const file = b.buckets.engagement_relance.ids
    for (const [cas, d] of Object.entries(devis)) expect(file, `${cas} : reste dans engagement_relance`).toContain(d.id)
    for (const cas of ['oppose', 'perdu', 'archive']) {
      const id = devis[cas].id
      expect(b.wa_drafts[id] ?? b.wa_drafts[String(id)], `${cas} : aucun brouillon WhatsApp`).toBeUndefined()
      const ligne = b.devis[id] ?? b.devis[String(id)]
      expect(ligne, `${cas} : ligne servie`).toBeTruthy()
      expect([ligne.client_telephone, ligne.client_whatsapp], `${cas} : numéros null`).toEqual([null, null])
    }
    const lt = b.devis[devis.temoin.id] ?? b.devis[String(devis.temoin.id)]
    expect(b.wa_drafts[devis.temoin.id] ?? b.wa_drafts[String(devis.temoin.id)], 'témoin : brouillon gardé').toBeTruthy()
    expect(lt.client_telephone, 'témoin : téléphone gardé').toBeTruthy()
    expect(lt.client_whatsapp, 'témoin : WhatsApp gardé').toBeTruthy()
    // Écran du commercial : Ventes → « Relances du jour » : ni « Appeler » ni WhatsApp sur les trois lignes.
    const p = suivi.surveiller(await ctxUi.newPage())
    await p.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    await uiLoginJusquAuxApps(p, { username: com.nom, password: MDP_ESSAI })
    await p.goto('/ventes/devis/action-requise')
    const ligneEcran = (d) => p.locator('li').filter({ hasText: d.reference }).first()
    await expect(ligneEcran(devis.temoin)).toBeVisible({ timeout: 60_000 })
    await expect(ligneEcran(devis.temoin).getByTitle('Appeler')).toHaveCount(1)
    await expect(ligneEcran(devis.temoin).getByRole('link', { name: /^WhatsApp/ })).toHaveCount(1)
    for (const cas of ['oppose', 'perdu', 'archive']) {
      await expect(ligneEcran(devis[cas]), `${cas} : ligne affichée`).toBeVisible()
      await expect(ligneEcran(devis[cas]).getByTitle('Appeler'), `${cas} : pas d'appel`).toHaveCount(0)
      await expect(ligneEcran(devis[cas]).getByRole('link', { name: /^WhatsApp/ }), `${cas} : pas de WhatsApp`).toHaveCount(0)
    }
    // Persistance : recharger l'écran, relire.
    await p.reload()
    await expect(ligneEcran(devis.oppose)).toBeVisible({ timeout: 60_000 })
    await expect(ligneEcran(devis.oppose).getByRole('link', { name: /^WhatsApp/ })).toHaveCount(0)
  } finally {
    await ctxUi.close().catch(() => undefined)
    await nettoyer(page.request, { devis: Object.values(devis).map((d) => d.id), leads: Object.values(leads).map((l) => l.id) })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.2 — AMSG4 : « Anonymiser » une fiche client anonymise aussi ses leads liés
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2.anonymiser_client_leads_lies', ['AMSG4'], async ({ page }) => {
  const m = marque()
  const lie = await nouveauLead(page.request, `AMSG4 Benali ${m}`, { whatsapp: telephoneMobileUnique() })
  const autre = await nouveauLead(page.request, `AMSG4 Temoin ${m}`)
  const c = await py(`from apps.crm.models import Client, Lead
co = U.objects.get(username='demo_admin').company_id
c1 = Client.objects.create(company_id=co, nom='AMSG4 Client ${m}', email='amsg4-client-${m}@example.invalid')
c2 = Client.objects.create(company_id=co, nom='AMSG4 Autre ${m}')
Lead.objects.filter(pk=${lie.id}).update(client=c1)
Lead.objects.filter(pk=${autre.id}).update(client=c2)
sortie(dict(c1=c1.id, c2=c2.id))`)
  const d = await devisBrouillon(page.request, lie.id)
  await envoyer(page.request, d.id)
  const tch = await touche(lie.id, 'identite', { cadence: 'contact', ordre: 3 })
  const url = `${API}/crm/clients/${c.c1}/anonymize/`
  const r = await page.request.post(url, T)
  expect(r.status(), `anonymiser → ${await r.text()}`).toBe(200)
  // Persistance : relire le lead lié (identité vide, aucune touche à faire), le devis (aucun destinataire), le témoin.
  const base = await py(`from apps.crm.models import Lead, Client
from apps.crm.models_cadence import RelanceEtape
from apps.ventes.models import Devis
from apps.ventes.utils.whatsapp import devis_recipient_phone
M = getattr(Lead, 'all_objects', Lead.objects)
l = M.get(pk=${lie.id}); a = M.get(pk=${autre.id})
sortie(dict(lie=[l.nom, l.email, l.telephone, l.whatsapp], touche=RelanceEtape.objects.get(pk=${tch}).statut,
  a_faire=RelanceEtape.objects.filter(lead_id=${lie.id}, statut='a_faire').count(),
  dest=devis_recipient_phone(Devis.objects.select_related('client', 'lead').get(pk=${d.id})),
  client=Client.objects.get(pk=${c.c1}).is_anonymized, autre=[a.nom, bool(a.telephone)]))`)
  expect(base.lie, 'lead lié : nom anonymisé, sans e-mail, téléphone ni WhatsApp').toEqual(['Anonymisé', null, null, null])
  expect(base.touche, 'sa touche est arrêtée').toBe('annulee')
  expect(base.a_faire, 'aucune touche à faire').toBe(0)
  expect(base.dest, 'devis_recipient_phone du devis : chaîne vide').toBe('')
  expect(base.client, 'client anonymisé comme avant').toBe(true)
  expect(base.autre, 'le lead d\'un autre client est intact').toEqual([`AMSG4 Temoin ${m}`, true])
  const lu = await lireJson(await page.request.get(`${API}/crm/leads/${lie.id}/`, T), 'lead relu')
  expect([lu.nom, lu.telephone || null, lu.email || null]).toEqual(['Anonymisé', null, null])
  const bis = await page.request.post(url, T)
  expect(bis.status(), 'relancer l\'action ⇒ 409 « déjà anonymisé »').toBe(409)
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.2 — AMSG5 : la demande d'effacement par e-mail atteint la fiche sœur au seul téléphone (un rebond)
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2.effacement_fiche_soeur', ['AMSG5'], async ({ page }) => {
  const m = marque()
  const email = `amsg5-${m}@example.invalid`
  const chiffres = telephoneMobileUnique().slice(-9)           // 6XXXXXXXX
  const tel = `+212${chiffres}`
  const autrement = `0${chiffres.slice(0, 1)} ${chiffres.slice(1, 3)} ${chiffres.slice(3, 5)} ${chiffres.slice(5, 7)} ${chiffres.slice(7)}`
  const f = await py(`from authentication.models import Company
from apps.crm.models import Client, Lead
co = U.objects.get(username='demo_admin').company_id
cl = Client.objects.create(company_id=co, nom='AMSG5 Client ${m}')
site = Lead.objects.create(company_id=co, nom='AMSG5 Site ${m}', email=${J(email)}, telephone=${J(tel)}, client=cl)
meta = Lead.objects.create(company_id=co, nom='AMSG5 Meta ${m}', telephone=${J(autrement)})
autre_co = Company.objects.create(nom='AMSG5 Autre ${m}', slug='amsg5-autre-${m}')
ailleurs = Lead.objects.create(company=autre_co, nom='AMSG5 Ailleurs ${m}', telephone=${J(tel)})
sortie(dict(client=cl.id, site=site.id, meta=meta.id, ailleurs=ailleurs.id, autre_co=autre_co.id,
            meme_cle=site.phone_normalise == meta.phone_normalise))`)
  try {
    expect(f.meme_cle, 'précondition : la fiche Meta porte le même téléphone écrit autrement').toBe(true)
    const dsr = await lireJson(await page.request.post(`${API}/core/dsr-requests/`, { ...T, data: { subject_identifier: email, kind: 'effacement' } }), 'demande d\'effacement')
    await lireJson(await page.request.post(`${API}/core/dsr-requests/${dsr.id}/prendre-en-charge/`, T), 'prise en charge')
    const traitee = await lireJson(await page.request.post(`${API}/core/dsr-requests/${dsr.id}/traiter/`, T), 'traitement')
    expect(traitee.statut, 'demande traitée').toBe('traitee')
    // Persistance : relire la fiche Meta, la fiche site, le client lié, la fiche de l'autre société.
    const base = await py(`from apps.crm.models import Client, Lead
M = getattr(Lead, 'all_objects', Lead.objects)
f = lambda i: (lambda l: [l.nom, l.email, l.telephone, l.whatsapp])(M.get(pk=i))
sortie(dict(site=f(${f.site}), meta=f(${f.meta}), ailleurs=f(${f.ailleurs}), client=Client.objects.get(pk=${f.client}).is_anonymized))`)
    expect(base.site, 'fiche site anonymisée').toEqual(['Anonymisé', null, null, null])
    expect(base.meta, 'fiche Meta (même téléphone, sans e-mail) anonymisée par le rebond').toEqual(['Anonymisé', null, null, null])
    expect(base.client, 'client lié anonymisé').toBe(true)
    expect([base.ailleurs[0], base.ailleurs[2]], 'fiche de l\'autre société intacte').toEqual([`AMSG5 Ailleurs ${m}`, tel])
    const inconnu = await py(`from authentication.models import Company
from apps.crm import dsr_provider
co = Company.objects.get(pk=U.objects.get(username='demo_admin').company_id)
leads, clients = dsr_provider._matcher(co, 'inconnu-${m}@example.invalid')
sortie([leads.count(), clients.count()])`)
    expect(inconnu, 'un identifiant inconnu ne ramène personne').toEqual([0, 0])
  } finally {
    await py(`from authentication.models import Company
Company.objects.filter(pk=${f.autre_co}).delete()
sortie(1)`).catch(() => undefined)
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.1 — AMSG6 : l'action d'assistant « Préparer un envoi WhatsApp de devis » joue l'aperçu sans effet
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.1.assistant_apercu_whatsapp', ['AMSG6'], async ({ page, testInfo }) => {
  const s = sonde('C-AMSG-007')
  expect(s.repro, 'sonde C-AMSG-007 rejouée : repro False').toBe(false)
  const com = await commercial(testInfo)
  const m = marque()
  const lead = await nouveauLead(page.request, `AMSG6 ${m}`, { whatsapp: telephoneMobileUnique() })
  try {
    await poserLead(lead.id, { owner_id: com.id })
    const d = await devisBrouillon(page.request, lead.id)
    // L'endpoint exécuté est celui que le catalogue d'actions sert à l'assistant (FastAPI le lit, `run_catalogue_action`).
    const cat = await lireJson(await page.request.get(`${API}/agent/actions/`, T), 'catalogue des actions')
    const action = (cat.actions || []).find((a) => a.key === 'crm.lead.whatsapp_prepare')
    expect(action, `action crm.lead.whatsapp_prepare au catalogue (${(cat.actions || []).length} actions)`).toBeTruthy()
    expect(action.endpoint, 'l\'action appelle l\'aperçu sans effet').toBe('/api/django/crm/leads/{id}/whatsapp-devis-apercu/')
    const avant = await py(`from apps.crm.models import Lead, LeadActivity
from apps.crm.models_cadence import RelanceEtape
from apps.ventes.models import Devis
l = Lead.objects.get(pk=${lead.id}); dv = Devis.objects.get(pk=${d.id})
sortie(dict(stage=l.stage, statut=dv.statut, envoi=dv.date_envoi, apres=RelanceEtape.objects.filter(lead_id=${lead.id}, cadence='apres_devis').count(),
            notes=LeadActivity.objects.filter(lead_id=${lead.id}).count()))`)
    const r = await lireJson(await com.ctx.fetch(action.endpoint.replace('{id}', String(lead.id)), {
      ...T, method: action.method || 'POST', data: { devis_ids: [d.id], langue: 'fr' },
    }), 'action exécutée')
    expect(r.wa_url, 'wa_url').toMatch(/^https:\/\/wa\.me\//)
    expect(r.message, 'message').toBeTruthy()
    expect(Array.isArray(r.links) ? r.links.length : Object.keys(r.links || {}).length, 'links').toBeGreaterThan(0)
    // Persistance : relire devis et lead ⇒ inchangés.
    const apres = await py(`from apps.crm.models import Lead, LeadActivity
from apps.crm.models_cadence import RelanceEtape
from apps.ventes.models import Devis
l = Lead.objects.get(pk=${lead.id}); dv = Devis.objects.get(pk=${d.id})
sortie(dict(stage=l.stage, statut=dv.statut, envoi=dv.date_envoi, apres=RelanceEtape.objects.filter(lead_id=${lead.id}, cadence='apres_devis').count(),
            notes=LeadActivity.objects.filter(lead_id=${lead.id}).count()))`)
    expect(apres, 'devis brouillon sans date d\'envoi, lead à son étape, aucune touche après-devis, aucune note').toEqual(avant)
    expect(apres.statut).toBe('brouillon')
    expect(apres.envoi).toBeNull()
    expect(apres.apres).toBe(0)
    const relu = await devisRelu(page.request, d.id)
    expect(relu.statut, 'la liste lit toujours un brouillon').toBe('brouillon')
  } finally {
    await nettoyer(page.request, { leads: [lead.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.1 — AMSG11 : confirmation WhatsApp d'un RDV = gabarit société `visite_confirmation`, langue du lead
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.1.confirmation_rdv_gabarit_langue', ['AMSG11'], async ({ page, testInfo }) => {
  const com = await commercial(testInfo)
  const m = marque()
  const darija = await nouveauLead(page.request, `AMSG11 Darija ${m}`)
  const fr = await nouveauLead(page.request, `AMSG11 Francais ${m}`)
  try {
    await poserLead(darija.id, { owner_id: com.id, langue_preferee: 'darija' })
    await poserLead(fr.id, { owner_id: com.id, langue_preferee: 'fr' })
    const rdv = await py(`from apps.crm.models import Appointment, Lead
import zoneinfo
from apps.crm.cadence_messages import _date_visite_francais
res = {}
for k, i in (('darija', ${darija.id}), ('fr', ${fr.id})):
    l = Lead.objects.get(pk=i)
    a = Appointment.objects.create(company_id=l.company_id, lead=l, scheduled_at=timezone.now() + datetime.timedelta(days=2))
    res[k] = dict(id=a.id, jour=_date_visite_francais(a.scheduled_at.astimezone(zoneinfo.ZoneInfo('Africa/Casablanca')).date()))
sortie(res)`)
    const r = await lireJson(await com.ctx.post(`${API}/crm/appointments/${rdv.darija.id}/confirmer-whatsapp/`, T), 'confirmation darija')
    expect(r.message, 'corps darija du gabarit visite_confirmation').toContain('الزيارة التقنية')
    expect(r.message, 'date parlée du rendez-vous').toContain(rdv.darija.jour)
    expect(r.message, '{conseiller} = responsable du lead').toContain(com.prenom)
    expect(r.message, 'plus la chaîne française codée').not.toContain('je confirme notre rendez-vous')
    expect(decodeURIComponent(r.wa_url.split('text=')[1] || ''), 'wa_url porte le même texte').toBe(r.message)
    expect(r.ics_url, 'ics_url inchangée').toContain(`/crm/appointments/${rdv.darija.id}/ics/`)
    await avecGabarit('visite_confirmation', { corps_fr: `Texte maison AMSG11 ${m} : visite {date_visite}.` }, async () => {
      const r2 = await lireJson(await com.ctx.post(`${API}/crm/appointments/${rdv.fr.id}/confirmer-whatsapp/`, T), 'confirmation fr personnalisée')
      expect(r2.message, 'le texte personnalisé par la société est celui qui part').toMatch(new RegExp(`^Texte maison AMSG11 ${m} : visite `))
      expect(r2.message, 'avec la date du rendez-vous').toContain(rdv.fr.jour)
      expect(decodeURIComponent(r2.wa_url.split('text=')[1] || '')).toBe(r2.message)
    })
  } finally {
    await nettoyer(page.request, { leads: [darija.id, fr.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.2 — AMSG15 : confirmation d'un RDV annulé, effectué, manqué ou passé refusée (409 nommé)
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2.confirmation_rdv_hors_jeu', ['AMSG15'], async ({ page, testInfo }) => {
  const com = await commercial(testInfo)
  const lead = await nouveauLead(page.request, `AMSG15 ${marque()}`)
  try {
    await poserLead(lead.id, { owner_id: com.id })
    const rdv = await py(`from apps.crm.models import Appointment, Lead
l = Lead.objects.get(pk=${lead.id}); n = timezone.now(); D = datetime.timedelta
cree = lambda statut, delta: Appointment.objects.create(company_id=l.company_id, lead=l, statut=statut, scheduled_at=n + delta).id
sortie(dict(annule=cree('annule', D(days=2)), effectue=cree('effectue', D(days=2)), no_show=cree('no_show', D(days=2)),
            passe=cree('planifie', -D(hours=1)), a_venir=cree('planifie', D(days=2))))`)
    for (const cas of ['annule', 'effectue', 'no_show', 'passe']) {
      const r = await com.ctx.post(`${API}/crm/appointments/${rdv[cas]}/confirmer-whatsapp/`, T)
      const corps = await r.json().catch(() => ({}))
      expect(r.status(), `${cas} : 409 (${J(corps)})`).toBe(409)
      expect(corps.detail, cas).toBe('Rendez-vous annulé, effectué, manqué ou passé : rien à confirmer.')
      expect(corps.wa_url, `${cas} : aucun wa_url`).toBeUndefined()
    }
    const ok = await lireJson(await com.ctx.post(`${API}/crm/appointments/${rdv.a_venir}/confirmer-whatsapp/`, T), 'RDV planifié à venir')
    expect(ok.wa_url, 'planifié à J+2 : 200 comme avant').toMatch(/^https:\/\/wa\.me\//)
    const statuts = await py(`from apps.crm.models import Appointment
sortie(sorted(Appointment.objects.filter(lead_id=${lead.id}).values_list('statut', flat=True)))`)
    expect(statuts, 'persistance : rien n\'est écrit (statuts inchangés)').toEqual(['annule', 'effectue', 'no_show', 'planifie', 'planifie'])
  } finally {
    await nettoyer(page.request, { leads: [lead.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.2 — AMSG12 : résumé à l'associé rendu avec tout le contexte, aucune accolade brute
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2.resume_associe_contexte', ['AMSG12'], async ({ page, testInfo }) => {
  const com = await commercial(testInfo)
  const m = marque()
  const nom = `Alaoui${m}`
  const lead = await nouveauLead(page.request, nom)
  try {
    await poserLead(lead.id, { owner_id: com.id, civilite: 'M.', ville: '', contact_secondaire_nom: 'Hassan (associé)', contact_secondaire_telephone: '0661223344' })
    const d = await devisBrouillon(page.request, lead.id)
    await envoyer(page.request, d.id)
    const avant = await devisRelu(page.request, d.id)
    const notes = () => py(`from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(lead_id=${lead.id}).count())`)
    const n0 = await notes()
    await avecGabarit('resume_associe', {
      corps_fr: 'Bonjour, à la demande de {civilite} {nom}, voici le résumé de la proposition {reference} : {lien}. Ville : {ville}. — {conseiller}',
    }, async () => {
      const r = await lireJson(await com.ctx.post(`${API}/crm/leads/${lead.id}/resume-associe/`, {
        ...T, data: { devis_id: d.id, accord_client: true },
      }), 'résumé à l\'associé')
      expect(r.message, 'civilité et nom').toContain(`à la demande de M. ${nom}`)
      expect(r.message, 'référence du devis').toContain(`proposition ${avant.reference} : `)
      expect(r.message, 'lien de la proposition').toContain('/proposition/')
      expect(r.message, 'phrase « Ville : » omise (placeholder sans valeur)').not.toContain('Ville :')
      expect(r.message, 'aucune accolade').not.toMatch(/[{}]/)
      expect(r.wa_url).toMatch(/^https:\/\/wa\.me\/212661223344/)
    })
    expect(await notes(), 'une seule ligne d\'historique, comme avant').toBe(n0 + 1)
    const apres = await devisRelu(page.request, d.id)
    expect([apres.statut, apres.date_envoi], 'persistance : devis, statut et date d\'envoi inchangés').toEqual([avant.statut, avant.date_envoi])
  } finally {
    await nettoyer(page.request, { leads: [lead.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.1 — AMSG13 : `{lien}` d'une touche seulement pour un devis encore en jeu
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.1.lien_devis_hors_jeu', ['AMSG13'], async ({ page }) => {
  const m = marque()
  const lead = await nouveauLead(page.request, `AMSG13 ${m}`)
  const ids = {}
  try {
    for (const cas of ['expire', 'refuse', 'v1', 'v2']) {
      ids[cas] = (await devisBrouillon(page.request, lead.id)).id
      await envoyer(page.request, ids[cas])
    }
    await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${ids.expire}).update(statut='expire')
Devis.objects.filter(pk=${ids.refuse}).update(statut='refuse')
Devis.objects.filter(pk=${ids.v1}).update(is_active=False, superseded_by_id=${ids.v2})
sortie(1)`)
    const liens = () => py(`from apps.ventes.models import ShareLink
sortie({k: ShareLink.objects.filter(devis_id=v).count() for k, v in json.loads(${J(J(ids))}).items()})`)
    const avant = await liens()
    await avecGabarit('j9_validite', { corps_fr: `Bonjour. Votre proposition : {lien}. À bientôt AMSG13 ${m}.` }, async () => {
      for (const cas of ['expire', 'refuse', 'v1']) {
        const t = await touche(lead.id, 'j9_validite', { devis: ids[cas], ordre: 7 })
        const r = await messageTouche(page.request, t)
        expect(r.message, `${cas} : rendu du texte société`).toContain(`À bientôt AMSG13 ${m}.`)
        expect(r.message, `${cas} : phrase du lien omise`).not.toContain('Votre proposition')
        expect(r.message, `${cas} : aucune URL`).not.toMatch(/\/proposition\/|https?:\/\//)
      }
      const t2 = await touche(lead.id, 'j9_validite', { devis: ids.v2, ordre: 7 })
      const r2 = await messageTouche(page.request, t2)
      expect(r2.message, 'témoin en jeu : la phrase avec l\'URL comme avant').toContain('Votre proposition : ')
      expect(r2.message).toContain('/proposition/')
    })
    const apres = await liens()
    for (const cas of ['expire', 'refuse', 'v1']) expect(apres[cas], `${cas} : aucun nouveau lien de partage frappé`).toBe(avant[cas])
  } finally {
    await nettoyer(page.request, { leads: [lead.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.1 — AMSG14 : jamais la signature d'un responsable désactivé
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.1.signature_responsable_desactive', ['AMSG14'], async ({ page, testInfo }) => {
  const com = await commercial(testInfo)
  const dir = await directeur(testInfo)
  const d = await demo()
  const comptes = await py(`a = compte('amsg_parti', role=${d.commercial}, societe=${d.co}); a.first_name = 'Ancien'; a.is_active = False; a.save()
b = compte('amsg_defaut', role=${d.commercial}, societe=${d.co}); b.first_name = 'Nadia'; b.save()
sortie(dict(parti=a.id, defaut=b.id))`)
  const m = marque()
  const orphelin = await nouveauLead(page.request, `AMSG14 Parti ${m}`)
  const actif = await nouveauLead(page.request, `AMSG14 Actif ${m}`)
  const profil = await py(`from apps.parametres.models import CompanyProfile
p, _ = CompanyProfile.objects.get_or_create(company_id=${d.co})
sortie(p.responsable_defaut_leads_id)`)
  const poserDefaut = (id) => py(`from apps.parametres.models import CompanyProfile
p = CompanyProfile.objects.get(company_id=${d.co}); p.responsable_defaut_leads_id = ${id == null ? 'None' : Number(id)}; p.save(update_fields=['responsable_defaut_leads'])
sortie(1)`)
  try {
    await poserLead(orphelin.id, { owner_id: comptes.parti })
    await poserLead(actif.id, { owner_id: com.id })
    const t1 = await touche(orphelin.id, 'identite', { cadence: 'contact', ordre: 3 })
    const t2 = await touche(actif.id, 'identite', { cadence: 'contact', ordre: 3 })
    await poserDefaut(comptes.defaut)
    await avecGabarit('identite', { corps_fr: 'Je suis {conseiller}.' }, async () => {
      const r1 = await messageTouche(dir.ctx, t1)
      expect(r1.message, 'signature : le responsable par défaut actif, jamais le compte désactivé').toBe('Je suis Nadia.')
      await py(`U.objects.filter(pk=${comptes.defaut}).update(is_active=False); sortie(1)`)
      const r2 = await messageTouche(dir.ctx, t1)
      expect(r2.message, 'sans responsable par défaut actif : l\'utilisateur courant').toBe(`Je suis ${dir.prenom}.`)
      const r3 = await messageTouche(dir.ctx, t2)
      expect(r3.message, 'lead à responsable actif : inchangé').toBe(`Je suis ${com.prenom}.`)
    })
  } finally {
    await poserDefaut(profil)
    await py(`U.objects.filter(pk=${comptes.defaut}).update(is_active=True); sortie(1)`).catch(() => undefined)
    await nettoyer(page.request, { leads: [orphelin.id, actif.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.5 — AMSG16 : visite annulée ⇒ son rendez-vous d'agenda annulé, aucun « Rappel visite »
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.5.visite_annulee_rdv_annule', ['AMSG16'], async ({ page }) => {
  const m = marque()
  const l1 = await nouveauLead(page.request, `AMSG16 Date ${m}`)
  const l2 = await nouveauLead(page.request, `AMSG16 Arret ${m}`)
  const l3 = await nouveauLead(page.request, `AMSG16 Temoin ${m}`)
  try {
    const d = await demo()
    for (const l of [l1, l2, l3]) await poserLead(l.id, { owner_id: d.admin })
    // Créneaux du JOUR (heure locale Casablanca) dans la fenêtre du rappel.
    const creneaux = await py(`import zoneinfo
Z = zoneinfo.ZoneInfo('Africa/Casablanca'); n = timezone.now()
fin = datetime.datetime.combine(n.astimezone(Z).date(), datetime.time(23, 59), tzinfo=Z)
pas = max(min(datetime.timedelta(minutes=10), (fin - n) / 4), datetime.timedelta(minutes=2))
sortie([(n + pas * k).isoformat() for k in (1, 2, 3)])`)
    const reserver = async (lead, quand) => lireJson(await page.request.post(`${API}/crm/appointments/`, { ...T, data: { lead: lead.id, scheduled_at: quand } }), `rendez-vous ${lead.nom}`)
    const rdv1 = await reserver(l1, creneaux[0])
    const rdv2 = await reserver(l2, creneaux[1])
    const rdv3 = await reserver(l3, creneaux[2])
    const visite = await py(`from apps.visites.models import VisiteTerrain
from apps.crm.models import Appointment, Lead
v = VisiteTerrain.objects.filter(lead_id=${l1.id}).order_by('-id').first()
l = Lead.objects.get(pk=${l1.id})
autre = Appointment.objects.create(company_id=l.company_id, lead=l, scheduled_at=timezone.now() + datetime.timedelta(days=2)).id
sortie(dict(visite=v and v.id, date=v and v.date_prevue, autre=autre))`)
    expect(visite.visite, 'book_appointment a créé la visite du jour').toBeTruthy()
    const p = await lireJson(await page.request.patch(`${API}/visites/visites/${visite.visite}/`, { ...T, data: { date_prevue: null } }), 'visite : date vidée')
    expect(p.date_prevue ?? null).toBeNull()
    // Arrêt du suivi du second lead : la porte que le CRM appelle (`visites.services.annuler_rendez_vous`).
    const n = await py(`from apps.visites import services as vs
from apps.crm.models import Lead
sortie(vs.annuler_rendez_vous(Lead.objects.get(pk=${l2.id}), U.objects.get(username='demo_admin')))`)
    expect(n, 'arrêt du suivi : une visite annulée').toBeGreaterThanOrEqual(1)
    // Passage du beat des rappels, puis relecture (persistance).
    const res = await py(`from apps.crm.visites_rdv import send_due_appointment_reminders
from apps.crm.models import Appointment
from apps.notifications.models import Notification
envoyes = send_due_appointment_reminders()
r = {a.id: [a.statut, a.reminder_sent] for a in Appointment.objects.filter(pk__in=${J([rdv1.id, rdv2.id, rdv3.id, visite.autre])})}
sortie(dict(envoyes=envoyes, rdv=r, rappels={k: Notification.objects.filter(title='Rappel visite — ' + k).count() for k in ${J([l1.nom, l2.nom, l3.nom])}}))`)
    expect(res.rdv[rdv1.id], 'visite à date vidée : son rendez-vous annulé, aucun rappel').toEqual(['annule', false])
    expect(res.rdv[rdv2.id], 'arrêt du suivi : son rendez-vous annulé, aucun rappel').toEqual(['annule', false])
    expect(res.rdv[visite.autre], 'rendez-vous d\'un autre jour : reste planifié').toEqual(['planifie', false])
    expect(res.rappels[l1.nom], '0 « Rappel visite » pour la visite annulée').toBe(0)
    expect(res.rappels[l2.nom], '0 « Rappel visite » pour l\'arrêt du suivi').toBe(0)
    // Témoin : le beat a bien tourné — le rendez-vous non annulé reçoit son rappel.
    expect(res.rdv[rdv3.id], 'témoin : rappel parti').toEqual(['planifie', true])
    expect(res.rappels[l3.nom], 'témoin : une cloche « Rappel visite »').toBeGreaterThanOrEqual(1)
  } finally {
    await nettoyer(page.request, { leads: [l1.id, l2.id, l3.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// PF8.3 — AMSG37 : « Relancer ce devis » servi du gabarit `relance_devis`, la modale l'ouvre tel quel
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.3.relancer_devis_gabarit', ['AMSG37'], async ({ page }) => {
  const m = marque()
  const lead = await nouveauLead(page.request, `Amina${m}`)
  const d = await devisBrouillon(page.request, lead.id)
  try {
    await envoyer(page.request, d.id)
    const ref = (await devisRelu(page.request, d.id)).reference
    const apercu = async () => lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/whatsapp-preview/`, { ...T, data: {} }), 'aperçu WhatsApp')
    const a = await apercu()
    expect(a.message_relance, 'gabarit relance_devis rendu').toMatch(/^Bonjour .*Amina.*, petit rappel concernant votre devis /)
    for (const attendu of [ref, a.url]) expect(a.message_relance, `contient ${attendu}`).toContain(attendu)
    expect(a.message_relance, 'distinct du message d\'envoi').not.toBe(a.message)
    expect(a.devis_statut, 'aperçu : statut inchangé').toBe('envoye')
    await avecGabarit('relance_devis', { corps_fr: `Rappel AMSG37 {nom} : {reference}` }, async () => {
      const b = await apercu()
      expect(b.message_relance, 'société personnalisée : son texte').toMatch(new RegExp(`^Rappel AMSG37 .*Amina.* : ${ref}$`))
    })
    // Écran : liste des devis → « Relancer » → l'aperçu porte le texte servi, « Ouvrir WhatsApp » ouvre wa.me avec lui.
    await page.addInitScript(() => { window.open = (u) => { window.__waOuvert = String(u); return null } })
    await page.goto(`/ventes/devis?q=${encodeURIComponent(ref)}`)
    const ligne = page.locator(`#devis-row-${d.id}`)
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: /Relancer/ }).click()
    const dialogue = page.getByRole('dialog').filter({ hasText: 'Relancer par WhatsApp' })
    await expect(dialogue).toContainText(a.message_relance, { timeout: 30_000 })
    await dialogue.getByRole('button', { name: /Ouvrir WhatsApp/ }).click()
    await expect.poll(() => page.evaluate(() => window.__waOuvert || ''), { timeout: 30_000 }).toMatch(/^https:\/\/wa\.me\//)
    const ouvert = await page.evaluate(() => window.__waOuvert)
    expect(decodeURIComponent(ouvert.split('text=')[1] || ''), 'le lien wa.me porte le texte servi (nom du client)').toBe(a.message_relance)
    // Persistance : recharger, l'aperçu servi est identique.
    await page.reload()
    expect((await apercu()).message_relance).toBe(a.message_relance)
  } finally {
    await nettoyer(page.request, { devis: [d.id], leads: [lead.id] })
  }
})
