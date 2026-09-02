"""AUD305 — la signature client du bon de livraison chantier est gardée et tracée.

Défaut d'origine (NTMOB16) : l'action `signer-client` écrasait
INCONDITIONNELLEMENT `signature_client` / `signataire_nom` / `signe_le` ; ces
3 champs étaient en plus librement modifiables par un PATCH générique
(`fields='__all__'`, absents de `read_only_fields`) ; et `TRACKED_FIELDS` ne
les couvrait pas — ni une re-signature ni un PATCH n'apparaissaient dans
l'Historique visible du chantier. La preuve de livraison signée disparaissait
donc sans trace, précisément quand un litige la réclame.

Après correctif : re-signature refusée en 409 sans motif d'override explicite
(patron `motif_override_acompte`), motif journalisé au chatter, les 3 champs
en lecture seule sur le serializer générique, et les 3 champs suivis.

Run :
    python manage.py test apps.installations.tests_aud305_resignature -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.activity import TRACKED_FIELDS
from apps.installations.models import Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'
SIG_A = 'data:image/png;base64,AAAA'
SIG_B = 'data:image/png;base64,BBBB'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud305-co-{n}', defaults={'nom': f'AUD305 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ResignatureGardeeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud305-resp-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference='AUD305-1',
            statut=Installation.Statut.INSTALLE)

    def _signer(self, sig, **extra):
        body = {'signature_client': sig, 'signataire_nom': 'Client A'}
        body.update(extra)
        return self.api.post(
            f'{BASE}/{self.inst.id}/signer-client/', body, format='json')

    def test_premiere_signature_passe(self):
        r = self._signer(SIG_A)
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, SIG_A)
        self.assertIsNotNone(self.inst.signe_le)

    def test_resignature_sans_motif_refusee(self):
        """ROUGE avant AUD305 : le second appel écrasait silencieusement."""
        self.assertEqual(self._signer(SIG_A).status_code, 200)
        r = self._signer(SIG_B)
        self.assertEqual(r.status_code, 409, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, SIG_A)

    def test_resignature_avec_motif_passe_et_est_journalisee(self):
        self._signer(SIG_A)
        r = self._signer(SIG_B, motif_override_signature='Tablette effacée')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, SIG_B)
        notes = [a.body or '' for a in self.inst.activites.all()]
        self.assertTrue(
            any('Tablette effacée' in n for n in notes), notes)

    def test_patch_generique_ne_touche_plus_les_champs_de_signature(self):
        """ROUGE avant AUD305 : un PATCH vidait la preuve signée."""
        self._signer(SIG_A)
        r = self.api.patch(
            f'{BASE}/{self.inst.id}/',
            {'signature_client': '', 'signataire_nom': 'Pirate',
             'signe_le': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, SIG_A)
        self.assertEqual(self.inst.signataire_nom, 'Client A')
        self.assertIsNotNone(self.inst.signe_le)

    def test_les_trois_champs_sont_suivis_au_chatter(self):
        for champ in ('signature_client', 'signataire_nom', 'signe_le'):
            self.assertIn(champ, TRACKED_FIELDS)

    def test_le_chatter_ne_recopie_jamais_la_data_url(self):
        """La signature est un PNG en base64 : le chatter en montre la
        PRÉSENCE, jamais le blob."""
        from apps.installations import activity
        self.assertNotIn(
            'AAAA', activity._display(self.inst, 'signature_client', SIG_A))
