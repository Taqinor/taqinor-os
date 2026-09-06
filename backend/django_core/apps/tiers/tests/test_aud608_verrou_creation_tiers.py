"""AUD608 — créer le Tiers MIROIR d'un enregistrement est SÉRIALISÉ.

``attacher_ou_creer_tiers`` déduplique par e-mail/ICE avec un « je cherche, je
ne trouve pas, je crée ». Deux ponts déclenchés ensemble sur le même
enregistrement lisaient tous les deux « pas de tiers » et en créaient DEUX pour
le même e-mail : le miroir se dédouble, et les pièces comptables qui le
référencent en string-FK NON CONTRAINT se répartissent entre les deux.

Aucune ligne de tiers n'existe encore à verrouiller : le service sérialise donc
sur la ligne SOCIÉTÉ, et UNIQUEMENT sur le chemin de création — le cas courant
(tiers déjà trouvé) ne doit prendre aucun verrou.

Run :
    python manage.py test apps.tiers.tests.test_aud608_verrou_creation_tiers -v2
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.tiers.models import Tiers
from apps.tiers.services import attacher_ou_creer_tiers
from authentication.models import Company


def _verrous_societe(capture):
    return [q['sql'] for q in capture.captured_queries
            if 'FOR UPDATE' in q['sql'].upper()
            and 'company' in q['sql'].lower()]


class TestVerrouSurLeCheminDeCreation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD608 Tiers',
                                              slug='aud608-tiers')

    def _attacher(self, **extra):
        params = {'company': self.company, 'nom': 'SunRak',
                  'email': 'contact@sunrak.ma', 'roles': ('is_client',)}
        params.update(extra)
        return attacher_ou_creer_tiers(**params)

    def test_la_creation_verrouille_la_societe(self):
        with CaptureQueriesContext(connection) as capture:
            _tiers, cree = self._attacher()
        self.assertTrue(cree)
        self.assertTrue(
            _verrous_societe(capture),
            'La création du miroir ne prend AUCUN verrou : deux ponts '
            'simultanés créeraient deux Tiers pour le même e-mail.')

    def test_le_rattachement_ne_verrouille_rien(self):
        self._attacher()
        with CaptureQueriesContext(connection) as capture:
            _tiers, cree = self._attacher()
        self.assertFalse(cree)
        self.assertEqual(_verrous_societe(capture), [])

    def test_la_dedup_reste_intacte(self):
        premier, _ = self._attacher()
        second, cree = self._attacher(nom='SunRak SARL')
        self.assertFalse(cree)
        self.assertEqual(second.pk, premier.pk)
        self.assertEqual(Tiers.objects.filter(company=self.company).count(), 1)

    def test_les_roles_sont_toujours_poses_a_la_creation(self):
        """Non-régression : le chemin CREATE passe désormais par un `with`."""
        tiers, cree = self._attacher(roles=('is_client', 'is_fournisseur'))
        self.assertTrue(cree)
        tiers.refresh_from_db()
        self.assertTrue(tiers.is_client)
        self.assertTrue(tiers.is_fournisseur)

    def test_les_champs_miroites_sont_toujours_poses(self):
        tiers, _ = self._attacher(ice='002345678000091')
        tiers.refresh_from_db()
        self.assertEqual(tiers.email, 'contact@sunrak.ma')
        self.assertEqual(tiers.ice, '002345678000091')

    def test_deux_societes_gardent_leur_propre_miroir(self):
        voisine = Company.objects.create(nom='AUD608 Tiers voisine',
                                         slug='aud608-tiers-voisine')
        a, _ = self._attacher()
        b, cree = attacher_ou_creer_tiers(
            company=voisine, nom='SunRak', email='contact@sunrak.ma')
        self.assertTrue(cree)
        self.assertNotEqual(a.pk, b.pk)
