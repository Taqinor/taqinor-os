"""QJR59 — ``LigneDevis.quantite_manuelle`` / ``prix_manuel`` : le trou des
quantités se ferme.

CE QUI ÉTAIT FAUX. Une ligne ne portait AUCUN marqueur de saisie manuelle : la
resynchro réécrivait librement les QUANTITÉS (panneaux, mètres de câble,
structures/socles) pendant que le PRIX tapé sur la MÊME ligne était sacré.
Décision fondateur D12 : le commercial garde la main TOTALE sur les prix ET les
quantités, et ces choix sont PERSISTANTS.

CE QUE CES TESTS TIENNENT :

1. **AUCUN comportement ne change sur les données existantes** — une ligne sans
   les nouveaux champs (donc ``False``) est traitée exactement comme avant, et
   le repli ``services._est_au_prix_catalogue`` RESTE : une ligne au prix ≠
   catalogue avec ``prix_manuel=False`` reste « négociée ».
2. **Les deux champs font l'ALLER-RETOUR** GET → replace-lignes : sans cela, le
   seul chemin d'écriture de l'écran les remettrait à False à chaque
   enregistrement.

Aucun écrivain de resynchro n'est branché ici (QJR60).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_ligne_manuelle -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import LigneDevis
from apps.ventes.services import _est_au_prix_catalogue
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


class _LigneManuelleBase(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(company=self.company,
                                      prix_vente=Decimal('1000.00'))
        self.devis = DevisFactory(company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _ligne(self, **extra):
        champs = dict(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1000.00'), remise=Decimal('0'))
        champs.update(extra)
        return LigneDevis.objects.create(**champs)


class DefautsInchangesTests(_LigneManuelleBase):
    """Les données existantes ne bougent pas d'un pouce."""

    def test_les_deux_champs_valent_false_par_defaut(self):
        ligne = self._ligne()
        ligne.refresh_from_db()
        self.assertFalse(ligne.quantite_manuelle)
        self.assertFalse(ligne.prix_manuel)

    def test_le_repli_prix_catalogue_reste_le_juge_des_lignes_anciennes(self):
        """Une ligne au prix ≠ catalogue avec ``prix_manuel=False`` reste
        « négociée » : supprimer ce repli traiterait rétroactivement des
        milliers de prix négociés comme des prix catalogue."""
        catalogue = self._ligne()
        self.assertTrue(_est_au_prix_catalogue(catalogue))

        negociee = self._ligne(prix_unitaire=Decimal('900.00'))
        self.assertFalse(negociee.prix_manuel)
        self.assertFalse(_est_au_prix_catalogue(negociee))

    def test_le_marqueur_ne_change_pas_le_verdict_du_repli(self):
        """Les deux mécanismes COEXISTENT : le marqueur est la vérité NEUVE,
        le repli reste celle des lignes d'hier — l'un ne réécrit pas l'autre."""
        ligne = self._ligne(prix_manuel=True)
        self.assertTrue(_est_au_prix_catalogue(ligne))


class AllerRetourApiTests(_LigneManuelleBase):
    """GET → replace-lignes : les marqueurs survivent à l'enregistrement."""

    def _replace(self, lignes):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes}, format='json')

    def test_le_get_expose_les_deux_champs(self):
        self._ligne(quantite_manuelle=True, prix_manuel=True)
        resp = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = resp.data['lignes'][0]
        self.assertTrue(ligne['quantite_manuelle'])
        self.assertTrue(ligne['prix_manuel'])

    def test_replace_lignes_persiste_les_marqueurs(self):
        resp = self._replace([{
            'produit': self.produit.id, 'designation': self.produit.nom,
            'quantite': '12', 'prix_unitaire': '950.00',
            'quantite_manuelle': True, 'prix_manuel': True,
        }])
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = self.devis.lignes.get()
        self.assertTrue(ligne.quantite_manuelle)
        self.assertTrue(ligne.prix_manuel)

    def test_replace_lignes_sans_les_champs_reste_a_false(self):
        """Tous les appelants d'hier : comportement strictement inchangé."""
        resp = self._replace([{
            'produit': self.produit.id, 'designation': self.produit.nom,
            'quantite': '12', 'prix_unitaire': '950.00',
        }])
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = self.devis.lignes.get()
        self.assertFalse(ligne.quantite_manuelle)
        self.assertFalse(ligne.prix_manuel)

    def test_l_aller_retour_complet_conserve_les_marqueurs(self):
        self._ligne(quantite_manuelle=True, prix_manuel=False)
        lu = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/').data['lignes'][0]
        resp = self._replace([{
            'produit': lu['produit'], 'designation': lu['designation'],
            'quantite': lu['quantite'], 'prix_unitaire': lu['prix_unitaire'],
            'quantite_manuelle': lu['quantite_manuelle'],
            'prix_manuel': lu['prix_manuel'],
        }])
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = self.devis.lignes.get()
        self.assertTrue(ligne.quantite_manuelle)
        self.assertFalse(ligne.prix_manuel)

    def test_les_marqueurs_apparaissent_dans_le_registre_du_devis(self):
        """QJR58 — le bloc ``lignes`` du registre est une carte {id: {...}},
        jamais une liste indexée par position."""
        ligne = self._ligne(prix_manuel=True)
        resp = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/overrides/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['lignes'],
                         {str(ligne.pk): {'quantite_manuelle': False,
                                          'prix_manuel': True}})
