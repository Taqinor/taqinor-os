# -*- coding: utf-8 -*-
"""STKCAT23 — `LigneDevis.role_devis` : écrit à la création, lu par le moteur.

CE QUE CE FICHIER PROTÈGE, ET POURQUOI.

Le rôle d'une ligne de devis (« panneau », « structure », « batterie »…) était
RE-DEVINÉ par mots-clés à CHAQUE lecture : une fois par le répartiteur
d'options du PDF, une fois par la table d'icônes, une fois par les paniers du
noyau monnaie. Trois devinettes sur une DÉSIGNATION que le commercial peut
éditer à la main après coup — et le catalogue réel du fondateur contient
« Pergola alu », un nom qu'AUCUN mot-clé ne reconnaît (défaut « Pergola
introuvable », audit L3 du 16/09/2026).

Le rôle est désormais FIGÉ à la création de la ligne et LU EN PREMIER. Les
deux invariants que ce fichier verrouille :

  1. NON-RÉGRESSION ABSOLUE — une ligne SANS rôle (toutes celles d'hier, et
     toutes celles écrites hors de ``apps.ventes``) se répartit et s'illustre
     EXACTEMENT comme avant. Les mots-clés ne sont pas
     remplacés : ils sont un REPLI PERMANENT.
  2. UNE CONTRADICTION EST UN AVERTISSEMENT, JAMAIS UNE PERTE — quand le rôle
     stocké et la désignation ne disent pas la même chose, la ligne reste là où
     son rôle la met, le rôle n'est PAS écrasé, et rien ne disparaît du
     document. Même discipline que ``LigneDevis.variante``.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_stkcat23_role_ligne -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.stock.models import Produit
from apps.ventes.domain.lignes import (CHAMPS_CLONES, CHAMPS_LIGNE,
                                       _role_a_la_creation, creer_ligne)
from apps.ventes.models import LigneDevis
from apps.ventes.quote_engine import generate_devis_premium as generateur
from apps.ventes.quote_engine.builder import _repartir_options
from core.product_roles import ROLES_DEVIS

User = get_user_model()


class _LigneFactice:
    """Le strict minimum que ``_repartir_options`` lit sur une ligne ORM."""

    def __init__(self, role=None, variante='', devis_id=1):
        self.role_devis = role
        self.variante = variante
        self.devis_id = devis_id


def _paire(designation, role=None, variante='', produit_nom=''):
    return (_LigneFactice(role, variante),
            {'designation': designation, '_produit_nom': produit_nom,
             'role_devis': role})


def _paniers(paires):
    sans, avec, _ = _repartir_options(paires)
    return ([it['designation'] for _, it in sans],
            [it['designation'] for _, it in avec])


class ChampRoleLigneTest(SimpleTestCase):
    """La colonne et sa place dans l'écrivain unique."""

    def test_colonne_nullable_au_vocabulaire_partage(self):
        champ = LigneDevis._meta.get_field('role_devis')
        self.assertTrue(champ.null)
        self.assertTrue(champ.blank)
        self.assertEqual(champ.max_length, 32)
        self.assertEqual([cle for cle, _ in champ.choices], list(ROLES_DEVIS))

    def test_le_role_appartient_au_jeu_de_champs_et_aux_copies(self):
        # Sans cela, une COPIE de devis (duplication, variante, renouvellement)
        # re-devinerait le rôle au lieu de reprendre celui de la source.
        self.assertIn('role_devis', CHAMPS_LIGNE)
        self.assertIn('role_devis', CHAMPS_CLONES)


class ResolutionDuRoleALaCreationTest(SimpleTestCase):
    """``_role_a_la_creation`` — le rôle DÉCLARÉ, puis les mots-clés."""

    class _Produit:
        def __init__(self, role=None):
            self.role_devis = role

    def test_le_role_declare_du_produit_passe_devant(self):
        champs = {'designation': 'Panneau Jinko 710W',
                  'produit': self._Produit('structure')}
        self.assertEqual(_role_a_la_creation(champs), 'structure')

    def test_sans_role_declare_les_mots_cles_decident(self):
        self.assertEqual(
            _role_a_la_creation({'designation': 'Panneau Jinko 710W'}),
            'panneau')
        self.assertEqual(
            _role_a_la_creation({'designation': 'Batterie Dyness 10 kWh'}),
            'batterie')
        self.assertEqual(
            _role_a_la_creation({'designation': 'Onduleur hybride Deye 5kW'}),
            'onduleur_hybride')

    def test_un_nom_reel_que_les_mots_cles_ne_voient_pas(self):
        """« Pergola alu » — le défaut fondateur, et sa réparation."""
        self.assertIsNone(_role_a_la_creation({'designation': 'Pergola alu'}))
        self.assertEqual(
            _role_a_la_creation({'designation': 'Pergola alu',
                                 'produit': self._Produit('structure')}),
            'structure')

    def test_ne_leve_jamais_et_ignore_un_role_hors_vocabulaire(self):
        self.assertIsNone(_role_a_la_creation({}))
        self.assertIsNone(_role_a_la_creation({'designation': ''}))
        self.assertIsNone(_role_a_la_creation(
            {'designation': 'X', 'produit': self._Produit('role_invente')}))


