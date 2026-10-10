"""CAL211 — le plan de pose de l'équipe terrain : aucun montant, l'empreinte.

L'app terrain a ses PDF (assemblage, livraison) mais aucun plan d'implantation :
l'équipe travaille sans la planche. Cette variante lui donne ce qu'il lui faut —
repères de RANGÉE, SENS DE POSE, LISTE DES CHAÎNES — et rien d'autre.

Ce qui est prouvé (essais PURS) :

* le plan de pose ne porte AUCUN montant, ni `prix_achat` : la garde REFUSE le
  document plutôt que de filtrer en silence ;
* il porte l'empreinte du calepinage (CAL173), donc il reste rattachable à sa
  conception ;
* les repères de rangée viennent de la SEULE définition de « rangée » du module
  (celle de CAL179) — deux définitions feraient diverger le plan de l'équipe et
  le tableau du bureau d'études ;
* l'emplacement des onduleurs n'est PAS dessiné : la donnée n'existe pas, et un
  onduleur posé à un endroit plausible enverrait une équipe percer le mauvais
  mur. Le bandeau le dit en toutes lettres.

Run :
    python manage.py test apps.calepinage.tests.test_cal211_plan_pose -v2
"""
import copy
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.rangees import rangees_du_pan
from apps.calepinage.services.planche import (
    CONTENU_POSE, CONTENU_TOITURE, PlanDePoseRefuse, geometrie_de_planche,
    _lignes_de_chaines, _rendre_plan_pose_svg, svg_de_planche,
    _verifier_absence_d_argent,
)

from .acal_livrables_helpers import (
    LAYOUT_PLANCHE_SIMULABLE, MATERIEL, calepinage_simule_reel,
    patch_materiel,
)
from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import MOMENT, FauxCalepinage

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']


def calepinage_de_pose():
    """ACAL216 - un calepinage SIMULE par les vrais ecrivains : le plan de
    pose lit le resultat SERVI, jamais le contrat colle dans la colonne."""
    simule = calepinage_simule_reel(LAYOUT_PLANCHE_SIMULABLE)
    calepinage = FauxCalepinage(roof_layout=simule.roof_layout)
    calepinage.resultat = simule.resultat
    return calepinage


def plan_de_pose_svg(calepinage, **options):
    """Le plan de pose, materiel injecte (le stock n'a pas de base ici)."""
    with patch_materiel():
        return _rendre_plan_pose_svg(calepinage, moment=MOMENT, **options)


class AucunMontantTest(SimpleTestCase):
    def test_le_plan_de_pose_ne_porte_aucun_montant(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        for interdit in ('prix', 'prix_achat', 'MAD', 'montant', 'Tarif'):
            self.assertNotIn(interdit.lower(), svg.lower())

    def test_la_garde_refuse_un_document_qui_porterait_un_prix(self):
        with self.assertRaises(PlanDePoseRefuse) as capture:
            _verifier_absence_d_argent('<svg><text>Module 720 Wc — 1 200 MAD'
                                       '</text></svg>')
        self.assertIn('montant', str(capture.exception).lower())

    def test_un_resultat_qui_charrie_un_prix_fait_refuser_le_plan(self):
        avec_prix = copy.deepcopy(MATERIEL)
        avec_prix['designations']['onduleur'] = 'ONDULEUR 10 kW (prix sur demande)'
        calepinage = calepinage_de_pose()
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=avec_prix):
            with self.assertRaises(PlanDePoseRefuse):
                _rendre_plan_pose_svg(calepinage, moment=MOMENT)


class EmpreinteEtCheminTest(SimpleTestCase):
    def test_le_plan_de_pose_porte_l_empreinte_du_calepinage(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        self.assertIn('calepinage aaaaaaaaaaaa', svg)
        self.assertIn('moteur calepinage-1.0.0', svg)

    def test_le_titre_nomme_la_piece(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        self.assertIn('Plan de pose', svg)


class ReperesDePoseTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(LAYOUT)
        self.svg = svg_de_planche(self.geometrie, contenu=CONTENU_POSE)

    def test_les_reperes_de_rangee_sont_sur_le_plan(self):
        self.assertIn('>R1</text>', self.svg)

    def test_la_numerotation_est_celle_du_tableau(self):
        # UNE seule définition de « rangée » : celle de CAL179.
        pan = self.geometrie['pans'][0]
        numeros = set(rangees_du_pan(pan['modules'],
                                     pan['azimut_deg']).values())
        for numero in numeros:
            self.assertIn('>R%d</text>' % numero, self.svg)

    def test_le_sens_de_pose_est_trace_quand_il_est_deductible(self):
        # Deux modules alignés -> une flèche ; la rangée d'un seul module n'en
        # porte aucune (il n'y a pas de sens à déduire).
        self.assertIn('stroke-dasharray="1 0.8"', self.svg)

    def test_un_pan_d_un_seul_module_ne_trace_aucun_sens(self):
        layout = copy.deepcopy(LAYOUT)
        layout['zones'][0]['geometry']['panels'] = [{'cx': 1.0, 'cy': 1.0}]
        svg = svg_de_planche(geometrie_de_planche(layout),
                             contenu=CONTENU_POSE)
        self.assertIn('>R1</text>', svg)
        self.assertNotIn('stroke-dasharray="1 0.8"', svg)

    def test_les_reperes_n_apparaissent_pas_sur_les_autres_plans(self):
        toiture = svg_de_planche(self.geometrie, contenu=CONTENU_TOITURE)
        self.assertNotIn('>R1</text>', toiture)


class ListeDesChainesTest(SimpleTestCase):
    def test_les_chaines_sont_recopiees_du_moteur(self):
        lignes = _lignes_de_chaines(RESULTAT)
        chainage = RESULTAT['electrique']['chainage']
        self.assertIn('Chaînes : %s' % chainage['chaines'], lignes)
        self.assertIn('Modules par chaîne : %s'
                      % chainage['modules_par_chaine'], lignes)

    def test_les_onduleurs_sont_listes_avec_leurs_mppt(self):
        lignes = _lignes_de_chaines(RESULTAT)
        self.assertTrue(any('ONDULEUR-ESSAI-1' in ligne and 'MPPT' in ligne
                            for ligne in lignes))

    def test_l_emplacement_des_onduleurs_n_est_jamais_invente(self):
        # La donnée n'existe ni dans le layout ni dans le résultat : on le DIT
        # plutôt que de poser un onduleur à un endroit plausible.
        lignes = _lignes_de_chaines(RESULTAT)
        self.assertTrue(any('non relevé' in ligne for ligne in lignes))

    def test_sans_resultat_aucune_ligne_n_est_fabriquee(self):
        self.assertEqual(_lignes_de_chaines(None), ())
        self.assertEqual(_lignes_de_chaines({}), ())

    def test_la_liste_paraît_dans_le_bandeau_du_plan(self):
        from apps.calepinage import selectors

        calepinage = calepinage_de_pose()
        svg = plan_de_pose_svg(calepinage)
        with patch_materiel():
            servi = selectors.resultat_servi(calepinage)
        chainage = servi['electrique']['chainage']
        self.assertIn('Chaînes : %s' % chainage['chaines'], svg)
        self.assertIn('Onduleur', svg)
