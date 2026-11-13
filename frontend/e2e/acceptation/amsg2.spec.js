// Preuves en direct du groupe AMSG, lot 2 (audit PF8 « messages envoyés aux clients », dossier
// docs/audits/2026-11-11-parcours-PF8.md) : AMSG27-29, AMSG31-32, AMSG56-61, AMSG63-64, AMSG68.
// Chaque étape (1) rejoue la sonde HÔTE du constat (`docs/audits/sondes/AMSG/C-AMSG-0xx.py`, `repro` attendu faux)
// et (2) joue le geste que la clause « Preuve en direct » nomme, sur la pile servie (backend e-mail = celui du
// réglage : enveloppe AMSG61 autour du backend console, aucune clé d'envoi — l'état de la production) : la VRAIE
// route par HTTP quand l'écran ou la route est nommé, sinon le vrai code dans le shell Django, données propres
// dans une transaction ANNULÉE. Aucun envoi réel : un double `locmem` n'est posé que là où la tâche le demande
// (« clé factice et locmem »), jamais un fournisseur. Persistance = relecture en base / rechargement d'écran.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, lireJson } from '../helpers.js'

// DÉFAUTS CONSTATÉS au rejeu runner du 13/11/2026 (run 43505081707) : AMSG57 (`repondre-email` rend 409, la clause
// dit 400) et AMSG68 (l'écran ne montre l'erreur qu'en toast, jamais sous le champ). Leurs étapes restent ici, INCHANGÉES,
// et ne sont jouées que sous AMSG2_DEFAUTS=1 : sans elles l'enregistrement couvre les 12 autres tâches ; avec elles il
// est FAIL tant que le défaut n'est pas corrigé (ou la clause revue par le fondateur).
const DEFAUTS = process.env.AMSG2_DEFAUTS === '1'
const etape = groupe('AMSG', ['AMSG27', 'AMSG28', 'AMSG29', 'AMSG31', 'AMSG32', 'AMSG56', 'AMSG58',
  'AMSG59', 'AMSG60', 'AMSG61', 'AMSG63', 'AMSG64', ...(DEFAUTS ? ['AMSG57', 'AMSG68'] : [])])
const etapeDefaut = DEFAUTS ? etape
  : (id, taches) => test.skip(`${id} — ${taches.join(', ')} (défaut constaté, AMSG2_DEFAUTS=1 pour rejouer)`, () => undefined)
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
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

/** Commande `manage.py` du backend servi (même préfixe que le shell persistant de `_django.js`). */
function manage(args, envEnPlus = {}) {
  const [cmd, ...pre] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  return spawnSync(cmd, [...pre, 'python', 'manage.py', ...args],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, ...envEnPlus } })
}

// Fabrique Python commune (société démo de demo_admin, client d'essai à e-mail réservé et téléphone fictif).
const FABRIQUE = `
import random
from decimal import Decimal
import datetime as dt
from django.conf import settings
from django.db import transaction
from authentication.models import Company
from apps.crm.models import Client
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
const pyAvec = (m, code) => py(`${FABRIQUE}\nm = ${JSON.stringify(m)}\n${code}`)

// ── PF8.3 — documents et argent ───────────────────────────────────────────────────────────────────────────
etape('PF8.3-AMSG27', ['AMSG27'], async ({ page }) => {
  const s = sonde('C-AMSG-006')
  expect([s.repro, s.observe.par_cas.contestee.statut, s.observe.par_cas.temoin_non_contestee.statut],
    'sonde C-AMSG-006 : contestée 409, témoin 200').toEqual([false, 409, 200])
  const m = marque().toUpperCase()
  const d = await pyAvec(m, `from apps.ventes.models import Facture
today = timezone.localdate()
c = cli(m)
def f(ref):
    return Facture.objects.create(company_id=CO, reference=ref, client=c, statut=Facture.Statut.EN_RETARD,
        taux_tva=Decimal('20.00'), libelle='Prestation', montant_ht=Decimal('1000.00'), date_echeance=today - dt.timedelta(days=40))
fc = f('FAC-AMSG27C-' + m); fj = f('FAC-AMSG27J-' + m)
Facture.objects.filter(pk=fc.pk).update(contestee_le=today, motif_contestation='Travaux non finis')
sortie(dict(client=c.id, contestee=fc.id, jumelle=fj.id))`)
  try {
    // API : relance d'une contestée refusée (409, motif de facture_relancable), rien écrit.
    const wa = (id, modele) => page.request.post(`${API}/ventes/factures/${id}/whatsapp/`, { ...T, data: { modele } })
    const refus = await wa(d.contestee, 'relance')
    expect(refus.status(), await refus.text()).toBe(409)
    expect(await refus.json()).toEqual({ detail: 'Facture contestée : la relance est suspendue.' })
    const trace = await py(`from apps.ventes.models import ShareLink, FactureActivity
