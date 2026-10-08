"""YBW51 — récepteur `POST /api/django/crm/webhooks/demande-rdv/` (site YanBow).

Gardes prouvées ici (contrat `contract_samples/demande_rdv_site.json`, YBW50) :
  * société tirée de la CLÉ, jamais du corps, aucun repli : clé de A signée
    avec le secret de B → 401 et 0 lead NULLE PART ;
  * le vecteur de signature doré du contrat vérifie ;
  * rejeu → un seul lead, même avec un AUTRE en-tête `Idempotency-Key` ;
  * requête non signée → 0 ligne `ProcessedWebhookEvent` (rien écrit) ;
  * chaque clé du contrat est mappée par la vue ou listée dans `refus` ;
  * pas de devis automatique (le récepteur taqinor.ma en lance un).
"""
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company
from core.idempotency import ProcessedWebhookEvent

from apps.crm import webhooks
from apps.crm.models import Lead, LeadActivity

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'demande_rdv_site.json').read_text(encoding='utf-8'))

SECRET_A = 'a' * 64
SECRET_B = 'b' * 64


def signer(secret, corps, t=None):
    t = int(time.time()) if t is None else t
    hexa = hmac.new(secret.encode('utf-8'), f'{t}.'.encode('utf-8') + corps,
                    hashlib.sha256).hexdigest()
    return f't={t},v1={hexa}'


def corps_valide(**extra):
    corps = dict(CONTRAT['corps'])
    corps['idempotency_key'] = str(uuid.uuid4())
    corps.update(extra)
    return corps


class TestContratEtSignature(TestCase):
    def test_vecteur_dore_du_contrat_verifie(self):
        v = CONTRAT['vecteur_signature']
        corps = v['corps_brut'].encode('utf-8')
        self.assertTrue(webhooks._rdv_signature_valide(
            v['secret'], corps, v['x_signature'], maintenant=v['t']))
        self.assertEqual(signer(v['secret'], corps, t=v['t']), v['x_signature'])
        # Un octet du corps change → invalide.
        self.assertFalse(webhooks._rdv_signature_valide(
            v['secret'], corps + b' ', v['x_signature'], maintenant=v['t']))
        # t hors tolérance (301 s) → invalide.
        self.assertFalse(webhooks._rdv_signature_valide(
            v['secret'], corps, v['x_signature'], maintenant=v['t'] + 301))

    def test_entete_hostile_invalide_jamais_une_exception(self):
        for entete in ('', 'n-importe', 't=abc,v1=00', 't=1,v1=é', None):
            self.assertFalse(webhooks._rdv_signature_valide(
                SECRET_A, b'{}', entete))

    def test_chaque_cle_du_contrat_est_mappee_ou_refusee(self):
        mappees = set(webhooks.DEMANDE_RDV_CLES_CORPS)
        self.assertEqual(set(CONTRAT['champs']), mappees)
        for cle in CONTRAT['corps']:
            self.assertIn(cle, mappees | set(CONTRAT['refus']), cle)
        self.assertEqual(set(CONTRAT['refus']), set(webhooks.DEMANDE_RDV_REFUS))
        for cle, spec in CONTRAT['champs'].items():
            if 'max' in spec:
                self.assertEqual(webhooks._RDV_MAX[cle], spec['max'], cle)
        self.assertEqual(sorted(CONTRAT['champs']['produit']['valeurs']),
                         sorted(webhooks._RDV_PRODUITS))
        self.assertEqual(sorted(CONTRAT['champs']['langue']['valeurs']),
                         sorted(webhooks._RDV_LANGUES))

    def test_parse_des_cles(self):
        with override_settings(SITE_RDV_CLES=(
                'k1:yanbow:s1, mal-formee ,k2::s2,k3:x:,:y:s4')):
            cles = webhooks._rdv_cles_configurees()
        self.assertEqual(cles, {'k1': ('yanbow', 's1'), 'k2': ('', 's2')})


