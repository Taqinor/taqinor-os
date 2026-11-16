// Preuves en direct du groupe APUB, lot 3 (audit PF5 « accès publics et à lien », dossier
// docs/audits/2026-11-11-parcours-PF5.md ; vague 6 sur runner GitHub, 16/11/2026) : APUB7 (lien du compte-rendu
// d'intervention : 90 jours après la clôture), APUB10 (livechat public parqué), APUB39 (un rappel demandé par le lien du
// devis ne lève pas l'opposition loi 09-08). Aucune de ces tâches n'a d'écran : le visiteur est un contexte API SANS
// cookie muni du vrai jeton, face à la VRAIE route (gunicorn du job), et l'état « Given » que nulle route n'écrit est
// posé par le shell Django. Persistance = base relue après le geste.
// APUB15 (nginx de production) et APUB73 (`settings.prod`) ne sont pas jouées ici : leur preuve est la configuration
// de PRODUCTION (fichier nginx, réglage sous `settings.prod`), que le serveur de ce job (settings.dev, sans nginx) ne sert pas.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('APUB', ['APUB7', 'APUB10', 'APUB39'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='

/** Visiteur SANS session : contexte API neuf (aucun cookie). */
const visiteur = (testInfo) => pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })

// ═══ APUB7 — le lien public du compte-rendu expire 90 jours après la clôture ═══
etape('PF5.APUB7', ['APUB7'], async ({ page, testInfo }) => {
  const m = marque()
  const cas = await py(`import base64
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations import field_services
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.records.models import Attachment
from apps.records.storage import store_attachment
u = U.objects.get(username='demo_admin'); co = u.company
cl = Client.objects.create(company=co, nom='APUB7 ${m}', prenom='Client', email='apub7-${m}@example.invalid')
lead = Lead.objects.create(company=co, nom='APUB7 ${m}', prenom='Client', stage='SIGNED', type_installation='residentiel')
devis = Devis.objects.create(company=co, reference='DEV-APUB7-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'), mode_installation='residentiel')
inst, _ = create_installation_from_devis(devis, u, co)
field_services.seed_shotlist_slots(co)
slot = next(s for s in field_services.active_shotlist(co) if s.phase == 'avant')
png = base64.b64decode(${J(PNG_B64)})
now = timezone.now()
out = []
for etiq, champs, attendu in (
        ('cloturee_notifiee_le J-91', dict(cloturee_notifiee_le=now - datetime.timedelta(days=91)), 404),
        ('cloturee_notifiee_le J-89', dict(cloturee_notifiee_le=now - datetime.timedelta(days=89)), 200),
        ('sans notification, date_realisee J-120', dict(date_realisee=timezone.localdate() - datetime.timedelta(days=120)), 404)):
    it = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u, technicien=u,
                                     statut=Intervention.Statut.VALIDEE, signataire_nom='Client', **champs)
    d, err = store_attachment(SimpleUploadedFile('p.png', png, content_type='image/png'), company=co)
    assert d, err
    ph = Attachment.objects.create(company=co, content_type=ContentType.objects.get_for_model(Intervention), object_id=it.id,
                                   file_key=d['file_key'], mime=d['mime'], filename=field_services.encode_slot_filename(slot.cle, 'p.png'))
    jeton = it.ensure_lien_rapport_token()
    it.refresh_from_db()
    out.append(dict(etiq=etiq, interv=it.pk, jeton=jeton, photo=ph.pk, attendu=attendu,
                    lu=dict(statut=it.statut, notifiee=str(it.cloturee_notifiee_le), realisee=str(it.date_realisee), creation=str(it.date_creation), jour=str(timezone.localdate()))))
sortie(out)`)
  expect(cas, 'Given : trois interventions VALIDÉE').toHaveLength(3)
  const anonyme = await visiteur(testInfo)
  const PUB = `${API}/public/installations/intervention-rapport`
  const relevé = []
  const echecs = []
  for (const c of cas) {
    console.log(`[APUB7] ${c.etiq} : état relu en base ${J(c.lu)}`)
    for (const [vue, chemin] of [['page', ''], ['PDF', 'pdf/'], ['photo', `photos/${c.photo}/`]]) {
      const r = await anonyme.get(`${PUB}/${c.jeton}/${chemin}`, T)
      relevé.push(`${c.etiq} · ${vue} → ${r.status()}`)
      if (r.status() !== c.attendu) echecs.push(`${c.etiq} : ${vue} publique rend ${r.status()} (attendu ${c.attendu})`)
    }
  }
  console.log(`[APUB7] ${relevé.join(' ; ')}`)
  expect(echecs, 'page, PDF et photo publics : 404 sur les liens expirés, 200 sur le lien valide').toEqual([])
  // `lien-rapport/` sur la 1re (expirée) rend le MÊME jeton : pas de rotation silencieuse.
  const lien = await lireJson(await page.request.get(`${API}/installations/interventions/${cas[0].interv}/lien-rapport/`, T), 'lien-rapport')
  expect(lien.token, 'lien-rapport sur l\'intervention expirée : même jeton').toBe(cas[0].jeton)
  expect(await py(`from apps.installations.models import Intervention
sortie(Intervention.objects.get(pk=${cas[0].interv}).lien_rapport_token)`), 'persistance : jeton inchangé en base').toBe(cas[0].jeton)
  // Relu après coup : l'expiration est relue à chaque GET, rien n'a été écrit — la page expirée reste 404, la valide 200.
  expect((await anonyme.get(`${PUB}/${cas[0].jeton}/`, T)).status(), 'relu : expirée toujours 404').toBe(404)
  expect((await anonyme.get(`${PUB}/${cas[1].jeton}/`, T)).status(), 'relu : J-89 toujours 200').toBe(200)
  await anonyme.dispose()
})