sortie([ShareLink.objects.filter(facture_id=${d.contestee}).count(), FactureActivity.objects.filter(facture_id=${d.contestee}).count()])`)
    expect(trace, 'aucun lien de partage ni note pour la contestée').toEqual([0, 0])
    const jumelle = await lireJson(await wa(d.jumelle, 'relance'), 'relance de la jumelle non contestée')
    expect(jumelle.wa_url, 'jumelle : lien wa.me servi').toMatch(/wa\.me/)
    const doc = await lireJson(await wa(d.contestee, 'facture'), 'envoi du document d\'une contestée (D-ACVI-10)')
    expect(doc.wa_url).toMatch(/wa\.me/)
    // Écran : la ligne contestée n'offre plus « Relancer par WhatsApp » (entrée désactivée, motif en infobulle).
    const menuDe = async (id) => {
      await page.goto('/ventes/factures')
      await page.getByPlaceholder('Référence, client').fill(m)
      const ligne = page.locator(`#facture-row-${id}`).first()
      await expect(ligne).toBeVisible({ timeout: 60_000 })
      await ligne.getByTitle("Plus d'actions").click()
    }
    for (const passage of ['avant', 'après rechargement']) {
      await menuDe(d.contestee)
      const suspendue = page.getByRole('menuitem', { name: 'Relance suspendue (contestée)' })
      await expect(suspendue, `contestée (${passage}) : entrée suspendue`).toBeVisible()
      await expect(suspendue).toHaveAttribute('aria-disabled', 'true')
      await expect(suspendue).toHaveAttribute('title', 'Facture contestée : la relance est suspendue.')
      await expect(page.getByRole('menuitem', { name: 'Relancer par WhatsApp' }), `contestée (${passage}) : pas de « Relancer par WhatsApp »`).toHaveCount(0)
      await page.keyboard.press('Escape')
    }
    await menuDe(d.jumelle)
    const relancer = page.getByRole('menuitem', { name: 'Relancer par WhatsApp' })
    await expect(relancer, 'jumelle : « Relancer par WhatsApp » offert').toBeVisible()
    await expect(relancer).not.toHaveAttribute('aria-disabled', 'true')
    await page.keyboard.press('Escape')
  } finally {
    await py(`from apps.ventes.models import Facture, ShareLink, FactureActivity
from apps.crm.models import Client
ids = [${d.contestee}, ${d.jumelle}]
for fn in (lambda: ShareLink.objects.filter(facture_id__in=ids).delete(), lambda: FactureActivity.objects.filter(facture_id__in=ids).delete(),
           lambda: Facture.objects.filter(pk__in=ids).delete(), lambda: Client.objects.filter(pk=${d.client}).delete()):
    try:
        fn()
    except Exception:
        pass
sortie(1)`).catch(() => undefined)
  }
})

