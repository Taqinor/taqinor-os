"""PV16 — ``cible_depuis_lignes`` : la cible de calepinage vient des LIGNES.

L'écran de conception 3D doit repartir de ce que le devis dit AUJOURD'HUI
(panneaux, wattage unitaire, scénario), pas d'un blob de layout absent ou
périmé. Cette fonction est une LECTURE PURE : elle n'écrit ni statut, ni
ligne, ni étude — et elle expose ses doutes en français plutôt que de choisir
en silence.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_pv16_cible_depuis_lignes -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import CIBLE_WATT_DEFAUT, cible_depuis_lignes

User = get_user_model()


class TestCibleDepuisLignes(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='pv16-co', defaults={'nom': 'PV16'})
        self.user = User.objects.create_user(
            username='pv16user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PV16')
        self.compteur = 0

    def _produit(self, nom, sku):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'),
            quantite_stock=50)

    def _devis(self, *, etude=None):
        self.compteur += 1
        return Devis.objects.create(
            company=self.company, reference=f'DEV-PV16-{self.compteur}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, etude_params=etude)

    def _ligne(self, devis, designation, quantite=1, produit=None,
               type_ligne='produit'):
        return devis.lignes.create(
            produit=produit, designation=designation,
            quantite=(Decimal(str(quantite)) if quantite is not None else None),
            prix_unitaire=(Decimal('1000') if type_ligne == 'produit'
                           else None),
            type_ligne=type_ligne)

    # ── Cas nominal ─────────────────────────────────────────────────────────
    def test_devis_propre_aucun_avertissement(self):
        devis = self._devis()
        panneau = self._produit('Panneau Jinko 550W', 'PV16-PAN550')
        self._ligne(devis, 'Panneau Jinko 550W', 12, produit=panneau)
        self._ligne(devis, 'Onduleur réseau Huawei 5kW', 1,
                    produit=self._produit('Onduleur réseau Huawei 5kW',
                                          'PV16-ONDR'))
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panneaux'], 12)
        self.assertEqual(cible['panel_watt'], 550)
        self.assertAlmostEqual(cible['kwc'], 6.6, places=3)
        self.assertEqual(cible['scenario'], 'reseau')
        self.assertFalse(cible['batterie'])
        self.assertEqual(cible['avertissements'], [])

    def test_toutes_les_cles_toujours_presentes(self):
        cible = cible_depuis_lignes(self._devis())
        self.assertEqual(
            set(cible),
            {'panneaux', 'kwc', 'panel_watt', 'scenario', 'batterie',
             'avertissements'})

    def test_lignes_section_et_note_ignorees(self):
        devis = self._devis()
        panneau = self._produit('Panneau Jinko 550W', 'PV16-PAN-S')
        self._ligne(devis, 'Panneaux photovoltaïques', quantite=None,
                    type_ligne='section')
        self._ligne(devis, 'Panneau Jinko 550W', 8, produit=panneau)
        self._ligne(devis, 'Panneaux posés côté sud', quantite=None,
                    type_ligne='note')
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panneaux'], 8)
        self.assertEqual(cible['avertissements'], [])

    # ── Avertissement 1 — aucune ligne de panneau ───────────────────────────
    def test_avertissement_aucun_panneau(self):
        devis = self._devis()
        self._ligne(devis, 'Onduleur réseau Huawei 5kW', 1,
                    produit=self._produit('Onduleur réseau Huawei 5kW',
                                          'PV16-ONDR-B'))
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panneaux'], 0)
        self.assertEqual(cible['kwc'], 0.0)
        self.assertEqual(len(cible['avertissements']), 1)
        self.assertIn('Aucune ligne de panneau', cible['avertissements'][0])
        # Pas de second avertissement « wattage illisible » : sans panneau,
        # la question ne se pose pas.
        self.assertEqual(cible['panel_watt'], CIBLE_WATT_DEFAUT)

    def test_devis_sans_aucune_ligne(self):
        cible = cible_depuis_lignes(self._devis())
        self.assertEqual(cible['panneaux'], 0)
        self.assertEqual(len(cible['avertissements']), 1)

    # ── Avertissement 2 — wattage illisible ─────────────────────────────────
    def test_avertissement_wattage_illisible(self):
        devis = self._devis()
        produit = self._produit('Panneau monocristallin', 'PV16-PAN-MUET')
        self._ligne(devis, 'Panneau monocristallin', 10, produit=produit)
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], CIBLE_WATT_DEFAUT)
        self.assertEqual(len(cible['avertissements']), 1)
        self.assertIn('illisible', cible['avertissements'][0])

    def test_wattage_deduit_de_l_etude_sans_avertissement(self):
        """Repli chiffré : la puissance de l'étude vaut une lecture, pas un doute."""
        devis = self._devis(etude={'puissance_kwc': 7.1})
        produit = self._produit('Panneau monocristallin', 'PV16-PAN-ETUDE')
        self._ligne(devis, 'Panneau monocristallin', 10, produit=produit)
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], 710)
        self.assertAlmostEqual(cible['kwc'], 7.1, places=3)
        self.assertEqual(cible['avertissements'], [])

    def test_wattage_lu_sur_le_nom_du_produit_si_designation_muette(self):
        devis = self._devis()
        produit = self._produit('Panneau Jinko 550W', 'PV16-PAN-NOM')
        self._ligne(devis, 'Panneau solaire (pose comprise)', 10,
                    produit=produit)
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], 550)
        self.assertEqual(cible['avertissements'], [])

    # ── Avertissement 3 — deux modèles de panneau ───────────────────────────
    def test_avertissement_deux_modeles_de_panneau(self):
        devis = self._devis()
        p450 = self._produit('Panneau Longi 450W', 'PV16-PAN450')
        p550 = self._produit('Panneau Jinko 550W', 'PV16-PAN550-D')
        self._ligne(devis, 'Panneau Longi 450W', 4, produit=p450)
        self._ligne(devis, 'Panneau Jinko 550W', 14, produit=p550)
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panneaux'], 18)
        # Le wattage vient de la ligne DOMINANTE (la plus grosse quantité).
        self.assertEqual(cible['panel_watt'], 550)
        self.assertEqual(len(cible['avertissements']), 1)
        message = cible['avertissements'][0]
        self.assertIn('2 modèles', message)
        self.assertIn('Panneau Jinko 550W', message)

    # ── Scénario ────────────────────────────────────────────────────────────
    def test_scenario_avec_batterie(self):
        devis = self._devis()
        self._ligne(devis, 'Panneau Jinko 550W', 12,
                    produit=self._produit('Panneau Jinko 550W', 'PV16-PB'))
        self._ligne(devis, 'Onduleur hybride Deye 5kW', 1,
                    produit=self._produit('Onduleur hybride Deye 5kW',
                                          'PV16-ONDH'))
        self._ligne(devis, 'Batterie Deyness 5 kWh', 1,
                    produit=self._produit('Batterie Deyness 5 kWh',
                                          'PV16-BAT'))
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['scenario'], 'avec_batterie')
        self.assertTrue(cible['batterie'])

    def test_scenario_hybride_sans_batterie(self):
        devis = self._devis()
        self._ligne(devis, 'Panneau Jinko 550W', 12,
                    produit=self._produit('Panneau Jinko 550W', 'PV16-PH'))
        self._ligne(devis, 'Onduleur hybride Deye 5kW', 1,
                    produit=self._produit('Onduleur hybride Deye 5kW',
                                          'PV16-ONDH2'))
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['scenario'], 'hybride')
        self.assertFalse(cible['batterie'])

    # ── Fiche technique (sélecteur stock, absent ou présent) ────────────────
    def test_pmax_de_la_fiche_technique_prime_sur_le_libelle(self):
        from apps.stock import selectors as stock_selectors

        devis = self._devis()
        produit = self._produit('Panneau Jinko 550W', 'PV16-PAN-FICHE')
        self._ligne(devis, 'Panneau Jinko 550W', 10, produit=produit)
        with mock.patch.object(stock_selectors, 'specs_for_produit',
                               create=True,
                               return_value={'pmax_wc': Decimal('610')}):
            cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], 610)
        self.assertAlmostEqual(cible['kwc'], 6.1, places=3)

    def test_selecteur_en_panne_retombe_sur_le_libelle(self):
        from apps.stock import selectors as stock_selectors

        devis = self._devis()
        produit = self._produit('Panneau Jinko 550W', 'PV16-PAN-PANNE')
        self._ligne(devis, 'Panneau Jinko 550W', 10, produit=produit)
        with mock.patch.object(stock_selectors, 'specs_for_produit',
                               create=True,
                               side_effect=RuntimeError('indisponible')):
            cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], 550)
        self.assertEqual(cible['avertissements'], [])

    def test_selecteur_absent_est_un_non_evenement(self):
        """L'arbre peut ne pas encore porter ``specs_for_produit`` : c'est normal."""
        devis = self._devis()
        produit = self._produit('Panneau Jinko 550W', 'PV16-PAN-ABSENT')
        self._ligne(devis, 'Panneau Jinko 550W', 10, produit=produit)
        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panel_watt'], 550)
        self.assertEqual(cible['avertissements'], [])

    # ── Lecture pure ────────────────────────────────────────────────────────
    def test_aucune_ecriture(self):
        devis = self._devis()
        produit = self._produit('Panneau Jinko 550W', 'PV16-PAN-PUR')
        self._ligne(devis, 'Panneau Jinko 550W', 12, produit=produit)
        cible_depuis_lignes(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.lignes.count(), 1)
        self.assertIsNone(devis.etude_params)