// ═══ APUB10 — livechat public parqué : 404 aux trois routes, rien n'est écrit ═══
etape('PF5.APUB10', ['APUB10'], async ({ testInfo }) => {
  const m = marque()
  const tel = `06${String(Math.floor(Math.random() * 1e8)).padStart(8, '0')}`
  const monte = await py(`from apps.crm import stages
from apps.crm.models import Lead, ChatSessionPublique
l = Lead.objects.create(company_id=U.objects.get(username='demo_admin').company_id, nom='Client Signé APUB10 ${m}', telephone=${J(tel)}, stage=stages.SIGNED)
s = ChatSessionPublique.objects.create(company_id=l.company_id)
sortie(dict(lead=l.pk, token=s.token))`)
  const lu = () => py(`from apps.crm.models import Lead, LeadActivity, ChatSessionPublique
l = Lead.objects.get(pk=${monte.lead})
sortie(dict(sessions=ChatSessionPublique.objects.count(), notes=LeadActivity.objects.filter(lead_id=l.pk).count(), email=l.email or '',
            leads=Lead.objects.filter(telephone=${J(tel)}).count()))`)
  const avant = await lu()
  const anonyme = await visiteur(testInfo)
  const BASE = `${API}/crm/public/chat/sessions/`
  const ouvrir = await anonyme.post(BASE, { ...T, data: {} })
  expect(ouvrir.status(), 'ouvrir une session rend 404 (réglage non posé)').toBe(404)
  const poster = await anonyme.post(`${BASE}${monte.token}/messages/`, { ...T, data: { message: `je m'appelle X, ${tel}, x-${m}@exemple.invalid` } })
  expect(poster.status(), 'poster un message rend 404').toBe(404)
  const relire = await anonyme.get(`${BASE}${monte.token}/`, T)
  expect(relire.status(), 'relire un transcript rend 404').toBe(404)
  const apres = await lu()
  expect(apres.sessions, 'aucune ChatSessionPublique créée').toBe(avant.sessions)
  expect(apres.notes, 'aucune LeadActivity écrite sur le lead Signé').toBe(avant.notes)
  expect(apres.email, 'e-mail du lead toujours vide').toBe('')
  expect(apres.leads, 'aucun lead créé au même téléphone').toBe(avant.leads)
  await anonyme.dispose()
})

