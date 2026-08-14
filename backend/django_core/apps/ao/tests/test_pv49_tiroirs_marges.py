"""PV49 — le calcul publie enfin ses TIROIRS et ses MARGES, sous garde de coût.

Le moteur produisait déjà les deux (``core.calepinage.tiroirs`` depuis PV48,
``robustesse.marges_du_plan`` depuis AOF28) et le serveur n'en publiait aucun :
l'atelier n'avait rien à afficher, et les marges ne vivaient que dans la preuve
sous d'autres noms. Ce module verrouille ce que la publication garantit :

  1. **La forme est celle du contrat PARTAGÉ**
     (``contract_samples/calepinage_tiroirs.json`` et
     ``calepinage_marges.json``) : les tests LISENT ces fichiers, ils ne
     recopient pas leurs clés à la main — un mock écrit à la main serait une
     DEUXIÈME source de vérité, exactement l'incident du 03/08/2026.
  2. **Une marge NON MESURÉE vaut ``null``, jamais ``0``.** Une toiture sans
     obstacle n'a aucune marge de bande : publier ``0`` ferait lire « au ras ».
  3. **Le vocabulaire du MOTEUR est traduit vers celui du CONTRAT** — et
     jamais une grandeur rebaptisée du nom d'une autre.
  4. **La promesse synchrone n'est jamais rompue en douce.** Chaque impact
     chiffré d'un tiroir rejoue un DP complet : le coût est estimé AVANT, et
     hors budget les tiroirs sont DÉGRADÉS (``donnees: null``) — jamais payés
     en silence, jamais absents de la forme.
  5. **Les tiroirs ne sont pas PERSISTÉS** dans une variante : leurs chiffres
     valent pour les paramètres du moment.

Run :
    python manage.py test apps.ao.tests.test_pv49_tiroirs_marges -v2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.ao import calepinage_io, calepinage_service
from apps.ao.calepinage_serializers import ResultatCalepinageSerializer
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ObstacleAO, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company
from core.calepinage.perf import BudgetCalcul
from core.calepinage.tiroirs import BUDGET_APPELS_DEFAUT

#: Le contrat PARTAGÉ (PACT10). Les tests le lisent : il est la source unique.
DOSSIER_CONTRATS = (Path(__file__).resolve().parent.parent
                    / 'contract_samples')

CODE_KIT = 'AO-TABLE-PORTRAIT'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': [CODE_KIT],
    'pas_recherche_m': 0.01,
}


def contrat(nom):
    return json.loads((DOSSIER_CONTRATS / nom).read_text(encoding='utf-8'))


class BasePv49(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV49 Co', slug='pv49-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-49-1', objet='Tiroirs')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code=CODE_KIT,
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _document(self, **kwargs):
        return calepinage_io.document_entree(self.toiture, **kwargs)

    def _calepiner(self, **kwargs):
        return calepinage_service.calepiner(
            self._document(), company=self.company, **kwargs)

    def _obstacle(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='A',
            nature=ObstacleAO.Nature.EDICULE,
            provenance=ObstacleAO.Provenance.MESURE,
            rect_x0_m=Decimal('5.000'), rect_x1_m=Decimal('7.000'),
            rect_y0_m=Decimal('6.000'), rect_y1_m=Decimal('8.000'))
        obstacle.appliquer_degagement()
        obstacle.save()
        return obstacle


class LaFormeEstCelleDuContratPartage(BasePv49):
    """PACT10 — les clés viennent du fichier versionné, pas d'un mock local."""

    def test_les_marges_ont_exactement_les_cles_du_contrat(self):
        attendu = set(contrat('calepinage_marges.json')['exemple'])
        sortie = self._calepiner()
        self.assertEqual(set(sortie['marges']), attendu)

    def test_les_cinq_tiroirs_sont_ceux_du_contrat(self):
        exemple = contrat('calepinage_tiroirs.json')['exemple']
        sortie = self._calepiner()
        self.assertEqual(set(sortie['tiroirs']), set(exemple))
        for nom, tiroir in sortie['tiroirs'].items():
            self.assertEqual(set(tiroir), {'donnees', 'valeurs'}, nom)

    def test_chaque_tiroir_reste_dans_le_vocabulaire_du_contrat(self):
        """Aucune clé de ``donnees`` inventée hors du contrat partagé."""
        exemple = contrat('calepinage_tiroirs.json')['exemple']
        sortie = self._calepiner()['tiroirs']
        for nom, tiroir in sortie.items():
            if tiroir['donnees'] is None:
                continue
            autorisees = set(exemple[nom]['donnees'] or {})
            self.assertLessEqual(set(tiroir['donnees']), autorisees, nom)

    def test_les_tiroirs_degrades_ont_la_forme_de_l_exemple_vide(self):
        vide = contrat('calepinage_tiroirs.json')['exemple_vide']
        self.assertEqual(calepinage_io.tiroirs_vides(), vide)

    def test_un_champ_de_rive_reste_dans_le_vocabulaire_du_contrat(self):
        exemple = contrat('calepinage_tiroirs.json')['exemple']
        autorisees = set(exemple['rives']['donnees']['champs'][0])
        champs = self._calepiner()['tiroirs']['rives']['donnees']['champs']
        self.assertTrue(champs)
        for champ in champs:
            self.assertLessEqual(set(champ), autorisees)
            self.assertIn('impacts', champ)


