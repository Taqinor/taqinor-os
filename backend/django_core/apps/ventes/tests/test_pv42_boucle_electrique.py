"""PV42 — la boucle se ferme : calepinage 3D → conception ÉLECTRIQUE par pan.

Quatre promesses, et rien d'autre :

1. **Un devis à deux pans reçoit DEUX groupes de chaînes, jamais mélangés.**
   Deux orientations n'atteignent pas leur point de puissance maximale au même
   instant : les faire partager une entrée MPPT coûte de la production tous les
   jours de l'année, en silence. La séparation est donc VÉRIFIÉE ici, sur la
   sortie réellement persistée — pas déduite du code du moteur.
2. **Une panne d'étude électrique ne fait JAMAIS perdre un devis.** Ni à la
   création, ni à la resynchronisation. La pièce technique est un plus ; le
   devis est le métier.
3. **Le kit-produit est transmis au calepinage (PV12).** Le panneau réellement
   vendu — la ligne du devis d'abord, le catalogue de la société ensuite —
   arrive en ``produit_panneau`` jusqu'à ``calepinage_villa``, avec le scoping
   société correct (un produit du catalogue GLOBAL n'est jamais opposé à une
   société : ce serait un refus, donc un kit perdu).
4. **Un layout SANS géométrie ne bouge pas d'un octet.** Mêmes lignes, mêmes
   quantités, mêmes ``etude_params``, même ``roof_layout``, même statut. La
   seule différence admise est ADDITIVE : la pièce technique électrique, qui
   n'existait nulle part avant.

Règle #4 : ce module ne fait écrire AUCUN statut — la garde est explicite.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv42_boucle_electrique -v 2
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes import services
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

#: Ancre géographique quelconque — la géométrie n'est lue que par le moteur de
#: calepinage, qui est REMPLACÉ par un mouchard dans les tests de kit-produit.
LNG0, LAT0 = -7.5898, 33.5731


def _carre(decalage=0.0):
    """Un contour à 4 sommets ``[lng, lat]`` — assez pour être « exploitable »."""
    d = 0.0005
    return [[LNG0 + decalage, LAT0],
            [LNG0 + decalage + d, LAT0],
            [LNG0 + decalage + d, LAT0 + d],
            [LNG0 + decalage, LAT0 + d]]


def layout_deux_pans():
    """Layout roofPro11 à DEUX pans d'orientations DIFFÉRENTES."""
    return {
        'scenario': 'reseau',
        'panelWatt': 550,
        'result': {'panels': 24, 'kwc': 13.2,
                   'annualKwh': 21000, 'savings': 18000},
        'zones': [
            {'id': 'Z1', 'label': 'Pan Sud', 'vertices': _carre(),
             'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 25,
             'facingAzimuthDeg': 0,
             'result': {'count': 16, 'kwc': 8.8, 'areaM2': 40.0}},
            {'id': 'Z2', 'label': 'Pan Est', 'vertices': _carre(0.001),
             'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 25,
             'facingAzimuthDeg': -90,
             'result': {'count': 8, 'kwc': 4.4, 'areaM2': 20.0}},
        ],
    }


def layout_un_pan():
    """Le même toit, mais sur un SEUL pan (base des tests de resynchro)."""
    return {
        'scenario': 'reseau',
        'panelWatt': 550,
        'result': {'panels': 16, 'kwc': 8.8,
                   'annualKwh': 14000, 'savings': 12000},
        'zones': [
            {'id': 'Z1', 'label': 'Pan Sud', 'vertices': _carre(),
             'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 25,
             'facingAzimuthDeg': 0,
             'result': {'count': 16, 'kwc': 8.8, 'areaM2': 40.0}},
        ],
    }


def layout_sans_geometrie():
    """Le layout HISTORIQUE : un bloc ``result``, et rien d'autre."""
    return {'scenario': 'reseau', 'panelWatt': 550,
            'result': {'panels': 9, 'kwc': 4.95,
                       'annualKwh': 8000, 'savings': 7000}}


class _Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='pv42-co', defaults={'nom': 'PV42'})
        self.user = User.objects.create_user(
            username='pv42', password='x', role_legacy='responsable',
            company=self.company)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV42-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('800'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Triphasé',
            sku='PV42-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('11000'), quantite_stock=10)

    def _lead(self):
        return Lead.objects.create(
            company=self.company, nom='Boucle', prenom='Villa',
            email='boucle@ex.com')

    def _devis(self, layout):
        return services.build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())

    def _snapshot_lignes(self, devis):
        return sorted(
            (ligne.designation, int(ligne.quantite),
             Decimal(ligne.prix_unitaire))
            for ligne in devis.lignes.all())