class RepartitionDesOptionsTest(SimpleTestCase):
    """Le répartiteur d'options : rôle stocké d'abord, mots-clés en repli."""

    def test_sans_role_la_repartition_est_celle_dhier(self):
        sans, avec = _paniers([
            _paire('Structures acier'),
            _paire('Batterie Dyness 10 kWh'),
            _paire('Onduleur réseau Huawei 5kW'),
            _paire('Onduleur hybride Deye 5kW'),
            _paire('Panneau Jinko 710W'),
        ])
        # « sans batterie » : ni batterie ni hybride. « avec » : pas de réseau.
        self.assertEqual(sans, ['Structures acier',
                                'Onduleur réseau Huawei 5kW',
                                'Panneau Jinko 710W'])
        self.assertEqual(avec, ['Structures acier',
                                'Batterie Dyness 10 kWh',
                                'Onduleur hybride Deye 5kW',
                                'Panneau Jinko 710W'])

    def test_role_structure_sans_mot_cle_atterrit_comme_structures_acier(self):
        """LE CRITÈRE D'ACCEPTATION DE STKCAT23.

        Une ligne dont la désignation ne porte AUCUN mot-clé (« Pergola alu »)
        mais qui porte ``role_devis='structure'`` doit tomber dans exactement
        les mêmes paniers qu'une ligne « Structures acier » aujourd'hui.
        """
        self.assertEqual(_paniers([_paire('Pergola alu', role='structure')]),
                         (['Pergola alu'], ['Pergola alu']))
        self.assertEqual(_paniers([_paire('Structures acier')]),
                         (['Structures acier'], ['Structures acier']))

    def test_le_role_exclut_du_panier_sans_ce_que_les_mots_ne_voient_pas(self):
        # Désignation muette, rôle batterie : la ligne ne peut pas servir
        # l'option « sans batterie ».
        self.assertEqual(
            _paniers([_paire('Module de stockage X', role='batterie')]),
            ([], ['Module de stockage X']))

    def test_une_contradiction_est_journalisee_jamais_une_perte(self):
        paires = [_paire('Batterie Dyness 10 kWh', role='accessoires')]
        with self.assertLogs('apps.ventes.quote_engine.builder',
                             level='WARNING') as journal:
            sans, avec = _paniers(paires)
        # La ligne reste dans les DEUX paniers (son RÔLE décide) : aucune
        # ligne, aucun dirham ne s'évapore entre le devis et son PDF.
        self.assertEqual(sans, ['Batterie Dyness 10 kWh'])
        self.assertEqual(avec, ['Batterie Dyness 10 kWh'])
        message = '\n'.join(journal.output)
        self.assertIn('accessoires', message)
        self.assertIn('CONSERVÉ', message)
        # Le rôle stocké n'est PAS réécrit par la lecture.
        self.assertEqual(paires[0][0].role_devis, 'accessoires')

    def test_la_variante_declaree_reste_au_dessus_du_role(self):
        # F14 — une ligne DÉCLARÉE 'sans' reste dans « sans », même quand son
        # rôle l'en exclurait ; la contradiction est REMONTÉE, pas appliquée.
        sans, avec, contradictions = _repartir_options(
            [_paire('Module de stockage X', role='batterie', variante='sans')])
        self.assertEqual([it['designation'] for _, it in sans],
                         ['Module de stockage X'])
        self.assertEqual(avec, [])
        self.assertEqual(contradictions, ['Module de stockage X'])


