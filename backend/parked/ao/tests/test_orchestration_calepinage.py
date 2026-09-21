"""AOF60 — le service d'orchestration du calepinage : la COUTURE.

Ce que ces tests VERROUILLENT :

* les 3 jeux FRDISI passent par ``calepiner`` et redonnent leurs comptes
  réconciliés (A 148, B 120, C 314) — sans base de données ;
* ``calepiner`` n'écrit RIEN : aucune ligne créée, aucun statut changé ;
* ``valider()`` (AOF51) est appelée et un résultat INCOHÉRENT lève AVANT le
  retour — un moteur qui annonce plus que ce que le plan contient ne sort
  jamais du service ;
* le service n'importe ``apps.crm`` / ``apps.ventes`` / ``apps.stock`` nulle
  part ;
* les 3 causes de refus de publication d'AOF28 sont bien appliquées par
  ``calculer_variante``.

Run :
    python manage.py test apps.ao.tests.test_orchestration_calepinage -v2
"""
import io
import json
import os
from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ao import calepinage_io, calepinage_service
from apps.ao.calepinage_io import EntreeInvalide
from apps.ao.calepinage_service import (
    MoteurCalepinage, calepiner, calculer_variante,
)
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ObstacleAO, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company
from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.optimum import optimiser
from core.calepinage.version import VERSION_MOTEUR

#: core/calepinage/golden/frdisi_2026_07_27 — apps/ao/tests -> … -> django_core
_DJANGO_CORE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
GOLDEN = os.path.join(_DJANGO_CORE, 'core', 'calepinage', 'golden',
                      'frdisi_2026_07_27')


def _document(nom):
    """Charge un golden et en fait un document du contrat AOF57.

    La clé ``golden`` (comptes témoins, rangées des planches d'origine) n'est
    PAS du contrat : elle sert au test, jamais au moteur.
    """
    with io.open(os.path.join(GOLDEN, nom), encoding='utf-8') as fichier:
        brut = json.load(fichier)
    temoin = brut.pop('golden')
    if 'segments' in temoin:
        # L'arc est découpé en segments : l'affectation des obstacles est
        # DÉCLARÉE (le relevé la connaît), jamais devinée.
        brut['affectations'] = {s['repere']: s['obstacles']
                                for s in temoin['segments']}
        # Les segments S2/S3 sont posés en PAYSAGE : les deux kits doivent
        # être ouverts au DP, sinon il ne peut pas atteindre les 120 modules.
        brut['parametres']['kits'] = ['AO_PORTRAIT', 'AO_PAYSAGE']
    return brut, temoin


class MoteurMenteur:
    """Moteur qui ANNONCE 10 modules de plus que son plan n'en contient.

    C'est exactement la panne du dossier réel : « la pièce la plus lue était
    la plus fausse ». ``valider()`` doit l'attraper AVANT tout retour.
    """

    def calculer(self, surface, parametres, obstacles=(), zones=(),
                 politique=None):
        vrai = optimiser(surface, parametres, obstacles, zones, politique)
        return replace(vrai, preuve=replace(
            vrai.preuve, compte_retenu=vrai.preuve.compte_retenu + 10))


class LesTroisJeuxFrdisi(SimpleTestCase):
    """Les 3 planches du dossier, rejouées par le SERVICE (pas par le moteur)."""

    def _calepiner(self, nom):
        document, temoin = _document(nom)
        moteur = MoteurCalepinage()
        return calepiner(document, company=1, moteur=moteur), temoin, moteur

    def test_batiment_c_ecole_redonne_314(self):
        sortie, temoin, _ = self._calepiner('bat_C_ecole.json')
        self.assertEqual(sortie['total_modules'], 314)
        self.assertEqual(temoin['compte_temoin'], 314)
        self.assertEqual(sortie['hash_entree'], temoin['hash_entree'])

    def test_batiment_a_aile_l_redonne_148(self):
        sortie, temoin, _ = self._calepiner('bat_A_aile_L.json')
        self.assertEqual(sortie['total_modules'], 148)
        self.assertEqual(temoin['compte_temoin'], 148)
        self.assertEqual(sortie['hash_entree'], temoin['hash_entree'])

    def test_batiment_b_arc_redonne_120_en_trois_segments(self):
        sortie, temoin, moteur = self._calepiner('bat_B_arc.json')
        self.assertEqual(sortie['total_modules'], 120)
        self.assertEqual(temoin['compte_temoin'], 120)
        self.assertEqual(len(sortie['plans']), 3)
        # un appel moteur PAR SEGMENT — jamais un appel global qui mélangerait
        # les abscisses locales de trois segments
        self.assertEqual(moteur.appels, 3)

    def test_la_preuve_porte_le_couple_hash_version(self):
        sortie, _temoin, _ = self._calepiner('bat_C_ecole.json')
        self.assertEqual(sortie['version_moteur'], VERSION_MOTEUR)
        self.assertTrue(sortie['hash_entree'])
        self.assertTrue(sortie['preuve']['optimal'])
        self.assertEqual(sortie['preuve']['methode'], 'dp_exact_1cm')

    def test_les_neuf_controles_sont_passes(self):
        sortie, _temoin, _ = self._calepiner('bat_A_aile_L.json')
        self.assertIn('non_chevauchement', sortie['preuve']['controles'])
        self.assertIn('degagement_obstacle', sortie['preuve']['controles'])
        self.assertIn('rive_laterale', sortie['preuve']['controles'])

    def test_aile_l_non_engageable_les_non_releves_sont_nommes(self):
        """GRECT (deviné) et PAN (venu du plan) valent 12 modules — et le
        service dit POURQUOI le compte n'engage pas."""
        sortie, _temoin, _ = self._calepiner('bat_A_aile_L.json')
        self.assertFalse(sortie['engageable'])
        self.assertTrue(sortie['motifs_non_engageable'])