class TestDemandeRdvWebhook(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='YanBow Test A', slug='yanbow-a')
        self.b = Company.objects.create(nom='Autre Test B', slug='autre-b')
        self.cle_a = f'ka-{uuid.uuid4().hex[:8]}'
        self.cle_b = f'kb-{uuid.uuid4().hex[:8]}'
        self.url = reverse('demande-rdv-webhook')
        self.reglages = override_settings(SITE_RDV_CLES=(
            f'{self.cle_a}:yanbow-a:{SECRET_A},{self.cle_b}:autre-b:{SECRET_B}'))
        self.reglages.enable()
        self.addCleanup(self.reglages.disable)

    def post(self, corps, *, cle=None, secret=SECRET_A, t=None,
             signature=None, entete_idem=None):
        brut = json.dumps(corps).encode('utf-8')
        headers = {}
        cle = self.cle_a if cle is None else cle
        if cle:
            headers['HTTP_X_SITE_CLE'] = cle
        if signature is None and secret:
            signature = signer(secret, brut, t=t)
        if signature:
            headers['HTTP_X_SIGNATURE'] = signature
        if entete_idem:
            headers['HTTP_IDEMPOTENCY_KEY'] = entete_idem
        return self.client.post(self.url, data=brut,
                                content_type='application/json', **headers)

    def assertRienEcrit(self):
        self.assertEqual(Lead.all_objects.count(), 0)
        self.assertEqual(ProcessedWebhookEvent.objects.filter(
            source=webhooks.DEMANDE_RDV_SOURCE).count(), 0)

    # ── Authentification : échec = fermé ────────────────────────────────
    def test_reglage_vide_tout_refuse(self):
        with override_settings(SITE_RDV_CLES=''):
            r = self.post(corps_valide())
        self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    def test_cle_de_a_signee_avec_le_secret_de_b(self):
        r = self.post(corps_valide(), cle=self.cle_a, secret=SECRET_B)
        self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    def test_requete_non_signee_n_ecrit_rien(self):
        r = self.post(corps_valide(), secret=None)
        self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    def test_entete_cle_absent_ou_inconnu(self):
        for cle in ('', 'inconnue'):
            with self.subTest(cle=cle):
                r = self.post(corps_valide(), cle=cle or False)
                self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    def test_t_perime(self):
        r = self.post(corps_valide(), t=int(time.time()) - 301)
        self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    def test_corps_401_constant(self):
        corps_401 = {
            self.post(corps_valide(), secret=None).content,
            self.post(corps_valide(), cle='inconnue').content,
            self.post(corps_valide(), secret=SECRET_B).content,
        }
        self.assertEqual(len(corps_401), 1)

    def test_slug_vide_ou_societe_introuvable(self):
        for reglage in (f'k:{""}:{SECRET_A}', f'k:nulle-part:{SECRET_A}'):
            with self.subTest(reglage=reglage), \
                    override_settings(SITE_RDV_CLES=reglage):
                r = self.post(corps_valide(), cle='k')
                self.assertEqual(r.status_code, 401)
        self.assertRienEcrit()

    # ── Corps ────────────────────────────────────────────────────────────
    def test_cles_company_refusees(self):
        for cle in ('company', 'company_id', 'societe_id', 'companySlug'):
            with self.subTest(cle=cle):
                r = self.post(corps_valide(**{cle: self.b.pk}))
                self.assertEqual(r.status_code, 400)
                self.assertIn(cle, r.json()['refus'])
        self.assertRienEcrit()

    def test_erreurs_par_champ_sans_valeur_recue(self):
        corps = corps_valide(email='pas-un-email', produit='autre',
                             consentement=False)
        del corps['nom']
        r = self.post(corps)
        self.assertEqual(r.status_code, 400)
        erreurs = r.json()['erreurs']
        self.assertEqual(erreurs['email'], 'format')
        self.assertEqual(erreurs['produit'], 'valeur')
        self.assertEqual(erreurs['consentement'], 'obligatoire')
        self.assertEqual(erreurs['nom'], 'obligatoire')
        self.assertNotIn('pas-un-email', r.content.decode('utf-8'))
        self.assertRienEcrit()

    def test_message_trop_long(self):
        r = self.post(corps_valide(message='x' * 2001))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['erreurs']['message'], 'trop_long')

    # ── Création ─────────────────────────────────────────────────────────
    def test_demande_valide_cree_le_lead_dans_la_societe_de_la_cle(self):
        with mock.patch('apps.crm.services.notify_new_lead') as notif, \
                mock.patch('apps.ventes.services.'
                           'planifier_devis_automatique_pour_lead') as devis, \
                self.captureOnCommitCallbacks(execute=True):
            r = self.post(corps_valide(message='Bonjour, une démo ?'))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['statut'], 'recu')
        lead = Lead.objects.get(pk=r.json()['id'])
        self.assertEqual(lead.company, self.a)
        self.assertEqual(Lead.all_objects.filter(company=self.b).count(), 0)
        self.assertEqual(lead.source, Lead.Source.SITE_WEB)
        self.assertEqual(lead.canal, Lead.Canal.SITE_WEB)
        self.assertEqual(lead.societe, 'Societe Test')
        self.assertEqual(lead.email, 'test@example.invalid')
        self.assertEqual(lead.tags, 'Rendez-vous SolarBow')
        self.assertEqual(lead.langue_preferee, 'fr')
        self.assertEqual(lead.utm_source, 'test')
        self.assertIsNotNone(lead.consent_timestamp)
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertEqual(notes.count(), 1)
        self.assertIn('SolarBow', notes.get().body)
        self.assertIn('Bonjour, une démo ?', notes.get().body)
        notif.assert_called_once()
        devis.assert_not_called()

    def test_rejeu_un_seul_lead_meme_avec_un_autre_entete(self):
        corps = corps_valide()
        r1 = self.post(corps, entete_idem='en-tete-1')
        r2 = self.post(corps, entete_idem='en-tete-2')
        r3 = self.post(corps)
        self.assertEqual(r1.status_code, 201)
        for r in (r2, r3):
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {'id': r1.json()['id'],
                                        'statut': 'deja_recu'})
        self.assertEqual(Lead.all_objects.count(), 1)

    def test_echec_apres_dedoublonnage_ne_perd_pas_le_lead(self):
        corps = corps_valide()
        with mock.patch.object(webhooks, '_rdv_creer_lead',
                               side_effect=RuntimeError('panne')):
            with self.assertRaises(RuntimeError):
                self.post(corps)
        self.assertRienEcrit()
        r = self.post(corps)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lead.all_objects.count(), 1)

    def test_langue_en_consignee_sans_valeur_hors_choix(self):
        r = self.post(corps_valide(langue='en', produit='sur_mesure'))
        self.assertEqual(r.status_code, 201)
        lead = Lead.objects.get(pk=r.json()['id'])
        self.assertIsNone(lead.langue_preferee)
        self.assertIn('en', lead.activites.get().body)

    @override_settings(SITE_RDV_LIMITE_PAR_MINUTE=1)
    def test_limite_par_cle(self):
        self.assertEqual(self.post(corps_valide()).status_code, 201)
        r = self.post(corps_valide())
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r['Retry-After'], '60')
        # L'autre clé garde son propre budget.
        self.assertEqual(
            self.post(corps_valide(), cle=self.cle_b, secret=SECRET_B)
            .status_code, 201)
