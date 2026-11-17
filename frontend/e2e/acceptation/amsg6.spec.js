// AMSG — preuves en direct, lot 6 (vague d'acceptation 6 sur runner GitHub, 16/11/2026) du parcours PF8
// « messages envoyés aux clients » (dossier docs/audits/2026-11-11-parcours-PF8.md) :
// AMSG3, AMSG30, AMSG57, AMSG62, AMSG68, AMSG84, AMSG89, AMSG92, AMSG93, AMSG94, AMSG95, AMSG96.
// Même régime que `amsg2.spec.js` : AUCUN envoi réel (backend e-mail = console sous l'enveloppe AMSG61, aucune clé
// d'envoi — l'état de la production) ; un double `locmem` + clé factice n'est posé que là où la clause le dit.
// La VRAIE route par HTTP quand la clause nomme une route ou un écran, sinon le vrai code dans le shell Django,
// données propres dans une transaction ANNULÉE. Persistance = relecture en base / rechargement d'écran.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, lireJson, listeDe, connexionApi, connecterPortail } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG3', 'AMSG30', 'AMSG57', 'AMSG62', 'AMSG68', 'AMSG84', 'AMSG89', 'AMSG92', 'AMSG93',
  'AMSG94', 'AMSG95', 'AMSG96'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

/** Rejoue une sonde HÔTE (sans Django) ; renvoie son dict `{repro, observe}`. */
function sonde(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'AMSG', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  expect(ligne, `sonde ${constat} : ${(r.stderr || r.stdout || '').slice(-600)}`).toBeTruthy()
  return JSON.parse(ligne.slice(3))
}

// Fabrique Python commune (société démo de demo_admin, client d'essai à e-mail réservé et téléphone fictif).
const FABRIQUE = `
import random
from decimal import Decimal
import datetime as dt
from django.conf import settings
from django.db import transaction
from django.test.utils import override_settings
from django.core import mail
from authentication.models import Company
from apps.crm.models import Client
LOC = 'django.core.mail.backends.locmem.EmailBackend'
ADMIN = U.objects.get(username='demo_admin')
CO = ADMIN.company_id
def cli(m, co=None, **kw):
    d = dict(company_id=co or CO, nom='AMSG ' + m, prenom='Essai', email=m + '@example.invalid',
             telephone='+212600000' + str(random.randint(100, 999)))
    d.update(kw)
    return Client.objects.create(**d)
def appel(methode, url, data=None):
    from rest_framework.test import APIClient
    c = APIClient(); c.force_authenticate(ADMIN)
    r = getattr(c, methode)(url, data=data if data is not None else {}, format='json', HTTP_HOST='localhost')
    try:
        corps = r.json()
    except Exception:
        corps = None
    return r.status_code, corps
`
const pyAvec = (m, code) => py(`${FABRIQUE}\nm = ${J(m)}\n${code}`)

