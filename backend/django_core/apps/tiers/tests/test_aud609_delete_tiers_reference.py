"""AUD609 — un tiers RÉFÉRENCÉ par une pièce comptable ne se supprime plus.

``TiersViewSet`` était un ``ModelViewSet`` nu : aucune garde, aucune
journalisation. Or les apps aval désignent un tiers par ``tiers_id`` — un
ENTIER NU, sans contrainte de clé étrangère (``compta`` ne peut pas importer
``tiers``, le pont est volontairement additif). La base ne pouvait donc RIEN
refuser : un DELETE laissait des ``tiers_id`` orphelins dans des écritures, des
cautions bancaires, des retenues de garantie — des pièces comptables pointant
un tiers qui n'existe plus.

La détection est faite par le REGISTRE des modèles installés : ``tiers`` reste
une couche de fondation et ne connaît toujours aucun de ses consommateurs.
C'est aussi pourquoi ce module n'IMPORTE aucune app de domaine — il interroge
le registre, exactement comme le code de production.

Run :
    python manage.py test apps.tiers.tests.test_aud609_delete_tiers_reference -v2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.tiers import selectors
from apps.tiers.models import Tiers
from authentication.models import Company

User = get_user_model()

URL = '/api/django/tiers/tiers/'


class TestDecouverteDesConsommateurs(TestCase):
    """La moitié « détection » : le registre, jamais un import d'app."""

    def test_des_modeles_portent_bien_la_pseudo_fk(self):
        modeles = selectors.modeles_referencant_un_tiers()
        self.assertTrue(
            modeles,
            'Aucun modèle porteur de `tiers_id` trouvé : la garde de '
            'suppression ne protégerait plus rien.')

    def test_les_consommateurs_sont_des_pieces_comptables(self):
        etiquettes = {m._meta.app_label
                      for m in selectors.modeles_referencant_un_tiers()}
        self.assertIn('compta', etiquettes)

    def test_un_vrai_foreignkey_n_est_pas_compte_deux_fois(self):
        """Django gère déjà les VRAIES FK (`on_delete`) : hors périmètre ici."""
        for modele in selectors.modeles_referencant_un_tiers():
            champ = modele._meta.get_field(selectors.CHAMP_PSEUDO_FK)
            with self.subTest(modele=modele.__name__):
                self.assertFalse(champ.is_relation)


class BaseApi(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD609 Tiers',
                                              slug='aud609-tiers')
        self.user = User.objects.create_user(
            username='aud609_tiers', password='x', company=self.company,
            role_legacy=User.ROLE_ADMIN)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.tiers = Tiers.objects.create(
            company=self.company, nom='SunRak', email='contact@sunrak.ma')


class TestGardeDeSuppression(BaseApi):
    def test_un_tiers_reference_n_est_plus_supprimable(self):
        with patch('apps.tiers.selectors.references_pseudo_fk',
                   return_value=[('écriture comptable', 3)]):
            reponse = self.api.delete(f'{URL}{self.tiers.pk}/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertTrue(Tiers.objects.filter(pk=self.tiers.pk).exists())

    def test_le_refus_NOMME_les_pieces(self):
        with patch('apps.tiers.selectors.references_pseudo_fk',
                   return_value=[('écriture comptable', 3)]):
            reponse = self.api.delete(f'{URL}{self.tiers.pk}/')
        self.assertIn('écriture comptable', str(reponse.data))

    def test_un_tiers_libre_reste_supprimable(self):
        """Fermer la fuite ne doit pas geler le répertoire."""
        reponse = self.api.delete(f'{URL}{self.tiers.pk}/')
        self.assertEqual(reponse.status_code, 204, reponse.data)
        self.assertFalse(Tiers.objects.filter(pk=self.tiers.pk).exists())

    def test_un_tiers_neuf_n_a_aucune_reference(self):
        self.assertEqual(selectors.references_pseudo_fk(self.tiers), [])