// ═══ APUB39 — un rappel demandé depuis le lien du devis ne lève jamais l'opposition loi 09-08 ═══
etape('PF5.APUB39', ['APUB39'], async ({ page, testInfo }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `APUB39 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `apub39${m}@example.invalid` } }), 'lead')
  const prod = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur APUB39 ${m}`, prix_vente: '1000.00', prix_achat: '400.00' } }), 'produit')
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id,
    lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  // Given : un lead opposé (par le geste réel de la fiche), son empreinte posée, son devis envoyé et son lien public.
  await lireJson(await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { ne_plus_contacter: true } }), 'opposition')
  const etat = () => py(`from apps.crm.cadence_reperes import RAPPEL_DEMANDE_LIBELLE
from apps.crm.leads_consentement import FINALITES_CONTACT
from apps.crm.models import EmpreinteOpposition, Lead, LeadActivity, RelanceEtape
from core.models import ConsentRecord
l = Lead.objects.get(pk=${lead.id})
co = l.company
dernier = {}
for f in FINALITES_CONTACT:
    c = (ConsentRecord.objects.filter(company=co, subject_identifier=l.email, purpose=f).order_by('-occurred_at', '-pk').first())
    dernier[f] = None if c is None else bool(c.granted)
sortie(dict(
    opposee=bool(l.ne_plus_contacter),
    empreintes=EmpreinteOpposition.objects.filter(company=co, nature='telephone').count(),
    consentements=dernier,
    accordes=ConsentRecord.objects.filter(company=co, subject_identifier=l.email, granted=True).count(),
    note=LeadActivity.objects.filter(lead=l, body__startswith='Rappel demandé — opposition loi 09-08 active').count(),
    levee=LeadActivity.objects.filter(lead=l, body__contains='opposition levée à la demande du client').count(),
    touche=RelanceEtape.objects.filter(lead=l, libelle=RAPPEL_DEMANDE_LIBELLE, statut=RelanceEtape.Statut.A_FAIRE).count()))`)
  await py(`from apps.crm.leads_doublons import poser_empreintes_opposition
from apps.crm.models import Lead
l = Lead.objects.get(pk=${lead.id})
poser_empreintes_opposition(l.company, l)
sortie(1)`)
  const avant = await etat()
  expect(avant.opposee, 'Given : lead opposé').toBe(true)
  expect(avant.empreintes, 'Given : empreinte du téléphone posée').toBeGreaterThanOrEqual(1)
  expect(avant.touche, 'Given : aucune touche « rappel demandé » encore').toBe(0)
  // When : le porteur du lien demande un rappel.
  const anonyme = await visiteur(testInfo)
  const rep = await anonyme.post(`${API}/public/proposal/${lien.token}/contact/`, { ...T, data: { channel: 'rappel' } })
  expect(rep.status(), `POST …/contact/ {channel: rappel} → 200 (reçu ${rep.status()} ${(await rep.text()).slice(0, 200)})`).toBe(200)
  // Then : opposition, empreinte et registre intacts ; note « opposition active » et touche posées.
  const apres = await etat()
  expect(apres.opposee, 'le lead est toujours opposé (ne_plus_contacter vrai)').toBe(true)
  expect(apres.empreintes, 'empreinte gardée (nombre inchangé)').toBe(avant.empreintes)
  expect(apres.consentements, 'registre : dernière ligne de chaque finalité inchangée').toEqual(avant.consentements)
  expect(apres.accordes, 'aucun ConsentRecord accordé').toBe(avant.accordes)
  expect(Object.values(apres.consentements).every((x) => x === false || x === null), 'aucune finalité de contact accordée').toBe(true)
  expect(apres.note, 'note « Rappel demandé — opposition loi 09-08 active » posée').toBe(1)
  expect(apres.levee, 'aucune note « opposition levée à la demande du client »').toBe(0)
  expect(apres.touche, 'touche « rappel demandé » posée').toBe(1)
  // Persistance : relu par l'API, le lead est toujours opposé.
  const relu = await lireJson(await r.get(`${API}/crm/leads/${lead.id}/`, T), 'lead relu')
  expect(relu.ne_plus_contacter, 'persistance : lead relu opposé').toBe(true)
  await anonyme.dispose()
})