// ── données HTTP (copie des gabarits de `amsg.spec.js`) ─────────────────────────────────────────────
const courriel = (m) => `amsg-${m}-${Math.floor(Math.random() * 1e6)}@example.invalid`
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(marque()), ...extra },
}), `lead ${nom}`)
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
async function nettoyer(request, { leads = [], devis = [] }) {
  for (const id of devis) await request.delete(`${API}/ventes/devis/${id}/`, T).catch(() => null)
  for (const id of leads) await request.delete(`${API}/crm/leads/${id}/`, T).catch(() => null)
}

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG3 — l'opposition suit la personne jusqu'aux fiches DÉJÀ existantes (STOP, contact collé sur une fiche existante)
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.2-AMSG3', ['AMSG3'], async ({ page }) => {
  // VRAI geste STOP : réponse « Ne plus me contacter » sur une touche de cadence de la fiche A
  // (POST crm/relance-etapes/<id>/fait/ {reponse: 'ne_plus_contacter'} → repondre_ne_plus_contacter), aucun update() simulé.
  const m = marque()
  const d = await pyAvec(m, `from apps.crm.models import Lead
from apps.crm.models_cadence import RelanceEtape
EMAIL = 'amsg3-' + m + '@example.invalid'
TEL = '+2126' + ''.join(str(random.randint(0, 9)) for _ in range(8))
a = Lead.objects.create(company_id=CO, nom='AMSG3 A ' + m, email=EMAIL, telephone=TEL)
b = Lead.objects.create(company_id=CO, nom='AMSG3 B ' + m, telephone='0' + TEL[4:])
dd = Lead.objects.create(company_id=CO, nom='AMSG3 D ' + m, email=EMAIL.upper(), is_archived=True)
e = Lead.objects.create(company_id=CO, nom='AMSG3 E ' + m, telephone='+2126' + ''.join(str(random.randint(0, 9)) for _ in range(8)))
autre = Company.objects.create(nom='AMSG3 autre ' + m, slug='amsg3-autre-' + m)
c = Lead.objects.create(company=autre, nom='AMSG3 C', telephone=TEL)
et = RelanceEtape.objects.create(company_id=CO, lead=a, cadence='apres_devis', ordre=5, due_date=timezone.localdate(),
    due_at=timezone.now(), canal='whatsapp', libelle='Message AMSG3')
sortie(dict(a=a.id, b=b.id, d=dd.id, e=e.id, c=c.id, autre=autre.id, etape=et.id, tel=TEL))`)
  const etat = () => py(`from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import peut_contacter
M = getattr(Lead, 'all_objects', Lead._base_manager)
out = {}
for nom, pk in json.loads(${J(J({ a: d.a, b: d.b, d: d.d, e: d.e, c: d.c }))}).items():
    f = M.get(pk=pk)
    out[nom] = dict(nepc=f.ne_plus_contacter, chatter=LeadActivity.objects.filter(lead_id=pk, kind=LeadActivity.Kind.MODIFICATION, field='ne_plus_contacter').exists())
out['peut_B'] = bool(peut_contacter(M.get(pk=${d.b})))
sortie(out)`)
  try {
    const avant = await etat()
    expect(avant.b.nepc || avant.d.nepc || avant.e.nepc, 'avant le STOP : B, D, E contactables').toBe(false)
    const stop = await page.request.post(`${API}/crm/relance-etapes/${d.etape}/fait/`, { ...T, data: { reponse: 'ne_plus_contacter' } })
    expect(stop.status(), `STOP par la vraie route : ${(await stop.text()).slice(0, 300)}`).toBe(200)
    const apres = await etat()
    expect([apres.a.nepc, apres.b.nepc, apres.d.nepc, apres.c.nepc, apres.e.nepc], 'A, B, D opposées ; C (autre société) et E inchangées')
      .toEqual([true, true, true, false, false])
    expect([apres.b.chatter, apres.d.chatter, apres.c.chatter, apres.e.chatter], 'ligne de chatter ancien → nouveau sur B et D seulement')
      .toEqual([true, true, false, false])
    expect(apres.peut_B, 'peut_contacter(B) faux').toBe(false)
    // Écran : la fiche B montre « Ne plus contacter » cochée et la ligne dans son historique.
    await page.goto(`/crm/leads/${d.b}`)
    await expect(page.getByLabel('Ne plus contacter'), 'fiche B : case « Ne plus contacter » cochée').toBeChecked({ timeout: 60_000 })
    await expect(page.getByTestId('lw-context-rail'), 'historique de B : la ligne de bascule').toContainText(/ne plus contacter/i, { timeout: 30_000 })
    // Un numéro opposé collé sur la fiche existante E (vraie route PATCH) la rend opposée.
    const patchE = await page.request.patch(`${API}/crm/leads/${d.e}/`, { ...T, data: { telephone: d.tel } })
    expect(patchE.status(), (await patchE.text()).slice(0, 300)).toBeLessThan(300)
    expect((await etat()).e.nepc, 'E opposée dès son enregistrement').toBe(true)
    // Décocher B n'est pas défait par l'enregistrement suivant.
    const dec = await page.request.patch(`${API}/crm/leads/${d.b}/`, { ...T, data: { ne_plus_contacter: false } })
    expect(dec.status(), (await dec.text()).slice(0, 300)).toBeLessThan(300)
    const ville = await page.request.patch(`${API}/crm/leads/${d.b}/`, { ...T, data: { ville: 'Rabat' } })
    expect(ville.status(), (await ville.text()).slice(0, 300)).toBeLessThan(300)
    expect((await etat()).b.nepc, 'B reste décochée').toBe(false)
  } finally {
    await py(`from apps.crm.models import Lead
M = getattr(Lead, 'all_objects', Lead._base_manager)
for pk in ${J([d.a, d.b, d.d, d.e, d.c])}:
    try:
        M.filter(pk=pk).delete()
    except Exception:
        pass
sortie(1)`).catch(() => undefined)
  }
}, { ecart: { base: 'FAIL', raison: "clause « sonde rejouée ⇒ repro False » non jouable : docs/audits/sondes/AMSG/C-AMSG-003.py ne charge plus (ImportError `activity` dans leads_doublons.py, import ajouté par 3c5d382fc) — défaut de la sonde, hors Files: ; l'étape rejoue le scénario de la sonde sur le vrai code (vraie route STOP) et affirme la base et l'écran" } })

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG30 — commande remettre_relances_non_parties (dry-run par défaut, puis --appliquer --factures)
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.3-AMSG30', ['AMSG30'], async () => {
  const m = marque()
  const r = await pyAvec(m, `from io import StringIO
from django.core.management import call_command
from apps.ventes.recouvrement import ensure_default_followup_levels
from apps.ventes.domain.recouvrement import RELANCE_AUTO_NOTE, niveaux_cadence, prochain_niveau
from apps.ventes.models import Facture, RelanceLog
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG30 ' + m, slug='amsg30-' + m)
    ensure_default_followup_levels(co)
    niveaux = niveaux_cadence(co)
    today = timezone.localdate()
    def fac(k):
        c = Client.objects.create(company=co, nom='Client ' + k, prenom='AMSG30', email='amsg30-%s-%s@example.invalid' % (m, k), releve_mensuel_auto=True)
        return Facture.objects.create(company=co, reference='FAC-AMSG30-%s-%s' % (m, k), client=c, statut='en_retard',
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            date_echeance=today - dt.timedelta(days=40))
    f1, f2, f3 = fac('1'), fac('2'), fac('3')
    for f in (f1, f2):
        for n in niveaux:
            RelanceLog.objects.create(company=co, facture=f, niveau=n.ordre, niveau_nom=n.nom, note=RELANCE_AUTO_NOTE, canal='email')
    RelanceLog.objects.create(company=co, facture=f3, niveau=niveaux[0].ordre, note='Appel du client', canal='email', created_by=ADMIN)
    RelanceLog.objects.filter(company=co).update(date=dt.date(2026, 10, 1))
    res['niveaux'] = len(niveaux)
    res['f1_deja_tous_avant'] = bool(prochain_niveau(f1, niveaux)[1])
    out = StringIO()
    call_command('remettre_relances_non_parties', '--jusqu-au', '2026-10-08', stdout=out)
    dry = out.getvalue()
    res['dry'] = {'f1': f1.reference in dry, 'f2': f2.reference in dry, 'f3': f3.reference in dry, 'marque': 'DRY-RUN' in dry}
    res['dry_ecrit'] = RelanceLog.objects.filter(company=co, compte_dans_cadence=False).count()
    applis = []
    for _ in range(2):
        call_command('remettre_relances_non_parties', '--jusqu-au', '2026-10-08', '--appliquer', '--factures', str(f1.pk), stdout=StringIO())
        f1 = Facture.objects.get(pk=f1.pk)
        niveau, deja = prochain_niveau(f1, niveaux)
        applis.append({'logs': RelanceLog.objects.filter(facture=f1).count(),
                       'comptes': RelanceLog.objects.filter(facture=f1, compte_dans_cadence=True).count(),
                       'niveau_pk': niveau.pk, 'niveau1_pk': niveaux[0].pk, 'deja_tous': bool(deja),
                       'prochaine_posee': f1.prochaine_relance is not None})
    res['applis'] = applis
    res['intacts'] = RelanceLog.objects.filter(facture__in=[f2, f3], compte_dans_cadence=True).count()
    res['deja_tous_f2'] = bool(prochain_niveau(f2, niveaux)[1])
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.dry, 'dry-run : 2 factures listées (f1, f2), la relance manuelle (f3) absente, mention DRY-RUN')
    .toEqual({ f1: true, f2: true, f3: false, marque: true })
  expect(r.dry_ecrit, 'dry-run : 0 écriture').toBe(0)
  expect(r.f1_deja_tous_avant, 'avant : tous les niveaux consommés').toBe(true)
  for (const a of r.applis) {
    expect(a.logs, 'historique gardé (aucune relance effacée)').toBe(r.niveaux)
    expect(a.comptes, 'les relances automatiques de f1 sortent de la cadence').toBe(0)
    expect([a.niveau_pk, a.deja_tous], 'prochain_niveau = niveau 1').toEqual([a.niveau1_pk, false])
    expect(a.prochaine_posee, 'prochaine_relance posée par amorcer_cadence').toBe(true)
  }
  expect(r.intacts, 'f2 (non demandée) et la manuelle de f3 intactes').toBe(r.niveaux + 1)
  expect(r.deja_tous_f2, 'f2 toujours tous niveaux consommés').toBe(true)
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG57 + AMSG95 — avis de transition SAV et réponse e-mail d'un ticket : « envoyé » seulement si l'e-mail part
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.5-AMSG57', ['AMSG57'], async () => {
  const m = marque()
  const r = await pyAvec(m, `from django.contrib.contenttypes.models import ContentType
from apps.installations.models import Installation
from apps.records.models import Activity
from apps.sav.models import SavSlaSettings, Ticket, TicketEmailThread
from apps.sav.notifications_client import notify_ticket_transition
from apps.sav.services import appliquer_transition_ticket
res = {}
with transaction.atomic():
    c = cli(m)
    inst = Installation.objects.create(company_id=CO, client=c, reference='CHT-AMSG57-' + m)
    sla = SavSlaSettings.get(ADMIN.company)
    sla.notifications_client_sav = True
    sla.save(update_fields=['notifications_client_sav'])
    ticket = Ticket.objects.create(company_id=CO, reference='SAV-AMSG57-' + m, client=c, installation=inst,
        type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU, created_by=ADMIN)
    appliquer_transition_ticket(ticket, Ticket.Statut.PLANIFIE, ADMIN)
    t = Activity.objects.filter(content_type=ContentType.objects.get_for_model(Ticket), object_id=ticket.pk, summary='Envoyer ce WhatsApp')
    res['taches'] = t.count(); res['note'] = t.first().note if t.exists() else ''
    res['email_sent'] = notify_ticket_transition(ticket, 'planifie')['email_sent']
    res['repondre'] = appel('post', '/api/django/sav/tickets/%d/repondre-email/' % ticket.pk, {'corps': 'Nous intervenons demain.'})
    ticket.refresh_from_db()
    res['fil_sortant'] = TicketEmailThread.objects.filter(ticket=ticket, direction=TicketEmailThread.Direction.SORTANT).count()
    res['premiere_reponse'] = ticket.date_premiere_reponse
    res['notes_email'] = [a.note for a in Activity.objects.filter(content_type=ContentType.objects.get_for_model(Ticket), object_id=ticket.pk) if 'E-mail envoy' in (a.note or '')]
    with override_settings(ANYMAIL={'SENDINBLUE_API_KEY': 'cle-factice'}, EMAIL_BACKEND=LOC):
        mail.outbox = []
        res['avec_cle'] = appel('post', '/api/django/sav/tickets/%d/repondre-email/' % ticket.pk, {'corps': 'Nous intervenons demain.'})
        res['outbox_avec_cle'] = len(mail.outbox)
    transaction.set_rollback(True)
sortie(res)`)
  expect([r.taches, r.email_sent], 'transition « planifié » : 1 tâche « Envoyer ce WhatsApp », email_sent faux').toEqual([1, false])
  expect(r.note).toContain('wa.me')
  const [statut, corps] = r.repondre
  expect(JSON.stringify(corps)).toContain("rien n'est parti")
  // Écart clause/code : la clause AMSG57 dit « 400 », le code rend 409 (EmailNonConfigure, refus d'ÉTAT) — gelé par AMSG95
  // (« étape PF8.5-AMSG57 réalignée sur 409 »).
  expect(statut, `repondre-email sans e-mail opérationnel : ${J(corps)}`).toBe(409)
  expect([r.fil_sortant, r.premiere_reponse, r.notes_email], 'aucun fil SORTANT, première réponse non posée, aucune note « E-mail envoyé »').toEqual([0, null, []])
  expect([r.avec_cle[0], r.outbox_avec_cle], 'clé factice + locmem : inchangé (réponse acceptée, 1 e-mail)').toEqual([201, 1])
})

etape('PF8.5-AMSG95', ['AMSG95'], async () => {
  const m = marque()
  const r = await pyAvec(m, `from apps.sav.models import Ticket, TicketEmailThread
res = {}
with transaction.atomic():
    c = cli(m)
    st, t = appel('post', '/api/django/sav/tickets/', {'client': c.pk, 'priorite': 'haute', 'type': 'correctif', 'description': 'Onduleur en defaut ' + m})
    res['creation'] = st
    tid = t['id']
    with override_settings(ANYMAIL={}, EMAIL_BACKEND=LOC):
        mail.outbox = []
        res['rep'] = appel('post', '/api/django/sav/tickets/%d/repondre-email/' % tid, {'corps': 'Nous passons jeudi.', 'sujet': 'Votre ticket', 'destinataire': c.email})
        res['outbox'] = len(mail.outbox)
    tk = Ticket.objects.get(pk=tid)
    res['fil'] = TicketEmailThread.objects.filter(ticket=tk, direction=TicketEmailThread.Direction.SORTANT).count()
    res['premiere'] = tk.date_premiere_reponse
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.creation, 'ticket créé par l’API').toBe(201)
  const [statut, corps] = r.rep
  expect(statut, `repondre-email sans e-mail opérationnel : ${J(corps)}`).toBe(409)
  expect(corps.detail).toContain("rien n'est parti")
  expect([r.outbox, r.fil, r.premiere], 'mail.outbox vide, 0 fil SORTANT, date_premiere_reponse vide').toEqual([0, 0, null])
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG62 — neutraliser_contacts_demo : dry-run sans écriture, puis --appliquer --sauf
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.4-AMSG62', ['AMSG62'], async () => {
  const m = marque()
  const r = await pyAvec(m, `import ast
from io import StringIO
from django.apps import apps as django_apps
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from authentication.management.commands.neutraliser_contacts_demo import SEED
Fournisseur = django_apps.get_model('stock', 'Fournisseur')
AuditLog = django_apps.get_model('audit', 'AuditLog')
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG62 ' + m, slug='amsg62-' + m)
    fiches = []
    for noeud in ast.walk(ast.parse(SEED.read_text(encoding='utf-8'))):
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], 'id', '') == 'clients_data':
            for nom, prenom, email, tel, _adresse in ast.literal_eval(noeud.value):
                fiches.append(Client.objects.create(company=co, nom=nom, prenom=prenom, email=email, telephone=tel))
        if isinstance(noeud, ast.Call) and getattr(noeud.func, 'attr', '') == 'create' and 'Fournisseur' in ast.unparse(noeud.func):
            kw = {k.arg: ast.literal_eval(k.value) for k in noeud.keywords if k.arg != 'company'}
            fiches.append(Fournisseur.objects.create(company=co, **kw))
    res['clients'] = sum(1 for f in fiches if isinstance(f, Client))
    res['fournisseurs'] = sum(1 for f in fiches if isinstance(f, Fournisseur))
    temoin = Client.objects.create(company=co, nom='Temoin', prenom='Reel', email='temoin@client-reel.ma', telephone='+212611111111')
    def etat():
        return [list(type(f).objects.values_list('email', 'telephone').get(pk=f.pk)) for f in fiches + [temoin]]
    avant = etat()
    out = StringIO()
    call_command('neutraliser_contacts_demo', societe=co.slug, stdout=out)
    dry = out.getvalue()
    res['dry_texte'] = dry
    res['dry_ecriture'] = etat() != avant
    res['dry_adresse_complete'] = any(f.email in dry for f in fiches if f.email)
    exclu = fiches[0]
    out = StringIO()
    call_command('neutraliser_contacts_demo', societe=co.slug, appliquer=True, sauf=[exclu.pk], stdout=out)
    res['appli_texte'] = out.getvalue()
    apres = etat()
    res['exclu_intact'] = apres[0] == avant[0]
    res['temoin_intact'] = apres[-1] == avant[-1]
    res['neutralises'] = all(e.endswith('@example.invalid') and t.startswith('+212600') for e, t in apres[1:-1])
    res['audit'] = [AuditLog.objects.filter(content_type=ContentType.objects.get_for_model(f), object_id=str(f.pk), detail__startswith='AMSG62').count() for f in fiches[1:]]
    res['audit_exclu'] = AuditLog.objects.filter(content_type=ContentType.objects.get_for_model(exclu), object_id=str(exclu.pk), detail__startswith='AMSG62').count()
    transaction.set_rollback(True)
sortie(res)`)
  expect([r.clients, r.fournisseurs], '5 clients et 2 fournisseurs du seed').toEqual([5, 2])
  expect(r.dry_texte, 'dry-run : 7 fiches concernées, rien écrit').toContain('7 fiche(s) concernée(s)')
  expect(r.dry_texte).toContain('dry-run, rien écrit')
  expect((r.dry_texte.match(/^client \d+ /gm) || []).length, 'dry-run : 5 clients listés').toBe(5)
  expect((r.dry_texte.match(/^fournisseur \d+ /gm) || []).length, 'dry-run : 2 fournisseurs listés').toBe(2)
  expect([r.dry_ecriture, r.dry_adresse_complete], 'dry-run : 0 écriture, jamais l’adresse complète').toEqual([false, false])
  expect(r.appli_texte, 'application : décompte').toContain('6 fiche(s) neutralisée(s)')
  expect([r.exclu_intact, r.temoin_intact, r.neutralises], 'l’id exclu et le témoin intacts ; les autres en @example.invalid + téléphone fictif').toEqual([true, true, true])
  expect(r.audit, 'une ligne de journal d’audit par fiche neutralisée').toEqual([1, 1, 1, 1, 1, 1])
  expect(r.audit_exclu, 'aucune ligne pour l’exclu').toBe(0)
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG68 — règle send_email sans corps : 400 à la création, SKIPPED à l'envoi
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.4-AMSG68', ['AMSG68'], async ({ page }) => {
  const m = marque()
  const nom = `AMSG68 ${m}`
  const api = await page.request.post(`${API}/automation/rules/`, {
    ...T, data: { nom, trigger_type: 'lead_stage_change', trigger_config: {}, action_type: 'send_email', action_config: { subject: 'Relance' } },
  })
  const txt = await api.text()
  expect(api.status(), txt).toBe(400)
  expect(J(JSON.parse(txt).action_config || ''), 'motif nommé sous action_config').toContain('corps obligatoire')
  const regles = listeDe(await lireJson(await page.request.get(`${API}/automation/rules/?page_size=500`, T), 'règles'))
  expect(regles.filter((x) => x.nom === nom), 'aucune règle créée').toEqual([])
  // Données posées HORS transaction : l'AutomationRun est écrit à la validation (on_commit), jamais dans un bloc annulé.
  const r = await pyAvec(m, `from apps.automation.engine import run_action
from apps.automation.models import ActionType, AutomationRule, AutomationRun, TriggerType
from apps.crm.models import Lead
res = {}
co = Company.objects.create(nom='AMSG68 ' + m, slug='amsg68-' + m)
ancienne = None
lead = None
try:
    lead = Lead.objects.create(company=co, nom='Client AMSG68', stage='NEW', email='amsg68-' + m + '@example.invalid')
    ancienne = AutomationRule.objects.create(company=co, nom='Ancienne', enabled=False, trigger_type=TriggerType.LEAD_STAGE_CHANGE,
        trigger_config={}, action_type=ActionType.SEND_EMAIL, action_config={'subject': 'Bonjour'})
    with override_settings(ANYMAIL={'SENDINBLUE_API_KEY': 'cle-factice'}, EMAIL_BACKEND=LOC):
        mail.outbox = []
        run_action(ancienne, lead, co)
        res['outbox'] = len(mail.outbox)
    run = AutomationRun.objects.get(rule=ancienne)
    res['skipped'] = run.status == AutomationRun.Status.SKIPPED
    res['message'] = run.message
finally:
    for fn in (lambda: AutomationRun.objects.filter(rule=ancienne).delete(), lambda: ancienne and ancienne.delete(),
               lambda: lead and Lead.objects.filter(pk=lead.pk).delete(), lambda: co.delete()):
        try:
            fn()
        except Exception:
            pass
sortie(res)`)
  expect([r.skipped, r.message, r.outbox], 'règle ancienne sans corps : SKIPPED « Corps vide : e-mail non envoyé. », aucun e-mail')
    .toEqual([true, 'Corps vide : e-mail non envoyé.', 0])
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG94 (+ écran d'AMSG68) — le refus du serveur s'affiche SOUS le champ « Config action », sans toast
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.4-AMSG94', ['AMSG94', 'AMSG68'], async ({ page, suivi }) => {
  const nom = `AMSG94 ${marque()}`
  suivi.attendre(/\/automation\/rules\/$/, 400)
  await page.goto('/parametres?onglet=automatisations')
  const bloc = page.locator('div.border-dashed').filter({ has: page.getByPlaceholder('Nom de la règle') })
  await expect(bloc).toBeVisible({ timeout: 60_000 })
  await bloc.getByPlaceholder('Nom de la règle').fill(nom)
  await bloc.getByRole('combobox').nth(1).click()
  await page.getByRole('option', { name: 'Envoyer un email' }).click()
  const champ = bloc.getByPlaceholder(/Config action/)
  await champ.fill('{"subject": "Relance"}')
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/automation\/rules\/$/.test(new URL(x.url()).pathname), T),
    bloc.getByRole('button', { name: 'Ajouter la règle' }).click(),
  ])
  expect(rep.status(), 'serveur : 400').toBe(400)
  expect(J(await rep.json()), 'corps du refus : action_config nommé').toContain('action_config')
  await expect(bloc.getByText(/corps obligatoire/), 'erreur « corps obligatoire » SOUS le champ « Config action »').toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(1500)
  await expect(page.getByText('Ajout impossible.'), 'le toast « Ajout impossible. » ne paraît plus').toHaveCount(0)
  // Persistance côté serveur : aucune règle de ce nom.
  const regles = listeDe(await lireJson(await page.request.get(`${API}/automation/rules/?page_size=500`, T), 'règles'))
  expect(regles.filter((x) => x.nom === nom), 'aucune règle créée').toEqual([])
  // L'erreur s'efface à la frappe dans ce champ.
  await champ.fill('{"subject": "Relance", "body": "Bonjour"}')
  await expect(bloc.getByText(/corps obligatoire/), 'l’erreur s’efface à la frappe').toHaveCount(0)
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG84 — aperçu et envoi WhatsApp de devis refusés (409) depuis un lead perdu ou archivé, avant tout lien
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.4-AMSG84', ['AMSG84'], async ({ page }) => {
  const m = marque()
  const leads = {}
  const devis = {}
  for (const cas of ['perdu', 'archive', 'oppose', 'temoin']) leads[cas] = await nouveauLead(page.request, `AMSG84 ${cas} ${m}`, { whatsapp: telephoneMobileUnique() })
  try {
    for (const [cas, l] of Object.entries(leads)) devis[cas] = await devisBrouillon(page.request, l.id)
    await poserLead(leads.perdu.id, { perdu: true })
    await poserLead(leads.archive.id, { is_archived: true })
    await poserLead(leads.oppose.id, { ne_plus_contacter: true })
    const etat = (cas) => py(`from apps.ventes.models import Devis, ShareLink
from apps.crm.models import LeadActivity
d = Devis.objects.get(pk=${devis[cas].id})
sortie(dict(statut=d.statut, envoi=d.date_envoi, liens=ShareLink.objects.filter(devis_id=d.id).count(),
            notes=LeadActivity.objects.filter(lead_id=${leads[cas].id}).count()))`)
    for (const cas of ['perdu', 'archive']) {
      const avant = await etat(cas)
      for (const route of ['whatsapp-devis-apercu', 'whatsapp-devis']) {
        const r = await page.request.post(`${API}/crm/leads/${leads[cas].id}/${route}/`, { ...T, data: { devis_ids: [devis[cas].id], langue: 'fr' } })
        const corps = await r.json().catch(() => ({}))
        expect(r.status(), `${cas} ${route} : 409 (${J(corps)})`).toBe(409)
        expect(corps.detail, `${cas} ${route}`).toBe('Message refusé : perdu/archivé.')
        expect(corps.wa_url, `${cas} ${route} : aucun wa_url`).toBeUndefined()
      }
      const apres = await etat(cas)
      expect(apres, `${cas} : 0 ShareLink, devis brouillon sans date d’envoi, 0 note de chatter (relu en base)`).toEqual(avant)
      expect([apres.statut, apres.envoi, apres.liens]).toEqual(['brouillon', null, 0])
    }
    // Témoin contactable : 200 avec wa_url.
    const t = await page.request.post(`${API}/crm/leads/${leads.temoin.id}/whatsapp-devis-apercu/`, { ...T, data: { devis_ids: [devis.temoin.id], langue: 'fr' } })
    const tc = await t.json().catch(() => ({}))
    expect(t.status(), J(tc)).toBe(200)
    expect(tc.wa_url, 'témoin : wa_url rendu').toMatch(/^https:\/\/wa\.me\//)
    // Opposé : 409 MOTIF_CONTACT_REFUSE inchangé.
    for (const route of ['whatsapp-devis-apercu', 'whatsapp-devis']) {
      const o = await page.request.post(`${API}/crm/leads/${leads.oppose.id}/${route}/`, { ...T, data: { devis_ids: [devis.oppose.id], langue: 'fr' } })
      const oc = await o.json().catch(() => ({}))
      expect(o.status(), `opposé ${route} : ${J(oc)}`).toBe(409)
      expect(oc.detail).toContain('Contact refusé : la personne a demandé à ne plus être contactée')
    }
  } finally {
    await nettoyer(page.request, { leads: Object.values(leads).map((l) => l.id) })
  }
})

