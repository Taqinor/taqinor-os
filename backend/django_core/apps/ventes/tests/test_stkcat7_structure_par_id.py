# -*- coding: utf-8 -*-
"""STKCAT7 — la structure se choisit PAR PRODUIT, plus par un toggle.

Le fait que ces tests verrouillent (audit L3 stock ↔ CRM ↔ devis du
16/09/2026, « Pergola introuvable ») : une PERGOLA est une structure, mais son
nom ne contient pas le mot « structure ». Le classifieur par MOTS-CLÉS
(``classer_produit``) ne pouvait donc pas la voir, et aucun devis ne pouvait la
composer — quel que soit le soin mis à la saisir au catalogue.

Ce qui est verrouillé ici, point par point :

  * un produit dont la CATÉGORIE est typée ``structure`` (STKCAT2) entre au
    vivier structure même si son nom ne dit rien ;
  * il est composable PAR SON ID (``structure_produit_id``) — et JAMAIS par
    mot-clé : le toggle acier/alu ne voit que les structures NOMMÉES, donc une
    composition SANS id compose EXACTEMENT ce que ce dépôt composait hier ;
  * l'id est PRIORITAIRE sur ``structure_type`` (l'alias déprécié) et il n'est
    soumis NI au filtre acier/alu NI à la marque épinglée du rôle ;
  * la RÈGLE D'ÉMISSION DU RÔLE du contrat
    (``contract_samples/devis_composition.json``) : ``structure_acier`` /
    ``structure_alu`` quand le produit RETENU porte encore le mot-clé, le rôle
    générique ``structure`` quand il n'en porte AUCUN ;
  * un id qui ne désigne rien dans le catalogue SCOPÉ SOCIÉTÉ (autre société,
    produit sans prix, id inexistant) ne résout rien : repli silencieux sur le
    toggle, jamais une composition sans structure ni une fuite cross-tenant ;
  * la composition reste PURE : aucune requête par candidat (la catégorie est
    préchargée par ``catalogue_de_la_societe``).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, Produit
from apps.ventes import services
from authentication.models import Company

User = get_user_model()

COMPO_URL = '/api/django/ventes/devis/composition/'

#: Le kit minimal qui compose : un panneau, les deux onduleurs, les DEUX
#: structures NOMMÉES (le rail historique) et les forfaits.
CATALOGUE = [
    ('Panneau Canadien Solar 710W', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', '17000'),
    ('Structures acier', '500'),
    ('Structures aluminium', '850'),
    ('Socles', '80'),
    ('Transport', '1000'),
]


def auth_client(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(user))
    return api


class STKCAT7Base(TestCase):
    slug = 'stkcat7-co'

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})[0]
        self.autre_company = Company.objects.get_or_create(
            slug='%s-autre' % self.slug,
            defaults={'nom': '%s autre' % self.slug})[0]
        self.user = User.objects.create_user(
            username='stkcat7-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')

        for nom, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=1000)

        # La catégorie TYPÉE structure : c'est elle, et elle seule, qui fait
        # entrer au vivier les produits que le nom ne trahit pas.
        self.cat_structures = Categorie.objects.create(
            company=self.company, nom='STKCAT7 Structures spéciales',
            ordre=15, type_equipement=Categorie.TypeEquipement.STRUCTURE)
        self.pergola = Produit.objects.create(
            company=self.company, nom='Pergola acier 4x3',
            categorie=self.cat_structures, prix_vente=Decimal('18000'),
            prix_achat=Decimal('1'), quantite_stock=5)
        self.carport = Produit.objects.create(
            company=self.company, nom='Carport aluminium 6x3',
            categorie=self.cat_structures, prix_vente=Decimal('22000'),
            prix_achat=Decimal('1'), quantite_stock=5)
        #: Ni « acier » ni « alu » dans le nom ⇒ rôle GÉNÉRIQUE ``structure``.
        self.abri = Produit.objects.create(
            company=self.company, nom='Abri de jardin 3x5',
            categorie=self.cat_structures, prix_vente=Decimal('9000'),
            prix_achat=Decimal('1'), quantite_stock=5)
        self.pergola_sans_prix = Produit.objects.create(
            company=self.company, nom='Pergola acier prix à renseigner',
            categorie=self.cat_structures, prix_vente=Decimal('0'),
            prix_achat=Decimal('0'), quantite_stock=5)

        # La MÊME fiche, chez une AUTRE société : elle ne doit jamais résoudre.
        self.cat_voisine = Categorie.objects.create(
            company=self.autre_company, nom='STKCAT7 Structures voisines',
            ordre=15, type_equipement=Categorie.TypeEquipement.STRUCTURE)
        self.pergola_voisine = Produit.objects.create(
            company=self.autre_company, nom='Pergola voisine acier',
            categorie=self.cat_voisine, prix_vente=Decimal('17000'),
            prix_achat=Decimal('1'), quantite_stock=5)

    # ── outils de lecture ──────────────────────────────────────────────────
    def catalogue(self):
        return services.catalogue_de_la_societe(self.company)

    def composer(self, **extra):
        return services.composition_residentielle(
            self.catalogue(), kwc=5, panel_watt=710, **extra)

    @staticmethod
    def ligne_structure(lignes):
        """Le couple (rôle, ligne) de la structure retenue, ou (None, None)."""
        roles = list(lignes.roles)
        for index, ligne in enumerate(lignes):
            if roles[index].startswith('structure'):
                return roles[index], ligne
        return None, None


class LeToggleNeVoitQueLesStructuresNommees(STKCAT7Base):
    def test_sans_id_la_pergola_n_est_jamais_choisie_par_mot_cle(self):
        """LE test décisif : « Pergola acier 4x3 » porte bien « acier », mais
        elle n'entre au vivier que par sa CATÉGORIE — le toggle acier/alu ne
        peut donc pas la ramasser à la place de « Structures acier »."""
        role, ligne = self.ligne_structure(self.composer())
        self.assertEqual(role, 'structure_acier')
        self.assertEqual(ligne.designation, 'Structures acier')

    def test_sans_id_le_toggle_alu_reste_celui_d_hier(self):
        role, ligne = self.ligne_structure(
            self.composer(structure_type='aluminium'))
        self.assertEqual(role, 'structure_alu')
        self.assertEqual(ligne.designation, 'Structures aluminium')

    def test_non_regression_la_pergola_ne_change_rien_a_la_composition(self):
        """Comportement INCHANGÉ : les lignes composées sans id sont
        exactement celles d'un catalogue SANS aucun produit typé par
        catégorie — mêmes désignations, mêmes rôles, mêmes quantités."""
        avec_pergolas = self.composer()
        sans_pergolas = services.composition_residentielle(
            [p for p in self.catalogue() if p.categorie_id is None],
            kwc=5, panel_watt=710)
        self.assertEqual(
            [(r, li.designation, li.quantite, li.prix_unitaire)
             for r, li in zip(avec_pergolas.roles, avec_pergolas)],
            [(r, li.designation, li.quantite, li.prix_unitaire)
             for r, li in zip(sans_pergolas.roles, sans_pergolas)])


class LIdExpliciteGagne(STKCAT7Base):
    def test_la_pergola_est_composable_par_son_id(self):
        lignes = self.composer(structure_produit_id=self.pergola.id)
        role, ligne = self.ligne_structure(lignes)
        self.assertEqual(ligne.designation, 'Pergola acier 4x3')
        self.assertEqual(ligne.produit.id, self.pergola.id)
        # Le nom porte encore « acier » ⇒ l'ALIAS reste émis (règle du contrat).
        self.assertEqual(role, 'structure_acier')

    def test_l_id_gagne_sur_le_toggle_qui_le_contredit(self):
        """``structure_produit_id`` est PRIORITAIRE : les deux ne se combinent
        jamais, un ``structure_type`` contradictoire est simplement ignoré."""
        lignes = self.composer(structure_produit_id=self.carport.id,
                               structure_type='acier')
        role, ligne = self.ligne_structure(lignes)
        self.assertEqual(ligne.designation, 'Carport aluminium 6x3')
        self.assertEqual(role, 'structure_alu')

    def test_role_generique_quand_le_nom_ne_dit_ni_acier_ni_alu(self):
        lignes = self.composer(structure_produit_id=self.abri.id)
        role, ligne = self.ligne_structure(lignes)
        self.assertEqual(ligne.designation, 'Abri de jardin 3x5')
        self.assertEqual(role, 'structure')

    def test_une_structure_nommee_reste_choisissable_par_id(self):
        nommee = Produit.objects.get(company=self.company,
                                     nom='Structures aluminium')
        lignes = self.composer(structure_produit_id=nommee.id)
        role, ligne = self.ligne_structure(lignes)
        self.assertEqual(ligne.designation, 'Structures aluminium')
        self.assertEqual(role, 'structure_alu')

    def test_la_quantite_reste_une_par_panneau(self):
        lignes = self.composer(structure_produit_id=self.pergola.id)
        _role, ligne_structure = self.ligne_structure(lignes)
        panneaux = next(li for r, li in zip(lignes.roles, lignes)
                        if r == 'panneau')
        self.assertEqual(ligne_structure.quantite, panneaux.quantite)


class UnIdQuiNeDesigneRienRetombeSurLeToggle(STKCAT7Base):
    def _designation(self, **extra):
        return self.ligne_structure(self.composer(**extra))[1].designation

    def test_id_inexistant(self):
        self.assertEqual(
            self._designation(structure_produit_id=99999999),
            'Structures acier')

    def test_id_non_numerique(self):
        self.assertEqual(
            self._designation(structure_produit_id='pergola'),
            'Structures acier')

    def test_id_vide(self):
        self.assertEqual(
            self._designation(structure_produit_id=''), 'Structures acier')

    def test_id_d_un_produit_sans_prix(self):
        """Règle du dépôt : un produit SANS prix n'est jamais auto-coté — même
        désigné explicitement (la résolution par id passe APRÈS la garde de
        prix)."""
        self.assertEqual(
            self._designation(structure_produit_id=self.pergola_sans_prix.id),
            'Structures acier')

    def test_id_d_une_autre_societe(self):
        """Multi-tenant : l'id résout dans la liste DÉJÀ scopée société — la
        pergola de la société voisine n'y est pas, donc elle ne résout rien."""
        self.assertEqual(
            self._designation(structure_produit_id=self.pergola_voisine.id),
            'Structures acier')