class LaConceptionElectriqueSuitLeCalepinage(_Base):
    """Promesse 1 — deux pans, deux groupes, jamais sur la même entrée MPPT."""

    def test_deux_pans_donnent_deux_groupes_separes(self):
        devis = self._devis(layout_deux_pans())
        devis.refresh_from_db()
        design = devis.electrical_design
        self.assertIsInstance(design, dict)
        self.assertEqual(len(devis.electrical_design_hash), 64)

        chaines = design['chaines']
        self.assertTrue(chaines, 'aucune chaîne conçue')
        # Les deux pans du calepinage se retrouvent dans les chaînes.
        self.assertEqual({chaine['pan'] for chaine in chaines}, {1, 2})
        # ... et AUCUNE entrée MPPT ne porte deux pans à la fois.
        pans_par_mppt = {}
        for chaine in chaines:
            pans_par_mppt.setdefault(chaine['mppt'], set()).add(chaine['pan'])
        for mppt, pans in pans_par_mppt.items():
            self.assertEqual(
                len(pans), 1,
                "l'entrée MPPT %s porte %d orientations" % (mppt, len(pans)))

    def test_le_calepinage_stocke_porte_bien_les_deux_pans(self):
        """La source des groupes est ``roof_layout['_pans_geometry']``."""
        devis = self._devis(layout_deux_pans())
        devis.refresh_from_db()
        pans = devis.roof_layout['_pans_geometry']
        self.assertEqual(len(pans), 2)
        self.assertEqual([pan['nb_panneaux'] for pan in pans], [16, 8])
        self.assertNotEqual(pans[0]['azimut_deg'], pans[1]['azimut_deg'])

    def test_la_conception_ne_touche_aucun_statut(self):
        """Règle #4 — la pièce technique n'écrit jamais un statut."""
        devis = self._devis(layout_deux_pans())
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_la_resynchro_recalcule_la_conception(self):
        devis = self._devis(layout_un_pan())
        devis.refresh_from_db()
        avant = devis.electrical_design_hash
        self.assertEqual(
            {chaine['pan'] for chaine in devis.electrical_design['chaines']},
            {1})

        services.sync_devis_from_layout(devis, layout_deux_pans(),
                                        user=self.user)
        devis.refresh_from_db()
        self.assertNotEqual(devis.electrical_design_hash, avant)
        self.assertEqual(
            {chaine['pan'] for chaine in devis.electrical_design['chaines']},
            {1, 2})
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class UnePanneElectriqueNeCassePasLeDevis(_Base):
    """Promesse 2 — l'étude électrique est un PLUS, jamais un point de rupture."""

    def test_la_creation_survit_a_une_panne(self):
        with patch('apps.ventes.electrical_service.build_electrical_design',
                   side_effect=RuntimeError('moteur électrique HS')):
            devis = self._devis(layout_deux_pans())
        devis.refresh_from_db()
        self.assertIsNone(devis.electrical_design)
        # Le devis, lui, est complet : lignes, calepinage, étude, statut.
        self.assertEqual(len(self._snapshot_lignes(devis)), 2)
        self.assertEqual(devis.roof_layout['_pans_geometry'][0]['nb_panneaux'],
                         16)
        self.assertEqual(devis.etude_params['puissance_kwc'], 13.2)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_la_panne_est_journalisee(self):
        with patch('apps.ventes.electrical_service.build_electrical_design',
                   side_effect=RuntimeError('moteur électrique HS')):
            with self.assertLogs('apps.ventes.services',
                                 level='WARNING') as journal:
                self._devis(layout_deux_pans())
        self.assertTrue(any('PV42' in ligne for ligne in journal.output),
                        journal.output)

    def test_la_resynchro_survit_a_une_panne(self):
        devis = self._devis(layout_un_pan())
        with patch('apps.ventes.electrical_service.build_electrical_design',
                   side_effect=RuntimeError('moteur électrique HS')):
            resultat = services.sync_devis_from_layout(
                devis, layout_deux_pans(), user=self.user)
        self.assertFalse(resultat['inchange'])
        devis.refresh_from_db()
        # La resynchro elle-même a bien été validée (elle est en base).
        self.assertEqual(len(devis.roof_layout['_pans_geometry']), 2)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class _MoteurMouchard:
    """Remplace ``calepinage_villa`` et note ce qu'on lui a passé."""

    def __init__(self, modules=17):
        self.appels = []
        self.modules = modules

    def __call__(self, area, **kwargs):
        self.appels.append(kwargs)
        return {
            'resultat': SimpleNamespace(
                modules=self.modules, hash_entree='h', version_moteur='v'),
            'preuve': {'methode': 'mouchard', 'compte_optimal': self.modules},
        }