class LaPorteDeValidation(SimpleTestCase):
    def test_un_moteur_qui_ment_leve_avant_le_retour(self):
        document, _temoin = _document('bat_C_ecole.json')
        with self.assertRaises(CalepinageIncoherent) as capture:
            calepiner(document, company=1, moteur=MoteurMenteur())
        self.assertEqual(capture.exception.controle, 'compte_annonce')

    def test_sans_societe_le_service_refuse(self):
        document, _temoin = _document('bat_C_ecole.json')
        with self.assertRaises(EntreeInvalide):
            calepiner(document, company=None)

    def test_document_invalide_motif_francais(self):
        with self.assertRaises(EntreeInvalide) as capture:
            calepiner({'schema_version': 1}, company=1)
        self.assertTrue(str(capture.exception))

    def test_multi_surfaces_sans_affectation_refuse(self):
        document, _temoin = _document('bat_B_arc.json')
        document.pop('affectations')
        with self.assertRaises(EntreeInvalide) as capture:
            calepiner(document, company=1)
        self.assertIn('affectations', str(capture.exception))

    def test_obstacle_orphelin_refuse(self):
        document, _temoin = _document('bat_B_arc.json')
        document['affectations']['BAT_B_ARC_S3'] = []
        with self.assertRaises(EntreeInvalide) as capture:
            calepiner(document, company=1)
        self.assertIn('non affect', str(capture.exception))


class LesFrontieresDuService(SimpleTestCase):
    """Le service ne connaît AUCUNE app du cœur métier (CLAUDE.md)."""

    INTERDITS = ('apps.crm', 'apps.ventes', 'apps.stock', 'apps.sav',
                 'apps.installations')

    def test_aucun_import_du_coeur_metier(self):
        for module in (calepinage_service, calepinage_io):
            with io.open(module.__file__, encoding='utf-8') as fichier:
                source = fichier.read()
            for interdit in self.INTERDITS:
                self.assertNotIn(
                    'import %s' % interdit, source,
                    '%s importe %s' % (module.__name__, interdit))
                self.assertNotIn(
                    'from %s' % interdit, source,
                    '%s importe %s' % (module.__name__, interdit))

    def test_le_service_ne_contient_aucune_geometrie(self):
        """Aucun calcul trigonométrique ici : la géométrie vit dans le paquet
        pur, et une seule fois."""
        with io.open(calepinage_service.__file__, encoding='utf-8') as fichier:
            source = fichier.read()
        for interdit in ('import math', 'math.cos', 'math.sin', 'math.hypot'):
            self.assertNotIn(interdit, source)


class BaseToiture(TestCase):
    """Une toiture rectangulaire propre + le kit AO portrait."""

    PARAMS = {
        'rive_laterale_m': 0.35,
        'rive_extremite_m': 0.35,
        'allee_min_m': 0.60,
        'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
        'kits_autorises': ['AO-TABLE-PORTRAIT'],
        'pas_recherche_m': 0.01,
    }

    def setUp(self):
        self.company = Company.objects.create(nom='AOF60 Co', slug='aof60-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-60-1', objet='Orchestration')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            forme=ToitureAO.Forme.RECTANGLE,
            contour_local_m=[[0, 0], [40, 0], [40, 20], [0, 20]],
            parametres_calepinage=dict(self.PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code='AO-TABLE-PORTRAIT',
            libelle='Table dos-à-dos portrait',
            mode=KitCalepinage.Mode.TABLE_DOS_A_DOS, modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'),
            longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'),
            orientation_modules=KitCalepinage.Orientation.PORTRAIT)
        self.kit.appliquer_emprise()
        self.kit.save()


