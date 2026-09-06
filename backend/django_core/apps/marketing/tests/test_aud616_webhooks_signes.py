"""AUD616 — les webhooks marketing publics (Brevo, STOP SMS) exigent une
signature et ne déduisent JAMAIS le tenant du corps envoyé par l'expéditeur.

Constat d'origine : ``webhook_brevo_campagne`` / ``webhook_sms_stop`` étaient
deux routes STATIQUES ``AllowAny`` sans segment de jeton et sans aucune
vérification de signature. La société était déduite d'un champ du CORPS
(``campagne_id`` pour Brevo, ``company_id`` pour le STOP SMS) — n'importe
quel tiers non authentifié pouvait donc écrire dans la société de son choix :
marquer des envois, et surtout désinscrire en masse les contacts d'un
concurrent.

Tests ROUGES d'abord : ``test_post_sans_signature_refuse_brevo`` et
``test_post_sans_signature_refuse_sms_stop`` passaient 200 + écriture réelle
avant le correctif ; ``test_company_id_du_corps_est_ignore`` prouve que le
champ interne ne pilote plus la résolution du tenant.

Patron AUD212 (``ecommerce_connect``) : secret HMAC PROPRE à la société,
fail-closed sans secret configuré.
"""
import hashlib
import hmac
import json

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.compta import services
from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne

SECRET_TEST = 'secret-hmac-aud616'


def signer(company, payload, *, secret=None):
    """Corps brut + en-tête de signature d'un webhook marketing (AUD616)."""
    corps = json.dumps(payload).encode('utf-8')
    if secret is None:
        secret = mkt_services.parametres_marketing_pour(
            company).webhook_secret
    signature = hmac.new(
        secret.encode('utf-8'), corps, hashlib.sha256).hexdigest()
    return corps, signature


def configurer_secret(company, secret=SECRET_TEST):
    parametres = mkt_services.parametres_marketing_pour(company)
    parametres.webhook_secret = secret
    parametres.save(update_fields=['webhook_secret'])
    return parametres


def poster_webhook(chemin, company, payload, *, secret=None, cle=None,
                   signature=None, api=None):
    """POST signé sur une route webhook marketing. Chaque garde peut être
    neutralisée séparément pour prouver qu'elle est bien fail-closed."""
    corps, calculee = signer(company, payload, secret=secret)
    if cle is None:
        cle = mkt_services.generer_cle_webhook(company.id)
    entetes = {}
    if signature != '':
        entetes['HTTP_X_WEBHOOK_SIGNATURE'] = (
            calculee if signature is None else signature)
    return (api or APIClient()).post(
        f'{chemin}{cle}/', corps, content_type='application/json', **entetes)