@override_settings(USE_MOTEUR_CALEPINAGE=True)
class LeKitProduitEstTransmisAuCalepinage(_Base):
    """Promesse 3 — le panneau RÉELLEMENT vendu descend jusqu'au moteur."""

    def test_le_panneau_du_catalogue_est_transmis_a_la_creation(self):
        mouchard = _MoteurMouchard()
        with patch('apps.ao.selectors.calepinage_villa', mouchard):
            self._devis(layout_deux_pans())
        self.assertEqual(len(mouchard.appels), 2)
        for kwargs in mouchard.appels:
            self.assertEqual(kwargs['produit_panneau'], self.panneau)
            self.assertEqual(kwargs['company'], self.company)
            self.assertEqual(kwargs['ordre'], 'lnglat')

    def test_le_panneau_du_devis_prime_sur_le_catalogue(self):
        autre = Produit.objects.create(
            company=self.company, nom='Panneau Longi 600W', sku='PV42-PAN2',
            prix_vente=Decimal('2500'), prix_achat=Decimal('2000'),
            quantite_stock=10)
        devis = self._devis(layout_un_pan())
        devis.lignes.filter(designation__icontains='Panneau').update(
            produit=autre, designation=autre.nom)

        mouchard = _MoteurMouchard()
        with patch('apps.ao.selectors.calepinage_villa', mouchard):
            mesure = services.compte_moteur_du_layout(
                layout_deux_pans(), company=self.company, devis=devis)
        self.assertIsNotNone(mesure)
        self.assertEqual(mesure['produit_panneau'], autre.pk)
        for kwargs in mouchard.appels:
            self.assertEqual(kwargs['produit_panneau'], autre)

    def test_un_produit_global_n_est_pas_oppose_a_une_societe(self):
        """Catalogue GLOBAL : ``company=None``, sinon le kit serait REFUSÉ."""
        # Moins cher que le panneau société : c'est LUI que ``_pick_product``
        # retiendra (même wattage exact, prix le plus bas).
        global_ = Produit.objects.create(
            company=None, nom='Panneau Global 550W', sku='PV42-PAN-G',
            prix_vente=Decimal('900'), prix_achat=Decimal('700'),
            quantite_stock=10)
        mouchard = _MoteurMouchard()
        with patch('apps.ao.selectors.calepinage_villa', mouchard):
            services.compte_moteur_du_layout(layout_deux_pans(),
                                             company=self.company)
        self.assertTrue(mouchard.appels)
        for kwargs in mouchard.appels:
            self.assertEqual(kwargs['produit_panneau'], global_)
            self.assertIsNone(kwargs['company'])

    def test_sans_societe_ni_devis_l_appel_reste_celui_d_hier(self):
        mouchard = _MoteurMouchard()
        with patch('apps.ao.selectors.calepinage_villa', mouchard):
            services.compte_moteur_du_layout(layout_deux_pans())
        self.assertTrue(mouchard.appels)
        for kwargs in mouchard.appels:
            self.assertIsNone(kwargs['produit_panneau'])
            self.assertIsNone(kwargs['company'])


class UnLayoutSansGeometrieNeBougePas(_Base):
    """Promesse 4 — le chemin historique est verrouillé, clé par clé."""

    def test_le_devis_est_celui_d_hier(self):
        layout = layout_sans_geometrie()
        devis = self._devis(layout)
        devis.refresh_from_db()

        self.assertEqual(self._snapshot_lignes(devis), sorted([
            ('Panneau Jinko 550W', 9, Decimal('1100')),
            ('Onduleur réseau Huawei 10kW Triphasé', 1, Decimal('14000')),
        ]))
        self.assertEqual(devis.etude_params, {
            # PVSCE — le scénario est désormais STOCKÉ dès la création : sans
            # lui, le moteur PDF (QF6) déduit l'option depuis les lignes, et se
            # trompe dès que la composition est partielle. Ici le catalogue n'a
            # ni hybride ni batterie ⇒ « Sans batterie », ce que les lignes
            # peuvent réellement servir.
            'scenario': 'Sans batterie',
            'production_annuelle': 8000,
            'economies_annuelles': 7000,
            'puissance_kwc': 4.95,
            # ``payback_annees`` fait PARTIE d'hier : le récepteur QX24
            # (bien antérieur au calepinage) le dérive à chaque écriture de
            # ligne, ici 9 × 1 100 + 14 000 = 23 900 HT → 28 680 TTC, divisé
            # par 7 000 MAD/an d'économies. L'omettre reviendrait à figer une
            # promesse « d'hier » que le code d'hier ne tenait déjà pas.
            'payback_annees': 4.1,
        })
        # Aucune géométrie ⇒ aucun enrichissement du layout stocké.
        self.assertEqual(devis.roof_layout, layout)
        self.assertNotIn('_pans_geometry', devis.roof_layout)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_le_moteur_reste_muet_sans_geometrie(self):
        mouchard = _MoteurMouchard()
        with patch('apps.ao.selectors.calepinage_villa', mouchard):
            self.assertIsNone(services.compte_moteur_du_layout(
                layout_sans_geometrie(), company=self.company))
        self.assertEqual(mouchard.appels, [])

    def test_la_piece_technique_est_la_seule_nouveaute(self):
        """Additif : l'étude électrique retombe sur les LIGNES du devis (PV16)."""
        devis = self._devis(layout_sans_geometrie())
        devis.refresh_from_db()
        design = devis.electrical_design
        self.assertIsInstance(design, dict)
        # Un seul pan implicite ⇒ un seul groupe.
        self.assertEqual({chaine['pan'] for chaine in design['chaines']}, {1})
