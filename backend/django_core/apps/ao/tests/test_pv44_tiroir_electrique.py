"""PV44 — le tiroir « Contraintes électriques » de l'AO s'ALLUME.

La lane AO l'avait livré DÉGRADÉ (``donnees: null``) et c'était le bon choix à
ce moment-là : le calepinage n'a aucun modèle de chaîne, d'onduleur ni de ratio
DC/AC, et meubler le tiroir aurait publié des chiffres que rien ne soutenait.
``core.electrique`` existe depuis PV33-39 — et il produit DÉJÀ la projection
exacte que ``TiroirElectrique.jsx`` lit. Il ne restait qu'à lui donner l'entrée.

Ce module verrouille cinq choses, et rien d'autre :

  1. **Le tiroir porte de VRAIS chiffres**, calculés par le moteur électrique,
     et sa forme est celle du contrat PARTAGÉ
     (``contract_samples/calepinage_tiroirs.json``) — lu, jamais recopié.
  2. **Le plafond de 60 kWc par onduleur est celui du dossier**, lu à sa source
     (``core.calepinage.electrique.PLAFOND_DC_PAR_ONDULEUR_KWC``) et jamais
     recopié : le jour où le dossier change de plafond, le tiroir suit.
  3. **La répartition proposée est REJOUABLE.** Son ``patch`` est écrit dans le
     vocabulaire des PARAMÈTRES : le rejouer par le chemin normal fait
     réellement disparaître la non-conformité. Un patch intraduisible est mis à
     ``null`` — jamais un bouton qui n'applique rien.
  4. **Le garde de coût tient.** Le tiroir électrique est chiffré AVANT d'être
     produit, et hors budget la forme dégradée d'origine est rendue telle quelle.
  5. **Ce qu'on ne sait pas n'est pas inventé.** Le document AO ne déclare aucun
     onduleur : la puissance AC reste non renseignée, le ratio DC/AC sort « — »
     et le moteur DIT pourquoi.

Run :
    python manage.py test apps.ao.tests.test_pv44_tiroir_electrique -v2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.ao import calepinage_io, calepinage_service
from apps.ao.models import AppelOffre, BatimentAO, KitCalepinage, ToitureAO
from authentication.models import Company
from core.calepinage.electrique import (
    MODULES_PAR_CHAINE, PLAFOND_DC_PAR_ONDULEUR_KWC,
)
from core.calepinage.perf import BudgetCalcul
from core.calepinage.serialisation import hash_entree

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

#: Budget large : ces tests portent sur le CONTENU du tiroir, pas sur la
#: bascule de coût (verrouillée à part, plus bas).
BUDGET_LARGE = BudgetCalcul(seuil_synchrone_ms=1_000_000.0)


def contrat():
    return json.loads(
        (DOSSIER_CONTRATS / 'calepinage_tiroirs.json').read_text(
            encoding='utf-8'))


class LEntreeElectriqueEstConstruiteSansRienInventer(SimpleTestCase):
    """PV44-5 — module DÉDUIT, onduleur non déclaré, plafond lu à sa source."""

    def test_la_fiche_module_redonne_la_puissance_declaree(self):
        """``Vmp × Imp`` = la puissance du kit, au flottant près."""
        for wc in (450.0, 625.0, 720.0):
            module = calepinage_io.module_de_reference(wc)
            self.assertAlmostEqual(module.pmax_wc, wc)
            self.assertAlmostEqual(module.vmp_v * module.imp_a, wc, places=6)
            self.assertGreater(module.isc_a, module.imp_a)

    def test_une_puissance_nulle_ne_fabrique_aucun_courant(self):
        module = calepinage_io.module_de_reference(0)
        self.assertEqual(module.imp_a, 0.0)
        self.assertEqual(module.isc_a, 0.0)

    def test_l_onduleur_ne_declare_ni_calibre_ni_courant_d_entree(self):
        """Deux ZÉROS délibérés : ce sont les « non renseigné » du moteur."""
        onduleur = calepinage_io.onduleur_de_reference()
        self.assertEqual(onduleur.ac_kw, 0.0)
        self.assertEqual(onduleur.i_max_mppt_a, 0.0)
        self.assertGreater(onduleur.v_max_abs, onduleur.mppt_v_max)

    def test_le_plafond_vient_de_core_calepinage_electrique(self):
        entree = calepinage_io.entree_electrique(
            [{'label': 'A', 'nb_modules': 100}], 625.0)
        self.assertEqual(entree.plafond_kwc_par_onduleur,
                         PLAFOND_DC_PAR_ONDULEUR_KWC)

    def test_la_longueur_de_chaine_par_defaut_est_celle_du_dossier(self):
        entree = calepinage_io.entree_electrique(
            [{'label': 'A', 'nb_modules': 100}], 625.0)
        self.assertEqual(entree.longueur_chaine_forcee, MODULES_PAR_CHAINE)
        imposee = calepinage_io.entree_electrique(
            [{'label': 'A', 'nb_modules': 100}], 625.0, taille_chaine=14)
        self.assertEqual(imposee.longueur_chaine_forcee, 14)

    def test_un_groupe_par_pan_et_les_pans_vides_sont_ecartes(self):
        entree = calepinage_io.entree_electrique(
            [{'label': 'A', 'nb_modules': 100, 'azimut_deg': 180.0},
             {'label': 'B', 'nb_modules': 0}], 625.0)
        self.assertEqual([g.label for g in entree.groupes], ['A'])
        self.assertEqual(entree.nb_modules, 100)


class LaTraductionDuPatchEstExplicite(SimpleTestCase):
    """PV44-3 — même discipline que PV50 : non cartographié = proposition jetée."""

    def test_taille_chaine_traverse_sous_son_nom(self):
        self.assertEqual(
            calepinage_io.patch_electrique_vers_params({'taille_chaine': 14}),
            {'taille_chaine': 14})

    def test_une_cle_inconnue_fait_tomber_la_proposition(self):
        self.assertIsNone(
            calepinage_io.patch_electrique_vers_params({'calibre_kw': 50}))
        self.assertIsNone(calepinage_io.patch_electrique_vers_params(
            {'taille_chaine': 14, 'calibre_kw': 50}))

    def test_un_patch_vide_ne_propose_rien(self):
        self.assertIsNone(calepinage_io.patch_electrique_vers_params({}))
        self.assertIsNone(calepinage_io.patch_electrique_vers_params(None))

    def test_une_proposition_intraduisible_est_mise_a_null(self):
        tiroir = calepinage_io.tiroir_electrique_vers_json({
            'chaine': {'libelle_taille': '', 'reste_texte': ''},
            'onduleurs': {'nombre_texte': '', 'puissance_texte': '',
                          'plafond_texte': ''},
            'ratio_dc_ac': {'texte': '', 'fourchette_texte': ''},
            'conformite': {'conforme': False, 'bloquant': True, 'alerte': 'x',
                           'repartition_proposee': {
                               'texte': 't', 'patch': {'calibre_kw': 50}}},
        }, 16)
        self.assertIsNone(
            tiroir['donnees']['conformite']['repartition_proposee'])


class BasePv44(TestCase):
    """Une toiture 30 × 18 m, un kit dos-à-dos 625 Wc — 150 modules posés."""

    def setUp(self):
        self.company = Company.objects.create(nom='PV44 Co', slug='pv44-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-44-1', objet='Électrique')
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

    def _document(self, params=None):
        return calepinage_io.document_entree(
            self.toiture, params=params if params is not None else PARAMS)

    def _calepiner(self, params=None, **kwargs):
        kwargs.setdefault('budget', BUDGET_LARGE)
        return calepinage_service.calepiner(
            self._document(params), company=self.company, **kwargs)

    def _electrique(self, params=None, **kwargs):
        return self._calepiner(params, **kwargs)['tiroirs']['electrique']


class LeTiroirPorteDeVraisChiffres(BasePv44):
    """PV44-1 — plus de ``donnees: null`` sur le chemin normal."""

    def test_le_tiroir_est_publie_avec_des_donnees(self):
        electrique = self._electrique()
        self.assertIsNotNone(electrique['donnees'])
        self.assertEqual(electrique['valeurs'],
                         {'taille_chaine': MODULES_PAR_CHAINE})

    def test_les_chaines_sont_celles_du_plan(self):
        sortie = self._calepiner()
        donnees = sortie['tiroirs']['electrique']['donnees']
        modules = sortie['total_modules']
        self.assertGreater(modules, 0)
        attendu = modules // MODULES_PAR_CHAINE
        self.assertIn(str(attendu), donnees['chaine']['libelle_taille'])
        self.assertIn(str(MODULES_PAR_CHAINE),
                      donnees['chaine']['libelle_taille'])

    def test_le_reste_hors_chaine_est_annonce_jamais_dissimule(self):
        sortie = self._calepiner()
        reste = sortie['total_modules'] % MODULES_PAR_CHAINE
        texte = sortie['tiroirs']['electrique']['donnees']['chaine'][
            'reste_texte']
        if reste:
            self.assertIn(str(reste), texte)
            self.assertIn('réserve', texte)
        else:
            self.assertEqual(texte, '')

    def test_le_nombre_d_onduleurs_sort_du_plafond_du_dossier(self):
        """Le compte porte sur la puissance RÉELLEMENT chaînée, pas sur le plan.

        Les modules en réserve d'appoint ne sont câblés à rien : les compter
        gonflerait le nombre d'onduleurs d'un dossier qui ne les raccorde pas.
        """
        import math

        sortie = self._calepiner()
        chaines = sortie['total_modules'] // MODULES_PAR_CHAINE
        chainee_kwc = (chaines * MODULES_PAR_CHAINE
                       * self.kit.puissance_module_w / 1000.0)
        attendu = max(1, math.ceil(chainee_kwc / PLAFOND_DC_PAR_ONDULEUR_KWC))
        onduleurs = sortie['tiroirs']['electrique']['donnees']['onduleurs']
        self.assertIn(str(attendu), onduleurs['nombre_texte'])
        self.assertIn('60', onduleurs['plafond_texte'])

    def test_la_forme_est_celle_du_contrat_partage(self):
        exemple = contrat()['exemple']['electrique']
        electrique = self._electrique()
        self.assertEqual(set(electrique), set(exemple))
        self.assertEqual(set(electrique['donnees']), set(exemple['donnees']))
        for bloc, attendu in exemple['donnees'].items():
            self.assertEqual(set(electrique['donnees'][bloc]), set(attendu),
                             bloc)
        self.assertLessEqual(set(electrique['valeurs']),
                             set(exemple['valeurs']))

    def test_la_puissance_ac_inconnue_n_est_pas_inventee(self):
        """Le document AO ne déclare aucun onduleur : le ratio reste muet."""
        donnees = self._electrique()['donnees']
        self.assertEqual(donnees['onduleurs']['puissance_texte'], '')
        self.assertEqual(donnees['ratio_dc_ac']['texte'], '—')
        self.assertTrue(donnees['ratio_dc_ac']['fourchette_texte'])

    def test_le_plan_sans_module_ne_bloque_pas_le_tiroir(self):
        """Une toiture trop petite : le tiroir DIT qu'il n'a rien à répartir."""
        minuscule = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='06H',
            contour_local_m=[[0, 0], [2, 0], [2, 2], [0, 2]],
            parametres_calepinage=dict(PARAMS))
        sortie = calepinage_service.calepiner(
            calepinage_io.document_entree(minuscule, params=PARAMS),
            company=self.company, budget=BUDGET_LARGE)
        self.assertEqual(sortie['total_modules'], 0)
        donnees = sortie['tiroirs']['electrique']['donnees']
        self.assertEqual(donnees['chaine']['libelle_taille'], '')
        self.assertTrue(donnees['conformite']['alerte'])


class LaRepartitionProposeeEstRejouable(BasePv44):
    """PV44-3 — le bouton « appliquer » applique VRAIMENT quelque chose."""

    def _params_impossibles(self):
        params = dict(PARAMS)
        params['taille_chaine'] = 40  # hors de toute plage de tension
        return params

    def test_une_longueur_impossible_bloque_et_propose(self):
        donnees = self._electrique(self._params_impossibles())['donnees']
        conformite = donnees['conformite']
        self.assertFalse(conformite['conforme'])
        self.assertTrue(conformite['bloquant'])
        self.assertIn('40', conformite['alerte'])
        self.assertIsNotNone(conformite['repartition_proposee'])

    def test_le_patch_est_du_vocabulaire_des_parametres(self):
        conformite = self._electrique(
            self._params_impossibles())['donnees']['conformite']
        patch = conformite['repartition_proposee']['patch']
        self.assertLessEqual(
            set(patch), set(calepinage_io.PATCH_ELECTRIQUE_VERS_PARAMS.values()))

    def test_rejouer_le_patch_leve_la_non_conformite(self):
        """La preuve que le patch est REJOUABLE : on le rejoue."""
        params = self._params_impossibles()
        patch = self._electrique(params)['donnees']['conformite'][
            'repartition_proposee']['patch']
        params.update(patch)
        conformite = self._electrique(params)['donnees']['conformite']
        self.assertTrue(conformite['conforme'], conformite['alerte'])
        self.assertIsNone(conformite['repartition_proposee'])

    def test_une_longueur_valide_ne_propose_rien(self):
        params = dict(PARAMS)
        params['taille_chaine'] = 12
        conformite = self._electrique(params)['donnees']['conformite']
        self.assertTrue(conformite['conforme'], conformite['alerte'])
        self.assertIsNone(conformite['repartition_proposee'])

    def test_une_longueur_de_chaine_absurde_est_refusee_a_l_entree(self):
        for valeur in ('seize', 0, -3):
            params = dict(PARAMS)
            params['taille_chaine'] = valeur
            with self.assertRaises(calepinage_service.EntreeInvalide):
                calepinage_io.document_entree(self.toiture, params=params)


class LEmpreinteSuitLaLongueurDeChaine(BasePv44):
    """PV44 — sans quoi le cache rendrait le tiroir d'AVANT la correction."""

    def test_sans_section_electrique_l_empreinte_ne_bouge_pas(self):
        """Non-régression : toutes les empreintes déjà publiées sont intactes."""
        document = self._document()
        self.assertNotIn('electrique', document)
        self.assertEqual(calepinage_service.empreinte_document(document),
                         hash_entree(calepinage_service._entree(document)))

    def test_changer_la_longueur_change_l_empreinte(self):
        params = dict(PARAMS)
        params['taille_chaine'] = 12
        avec = calepinage_service.empreinte_document(self._document(params))
        sans = calepinage_service.empreinte_document(self._document())
        self.assertNotEqual(avec, sans)
        params['taille_chaine'] = 14
        autre = calepinage_service.empreinte_document(self._document(params))
        self.assertNotEqual(avec, autre)

    def test_le_resultat_publie_l_empreinte_qui_porte_l_electrique(self):
        params = dict(PARAMS)
        params['taille_chaine'] = 12
        sortie = self._calepiner(params)
        self.assertEqual(sortie['hash_entree'],
                         calepinage_service.empreinte_document(
                             self._document(params)))


