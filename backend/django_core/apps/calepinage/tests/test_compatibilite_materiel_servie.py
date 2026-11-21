"""ACAL901 — la compatibilité du matériel désigné, servie au calepinage par le
sélecteur de ventes ``compatibilite_du_materiel`` (verdicts RELAYÉS tels
quels de ``ventes.compatibilites``, jamais recalculés).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.calepinage.tests.test_compatibilite_materiel_servie"
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.stock.models import Produit
from apps.ventes.selectors_calepinage import compatibilite_du_materiel
from authentication.models import Company

VERDICTS = 'apps.ventes.compatibilites.'


class CompatibiliteDuMaterielTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.create(nom='ACAL901 Co', slug='acal901-co')
        cls.autre = Company.objects.create(nom='ACAL901 Autre', slug='acal901-autre')

        def produit(company, nom):
            return Produit.objects.create(company=company, nom=nom,
                                          prix_vente=Decimal('1000'),
                                          prix_achat=Decimal('600'))

        cls.panneau = produit(cls.co, 'Panneau 710W sans fiche')
        cls.onduleur = produit(cls.co, 'Onduleur 5 kW sans fiche')
        cls.batterie = produit(cls.co, 'Batterie 5 kWh sans fiche')
        cls.onduleur_autre = produit(cls.autre, 'Onduleur d\'une autre société')

    def test_incompatible_rend_ses_raisons(self):
        raisons = ['Voc à froid 1 120 V au-dessus des 1 000 V admissibles']
        with mock.patch(VERDICTS + 'verdict_panneau_onduleur', return_value={
                'statut': 'incompatible', 'raisons': raisons, 'detail': ''}):
            r = compatibilite_du_materiel(self.panneau.pk, self.onduleur.pk, self.co)
        self.assertEqual(r['panneau_onduleur'],
                         {'statut': 'incompatible', 'raisons': raisons})
        self.assertIsNone(r['batterie_onduleur'])

    def test_reserve_relaye_tel_quel(self):
        with mock.patch(VERDICTS + 'verdict_panneau_onduleur', return_value={
                'statut': 'reserve', 'raisons': ['écrêtage'], 'nb_chaines': 2}):
            r = compatibilite_du_materiel(self.panneau.pk, self.onduleur.pk, self.co)
        self.assertEqual(r['panneau_onduleur'], {'statut': 'reserve',
                                                 'raisons': ['écrêtage']})

    def test_fiche_vide_inconnu_avec_champs_manquants(self):
        r = compatibilite_du_materiel(self.panneau.pk, self.onduleur.pk, self.co)
        self.assertEqual(r['panneau_onduleur']['statut'], 'inconnu')
        self.assertIn('complétez la fiche', r['panneau_onduleur']['raisons'][0])

    def test_autre_societe_ou_id_inconnu_inconnu(self):
        r = compatibilite_du_materiel(self.panneau.pk, self.onduleur_autre.pk, self.co)
        self.assertEqual(r['panneau_onduleur']['statut'], 'inconnu')
        self.assertEqual(r['panneau_onduleur']['raisons'],
                         ['onduleur introuvable dans le catalogue de la société'])
        r = compatibilite_du_materiel(None, self.onduleur.pk, self.co)
        self.assertEqual(r['panneau_onduleur']['statut'], 'inconnu')

    def test_batterie_donnee_verdict_batterie_onduleur(self):
        with mock.patch(VERDICTS + 'verdict_batterie_onduleur', return_value={
                'statut': 'compatible', 'raisons': []}) as verdict:
            r = compatibilite_du_materiel(self.panneau.pk, self.onduleur.pk,
                                          self.co, batterie_id=self.batterie.pk)
        verdict.assert_called_once()
        self.assertEqual(r['batterie_onduleur'], {'statut': 'compatible',
                                                  'raisons': []})