class UneMargeNonMesureeVautNull(BasePv49):
    """Le critère est le REPÈRE fautif — jamais un zéro qui ne veut rien dire."""

    def test_sans_obstacle_la_marge_de_bande_est_nulle_pas_zero(self):
        marges = self._calepiner()['marges']
        self.assertIsNone(marges['bande_min_cm'])
        self.assertEqual(marges['obstacle_critique'], '')
        # le tronçon, LUI, a été mesuré : il porte un nombre et son repère.
        self.assertIsNotNone(marges['troncon_min_cm'])
        self.assertTrue(marges['rangee_critique'])

    def test_avec_un_obstacle_la_marge_de_bande_est_mesuree_et_nommee(self):
        self._obstacle()
        marges = self._calepiner()['marges']
        self.assertIsNotNone(marges['bande_min_cm'])
        self.assertEqual(marges['obstacle_critique'], 'A')

    def test_les_marges_sont_en_centimetres(self):
        """La preuve publie des MÈTRES, le bloc marges des CENTIMÈTRES."""
        sortie = self._calepiner()
        self.assertAlmostEqual(sortie['marges']['troncon_min_cm'],
                               sortie['preuve']['marge_troncon_min'] * 100.0,
                               places=2)


class LeVocabulaireEstTraduit(BasePv49):
    """Le moteur nomme ses champs pour lui ; l'écran lit le contrat."""

    def test_les_codes_de_rive_sont_ceux_du_contrat(self):
        champs = self._calepiner()['tiroirs']['rives']['donnees']['champs']
        codes = [c['code'] for c in champs]
        self.assertIn('rive_laterale', codes)
        self.assertIn('rive_extremite', codes)
        self.assertIn('degagement_inconnu', codes)
        for code in codes:
            self.assertFalse(code.endswith('_m'), code)

    def test_l_approvisionnement_porte_toujours_ses_deux_cles(self):
        appro = self._calepiner()['tiroirs']['kits']['donnees'][
            'approvisionnement']
        self.assertEqual(set(appro), {'confirme', 'argument'})
        # AOF119 — tant que rien ne l'a confirmé, aucun argument n'est inventé.
        self.assertFalse(appro['confirme'])
        self.assertEqual(appro['argument'], '')

    def test_les_valeurs_refletent_les_parametres_RETENUS(self):
        tiroirs = self._calepiner()['tiroirs']
        self.assertEqual(tiroirs['kits']['valeurs'],
                         {'kit': CODE_KIT, 'granularite_kit': 'site'})
        self.assertAlmostEqual(tiroirs['allees']['valeurs']['allee_m'], 0.60)
        self.assertAlmostEqual(
            tiroirs['rives']['valeurs']['rive_laterale'], 0.35)
        self.assertAlmostEqual(
            tiroirs['rives']['valeurs']['degagement_inconnu'], 0.50)
        self.assertEqual(tiroirs['orientation']['valeurs']['sens_rangees'],
                         'NORD_SUD')

    def test_ni_segmentation_ni_forme_l_ne_sont_meublees(self):
        """Le moteur n'a aucun modèle pour ces deux groupes : ils sortent VIDES."""
        donnees = self._calepiner()['tiroirs']['orientation']['donnees']
        self.assertEqual(donnees['segmentations'], [])
        self.assertEqual(donnees['formes_l'], [])

    def test_le_tiroir_electrique_n_est_plus_vide(self):
        """PV44 — il sortait ``donnees: null`` faute de moteur électrique.

        ``core.electrique`` existe depuis PV33-39 : le tiroir est ALIMENTÉ.
        Ce que la publication garantit est verrouillé par
        ``test_pv44_tiroir_electrique`` ; ici on constate seulement que la
        forme dégradée n'est plus le comportement normal.
        """
        electrique = self._calepiner()['tiroirs']['electrique']
        self.assertIsNotNone(electrique['donnees'])
        self.assertIn('taille_chaine', electrique['valeurs'])