class LaMarqueEpingleeNeReprendPasUnChoixExplicite(STKCAT7Base):
    MARQUES = {'structure_acier': 'MarqueQuiNExistePas'}

    def test_sans_id_l_epingle_vide_le_vivier_et_se_consigne(self):
        """Comportement PVMRQ inchangé : une marque épinglée sans candidat
        vide le vivier (jamais un repli silencieux) et se consigne."""
        lignes = self.composer(marques=self.MARQUES)
        role, _ligne = self.ligne_structure(lignes)
        self.assertIsNone(role)
        self.assertIn(
            'structure_acier',
            [m['role'] for m in lignes.marques_manquantes])

    def test_avec_un_id_l_epingle_ne_s_applique_pas(self):
        lignes = self.composer(marques=self.MARQUES,
                               structure_produit_id=self.pergola.id)
        role, ligne = self.ligne_structure(lignes)
        self.assertEqual(ligne.designation, 'Pergola acier 4x3')
        self.assertEqual(role, 'structure_acier')
        self.assertNotIn(
            'structure_acier',
            [m['role'] for m in lignes.marques_manquantes])


class LaCompositionResteUneFonctionPure(STKCAT7Base):
    def test_aucune_requete_par_candidat(self):
        """``catalogue_de_la_societe`` précharge ``categorie`` : lire le type
        d'équipement de CHAQUE produit ne coûte AUCUNE requête.

        La garde compare DEUX catalogues de tailles différentes : ce qui est
        interdit, c'est qu'une requête apparaisse PAR CANDIDAT (la composition
        est une fonction pure — elle reçoit sa liste, elle n'interroge rien).
        """
        catalogue = self.catalogue()
        exclus = {self.carport.id, self.abri.id}
        court = [p for p in catalogue if p.id not in exclus]
        self.assertLess(len(court), len(catalogue))

        with CaptureQueriesContext(connection) as ctx_court:
            services.composition_residentielle(
                court, kwc=5, panel_watt=710,
                structure_produit_id=self.pergola.id)
        with CaptureQueriesContext(connection) as ctx_long:
            services.composition_residentielle(
                catalogue, kwc=5, panel_watt=710,
                structure_produit_id=self.pergola.id)
        self.assertEqual(len(ctx_court.captured_queries),
                         len(ctx_long.captured_queries),
                         'la composition requête PAR CANDIDAT : la catégorie '
                         "n'est plus préchargée par catalogue_de_la_societe")


