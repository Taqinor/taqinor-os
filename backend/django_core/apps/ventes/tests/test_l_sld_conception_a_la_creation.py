# -*- coding: utf-8 -*-
"""L-SLD (24/08/2026) — la CONCEPTION ÉLECTRIQUE au chemin de création du
générateur (``POST /devis/atomic/``).

Avant ce correctif, ``build_electrical_design`` n'avait qu'un seul appelant en
production : l'ouverture de l'onglet « Conception électrique ». Un devis créé
par l'écran générateur et jamais ouvert dans cet onglet n'avait donc pas
d'``electrical_design`` — donc pas de schéma unifilaire sur la page client
(même au niveau « confiance ») ni dans l'annexe technique du PDF.

Trois garanties :

  * un devis créé avec panneau + onduleur à fiches COMPLÈTES porte son étude
    dès la création (chaînes calculées, conformité rendue) ;
  * un devis SANS module (pompage, prestation) ne range RIEN — l'annexe
    technique se déclenche sur la seule EXISTENCE d'une étude, une étude vide
    imprimerait une annexe sans nomenclature ;
  * une fiche technique INCOMPLÈTE ne range rien non plus (PVFCH : on
    n'invente aucune variable d'équipement).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_l_sld_conception_a_la_creation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class LSldConceptionALaCreationTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='lsld-co', defaults={'nom': 'L-SLD Co'})
        self.user = User.objects.create_user(
            username='lsld_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='LSLD',
            telephone='+212600000091')

        # Panneau + onduleur du catalogue seedé (valeurs RÉELLES de fiche :
        # aucune n'est inventée ici, le moteur ne lit que celles-ci).
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadian Solar 550 Wc',
            sku='LSLD-PV550', prix_vente=Decimal('900'), quantite_stock=100)
        FicheTechnique.objects.create(
            company=self.company, produit=self.panneau, type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            vmp_v=Decimal('41.70'), isc_a=Decimal('13.95'),
            imp_a=Decimal('13.20'),
            temp_coeff_voc_pct_c=Decimal('-0.260'),
            temp_coeff_pmax_pct_c=Decimal('-0.340'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 5 kW monophasé',
            sku='LSLD-OND5', prix_vente=Decimal('9000'), quantite_stock=10)
        FicheTechnique.objects.create(
            company=self.company, produit=self.onduleur,
            type_fiche='onduleur', ond_ac_kw=Decimal('5.00'), ond_phases=1,
            ond_n_mppt=2, ond_mppt_v_min=Decimal('120.0'),
            ond_mppt_v_max=Decimal('500.0'), ond_v_max_abs=Decimal('600.0'),
            ond_i_max_mppt_a=Decimal('16.0'))
        self.pompe = Produit.objects.create(
            company=self.company, nom='Pompe immergée 3 CV',
            sku='LSLD-POMPE', prix_vente=Decimal('15000'), quantite_stock=5)

    def _creer(self, lignes):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'lignes': lignes,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return Devis.objects.get(id=resp.data['id'])

    def test_creation_generateur_pose_la_conception(self):
        """Panneau + onduleur à fiches complètes ⇒ l'étude est RANGÉE dès la
        création, sans ouvrir l'onglet « Conception électrique »."""
        devis = self._creer([
            {'produit': self.panneau.id, 'quantite': '8',
             'prix_unitaire': '900',
             'designation': 'Panneau Canadian Solar 550 Wc'},
            {'produit': self.onduleur.id, 'quantite': '1',
             'prix_unitaire': '9000',
             'designation': 'Onduleur réseau 5 kW monophasé'},
        ])
        self.assertIsInstance(devis.electrical_design, dict)
        self.assertTrue(devis.electrical_design)
        self.assertTrue(devis.electrical_design_hash)
        self.assertTrue(devis.electrical_design['chaines'])
        self.assertTrue(devis.electrical_design['conformite']['conforme'])
        # Le schéma unifilaire — la surface qui manquait — sort désormais.
        from apps.ventes.electrical_service import rendre_schema_du_devis
        self.assertTrue(rendre_schema_du_devis(devis))

    def test_sans_module_aucune_conception_rangee(self):
        """Devis de pompage : aucun module à répartir ⇒ RIEN n'est rangé
        (une étude vide déclencherait une annexe technique sans
        nomenclature)."""
        devis = self._creer([
            {'produit': self.pompe.id, 'quantite': '1',
             'prix_unitaire': '15000',
             'designation': 'Pompe immergée 3 CV'},
        ])
        self.assertIsNone(devis.electrical_design)

    def test_fiche_incomplete_aucune_conception_rangee(self):
        """PVFCH — une fiche muette n'est jamais comblée : sans fiche
        technique sur le panneau, aucune étude n'est rangée."""
        nu = Produit.objects.create(
            company=self.company, nom='Panneau PV 450 Wc sans fiche',
            sku='LSLD-PVNU', prix_vente=Decimal('700'), quantite_stock=10)
        devis = self._creer([
            {'produit': nu.id, 'quantite': '8', 'prix_unitaire': '700',
             'designation': 'Panneau PV 450 Wc sans fiche'},
            {'produit': self.onduleur.id, 'quantite': '1',
             'prix_unitaire': '9000',
             'designation': 'Onduleur réseau 5 kW monophasé'},
        ])
        self.assertIsNone(devis.electrical_design)