class LeGardeDeCout(BasePv49):
    """La promesse synchrone couvre AUSSI les tiroirs, ou ils sont dégradés."""

    def test_le_multiplicateur_est_lu_sur_le_moteur(self):
        self.assertEqual(calepinage_service.multiplicateur_tiroirs(),
                         BUDGET_APPELS_DEFAUT + 2)
        self.assertEqual(calepinage_service.multiplicateur_tiroirs(4), 6)

    def test_le_cout_tout_compris_inclut_les_appels_des_tiroirs(self):
        """PV44 : le tiroir électrique voyage AVEC les tiroirs, donc il compte."""
        document = self._document()
        seul = calepinage_service.cout_estime(document)
        tout = calepinage_service.cout_estime(document, tiroirs=True)
        self.assertEqual(
            tout.appels,
            seul.appels * (calepinage_service.multiplicateur_tiroirs()
                           + calepinage_service.multiplicateur_electrique()))
        self.assertGreater(tout.millisecondes, seul.millisecondes)

    def test_hors_budget_les_tiroirs_sont_degrades_pas_payes(self):
        sortie = self._calepiner(
            budget=BudgetCalcul(seuil_synchrone_ms=0.0001))
        self.assertEqual(sortie['tiroirs'], calepinage_io.tiroirs_vides())
        # le RÉSULTAT, lui, est complet : seule la charge utile cède.
        self.assertGreater(sortie['total_modules'], 0)
        self.assertIsNotNone(sortie['marges']['troncon_min_cm'])

    def test_dans_le_budget_les_tiroirs_sont_produits(self):
        sortie = self._calepiner(budget=BudgetCalcul(
            seuil_synchrone_ms=1_000_000.0))
        self.assertIsNotNone(sortie['tiroirs']['kits']['donnees'])
        self.assertIsNotNone(sortie['tiroirs']['allees']['donnees'])

    def test_les_tiroirs_peuvent_etre_refuses_a_l_appel(self):
        sortie = self._calepiner(tiroirs=False)
        self.assertEqual(sortie['tiroirs'], calepinage_io.tiroirs_vides())

    def test_un_document_multi_surfaces_degrade_les_tiroirs(self):
        """Le moteur n'a AUCUN tiroir GÉOMÉTRIQUE par segment : on n'en invente pas.

        PV44 : le tiroir ÉLECTRIQUE, lui, est PAR DOCUMENT (une conception pour
        l'ensemble posé — son coût ne se multiplie pas par surface) : il reste
        réel en multi-surfaces ; seuls les 4 tiroirs géométriques dégradent.
        """
        document = self._document()
        premiere = document['surfaces'][0]
        seconde = dict(premiere, repere=premiere['repere'] + '_B')
        document['surfaces'] = [premiere, seconde]
        document['affectations'] = {premiere['repere']: [],
                                    seconde['repere']: []}
        sortie = calepinage_service.calepiner(document, company=self.company)
        self.assertEqual(len(sortie['plans']), 2)
        vides = calepinage_io.tiroirs_vides()
        for cle in ('kits', 'allees', 'rives', 'orientation'):
            self.assertEqual(sortie['tiroirs'][cle], vides[cle])
        self.assertEqual(set(sortie['tiroirs']), set(vides))
        # PV44 — la charge utile d'un tiroir vit sous ``donnees`` (enveloppe
        # ``{'donnees': …, 'valeurs': …}`` commune aux cinq tiroirs, cf.
        # ``tiroir_electrique_vers_json``). Chercher ``chaine`` sur l'enveloppe
        # rendait la promesse inatteignable ; et la garde ``if … is not None``
        # ne pouvait jamais être fausse, l'enveloppe étant toujours un dict —
        # ce qui aurait laissé passer un tiroir électrique VIDE, exactement ce
        # que ce test doit interdire.
        electrique = sortie['tiroirs']['electrique']['donnees']
        self.assertIsNotNone(electrique)
        self.assertIn('chaine', electrique)
        self.assertIn('conformite', electrique)


class LesTiroirsNeSontPasPersistes(BasePv49):
    """Une variante fige un RÉSULTAT, pas une charge utile d'atelier."""

    def test_la_variante_garde_les_marges_et_jette_les_tiroirs(self):
        variante = calepinage_service.calculer_variante(self.toiture)
        self.assertNotIn('tiroirs', variante.resultat)
        self.assertIn('marges', variante.resultat)
        self.assertEqual(set(variante.resultat['marges']),
                         set(contrat('calepinage_marges.json')['exemple']))
        self.assertEqual(
            VarianteCalepinage.objects.filter(company=self.company).count(), 1)


class LeSerialiseurEstLeMiroirDuService(BasePv49):
    """PACT7 — un schéma qui ne dit rien ne contredit rien."""

    def test_les_deux_blocs_sont_declares_et_publies(self):
        sortie = self._calepiner()
        donnees = ResultatCalepinageSerializer(sortie).data
        self.assertEqual(set(donnees['marges']), set(sortie['marges']))
        self.assertEqual(set(donnees['tiroirs']), set(sortie['tiroirs']))
        for nom, tiroir in donnees['tiroirs'].items():
            self.assertEqual(set(tiroir), {'donnees', 'valeurs'}, nom)

    def test_le_serialiseur_declare_les_cles_du_tiroir_kits(self):
        sortie = self._calepiner()
        donnees = ResultatCalepinageSerializer(sortie).data
        publiees = set(donnees['tiroirs']['kits']['donnees'])
        self.assertEqual(publiees,
                         set(sortie['tiroirs']['kits']['donnees']))
