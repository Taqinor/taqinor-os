"""AMOT66 (C-AMOT-011) — la charge JSON publique d'un lien ne porte QUE son
propre jeton.

Avant : ``proposal_data`` appelait ``build_quote_data(devis, {'pdf_mode':
'full'})`` sans ``share_token`` ; le moteur retombait sur
``ShareLink.for_devis`` (le lien à l'expiration la plus lointaine, tout niveau
confondu) et un visiteur « standard » recevait dans ``quote.links.signer`` le
jeton du lien « confiance » du même devis (sonde VA b22). Le PDF public, lui,
était déjà corrigé (QRP1/A5, ``_opts_pdf_public``).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_amot66_jeton_public -v 2
"""
from datetime import timedelta
from unittest import mock

from django.test import Client as DjangoClient, TestCase
from django.utils import timezone

from apps.ventes.models import ShareLink

from .test_l_niv_niveau import make_client, make_company, make_devis, make_user


def _valeurs(obj):
    """Toutes les valeurs scalaires d'une réponse JSON, à toute profondeur."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _valeurs(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _valeurs(v)
    elif obj is not None:
        yield str(obj)


class JetonPublicTests(TestCase):

    def setUp(self):
        self.company = make_company('amot66')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                'DEV-AMOT66-0001')
        maintenant = timezone.now()
        self.lien_a = ShareLink.objects.create(
            company=self.company, devis=self.devis,
            niveau=ShareLink.NIVEAU_STANDARD,
            expires_at=maintenant + timedelta(days=5))
        self.lien_b = ShareLink.objects.create(
            company=self.company, devis=self.devis,
            niveau=ShareLink.NIVEAU_CONFIANCE,
            expires_at=maintenant + timedelta(days=900))
        self.http = DjangoClient()

    def _data(self, token):
        # Notification d'ouverture neutralisée (test seulement) : la lecture
        # est ce qu'on mesure, pas l'envoi d'un e-mail au commercial.
        with mock.patch('apps.ventes.public_views._notify_open'):
            return self.http.get(f'/api/django/public/proposal/{token}/data/')

    def test_charge_du_lien_standard_ne_contient_pas_le_jeton_confiance(self):
        # Prémisse : c'est bien B que le repli historique choisirait.
        self.assertEqual(ShareLink.for_devis(self.devis).token,
                         self.lien_b.token)
        resp = self._data(self.lien_a.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        corps = resp.json()
        fuites = [v for v in _valeurs(corps) if self.lien_b.token in v]
        self.assertEqual(fuites, [], 'jeton du lien confiance publié au '
                                     'visiteur du lien standard')
        signer = ((corps.get('quote') or {}).get('links') or {}).get('signer')
        self.assertTrue(signer, 'quote.links.signer absent de la charge')
        self.assertIn(self.lien_a.token, signer)

    def test_charge_du_lien_confiance_porte_son_propre_jeton(self):
        resp = self._data(self.lien_b.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        corps = resp.json()
        self.assertEqual(
            [v for v in _valeurs(corps) if self.lien_a.token in v], [])
        signer = corps['quote']['links']['signer']
        self.assertIn(self.lien_b.token, signer)

    def test_options_moteur_portent_le_jeton_du_lien(self):
        from apps.ventes.public_views import _opts_quote_data_public
        self.assertEqual(
            _opts_quote_data_public(self.lien_a),
            {'pdf_mode': 'full', 'share_token': self.lien_a.token})