class IconePdfTest(SimpleTestCase):
    """La vignette du PDF : rôle stocké d'abord, mots-clés en repli PERMANENT.

    Les icônes sont comparées à celles que des désignations de référence
    produisent — jamais à un octet en dur : le test dit « la même vignette
    que X », ce qui reste vrai si le dessin change.
    """

    def _icone(self, designation, role=None):
        return generateur.icon_img(designation, '', role)

    def test_le_role_singulier_atteint_la_vignette_plurielle(self):
        # La table de mots-clés est au PLURIEL (« panneaux »), le vocabulaire
        # de rôles au SINGULIER (« panneau ») : c'est l'écart que le rail
        # ferme. Sans rôle, « Panneau Jinko 710W » retombe sur la générique.
        self.assertEqual(self._icone('Panneau Jinko 710W', 'panneau'),
                         self._icone('Panneaux'))
        self.assertEqual(self._icone('Pergola alu', 'structure'),
                         self._icone('Structures'))
        self.assertEqual(self._icone('Pergola alu', 'structure_alu'),
                         self._icone('Structures'))

    def test_les_trois_familles_donduleur_partagent_leur_vignette(self):
        for role in ('onduleur_reseau', 'onduleur_hybride',
                     'onduleur_offgrid'):
            with self.subTest(role=role):
                self.assertEqual(self._icone('Appareil X', role),
                                 self._icone('Onduleur'))

    def test_sans_role_les_mots_cles_decident_comme_avant(self):
        """La table de mots-clés est un REPLI PERMANENT, pas une transition.

        Chaque désignation doit toujours atteindre SA vignette — comparée à
        l'entrée de ``_SVG`` elle-même, donc le test reste vrai si le dessin
        change, et faux si la branche mot-clé disparaît.
        """
        attendu = {
            'Panneaux Jinko': 'panneaux',
            'Batterie Dyness': 'batterie',
            'Onduleur X': 'onduleur',
            'Structures acier': 'structures',
            'Socles béton': 'socles',
            'Smart Meter': 'smart meter',
            'Wifi Dongle': 'wifi',
            'Tableau De Protection AC/DC': 'tableau',
            'Installation': 'installation',
            'Transport': 'transport',
            'Suivi journalier': 'suivi',
            # Rien de reconnu → la vignette générique, comme toujours.
            'Pergola alu': 'accessoires',
        }
        for designation, cle in attendu.items():
            with self.subTest(designation=designation):
                self.assertIn(
                    generateur.svg_uri(generateur._SVG[cle]),
                    self._icone(designation, None))

    def test_un_role_inconnu_retombe_sur_les_mots_cles(self):
        self.assertEqual(self._icone('Panneaux Jinko', 'role_invente'),
                         self._icone('Panneaux'))
        # Les deux rôles de CÂBLE n'ont pas de vignette : repli assumé.
        self.assertEqual(self._icone('Câble solaire DC', 'cable_dc'),
                         self._icone('Câble solaire DC'))


class EcritureDuRoleTest(TestCase):
    """Le rôle est réellement ÉCRIT en base par l'écrivain unique."""

    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='stkcat23', defaults={'nom': 'STKCAT23'})
        self.user = User.objects.create_user(
            username='stkcat23', password='x', company=self.company,
            role_legacy='admin')
        self.client_crm, _ = Client.objects.get_or_create(
            company=self.company, email='stkcat23@example.com',
            defaults={'nom': 'STKCAT23', 'prenom': 'Test',
                      'telephone': '+212600000023'})
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_crm,
            reference='DEV-STKCAT23-1', statut=Devis.Statut.BROUILLON,
            created_by=self.user)

    def test_le_role_est_resolu_a_la_creation(self):
        ligne = creer_ligne(
            self.devis, designation='Panneau Jinko 710W',
            quantite=Decimal('12'), prix_unitaire=Decimal('980'))
        ligne.refresh_from_db()
        self.assertEqual(ligne.role_devis, 'panneau')

    def test_le_role_declare_du_produit_gagne(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pergola alu', sku='STKCAT23-PERG',
            prix_vente=Decimal('4000'), prix_achat=Decimal('1'),
            role_devis='structure')
        ligne = creer_ligne(
            self.devis, produit=produit, designation='Pergola alu',
            quantite=Decimal('1'), prix_unitaire=Decimal('4000'))
        ligne.refresh_from_db()
        self.assertEqual(ligne.role_devis, 'structure')

    def test_un_role_explicite_nest_jamais_recalcule(self):
        ligne = creer_ligne(
            self.devis, designation='Panneau Jinko 710W',
            quantite=Decimal('1'), prix_unitaire=Decimal('980'),
            role_devis='accessoires')
        ligne.refresh_from_db()
        self.assertEqual(ligne.role_devis, 'accessoires')

    def test_une_designation_non_classee_laisse_le_role_vide(self):
        ligne = creer_ligne(
            self.devis, designation='Pergola alu', quantite=Decimal('1'),
            prix_unitaire=Decimal('4000'))
        ligne.refresh_from_db()
        self.assertIsNone(ligne.role_devis)

    def test_une_ligne_ecrite_hors_de_ventes_reste_sans_role(self):
        """Une ligne écrite en direct (hors du constructeur de ventes) vaut
        NULL, et NULL veut dire « les mots-clés décideront » — le comportement
        historique exact. Rien ne doit leur poser un rôle dans le dos.
        """
        ligne = LigneDevis.objects.create(
            devis=self.devis, designation='Panneau Jinko 710W',
            quantite=Decimal('1'), prix_unitaire=Decimal('980'))
        ligne.refresh_from_db()
        self.assertIsNone(ligne.role_devis)