etape('PF8.4-AMSG84-ecran', ['AMSG84'], async ({ page, suivi }) => {
  const m = marque()
  const lead = await nouveauLead(page.request, `AMSG84 ecran ${m}`, { whatsapp: telephoneMobileUnique() })
  try {
    const d = await devisBrouillon(page.request, lead.id)
    await poserLead(lead.id, { perdu: true })
    suivi.attendre(/\/crm\/leads\/\d+\/whatsapp-devis-apercu\/?$/, 409)
    await page.goto(`/crm/leads/${lead.id}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await page.getByRole('checkbox', { name: `Sélectionner ${d.reference} pour WhatsApp` }).click()
    await page.getByRole('button', { name: /Envoyer par WhatsApp/ }).click()
    await expect(page.getByText('Message refusé : perdu/archivé.').first(), 'toast du refus').toBeVisible({ timeout: 30_000 })
    // WhatsApp ne s'ouvre pas : aucun dialogue d'aperçu, devis toujours brouillon, aucun lien frappé.
    await expect(page.getByRole('button', { name: /Ouvrir WhatsApp/ })).toHaveCount(0)
    const base = await py(`from apps.ventes.models import Devis, ShareLink
d = Devis.objects.get(pk=${d.id})
sortie(dict(statut=d.statut, liens=ShareLink.objects.filter(devis_id=d.id).count()))`)
    expect(base, 'relu en base : brouillon, 0 lien').toEqual({ statut: 'brouillon', liens: 0 })
  } finally {
    await nettoyer(page.request, { leads: [lead.id] })
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG89 — Paramètres › E-mails : « Rappel de RDV (J-1) » sans corps modifiable
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.4-AMSG89', ['AMSG89'], async ({ page }) => {
  const eff = await lireJson(await page.request.get(`${API}/parametres/email-templates/effective/`, T), 'modèles effectifs')
  const lignes = Object.fromEntries(listeDe(eff).map((x) => [x.cle, x]))
  expect(lignes.rappel_rdv, 'ligne rappel_rdv servie').toBeTruthy()
  expect(lignes.rappel_rdv.corps_modifiable, 'rappel_rdv : corps_modifiable faux').toBe(false)
  const autres = Object.entries(lignes).filter(([cle]) => cle !== 'rappel_rdv')
  expect(autres.length, 'autres clés servies').toBeGreaterThan(0)
  expect(autres.filter(([, v]) => v.corps_modifiable !== true).map(([c]) => c), 'toutes les autres : corps_modifiable vrai').toEqual([])
  await page.goto('/parametres?onglet=email')
  await expect(page.locator('#pe-email-sujet-rappel_rdv'), 'carte « Rappel de RDV (J-1) » : sujet').toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Rappel de RDV (J-1)').first()).toBeVisible()
  // Sujet et traductions présents ; aucun champ Corps (français, anglais, arabe).
  for (const id of ['pe-email-sujet-rappel_rdv', 'pe-email-sujet-en-rappel_rdv', 'pe-email-sujet-ar-rappel_rdv']) {
    expect(await page.locator(`#${id}`).count(), `sujet ${id}`).toBe(1)
  }
  for (const id of ['pe-email-corps-rappel_rdv', 'pe-email-corps-en-rappel_rdv', 'pe-email-corps-ar-rappel_rdv']) {
    expect(await page.locator(`#${id}`).count(), `corps ${id} absent`).toBe(0)
  }
  await expect(page.getByText('Le texte de ce rappel suit le modèle de message WhatsApp du rappel de rendez-vous ; seul le sujet se règle ici.'))
    .toBeVisible()
  // « Envoi de devis » garde ses champs Corps.
  await expect(page.locator('#pe-email-corps-envoi_devis'), 'Envoi de devis garde son Corps').toHaveCount(1)
  for (const id of ['pe-email-corps-en-envoi_devis', 'pe-email-corps-ar-envoi_devis']) {
    expect(await page.locator(`#${id}`).count(), `corps ${id}`).toBe(1)
  }
  // Persistance : rechargé, même rendu.
  await page.reload()
  await expect(page.locator('#pe-email-sujet-rappel_rdv')).toBeVisible({ timeout: 60_000 })
  expect(await page.locator('#pe-email-corps-rappel_rdv').count()).toBe(0)
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG92 — portail client › Mon équipe : dire si l'invitation d'un collègue est réellement partie
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.5-AMSG92', ['AMSG92'], async ({ page, context, testInfo }) => {
  const s = sonde('C-AMSG-VER2-101')
  expect(s.repro, `sonde C-AMSG-VER2-101 rejouée : repro False (${J(s.observe)})`).toBe(false)
  const m = marque()
  const clientId = await pyAvec(m, 'c = cli(m)\nsortie(c.id)')
  const comptes = listeDe(await lireJson(await page.request.get(`${API}/portail/comptes-portail/`, T), 'comptes'))
  const compte = comptes.find((c) => c.client === clientId)
    ?? await lireJson(await page.request.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: clientId } }), 'compte')
  const prov = await lireJson(await page.request.post(`${API}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { ...T, data: {} }), 'accès')
  const mdp = `P0rtail!${m}`
  await py(`u = U.objects.get(username=${J(prov.username)}); u.set_password(${J(mdp)}); u.must_change_password = True; u.failed_login_count = 0; u.locked_until = None; u.save(); sortie(1)`)
  const pa = await connecterPortail({ request: pwRequest }, testInfo.project.use.baseURL, prov.username, mdp)
  try {
    // Route : POST portail/mon-equipe/ → 201, email_envoye faux, invitation « en attente ».
    const mail1 = `collegue-${m}@example.invalid`
    const r = await pa.post(`${API}/portail/mon-equipe/`, { ...T, data: { email: mail1, role: 'lecture' } })
    const corps = await r.json().catch(() => ({}))
    expect(r.status(), J(corps)).toBe(201)
    expect(corps.email_envoye, 'e-mail non opérationnel : email_envoye faux').toBe(false)
    const equipe = await lireJson(await pa.get(`${API}/portail/mon-equipe/`, T), 'équipe')
    const ligne = listeDe(equipe).find((x) => x.email === mail1)
    expect(ligne?.statut, 'invitation enregistrée « en attente » (relue)').toBe('en_attente')
    // Écran : « Mon équipe » › Inviter.
    await context.addCookies((await pa.storageState()).cookies)
    await page.goto('/portail/client/equipe')
    const mail2 = `collegue2-${m}@example.invalid`
    await page.getByRole('textbox', { name: 'E-mail' }).fill(mail2)
    await page.getByRole('button', { name: 'Inviter', exact: true }).click()
    const statut = page.getByRole('status').filter({ hasText: /Invitation/ })
    await expect(statut, 'message du titre : e-mail pas parti').toContainText("Invitation enregistrée, mais l'e-mail n'est pas parti : votre collègue ne l'a pas reçue.", { timeout: 30_000 })
    await expect(page.getByText('Invitation envoyée.')).toHaveCount(0)
    // Persistance : rechargé, la ligne de l'invitation reste listée.
    await page.reload()
    await expect(page.getByText(mail2)).toBeVisible({ timeout: 30_000 })
  } finally {
    await pa.dispose().catch(() => undefined)
  }
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG93 — accès portail partenaire : « envoyé par email » seulement si l'e-mail est parti
// ═══════════════════════════════════════════════════════════════════════════════════════════════
etape('PF8.5-AMSG93', ['AMSG93'], async () => {
  const m = marque()
  const r = await pyAvec(m, `from apps.crm.models import Partenaire
res = {}
with transaction.atomic():
    p = Partenaire.objects.create(company_id=CO, nom='AMSG93 ' + m, email='p' + m + '@example.invalid', token_acces='tok-amsg93-' + m)
    res['prov'] = appel('post', '/api/django/crm/partenaires/%d/provisionner-acces/' % p.id)
    u = U.objects.filter(company_id=CO, portail_partenaire_id=p.id).first()
    res['compte_cree'] = u is not None
    res['doit_changer'] = bool(u and u.must_change_password)
    transaction.set_rollback(True)
sortie(res)`)
  const [statut, corps] = r.prov
  expect(statut, J(corps)).toBe(200)
  expect(corps.cree, 'accès créé').toBe(true)
  expect(corps.email_envoye, 'e-mail non opérationnel : email_envoye faux').toBe(false)
  expect(corps.detail).toBe('Accès portail créé — e-mail non opérationnel : identifiants non envoyés.')
  expect(JSON.stringify(corps)).not.toMatch(/mot_de_passe|password/i)
  expect([r.compte_cree, r.doit_changer], 'compte créé (relu en base), mot de passe à changer').toEqual([true, true])
})

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// AMSG96 — la tâche « Envoyer ce WhatsApp » de l'expédition et du rappel J-1 va au technicien responsable
// ═══════════════════════════════════════════════════════════════════════════════════════════════
const SESSIONS_T = []
test.afterAll(async () => { for (const c of SESSIONS_T) await c.dispose().catch(() => undefined) })
/** Chantier(s) d'essai : A (responsable actif T), B (créateur C seul), C2 (aucun), D (responsable inactif, créateur C). */
async function montage96(m, avecAutres) {
  return pyAvec(m, `from apps.roles.models import Role
from apps.installations.models import Installation, Livraison
role = Role.objects.get(company_id=CO, nom='Commercial').pk
t = compte('amsg96_t', role=role, societe=CO)
c = compte('amsg96_c', role=role, societe=CO)
t2 = compte('amsg96_t2', role=role, societe=CO)
U.objects.filter(pk=t2.pk).update(is_active=False)
client = cli(m)
def inst(k, **kw):
    i = Installation.objects.create(company_id=CO, client=client, reference='CH-AMSG96-%s-%s' % (m, k))
    if kw:
        Installation.objects.filter(pk=i.pk).update(**kw)
    return i
def liv(i, k):
    return Livraison.objects.create(company_id=CO, installation=i, reference='LIV-AMSG96-%s-%s' % (m, k)).id
a = inst('A', technicien_responsable=t, created_by=ADMIN)
out = dict(t=t.id, c=c.id, client=client.id, inst_a=a.id, liv_a=liv(a, 'A'), installs=[a.id], livs=[])
if ${avecAutres ? 'True' : 'False'}:
    b = inst('B', created_by=c)
    c2 = inst('C')
    d = inst('D', technicien_responsable=t2, created_by=c)
    out['installs'] += [b.id, c2.id, d.id]
    out.update(liv_b=liv(b, 'B'), liv_c=liv(c2, 'C'), liv_d=liv(d, 'D'))
sortie(out)`)
}
const nettoyer96 = (d) => py(`from django.contrib.contenttypes.models import ContentType
from apps.installations.models import Installation, Livraison, Intervention
from apps.records.models import Activity
from apps.crm.models import Client
ids = json.loads(${J(J(d.installs))})
for fn in (
    lambda: Activity.objects.filter(content_type=ContentType.objects.get_for_model(Livraison), object_id__in=list(Livraison.objects.filter(installation_id__in=ids).values_list('pk', flat=True))).delete(),
    lambda: Activity.objects.filter(content_type=ContentType.objects.get_for_model(Intervention), object_id__in=list(Intervention.objects.filter(installation_id__in=ids).values_list('pk', flat=True))).delete(),
    lambda: Intervention.objects.filter(installation_id__in=ids).delete(),
    lambda: Livraison.objects.filter(installation_id__in=ids).delete(),
    lambda: Installation.objects.filter(pk__in=ids).delete(),
    lambda: Client.objects.filter(pk=${Number(d.client)}).delete()):
    try:
        fn()
    except Exception:
        pass
sortie(1)`).catch(() => undefined)

etape('PF8.5-AMSG96', ['AMSG96', 'AMSG56'], async ({ page, testInfo }) => {
  const m = marque().toUpperCase()
  const s009 = sonde('C-AMSG-009')
  expect([s009.repro, s009.observe.emplacements_qui_disent_envoye], 'sonde C-AMSG-009 : repro False, aucun emplacement ne dit « envoyé »').toEqual([false, []])
  const d = await montage96(m, true)
  try {
    // « Expédier » par la VRAIE route sur chaque livraison, sans clé d'envoi.
    for (const k of ['liv_a', 'liv_b', 'liv_c', 'liv_d']) {
      const rep = await lireJson(await page.request.post(`${API}/installations/livraisons/${d[k]}/expedier/`, { ...T, data: {} }), `expédier ${k}`)
      expect(rep.statut, `${k} en transit`).toBe('en_transit')
      if ('email_sent' in rep) expect(rep.email_sent, `${k} : email_sent faux`).toBe(false)
    }
    const transit = await py(`from apps.installations.models import Livraison
sortie([[bool(Livraison.objects.get(pk=pk).notifie_transit_le), Livraison.objects.get(pk=pk).statut] for pk in ${J([d.liv_a, d.liv_b, d.liv_c, d.liv_d])}])`)
    expect(transit, 'relu : notifie_transit_le posé (brouillon remis), en transit').toEqual([[true, 'en_transit'], [true, 'en_transit'], [true, 'en_transit'], [true, 'en_transit']])
    // Rappel J-1 sur le chantier A : balayage rejoué dans le shell (le beat ne tourne pas sur le runner).
    const sweep = await py(`import datetime as dt
from django.contrib.contenttypes.models import ContentType
from apps.installations.models import Installation, Intervention, Livraison
from apps.installations.tasks import rappel_rdv_j1, casablanca_today
from apps.records.models import Activity
a = Installation.objects.get(pk=${d.inst_a})
iv = Intervention.objects.create(company_id=a.company_id, installation=a, type_intervention='pose', created_by=U.objects.get(username='demo_admin'),
    date_prevue=casablanca_today() + dt.timedelta(days=1), rdv_confirme=False)
res_sweep = rappel_rdv_j1()
def tache(modele, pk):
    return Activity.objects.filter(content_type=ContentType.objects.get_for_model(modele), object_id=pk, summary='Envoyer ce WhatsApp')
out = dict(emails=res_sweep['emails_envoyes'], interv=iv.id,
           rappel=[[x.assigned_to_id, x.note.count('wa.me/')] for x in tache(Intervention, iv.pk)])
for k, lv in (('a', ${d.liv_a}), ('b', ${d.liv_b}), ('c', ${d.liv_c}), ('d', ${d.liv_d})):
    out['liv_' + k] = [[x.assigned_to_id, x.note.count('wa.me/')] for x in tache(Livraison, lv)]
sortie(out)`)
    expect(sweep.emails, 'sans clé d’envoi : emails_envoyes 0').toBe(0)
    expect(sweep.rappel, 'rappel J-1 : une tâche wa.me assignée au technicien responsable T').toEqual([[d.t, 1]])
    expect(sweep.liv_a, 'livraison A : tâche assignée au responsable T').toEqual([[d.t, 1]])
    expect(sweep.liv_b, 'livraison B (sans responsable) : tâche assignée à son créateur C').toEqual([[d.c, 1]])
    expect(sweep.liv_c, 'livraison C (ni responsable ni créateur) : tâche non assignée').toEqual([[null, 1]])
    expect(sweep.liv_d, 'livraison D (responsable inactif) : tâche assignée au créateur C').toEqual([[d.c, 1]])
    // « Mes activités » de T : GET records/activities/mine/ liste les deux tâches (livraison + rappel).
    const ctxT = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    SESSIONS_T.push(ctxT)
    await connexionApi(ctxT, { username: 'amsg96_t', password: MDP_ESSAI })
    const mine = await lireJson(await ctxT.get(`${API}/records/activities/mine/`, T), 'mes activités')
    const resumes = Object.values(mine).flat().filter((x) => x.summary === 'Envoyer ce WhatsApp')
    expect(resumes.length, `tâches « Envoyer ce WhatsApp » dans « Mes activités » de T (${resumes.length})`).toBeGreaterThanOrEqual(2)
    // Le créateur C ne reçoit pas celles de A.
    const ctxC = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    SESSIONS_T.push(ctxC)
    await connexionApi(ctxC, { username: 'amsg96_c', password: MDP_ESSAI })
    const mineC = await lireJson(await ctxC.get(`${API}/records/activities/mine/`, T), 'mes activités C')
    const idsT = new Set(resumes.map((x) => x.id))
    const idsC = Object.values(mineC).flat().filter((x) => x.summary === 'Envoyer ce WhatsApp').map((x) => x.id)
    expect(idsC.filter((id) => idsT.has(id)), 'aucune tâche commune T / C').toEqual([])
    expect(idsC.length, 'C voit les tâches de B et D').toBeGreaterThanOrEqual(2)
  } finally {
    await nettoyer96(d)
  }
}, { ecart: { base: 'FAIL', raison: "aucun écran de livraison (décision produit, hors Files) ; tâche montrée dans /activites ; lien wa.me non affiché (défaut antérieur, hors Files : MesActivitesPage.jsx targetLink sans entrée livraison/intervention, get_target_phone None hors crm, note wa.me jamais montrée)" } })

etape('PF8.5-AMSG96-ecran', ['AMSG96', 'AMSG56'], async ({ page, context, testInfo }) => {
  const m = marque().toUpperCase()
  const d = await montage96(m, false)
  try {
    const rep = await lireJson(await page.request.post(`${API}/installations/livraisons/${d.liv_a}/expedier/`, { ...T, data: {} }), 'expédier')
    expect(rep.statut).toBe('en_transit')
    const ctxT = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    SESSIONS_T.push(ctxT)
    await connexionApi(ctxT, { username: 'amsg96_t', password: MDP_ESSAI })
    await context.addCookies((await ctxT.storageState()).cookies)
    await page.goto('/activites')
    await expect(page.getByText('Envoyer ce WhatsApp').first(), '« Mes activités » du responsable : la tâche est listée').toBeVisible({ timeout: 60_000 })
    await page.reload()
    await expect(page.getByText('Envoyer ce WhatsApp').first(), 'persistance : toujours listée après rechargement').toBeVisible({ timeout: 60_000 })
  } finally {
    await nettoyer96(d)
  }
}, { ecart: { base: 'FAIL', raison: "aucun écran de livraison (décision produit, hors Files) ; tâche montrée dans /activites ; lien wa.me non affiché (défaut antérieur, hors Files : MesActivitesPage.jsx targetLink sans entrée livraison/intervention, get_target_phone None hors crm, note wa.me jamais montrée)" } })