class LeGardeDeCoutTient(BasePv44):
    """PV44-4 — la promesse synchrone couvre AUSSI le tiroir électrique."""

    def test_le_cout_des_tiroirs_inclut_l_electrique(self):
        document = self._document()
        seul = calepinage_service.cout_estime(document)
        tout = calepinage_service.cout_estime(document, tiroirs=True)
        self.assertEqual(
            tout.appels,
            seul.appels * (calepinage_service.multiplicateur_tiroirs()
                           + calepinage_service.multiplicateur_electrique()))

    def test_hors_budget_le_tiroir_retombe_sur_sa_forme_degradee(self):
        sortie = self._calepiner(budget=BudgetCalcul(
            seuil_synchrone_ms=0.0001))
        self.assertEqual(sortie['tiroirs'],
                         calepinage_io.tiroirs_vides())
        # Le RÉSULTAT, lui, reste complet : seule la charge utile cède.
        self.assertGreater(sortie['total_modules'], 0)

    def test_le_chemin_persistant_ne_paie_pas_le_tiroir(self):
        """``calculer_variante`` demande ``tiroirs=False`` : rien n'est produit."""
        sortie = self._calepiner(tiroirs=False, suggestions=False)
        self.assertIsNone(sortie['tiroirs']['electrique']['donnees'])
        self.assertEqual(sortie['tiroirs']['electrique']['valeurs'], {})
