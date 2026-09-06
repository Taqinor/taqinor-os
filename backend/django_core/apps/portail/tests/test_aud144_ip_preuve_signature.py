"""AUD144 — l'IP consignée dans la preuve de signature portail est celle du
DERNIER SAUT DE CONFIANCE, jamais un en-tête forgé par l'appelant ni
``REMOTE_ADDR`` seul (qui vaut l'IP du reverse-proxy, pas celle du client).

Défaut d'origine : ``portail/views_client._ip`` faisait
``request.META.get('REMOTE_ADDR')`` — derrière nginx/Caddy, cette valeur est
celle du proxy, pas du client (``identity/middleware.py``). Le dépôt possède
DÉJÀ la primitive UNIQUE qui corrige exactement ce défaut ailleurs (QJR416,
``core.throttling.ip_de_requete`` — voir
``apps/crm/tests/test_qjr416_primitive_ip.py::PreuveLegaleTests``, qui couvre
le même défaut sur le chemin de signature PUBLIC tokenisé
``ventes/public_views._client_ip``) : ce module est le pendant AUTHENTIFIÉ de
ce test-là, sur le MÊME champ de preuve légale (loi 53-05), jamais une
seconde primitive.

Honnêteté (reprise du constat d'audit) : la valeur EXACTE que
``ip_de_requete`` retient dépend de ``NUM_PROXIES`` (combien de nos propres
sauts séparent le client de Django) — un réglage de DÉPLOIEMENT que cette
lane ne peut pas lire. Le test ne fige donc PAS un exemple de chaîne
``X-Forwarded-For`` particulier : il prouve que ``_ip()`` délègue EXACTEMENT
à la primitive canonique (même valeur qu'un appel direct) et qu'un saut
FORGÉ par l'appelant en tête de chaîne n'est plus jamais accepté tel quel —
exactement le patron de ``PreuveLegaleTests``.

Run :
    python manage.py test apps.portail.tests.test_aud144_ip_preuve_signature -v2
"""
import itertools
from decimal import Decimal

from django.test import RequestFactory, SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.portail import views_client
from apps.portail.models import AcceptationDevisPortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser
from core.throttling import ip_de_requete
from rest_framework.test import APIClient

_seq = itertools.count(1)

#: Une chaîne réaliste : le visiteur a forgé « 9.9.9.9 » en tête, notre
#: infrastructure a APPENDU l'adresse qu'elle a réellement vue (même fixture
#: que ``test_qjr416_primitive_ip.py``, pour rester cohérent avec le patron
#: déjà en usage dans le dépôt).
_FORGEE = '9.9.9.9'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD144-{n}',
        email=f'aud144-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


class IpDePreuvePortailDelegueALaPrimitiveTests(SimpleTestCase):
    """Unitaire, sans DB : ``views_client._ip`` EST ``ip_de_requete``."""

    def test_ip_delegue_exactement_a_la_primitive_qjr416(self):
        requete = RequestFactory().get(
            '/x/', HTTP_X_FORWARDED_FOR='%s, 203.0.113.9' % _FORGEE)
        self.assertEqual(
            views_client._ip(requete), ip_de_requete(requete))

    # ROUGE avant correctif : `_ip` rendait `REMOTE_ADDR` (le pair TCP direct,
    # ici l'IP du proxy de test) même en présence d'un `X-Forwarded-For` —
    # jamais le dernier saut de la chaîne.
    def test_un_saut_forge_en_tete_nest_plus_jamais_rendu_tel_quel(self):
        requete = RequestFactory().get(
            '/x/', HTTP_X_FORWARDED_FOR='%s, 203.0.113.9' % _FORGEE,
            REMOTE_ADDR='127.0.0.1')
        self.assertNotEqual(views_client._ip(requete), _FORGEE)
        self.assertEqual(views_client._ip(requete), '203.0.113.9')

    def test_sans_en_tete_le_repli_reste_le_pair_tcp(self):
        """Comportement historique préservé : sans proxy déclaré, on lit
        toujours le pair TCP direct — jamais une régression sur le cas
        simple (dev local, requête directe)."""
        requete = RequestFactory().get('/x/', REMOTE_ADDR='198.51.100.4')
        self.assertEqual(views_client._ip(requete), '198.51.100.4')


class PreuveDeSignatureAcceptationPortailTests(TestCase):
    """Bout en bout : ``AcceptationDevisPortail.signature_ip`` reflète la
    primitive canonique, jamais un en-tête forgé par le client."""

    def setUp(self):
        self.company = make_company('aud144-co', 'AUD144 Société')
        self.client_crm = make_client(self.company, 'Alpha')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AUD144-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.user = make_portal_user(
            self.company, 'aud144-portail-a', self.client_crm.id)
        self.url = f'/api/django/portail/mes-devis/{self.devis.id}/accepter/'
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # ROUGE avant correctif : `signature_ip` valait l'IP du pair TCP du test
    # client (le "proxy"), pas le dernier saut de la chaîne `X-Forwarded-For`.
    def test_signature_ip_suit_la_primitive_pas_le_pair_tcp_du_proxy(self):
        charge = {'nom': 'Client Alpha', 'consent_esign': True}
        resp = self.api.post(
            self.url, charge, format='json',
            HTTP_X_FORWARDED_FOR='%s, 203.0.113.9' % _FORGEE)
        self.assertEqual(resp.status_code, 200, resp.data)

        preuve = AcceptationDevisPortail.objects.get(
            company=self.company, devis=self.devis)
        self.assertEqual(preuve.signature_ip, '203.0.113.9')
        self.assertNotEqual(preuve.signature_ip, _FORGEE)