class WebhookBrevoSignatureTests(TestCase):
    CHEMIN = '/api/django/compta/webhooks/brevo/'

    def setUp(self):
        self.co = Company.objects.create(slug='aud616', nom='AUD616')
        configurer_secret(self.co)
        self.camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(self.camp, destinataires=['c@x.ma'])
        self.payload = {'campagne_id': self.camp.id,
                        'destinataire': 'c@x.ma', 'event': 'click'}

    def test_signature_valide_acceptee(self):
        resp = poster_webhook(self.CHEMIN, self.co, self.payload)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_post_sans_signature_refuse_brevo(self):
        """ROUGE avant correctif : la route statique acceptait ce POST."""
        resp = poster_webhook(
            self.CHEMIN, self.co, self.payload, signature='')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_signature_invalide_refusee(self):
        resp = poster_webhook(
            self.CHEMIN, self.co, self.payload, signature='deadbeef')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_signature_dun_autre_secret_refusee(self):
        resp = poster_webhook(
            self.CHEMIN, self.co, self.payload, secret='mauvais-secret')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_corps_modifie_apres_signature_refuse(self):
        """La signature couvre le corps BRUT : le rejouer avec un autre
        contenu ne passe pas."""
        _, signature = signer(self.co, self.payload)
        cle = mkt_services.generer_cle_webhook(self.co.id)
        autre = json.dumps(
            dict(self.payload, event='bounce')).encode('utf-8')
        resp = APIClient().post(
            f'{self.CHEMIN}{cle}/', autre, content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_cle_url_forgee_refusee(self):
        resp = poster_webhook(
            self.CHEMIN, self.co, self.payload, cle='cle-bidon')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_secret_non_configure_est_fail_closed(self):
        """Une société sans secret n'accepte AUCUN webhook — jamais
        l'inverse."""
        configurer_secret(self.co, '')
        resp = poster_webhook(
            self.CHEMIN, self.co, self.payload, secret='nimporte')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_campagne_dune_autre_societe_inatteignable(self):
        """Le tenant vient de la clé signée : un ``campagne_id`` d'un autre
        tenant n'est plus résolu (avant : la société SUIVAIT la campagne du
        corps)."""
        autre = Company.objects.create(slug='aud616b', nom='AUD616b')
        camp_autre = Campagne.objects.create(
            company=autre, nom='B', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp_autre, destinataires=['b@x.ma'])
        resp = poster_webhook(self.CHEMIN, self.co, {
            'campagne_id': camp_autre.id, 'destinataire': 'b@x.ma',
            'event': 'click'})
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_route_marketing_exige_la_meme_signature(self):
        """Les deux routes (compta et marketing) servent la MÊME vue : la
        garde doit tenir des deux côtés."""
        chemin = '/api/django/marketing/webhooks/brevo/'
        self.assertEqual(
            poster_webhook(chemin, self.co, self.payload,
                           signature='').status_code, 403)
        self.assertEqual(
            poster_webhook(chemin, self.co, self.payload).status_code, 200)


class WebhookSmsStopSignatureTests(TestCase):
    CHEMIN = '/api/django/compta/webhooks/sms-stop/'

    def setUp(self):
        self.co = Company.objects.create(slug='aud616s', nom='AUD616-SMS')
        configurer_secret(self.co)

    def test_signature_valide_desinscrit(self):
        resp = poster_webhook(
            self.CHEMIN, self.co, {'numero': '0612345678'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(services.est_supprime(self.co, '212612345678'))

    def test_post_sans_signature_refuse_sms_stop(self):
        """ROUGE avant correctif : un tiers désinscrivait qui il voulait."""
        resp = poster_webhook(
            self.CHEMIN, self.co, {'numero': '0612345678'}, signature='')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertFalse(services.est_supprime(self.co, '212612345678'))

    def test_company_id_du_corps_est_ignore(self):
        """Le champ interne du corps ne pilote plus le tenant : signé pour la
        société A, l'événement atterrit chez A même s'il prétend viser B."""
        victime = Company.objects.create(slug='aud616v', nom='AUD616-V')
        resp = poster_webhook(self.CHEMIN, self.co, {
            'numero': '0612345678', 'company_id': victime.id})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(services.est_supprime(self.co, '212612345678'))
        self.assertFalse(services.est_supprime(victime, '212612345678'))

    def test_secret_dune_societe_ne_signe_pas_pour_une_autre(self):
        """Multi-tenance : la clé de A avec le secret de B est refusée."""
        autre = Company.objects.create(slug='aud616t', nom='AUD616-T')
        configurer_secret(autre, 'autre-secret')
        resp = poster_webhook(
            self.CHEMIN, self.co, {'numero': '0612345678'},
            secret='autre-secret')
        self.assertEqual(resp.status_code, 403, resp.content)


class WebhookSecretNonExposeTests(TestCase):
    """Le secret est POSABLE par un responsable/admin mais ne ressort jamais
    d'une lecture — un secret relu serait un secret diffusé."""

    def setUp(self):
        self.co = Company.objects.create(slug='aud616p', nom='AUD616-P')
        configurer_secret(self.co)

    def _serialise(self):
        from apps.marketing.serializers import ParametresMarketingSerializer

        parametres = mkt_services.parametres_marketing_pour(self.co)
        return ParametresMarketingSerializer(parametres).data

    def test_le_secret_ne_sort_jamais_dune_lecture(self):
        data = self._serialise()
        self.assertNotIn('webhook_secret', data)
        self.assertNotIn(SECRET_TEST, json.dumps(data))

    def test_lecran_sait_seulement_sil_est_configure(self):
        self.assertTrue(self._serialise()['webhook_secret_configure'])
        configurer_secret(self.co, '')
        self.assertFalse(self._serialise()['webhook_secret_configure'])

    def test_les_urls_de_webhook_portent_la_cle_de_la_societe(self):
        data = self._serialise()
        cle = mkt_services.generer_cle_webhook(self.co.id)
        company_id, = (mkt_services.societe_par_cle_webhook(cle).id,)
        self.assertEqual(company_id, self.co.id)
        for url in (data['webhook_url_brevo'], data['webhook_url_sms_stop']):
            self.assertTrue(url.endswith('/'))
            extraite = url.rstrip('/').rsplit('/', 1)[-1]
            self.assertEqual(
                mkt_services.societe_par_cle_webhook(extraite).id, self.co.id)