class LEndpointDryRunPorteLeChamp(STKCAT7Base):
    """Le contrat ``devis_composition.json`` documente ``structure_produit_id``
    dans le corps : l'endpoint doit vraiment le lire."""

    def setUp(self):
        super().setUp()
        self.api = auth_client(self.user)

    def _structure(self, charge):
        for ligne in charge['lignes']:
            if str(ligne['role']).startswith('structure'):
                return ligne
        return None

    def test_l_endpoint_compose_la_pergola_demandee(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
            'structure_produit_id': self.pergola.id,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne = self._structure(r.data)
        self.assertIsNotNone(ligne)
        self.assertEqual(ligne['designation'], 'Pergola acier 4x3')
        self.assertEqual(ligne['role'], 'structure_acier')
        self.assertEqual(ligne['produit'], self.pergola.id)

    def test_l_endpoint_emet_le_role_generique(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
            'structure_produit_id': self.abri.id,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._structure(r.data)['role'], 'structure')

    def test_un_id_non_numerique_ne_fait_pas_500(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
            'structure_produit_id': 'abc',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            self._structure(r.data)['designation'], 'Structures acier')

    def test_sans_le_champ_le_dry_run_est_inchange(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne = self._structure(r.data)
        self.assertEqual(ligne['designation'], 'Structures acier')
        self.assertEqual(ligne['role'], 'structure_acier')

    def test_l_id_d_une_autre_societe_ne_fuite_pas(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
            'structure_produit_id': self.pergola_voisine.id,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            self._structure(r.data)['designation'], 'Structures acier')
