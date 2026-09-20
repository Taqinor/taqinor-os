"""CAL200 — catalogue de modules et onduleurs favoris de la société.

Ce qui est prouvé ici :

* la section ``favoris_materiel`` de ``ParametresCalepinage`` (CAL45) ne
  porte que des identifiants — ``selectors.favoris_materiel_de_societe`` les
  résout sur le catalogue stock (marque/puissance/dimensions), JAMAIS une
  fiche technique inventée ;
* un module SANS dimensions reste dans la liste, ``dimensions_renseignees:
  False`` — jamais une taille par défaut ;
* un identifiant favori devenu introuvable est simplement omis ;
* une société sans réglage reçoit un dict vide — comportement d'aujourd'hui,
  inchangé.

Run :
    python manage.py test apps.calepinage.tests.test_cal200_favoris -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage import selectors
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company


class FavorisMaterielSelectorTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Favoris Co',
                                              slug='favoris-co-200')

    def _module(self, *, nom, longueur_mm=None, largeur_mm=None,
                pmax_wc=None):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'CAL200-{nom}',
            prix_achat=Decimal('900'), prix_vente=Decimal('1400'),
            quantite_stock=5, marque='ACME')
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='module',
            longueur_mm=longueur_mm, largeur_mm=largeur_mm, pmax_wc=pmax_wc)
        return produit

    def test_societe_sans_reglage_rend_dict_vide(self):
        self.assertEqual(selectors.favoris_materiel_de_societe(self.company),
                         {})

    def test_favori_complet_resolu_avec_dimensions(self):
        module = self._module(nom='Longi 610', longueur_mm=2384,
                              largeur_mm=1303, pmax_wc=Decimal('610'))
        enregistrer_parametres(
            self.company, {'favoris_materiel': {'modules': [module.pk]}})

        resultat = selectors.favoris_materiel_de_societe(self.company)

        self.assertEqual(len(resultat['modules']), 1)
        ligne = resultat['modules'][0]
        self.assertEqual(ligne['id'], module.pk)
        self.assertEqual(ligne['marque'], 'ACME')
        self.assertTrue(ligne['dimensions_renseignees'])
        self.assertEqual(ligne['longueur_mm'], 2384)

    def test_favori_sans_dimensions_signale_jamais_de_taille_par_defaut(self):
        module = self._module(nom='Sans fiche')  # tout None
        enregistrer_parametres(
            self.company, {'favoris_materiel': {'modules': [module.pk]}})

        resultat = selectors.favoris_materiel_de_societe(self.company)

        ligne = resultat['modules'][0]
        self.assertFalse(ligne['dimensions_renseignees'])
        self.assertIsNone(ligne['longueur_mm'])
        self.assertIsNone(ligne['largeur_mm'])

    def test_favori_introuvable_est_omis(self):
        enregistrer_parametres(
            self.company, {'favoris_materiel': {'modules': [999999]}})
        resultat = selectors.favoris_materiel_de_societe(self.company)
        self.assertEqual(resultat['modules'], [])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='Autre Co', slug='autre-co-200')
        module = self._module(nom='Longi 610', longueur_mm=2384,
                              largeur_mm=1303, pmax_wc=Decimal('610'))
        enregistrer_parametres(
            self.company, {'favoris_materiel': {'modules': [module.pk]}})
        self.assertEqual(selectors.favoris_materiel_de_societe(autre), {})