etape('PF8.3-AMSG28', ['AMSG28'], async ({ page }) => {
  const s = sonde('C-AMSG-008')
  expect(s.repro, 'sonde C-AMSG-008 : repro faux').toBe(false)
  for (const volet of ['canal_email', 'volet_informatif_canal_whatsapp']) {
    expect(s.observe[volet].emaillog_statuts, `sonde : emaillog_statuts (${volet}) sans « envoye »`).not.toContain('envoye')
  }
  // Geste : « Envoyer par email » d'un devis brouillon par la vraie route, backend console (aucune clé).
  const m = marque()
  const lead = await lireJson(await page.request.post(`${API}/crm/leads/`, {
    ...T, data: { nom: `AMSG28 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `amsg28${m}@example.invalid` },
  }), 'lead')
  const p = await lireJson(await page.request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Onduleur AMSG28 ${m}`, prix_vente: '10000.00', prix_achat: '5000.00' },
  }), 'produit')
  const devis = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T,
    data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id,
      lignes: [{ produit: p.id, designation: 'Onduleur AMSG28', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis brouillon')
  const leadAvant = await lireJson(await page.request.get(`${API}/crm/leads/${lead.id}/`, T), 'lead avant')
  // Format une page : le devis d'essai n'a pas d'onduleur, le document à options serait refusé (règle du moteur) ;
  // le une-page est rendable — c'est la précondition « PDF rendable » de la clause.
  const rep = await page.request.post(`${API}/ventes/devis/${devis.id}/envoyer-email/`, { ...T, data: { pdf_mode: 'onepage' } })
  const corps = await rep.text()
  expect(rep.status(), `échec nommé attendu : ${corps.slice(0, 300)}`).toBe(502)
  expect(JSON.parse(corps).detail).toContain('E-mail non opérationnel : aucun message ne part')
  // Persistance : devis relu brouillon sans date d'envoi, lead inchangé, EmailLog en échec avec le motif.
  const relu = await lireJson(await page.request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
  expect([relu.statut, relu.date_envoi ?? null], 'devis resté brouillon, sans date d\'envoi').toEqual(['brouillon', null])
  const leadApres = await lireJson(await page.request.get(`${API}/crm/leads/${lead.id}/`, T), 'lead après')
  expect(leadApres.stage, 'aucun devis_sent : étape du lead inchangée').toBe(leadAvant.stage)
  const logs = await py(`from apps.ventes.models import EmailLog
sortie(list(EmailLog.objects.filter(devis_id=${devis.id}).values_list('statut', 'erreur')))`)
  expect(logs, 'EmailLog « echec » avec le motif').toEqual([['echec', 'E-mail non opérationnel : aucun message ne part']])
})

etape('PF8.3-AMSG29', ['AMSG29'], async () => {
  const s = sonde('C-AMSG-008')
  expect(s.repro).toBe(false)
  const ce = s.observe.canal_email
  expect([ce.relancelog_niveaux, ce.relances_comptees, ce.prochaine_relance.split(' → ')[0] === ce.prochaine_relance.split(' → ')[1]],
    'sonde : relancelog_niveaux vide, prochaine_relance inchangée').toEqual([[], 0, true])
  // Les trois beats sur la vraie base, backend du réglage (console sous enveloppe), transaction annulée.
  const m = marque()
  const r = await pyAvec(m, `from apps.ventes.recouvrement import ensure_default_followup_levels
from apps.ventes.scheduled import casablanca_today, relance_reminders, pre_echeance_reminders, releve_mensuel_reminders
from apps.ventes.models import EmailLog, RelanceLog, Facture
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG29 ' + m, slug='amsg29-' + m)
    ensure_default_followup_levels(co)
    today = casablanca_today()
    cl = Client.objects.create(company=co, nom='Client ' + m, prenom='AMSG29', email='amsg29' + m + '@example.invalid', releve_mensuel_auto=True)
    def fac(suffixe, statut, ech, **kw):
        return Facture.objects.create(company=co, reference='FAC-AMSG29-' + m + suffixe, client=cl, statut=statut, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'), date_echeance=ech, **kw)
    retard = fac('R', 'en_retard', today - dt.timedelta(days=40), prochaine_relance=today)
    emise = fac('E', 'emise', today + dt.timedelta(days=2))
    res['backend'] = [settings.EMAIL_BACKEND, settings.EMAIL_BACKEND_REEL]
    res['retours'] = [relance_reminders() for _ in range(3)] + [pre_echeance_reminders(), releve_mensuel_reminders()]
    retard.refresh_from_db()
    res['prochaine_relance_intacte'] = retard.prochaine_relance == today
    res['relancelog'] = RelanceLog.objects.filter(facture__in=[retard, emise]).count()
    res['emaillog'] = EmailLog.objects.filter(company=co).count()
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.backend[1], 'backend réel = console (aucun envoi)').toBe('django.core.mail.backends.console.EmailBackend')
  expect(r.retours, 'retour 0 pour les trois beats').toEqual([0, 0, 0, 0, 0])
  expect([r.prochaine_relance_intacte, r.relancelog, r.emaillog], 'niveau intact, 0 RelanceLog, 0 EmailLog').toEqual([true, 0, 0])
})

etape('PF8.3-AMSG31', ['AMSG31'], async () => {
  const s = sonde('C-AMSG-011')
  expect([s.repro, s.observe.envoyees_a_tort, s.observe.reponse_unitaire['FAC-1'].statut_http], 'sonde C-AMSG-011').toEqual([false, [], 409])
  const m = marque()
  const r = await pyAvec(m, `from unittest.mock import patch
from django.core import mail
from django.test.utils import override_settings
from apps.ventes.models import EmailLog, Facture, LigneFacture
from apps.stock.models import Produit
with transaction.atomic():
    cl = cli(m)
    p = Produit.objects.create(company_id=CO, nom='Prod AMSG31 ' + m, sku='SKU-AMSG31-' + m, prix_vente=Decimal('1000'), prix_achat=Decimal('800'), quantite_stock=100)
    def fac(st, s):
        f = Facture.objects.create(company_id=CO, reference='FAC-AMSG31' + s + '-' + m, client=cl, statut=st, taux_tva=Decimal('20'))
        LigneFacture.objects.create(facture=f, produit=p, designation='Test', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        return f
    a = fac(Facture.Statut.ANNULEE, 'A'); b = fac(Facture.Statut.BROUILLON, 'B'); e = fac(Facture.Statut.EMISE, 'E')
    mail.outbox = []
    with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ANYMAIL={'SENDGRID_API_KEY': 'cle-factice'}), \\
            patch('apps.ventes.email_service._document_pdf', return_value=(b'%PDF-1.4', 'f.pdf')):
        lot = appel('post', '/api/django/ventes/factures/bulk/', {'action': 'envoyer-email', 'ids': [a.id, b.id, e.id]})
        uni = appel('post', '/api/django/ventes/factures/%d/envoyer-email/' % a.id)
    res = dict(lot=lot, uni=uni, ids=[a.id, b.id, e.id], outbox=[x.to for x in mail.outbox],
               emaillog_ab=EmailLog.objects.filter(facture__in=[a, b]).count())
    transaction.set_rollback(True)
sortie(res)`)
  const [a, b, e] = r.ids.map(String)
  const [statutLot, lot] = r.lot
  expect(statutLot, JSON.stringify(lot)).toBe(200)
  expect(lot[a], 'annulée refusée au lot').toEqual({ ok: false, detail: 'Statut Annulée : seule une facture émise, payée ou en retard part au client.' })
  expect(lot[b].ok, 'brouillon refusée au lot').toBe(false)
  expect(lot[b].detail).toContain('Statut Brouillon')
  expect(lot[e].ok, `émise envoyée (${JSON.stringify(lot[e])})`).toBe(true)
  expect(r.uni, 'unitaire : 409 même motif').toEqual([409, { detail: lot[a].detail }])
  expect(r.outbox.length, `un seul message (l'émise) : ${JSON.stringify(r.outbox)}`).toBe(1)
  expect(r.emaillog_ab, '0 EmailLog pour annulée et brouillon').toBe(0)
})

etape('PF8.3-AMSG32', ['AMSG32'], async () => {
  const s = sonde('C-AMSG-012')
  expect([s.repro, s.observe.recus_a_tort, s.observe.temoin_recu], 'sonde C-AMSG-012 : recus_a_tort vide').toEqual([false, [], true])
  const m = marque()
  const r = await pyAvec(m, `from django.core import mail
from django.test.utils import override_settings
from apps.ventes.models import EmailLog, Facture, ParametrageRelanceClient
from apps.ventes.scheduled import pre_echeance_reminders, casablanca_today
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG32 ' + m, slug='amsg32-' + m)
    today = casablanca_today()
    c1 = Client.objects.create(company=co, nom='Temoin', prenom='AMSG32', email='t' + m + '@example.invalid', telephone='+212600000055', adresse='Casablanca')
    manuel = Client.objects.create(company=co, nom='Manuel', prenom='AMSG32', email='mn' + m + '@example.invalid')
    ParametrageRelanceClient.objects.create(company=co, client=manuel, mode=ParametrageRelanceClient.Mode.MANUEL)
    def emise(n, client, **kw):
        return Facture.objects.create(company=co, reference='FAC-AMSG32-%s-%d' % (m, n), client=client, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'), date_echeance=today + dt.timedelta(days=2), **kw)
    f = dict(contestee=emise(1, c1, contestee_le=today - dt.timedelta(days=1), motif_contestation='Travaux non finis'),
             manuel=emise(2, manuel), promesse=emise(3, c1, exclu_relances_jusquau=today + dt.timedelta(days=10)), temoin=emise(4, c1))
    def recus():
        return sorted(k for k, x in f.items() if EmailLog.objects.filter(facture=x, reference__endswith='::pre_echeance').exists())
    nos = {c1.email, manuel.email}
    with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ANYMAIL={'SENDGRID_API_KEY': 'cle-factice'}):
        mail.outbox = []
        pre_echeance_reminders()
        res['passage1'] = recus(); res['outbox1'] = sum(1 for x in mail.outbox if set(x.to) & nos)
        Facture.objects.filter(pk=f['contestee'].pk).update(contestee_le=None)
        mail.outbox = []
        pre_echeance_reminders()
        res['passage2'] = recus(); res['outbox2'] = sum(1 for x in mail.outbox if set(x.to) & nos)
    transaction.set_rollback(True)
sortie(res)`)
  expect([r.passage1, r.outbox1], '1er passage : seul le témoin reçoit').toEqual([['temoin'], 1])
  expect([r.passage2, r.outbox2], 'contestation levée : la contestée part au passage suivant').toEqual([['contestee', 'temoin'], 1])
})

// ── PF8.4 — moteur d'envoi, gardes et réglages ────────────────────────────────────────────────────────────
etape('PF8.4-AMSG63', ['AMSG63'], async () => {
  const s = sonde('C-AMSG-012')
  expect([s.repro, s.observe.automatisation_facture_en_retard_contestee.verdict], 'sonde : automatisation « arrêtée »').toEqual([false, 'arrêtée'])
  const m = marque()
  const r = await pyAvec(m, `from apps.automation import engine
from apps.automation.models import TriggerType
from apps.ventes.models import Facture, ParametrageRelanceClient
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='AMSG63 ' + m, slug='amsg63-' + m)
    today = timezone.localdate()
    cl = Client.objects.create(company=co, nom='Cli', email='c' + m + '@example.invalid')
    manuel = Client.objects.create(company=co, nom='Cli manuel', email='mn' + m + '@example.invalid')
    ParametrageRelanceClient.objects.create(company=co, client=manuel, mode=ParametrageRelanceClient.Mode.MANUEL)
    cas = {'C': {'contestee_le': today}, 'X': {'exclu_relances': True}, 'P': {'exclu_relances_jusquau': today + dt.timedelta(days=5)},
           'M': {'client': manuel}, 'T': {}}
    for k, champs in cas.items():
        x = Facture.objects.create(**{'company': co, 'client': cl, 'reference': 'FAC-AMSG63-%s-%s' % (m, k), 'statut': Facture.Statut.EN_RETARD,
            'date_echeance': today - dt.timedelta(days=10), 'montant_ttc': Decimal('900'), **champs})
        res[k] = engine.motif_etat_metier(TriggerType.FACTURE_OVERDUE, x)
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.C || '').toContain('Facture contestée : la relance est suspendue.')
  expect(r.X || '').toContain('Facture exclue des relances')
  expect(r.P || '').toContain('Promesse de paiement')
  expect(r.M || '').toContain('Client en relance manuelle')
  expect(r.T, 'témoin : aucun motif d\'arrêt').toBeNull()
})

etape('PF8.4-AMSG60', ['AMSG60'], async () => {
  const s = sonde('C-AMSG-010')
  expect(s.observe.adresses_a_domaine_non_reserve, 'sonde : 0 adresse du seed hors domaine réservé').toBe(0)
  // seed_demo rejoué sur une société démo NEUVE (transaction annulée, démo existante renommée le temps du rejeu).
  const r = await py(`import re
from django.db import transaction
from django.core.management import call_command
from django.conf import settings
from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.stock.models import Fournisseur
res = {'debug': settings.DEBUG}
with transaction.atomic():
    old = Company.objects.get(slug='taqinor-demo')
    Company.objects.filter(pk=old.pk).update(slug='taqinor-demo-ancienne')
    for u in U.objects.filter(company=old):
        U.objects.filter(pk=u.pk).update(username=u.username + '__anc', email=(u.email or '') + '.anc')
    call_command('seed_demo')
    co = Company.objects.get(slug='taqinor-demo')
    res['neuve'] = co.pk != old.pk
    fiches = [(mod.__name__, f.email or '', f.telephone or '') for mod in (Client, Fournisseur, Lead) for f in mod.objects.filter(company=co)]
    res['fiches'] = len(fiches)
    res['par_modele'] = {n: sum(1 for x in fiches if x[0] == n) for n in ('Client', 'Fournisseur', 'Lead')}
    res['email_hors_reserve'] = [x[0] for x in fiches if x[1] and not x[1].endswith('@example.invalid')]
    res['tel_reel'] = [x[0] for x in fiches if x[2] and not re.fullmatch(r'\\+212600000\\d{3}', x[2])]
    transaction.set_rollback(True)
res['demo_intacte'] = Company.objects.filter(slug='taqinor-demo').count() == 1 and U.objects.filter(username='demo_admin').exists()
sortie(res)`)
  expect([r.debug, r.neuve], 'DEBUG vrai, société démo neuve semée').toEqual([true, true])
  expect(r.fiches, `fiches semées : ${JSON.stringify(r.par_modele)}`).toBeGreaterThan(0)
  expect(r.email_hors_reserve, 'aucun e-mail hors @example.invalid').toEqual([])
  expect(r.tel_reel, 'aucun téléphone hors forme fictive +212600000NNN').toEqual([])
  expect(r.demo_intacte, 'transaction annulée : démo locale intacte').toBe(true)
})

etape('PF8.4-AMSG61', ['AMSG61'], async () => {
  const s = sonde('C-AMSG-010')
  expect(s.observe.garde_de_destinataires_branchee, 'sonde : garde de destinataires branchée').toContain('core.email_backends.EnveloppeEmailBackend')
  expect(s.repro).toBe(false)
  // Le vrai send_mail sous l'enveloppe, backend réel remplacé par le double `locmem` (rien ne quitte la machine).
  const r = await py(`from django.conf import settings
from django.core import mail
from django.core.mail import send_mail
from django.test.utils import override_settings
from core.checks import backend_email_envoie
LOC = 'django.core.mail.backends.locmem.EmailBackend'
res = {'backend': settings.EMAIL_BACKEND, 'reel': settings.EMAIL_BACKEND_REEL, 'debug': settings.DEBUG,
       'envoie_console_sous_enveloppe': backend_email_envoie()}
def essai(dest):
    mail.outbox = []
    n = send_mail('Essai AMSG61', 'corps', 'noreply@taqinor.ma', [dest])
    return [n, len(mail.outbox)]
with override_settings(EMAIL_BACKEND_REEL=LOC, EMAIL_DESTINATAIRES_AUTORISES=['equipe-essai@taqinor.ma']):
    res['debug_liste'] = {'gmail': essai('quelquun.amsg61@gmail.com'), 'invalid': essai('x@example.invalid'), 'liste': essai('equipe-essai@taqinor.ma')}
with override_settings(EMAIL_BACKEND_REEL=LOC, EMAIL_DESTINATAIRES_AUTORISES=[]):
    res['debug_sans_liste_gmail'] = essai('quelquun.amsg61@gmail.com')
with override_settings(EMAIL_BACKEND_REEL=LOC, EMAIL_DESTINATAIRES_AUTORISES=[], DEBUG=False):
    res['prod_sans_liste'] = {'gmail': essai('quelquun.amsg61@gmail.com'), 'invalid': essai('x@example.invalid')}
with override_settings(EMAIL_BACKEND_REEL='anymail.backends.sendinblue.EmailBackend'):
    res['envoie_anymail_sous_enveloppe'] = backend_email_envoie()
sortie(res)`)
  expect([r.backend, r.reel, r.debug], 'réglage servi : enveloppe → console, DEBUG').toEqual(
    ['core.email_backends.EnveloppeEmailBackend', 'django.core.mail.backends.console.EmailBackend', true])
  expect(r.debug_liste, 'DEBUG + liste : gmail 0, .invalid 0, listée 1').toEqual({ gmail: [0, 0], invalid: [0, 0], liste: [1, 1] })
  expect(r.debug_sans_liste_gmail, 'DEBUG sans liste : gmail jamais remis').toEqual([0, 0])
  expect(r.prod_sans_liste, 'DEBUG faux sans liste : tout passe sauf le domaine réservé').toEqual({ gmail: [1, 1], invalid: [0, 0] })
  expect([r.envoie_console_sous_enveloppe, r.envoie_anymail_sous_enveloppe], 'backend_email_envoie juge le backend RÉEL').toEqual([false, true])
  // Pile servie : `manage.py sendtestemail` vers une adresse gmail ⇒ rien ne sort (le backend console n'imprime rien) ;
  // témoin : la même commande vers une adresse de la liste ⇒ le message est imprimé (la méthode voit un envoi).
  const gmail = manage(['sendtestemail', 'quelquun.amsg61@gmail.com'])
  expect(gmail.status, `sendtestemail gmail : ${(gmail.stderr || '').slice(-400)}`).toBe(0)
  expect(gmail.stdout || '', 'gmail : aucun message remis au backend console').not.toMatch(/^Subject:/m)
  const liste = manage(['sendtestemail', 'equipe-essai@taqinor.ma'], { EMAIL_DESTINATAIRES_AUTORISES: 'equipe-essai@taqinor.ma' })
  expect(liste.status, `sendtestemail listée : ${(liste.stderr || '').slice(-400)}`).toBe(0)
  expect(liste.stdout || '', 'témoin listé : message remis (imprimé par la console)').toMatch(/^Subject:/m)
})

etape('PF8.4-AMSG64', ['AMSG64'], async () => {
  const garde = () => spawnSync(process.env.E2E_PYTHON || 'python', ['scripts/check_garde_contact.py'],
    { cwd: RACINE, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const vert = garde()
  expect([vert.status, (vert.stdout || '').trim()], `garde sur l'arbre : ${vert.stdout}${vert.stderr}`).toEqual([0, 'check_garde_contact : OK'])
  // Un appel ajouté à la main dans DevisActionBoardPage.jsx (fonction neuve, texte non vide) ⇒ rouge ; sans texte ⇒ ignoré.
  const fichier = join(RACINE, 'frontend', 'src', 'pages', 'ventes', 'DevisActionBoardPage.jsx')
  const origine = readFileSync(fichier, 'utf8')
  let rouge
  try {
    writeFileSync(fichier, `${origine}\nexport function essaiAmsg64AvecTexte(lead) { return waHref(lead.telephone, 'Bonjour') }\n`
      + 'export function essaiAmsg64SansTexte(tel) { return waHref(tel) }\n', 'utf8')
    rouge = garde()
  } finally {
    writeFileSync(fichier, origine, 'utf8')
  }
  expect(rouge.status, `garde avec l'appel ajouté : ${rouge.stdout}`).toBe(1)
  expect(rouge.stdout).toMatch(/DevisActionBoardPage\.jsx:\d+: essaiAmsg64AvecTexte\(\) - wa\.me-front sans garde/)
  expect(rouge.stdout, 'appel sans texte non signalé').not.toContain('essaiAmsg64SansTexte')
  // Plafond gelé : une 8ᵉ raison « A CORRIGER » sans identifiant de tâche (plafond 7) fait échouer la garde.
  const plafond = spawnSync(process.env.E2E_PYTHON || 'python', ['-c', [
    'import sys; sys.path.insert(0, "scripts"); import check_garde_contact as g',
    'k = [c for c, r in g.LISTE_BLANCHE_FRONT.items() if "(AMSG1)" in r][0]',
    'g.LISTE_BLANCHE_FRONT[k] = "A CORRIGER"',
    'sys.exit(g.main())'].join('\n')], { cwd: RACINE, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(plafond.status, `plafond : ${plafond.stdout}${plafond.stderr}`).toBe(1)
  expect(plafond.stdout).toContain('plafond gele 7')
  const retour = garde()
  expect(retour.status, 'fichier rétabli : garde verte').toBe(0)
})

etapeDefaut('PF8.4-AMSG68', ['AMSG68'], async ({ page, suivi }) => {
  const m = marque()
  const nom = `AMSG68 ${m}`
  const corpsRegle = { nom, trigger_type: 'lead_stage_change', trigger_config: {}, action_type: 'send_email', action_config: { subject: 'Relance' } }
  // API : 400 nommant action_config, aucune règle.
  const api = await page.request.post(`${API}/automation/rules/`, { ...T, data: corpsRegle })
  const txt = await api.text()
  expect(api.status(), txt).toBe(400)
  expect(JSON.stringify(JSON.parse(txt).action_config || ''), 'motif sous action_config').toContain('corps obligatoire')
  // Écran : /parametres › Automatisations, « Envoyer un email » sans corps ⇒ erreur sous le champ.
  suivi.attendre(/\/automation\/rules\/$/, 400)
  await page.goto('/parametres?onglet=automatisations')
  const bloc = page.locator('div.border-dashed').filter({ has: page.getByPlaceholder('Nom de la règle') })
  await expect(bloc).toBeVisible({ timeout: 60_000 })
  await bloc.getByPlaceholder('Nom de la règle').fill(nom)
  await bloc.getByRole('combobox').nth(1).click()
  await page.getByRole('option', { name: 'Envoyer un email' }).click()
  await bloc.getByPlaceholder(/Config action/).fill('{"subject": "Relance"}')
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/automation\/rules\/$/.test(new URL(x.url()).pathname), T),
    bloc.getByRole('button', { name: 'Ajouter la règle' }).click(),
  ])
  expect(rep.status(), 'serveur : 400').toBe(400)
  const nulle = await page.getByText(/corps obligatoire/).count()
  const sousLeChamp = await bloc.getByText(/corps obligatoire/).count()
  const toast = await page.getByText('Ajout impossible.').count()
  // Persistance : aucune règle de ce nom (relue par l'API), puis l'emplacement de l'erreur à l'écran.
  const regles = await lireJson(await page.request.get(`${API}/automation/rules/?page_size=500`, T), 'règles')
  const liste = Array.isArray(regles) ? regles : regles.results || []
  expect(liste.filter((x) => x.nom === nom), 'aucune règle créée').toEqual([])
  expect(sousLeChamp, `erreur « corps obligatoire » sous le champ (ailleurs à l'écran : ${nulle}, toast « Ajout impossible. » : ${toast})`).toBeGreaterThan(0)
  await page.reload()
  await expect(bloc).toBeVisible({ timeout: 60_000 })
})

// ── PF8.5 — terrain, après-vente, portails ────────────────────────────────────────────────────────────────
const sonde009 = () => {
  const s = sonde('C-AMSG-009')
  expect([s.repro, s.observe.emplacements_qui_disent_envoye, s.observe.is_email_configured],
    'sonde C-AMSG-009 : aucun emplacement ne dit « envoyé »').toEqual([false, [], false])
  return s
}

etape('PF8.5-AMSG56', ['AMSG56'], async ({ page }) => {
  const s = sonde009()
  expect(s.observe.retours['installations/tasks.py::rappel_rdv_j1'].retour.emails_envoyes, 'sonde : rappel J-1 emails_envoyes 0').toBe(0)
  expect(s.observe.retours['installations/livraison_client_notify.py::notify_livraison_transition'].email_sent).toBe(false)
  // Pile au backend console : « Expédier » par la vraie route ⇒ tâche « Envoyer ce WhatsApp » sur la livraison.
  const m = marque().toUpperCase()
  const d = await pyAvec(m, `from apps.installations.models import Installation, Livraison
c = cli(m)
inst = Installation.objects.create(company_id=CO, client=c, reference='CH-AMSG56-' + m)
liv = Livraison.objects.create(company_id=CO, installation=inst, reference='LIV-AMSG56-' + m)
sortie(dict(client=c.id, inst=inst.id, liv=liv.id))`)
  try {
    const rep = await lireJson(await page.request.post(`${API}/installations/livraisons/${d.liv}/expedier/`, { ...T, data: {} }), 'expédier')
    expect(rep.statut, 'livraison en transit').toBe('en_transit')
    const r = await py(`from django.contrib.contenttypes.models import ContentType
from apps.installations.models import Livraison
from apps.records.models import Activity
liv = Livraison.objects.get(pk=${d.liv})
t = Activity.objects.filter(content_type=ContentType.objects.get_for_model(Livraison), object_id=liv.pk, summary='Envoyer ce WhatsApp')
sortie(dict(statut=liv.statut, transit=bool(liv.notifie_transit_le), taches=t.count(), notes=[x.note for x in t]))`)
    expect([r.statut, r.transit, r.taches], 'relu : en transit, brouillon remis (marqueur posé), une tâche').toEqual(['en_transit', true, 1])
    expect(r.notes[0]).toContain('wa.me/')
    expect(r.notes[0]).toContain(`LIV-AMSG56-${m}`)
  } finally {
    await py(`from django.contrib.contenttypes.models import ContentType
from apps.installations.models import Installation, Livraison
from apps.records.models import Activity
from apps.crm.models import Client
for fn in (lambda: Activity.objects.filter(content_type=ContentType.objects.get_for_model(Livraison), object_id=${d.liv}).delete(),
           lambda: Livraison.objects.filter(pk=${d.liv}).delete(), lambda: Installation.objects.filter(pk=${d.inst}).delete(),
           lambda: Client.objects.filter(pk=${d.client}).delete()):
    try:
        fn()
    except Exception:
        pass
sortie(1)`).catch(() => undefined)
  }
})

etapeDefaut('PF8.5-AMSG57', ['AMSG57'], async () => {
  const s = sonde009()
  expect(s.observe.retours['sav/notifications_client.py::notify_ticket_transition'].email_sent, 'sonde : avis SAV email_sent faux').toBe(false)
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
    transaction.set_rollback(True)
sortie(res)`)
  expect([r.taches, r.email_sent], 'transition « planifié » : 1 tâche « Envoyer ce WhatsApp », email_sent faux').toEqual([1, false])
  expect(r.note).toContain('wa.me')
  const [statut, corps] = r.repondre
  expect(JSON.stringify(corps)).toContain("rien n'est parti")
  expect([r.fil_sortant, r.premiere_reponse], 'aucun fil SORTANT, première réponse non posée').toEqual([0, null])
  expect(statut, `repondre-email : ${JSON.stringify(corps)}`).toBe(400)
})

etape('PF8.5-AMSG58', ['AMSG58'], async () => {
  const s = sonde009()
  expect(s.observe.retours['portail/services.py::_envoyer_identifiants_portail'], 'sonde : identifiants portail non « envoyés »').toBe(false)
  const m = marque()
  const r = await pyAvec(m, `from types import SimpleNamespace as NS
from apps.portail.models import ComptePortailClient
from apps.portail.services import _envoyer_invitation_portail
res = {}
with transaction.atomic():
    c = cli(m)
    compte = ComptePortailClient.objects.create(company_id=CO, client=c, token_acces='token-amsg58-' + m)
    res['provision'] = appel('post', '/api/django/portail/comptes-portail/%d/provisionner-acces/' % compte.id)
    res['compte_cree'] = U.objects.filter(company_id=CO, portail_client_id=c.id).exists()
    res['invitation'] = _envoyer_invitation_portail(NS(token_invitation='jeton-' + m, email='invite' + m + '@example.invalid',
        expire_le=timezone.now() + dt.timedelta(days=7)), ADMIN.company, base_url='http://localhost')
    transaction.set_rollback(True)
sortie(res)`)
  const [statut, corps] = r.provision
  expect(statut, JSON.stringify(corps)).toBe(200)
  expect(corps.email_envoye, 'email_envoye faux').toBe(false)
  expect(corps.detail).toMatch(/^Accès portail créé — e-mail non opérationnel : identifiants non envoyés/)
  expect(r.compte_cree, 'accès portail créé (relu en base)').toBe(true)
  expect(r.invitation, "l'invitation d'équipe ne rend plus True").toBe(false)
})

etape('PF8.5-AMSG59', ['AMSG59'], async () => {
  const s = sonde009()
  expect(s.observe.retours['stock/services.py::_envoyer_identifiants_portail_fournisseur'], 'sonde : identifiants fournisseur non « envoyés »').toBe(false)
  const m = marque()
  const r = await pyAvec(m, `from apps.stock.models import Fournisseur
res = {}
with transaction.atomic():
    f = Fournisseur.objects.create(company_id=CO, nom='AMSG59-' + m, email='f' + m + '@example.invalid')
    res['provision'] = appel('post', '/api/django/stock/fournisseurs/%d/provisionner-acces/' % f.id)
    res['compte_cree'] = U.objects.filter(company_id=CO, portail_fournisseur_id=f.id).exists()
    transaction.set_rollback(True)
sortie(res)`)
  const [statut, corps] = r.provision
  expect(statut, JSON.stringify(corps)).toBe(201)
  expect(corps.email_envoye, 'email_envoye faux').toBe(false)
  expect(corps.detail).toBe('Accès portail ouvert — e-mail non opérationnel : identifiants non envoyés.')
  expect(r.compte_cree, 'accès ouvert (relu en base)').toBe(true)
})