class LeCheminPersiste(BaseToiture):
    def test_calculer_variante_persiste_resultat_preuve_et_marges(self):
        variante = calculer_variante(self.toiture, user=None)
        self.assertGreater(variante.total_modules, 0)
        self.assertEqual(variante.version_moteur, VERSION_MOTEUR)
        self.assertTrue(variante.entree_hash)
        self.assertEqual(variante.preuve['total_retenu'],
                         variante.resultat['total_modules'])
        self.assertIn('marge_troncon_min', variante.preuve)
        self.assertEqual(variante.company_id, self.company.pk)
        self.assertEqual(variante.appel_offre_id, self.ao.pk)

    def test_un_plan_prouve_optimal_devient_publiable(self):
        variante = calculer_variante(self.toiture, user=None)
        self.assertEqual(variante.statut,
                         VarianteCalepinage.Statut.PUBLIABLE)

    def test_calepiner_n_ecrit_rien(self):
        avant = VarianteCalepinage.objects.count()
        document = calepinage_io.document_entree(self.toiture)
        calepiner(document, company=self.company)
        self.assertEqual(VarianteCalepinage.objects.count(), avant)
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.parametres_calepinage, self.PARAMS)

    def test_recalcul_a_entree_identique_donne_le_meme_hash(self):
        une = calculer_variante(self.toiture, user=None)
        deux = calculer_variante(self.toiture, user=None,
                                 variante=VarianteCalepinage.objects.get(
                                     pk=une.pk))
        self.assertEqual(une.entree_hash, deux.entree_hash)
        self.assertEqual(VarianteCalepinage.objects.count(), 1)


class LesTroisCausesDeRefusDePublication(BaseToiture):
    """AOF28 — la preuve est une PORTE, appliquée par le service."""

    def test_refus_quand_un_obstacle_non_mesure_est_actif(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='GRECT',
            nature=ObstacleAO.Nature.EDICULE,
            provenance=ObstacleAO.Provenance.DEVINE,
            rect_x0_m=Decimal('10'), rect_x1_m=Decimal('12'),
            rect_y0_m=Decimal('8'), rect_y1_m=Decimal('10'),
            degagement_m=Decimal('0.60'))
        variante = calculer_variante(self.toiture, user=None)
        self.assertEqual(variante.statut,
                         VarianteCalepinage.Statut.CALCULEE)
        self.assertIn('NON MESUR', variante.justification)

    def test_refus_quand_le_retenu_est_sous_l_optimum(self):
        variante = calculer_variante(self.toiture, user=None)
        preuve = dict(variante.preuve)
        preuve['total_retenu'] = preuve['total_optimal'] - 4
        variante.preuve = preuve
        variante.save(update_fields=['preuve'])
        raisons = variante.raisons_de_non_publiabilite()
        self.assertTrue(any('inférieur' in r for r in raisons))

    def test_refus_quand_une_marge_passe_sous_son_seuil(self):
        variante = calculer_variante(self.toiture, user=None)
        preuve = dict(variante.preuve)
        preuve['marge_troncon_min'] = 0.005
        preuve['marge_bande_min'] = 0.01
        variante.preuve = preuve
        variante.save(update_fields=['preuve'])
        raisons = variante.raisons_de_non_publiabilite()
        self.assertEqual(len(raisons), 2)
        self.assertTrue(any('tronçon' in r for r in raisons))
        self.assertTrue(any('bande' in r for r in raisons))


class LaCompositionDeLEntree(BaseToiture):
    def test_un_kit_d_une_autre_societe_n_entre_jamais(self):
        autre = Company.objects.create(nom='Autre', slug='autre-aof60')
        KitCalepinage.objects.create(
            company=autre, code='AO-TABLE-PORTRAIT', libelle='Intrus',
            modules_par_kit=2, pas_rangee_m=Decimal('1.134'),
            longueur_pente_m=Decimal('2.382'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        document = calepinage_io.document_entree(self.toiture)
        self.assertEqual(len(document['kits']), 1)
        self.assertEqual(document['kits'][0]['libelle'],
                         'Table dos-à-dos portrait')

    def test_un_obstacle_hors_zone_pv_ne_bloque_rien(self):
        avant = calculer_variante(self.toiture).total_modules
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='RIVE',
            nature=ObstacleAO.Nature.ACROTERE,
            provenance=ObstacleAO.Provenance.MESURE, hors_zone_pv=True,
            rect_x0_m=Decimal('5'), rect_x1_m=Decimal('30'),
            rect_y0_m=Decimal('5'), rect_y1_m=Decimal('15'),
            degagement_m=Decimal('0.30'))
        apres = calculer_variante(
            self.toiture,
            variante=VarianteCalepinage.objects.first()).total_modules
        self.assertEqual(avant, apres)

    def test_une_toiture_sans_enveloppe_est_refusee_avec_un_motif(self):
        self.toiture.contour_local_m = []
        self.toiture.save(update_fields=['contour_local_m'])
        with self.assertRaises(EntreeInvalide) as capture:
            calepinage_io.document_entree(self.toiture)
        self.assertIn('enveloppe', str(capture.exception))

    def test_un_arc_sans_segment_est_refuse_avec_un_motif(self):
        self.toiture.forme = ToitureAO.Forme.ARC
        self.toiture.rayon_ext_m = Decimal('274.000')
        self.toiture.largeur_m = Decimal('10.900')
        self.toiture.arc_segments = []
        self.toiture.save()
        with self.assertRaises(EntreeInvalide) as capture:
            calepinage_io.document_entree(self.toiture)
        self.assertIn('segment', str(capture.exception))
