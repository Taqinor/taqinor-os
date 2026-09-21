"""CALX145 — les deux sections société « simulation » et « electrique_societe ».

CE QUE CE FICHIER PROTÈGE
-------------------------
1. **L'ÉQUIVALENCE.** Les neuf sections historiques gardent leur rang et leur
   comportement ; une société qui n'a rien saisi reçoit les deux nouvelles
   sections à ``{}``, ce qui veut dire « comportement d'aujourd'hui » — aucune
   étape de simulation, aucun contrôle électrique ne se met à rendre un
   verdict qu'il ne rendait pas.
2. **LE REGISTRE APPEND-ONLY.** ``services/parametres_cles.py`` déclare les
   clés admises une par une. Le SOCLE initial figé ici doit rester le
   PRÉFIXE de chaque tuple : une clé peut s'ajouter EN FIN, jamais se
   renommer, se réordonner ni disparaître (décision D-CALX 13).
3. **ZÉRO CHIFFRE INVENTÉ (D-CALX 7).** Le registre ne porte AUCUNE valeur :
   quatre textes par ligne, jamais un nombre. Une valeur saisie sans sa
   provenance est REFUSÉE en nommant la clé ; une clé hors registre est
   refusée en la nommant ; une clé déclarée sans valeur est refusée en la
   nommant. Jamais un « non enregistré » générique.
4. **LA MIGRATION.** ``0010_calx145_parametres_simulation`` ajoute EXACTEMENT
   les deux champs, sur la tête réelle ``0009_cal212_pose_reelle``, et ses
   deux champs se déconstruisent comme ceux du modèle (sinon
   ``makemigrations --check`` rougit en CI, jamais ici).

Tout est en ``SimpleTestCase`` — aucune base — SAUF ``EquivalenceSocieteTest``
qui écrit un enregistrement et reste donc un ``TestCase``.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx145_parametres_simulation -v2
"""
import importlib
import json
import pathlib

from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import (
    SECTIONS_LECTURE_SEULE,
    SECTIONS_PARAMETRES,
    parametres_de_societe,
)
from apps.calepinage.services.parametres import (
    ReglageInvalide,
    _normaliseurs,
    enregistrer_parametres,
    normaliser_section_electrique_societe,
    normaliser_section_simulation,
)
from apps.calepinage.services.parametres_cles import (
    CLES_ELECTRIQUE_SOCIETE,
    CLES_SIMULATION,
    SECTION_ELECTRIQUE_SOCIETE,
    SECTION_SIMULATION,
    SOURCES_ADMISES,
    registre,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'parametres_calepinage.json').read_text(encoding='utf-8'))

#: LE SOCLE de la section ``simulation``, dans l'ordre où CALX145 le déclare.
#: Il doit rester le PRÉFIXE de ``CLES_SIMULATION`` : une tâche qui a besoin
#: d'un réglage AJOUTE sa clé EN FIN du tuple, elle ne touche pas à celles-ci.
SOCLE_SIMULATION = (
    'fenetre_annees',
    'mode_meteo',
    'modele_iam',
    'b0_iam',
    'sigma_modele_pct',
    'sigma_biais_meteo_pct',
    'sigma_meteo_saisi_pct',
    'tolerance_validation_pct',
    'resolution_minutes',
    'albedo_mensuel',
    'annees_exploitation',
    'regle_qualite_module',
    'lid_par_techno',
    'mismatch_fabricant_pct',
    'modele_degradation',
    'thermique_par_pose',
    'attenuation_horizon',
)

#: LE SOCLE de la section ``electrique_societe``, même règle.
SOCLE_ELECTRIQUE_SOCIETE = (
    'tolerance_polystring_acceptable_pct',
    'tolerance_polystring_bloquante_pct',
    'seuil_desequilibre_pct',
    'borne_usuelle_dc_ac',
    'seuil_alerte_dc_ac',
    'correspondances_nomenclature',
    'regle_bom_structure',
    'cos_phi_par_defaut',
)

#: Les NEUF sections d'avant CALX145, dans leur ordre : elles gardent leur
#: rang (une section qui change de place, c'est un contrat qui bouge).
SECTIONS_HISTORIQUES = (
    'imagerie', 'degagements', 'zones_types', 'gabarits_disposition',
    'presets', 'favoris_materiel', 'gabarits_dossier', 'norme_electrique',
    'lestage',
)


def _cles(declarations):
    return tuple(declaration[0] for declaration in declarations)


class RegistreAppendOnlyTest(SimpleTestCase):
    """Le registre ne peut que s'allonger, et ne porte aucune valeur."""

    def test_le_socle_simulation_est_le_prefixe_du_tuple(self):
        cles = _cles(CLES_SIMULATION)
        self.assertEqual(
            cles[:len(SOCLE_SIMULATION)], SOCLE_SIMULATION,
            "CLES_SIMULATION a été réordonné, renommé ou raccourci : le "
            "registre est APPEND-ONLY (D-CALX 13), une clé neuve s'ajoute EN "
            "FIN du tuple avec son commentaire « # CALX<id> ».")

    def test_le_socle_electrique_est_le_prefixe_du_tuple(self):
        cles = _cles(CLES_ELECTRIQUE_SOCIETE)
        self.assertEqual(
            cles[:len(SOCLE_ELECTRIQUE_SOCIETE)], SOCLE_ELECTRIQUE_SOCIETE,
            "CLES_ELECTRIQUE_SOCIETE a été réordonné, renommé ou raccourci : "
            "le registre est APPEND-ONLY (D-CALX 13).")

    def test_aucune_cle_en_double(self):
        for nom, declarations in (('simulation', CLES_SIMULATION),
                                  ('electrique_societe',
                                   CLES_ELECTRIQUE_SOCIETE)):
            with self.subTest(section=nom):
                cles = _cles(declarations)
                doublons = sorted({c for c in cles if cles.count(c) > 1})
                self.assertEqual(doublons, [],
                                 f"Clé(s) déclarée(s) deux fois : {doublons}.")

    def test_chaque_declaration_porte_ses_quatre_textes(self):
        """``(clé, libellé, unité, référence)`` — et QUE des textes.

        Aucune VALEUR n'entre au registre : il dit quelles clés existent,
        jamais ce qu'elles valent (D-CALX 7).
        """
        for declaration in CLES_SIMULATION + CLES_ELECTRIQUE_SOCIETE:
            with self.subTest(cle=declaration[0]):
                self.assertEqual(len(declaration), 4)
                for champ in declaration:
                    self.assertIsInstance(champ, str)
                cle, libelle, _unite, reference = declaration
                self.assertTrue(cle.strip() and cle == cle.strip(), cle)
                self.assertTrue(libelle.strip(),
                                f"« {cle} » n'a pas de libellé français.")
                self.assertTrue(
                    reference.strip(),
                    f"« {cle} » n'a pas de référence doctrinale : une clé "
                    "sans référence est une clé qu'on ne peut pas défendre.")

    def test_registre_rend_les_memes_cles_que_les_tuples(self):
        self.assertEqual(sorted(registre(SECTION_SIMULATION)),
                         sorted(_cles(CLES_SIMULATION)))
        self.assertEqual(sorted(registre(SECTION_ELECTRIQUE_SOCIETE)),
                         sorted(_cles(CLES_ELECTRIQUE_SOCIETE)))

    def test_une_section_sans_registre_rend_un_dict_vide(self):
        self.assertEqual(registre('imagerie'), {})


class SectionsAdmisesTest(SimpleTestCase):
    """Les deux sections sont des sections ADMISES, et les neuf autres
    gardent leur rang."""

    def test_le_modele_et_le_selecteur_declarent_la_meme_liste(self):
        self.assertEqual(tuple(ParametresCalepinage.SECTIONS),
                         tuple(SECTIONS_PARAMETRES))

    def test_les_neuf_sections_historiques_gardent_leur_rang(self):
        self.assertEqual(
            tuple(SECTIONS_PARAMETRES)[:len(SECTIONS_HISTORIQUES)],
            SECTIONS_HISTORIQUES)

    def test_les_deux_sections_neuves_sont_admises(self):
        for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
            with self.subTest(section=section):
                self.assertIn(section, SECTIONS_PARAMETRES)
                self.assertIn(section, ParametresCalepinage.SECTIONS)
                self.assertEqual(
                    ParametresCalepinage.sections_inconnues({section: {}}), [])

    def test_une_section_inconnue_est_toujours_refusee_en_la_nommant(self):
        self.assertEqual(
            ParametresCalepinage.sections_inconnues({'simulacion': {}}),
            ['simulacion'])

    def test_les_deux_normaliseurs_sont_enregistres(self):
        normaliseurs = _normaliseurs()
        self.assertIn(SECTION_SIMULATION, normaliseurs)
        self.assertIn(SECTION_ELECTRIQUE_SOCIETE, normaliseurs)


class NormalisationTest(SimpleTestCase):
    """Les refus NOMMENT la clé fautive, et le vide reste le vide."""

    def test_rien_de_saisi_rend_une_section_vide(self):
        for valeur in (None, {}):
            with self.subTest(valeur=valeur):
                self.assertEqual(normaliser_section_simulation(valeur), {})
                self.assertEqual(
                    normaliser_section_electrique_societe(valeur), {})

    def test_une_section_qui_n_est_pas_un_objet_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation([1, 2])
        self.assertEqual(refus.exception.champ, SECTION_SIMULATION)

    def test_une_cle_hors_registre_est_refusee_en_la_nommant(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation(
                {'coefficient_maison': {'valeur': 1, 'source': 'societe'}})
        self.assertEqual(refus.exception.champ, 'coefficient_maison')
        self.assertIn('coefficient_maison', str(refus.exception))

    def test_une_valeur_sans_source_est_refusee_en_nommant_la_cle(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation(
                {'mismatch_fabricant_pct': {'valeur': 1.5}})
        self.assertEqual(refus.exception.champ, 'mismatch_fabricant_pct')
        self.assertIn('Mismatch de fabrication', str(refus.exception))

    def test_une_source_vide_est_refusee_comme_une_source_absente(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation(
                {'b0_iam': {'valeur': 0.05, 'source': '   '}})
        self.assertEqual(refus.exception.champ, 'b0_iam')

    def test_une_provenance_hors_liste_est_refusee_en_la_citant(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_electrique_societe(
                {'seuil_desequilibre_pct': {'valeur': 5,
                                            'source': 'au_pif'}})
        self.assertEqual(refus.exception.champ, 'seuil_desequilibre_pct')
        self.assertIn('au_pif', str(refus.exception))

    def test_une_cle_declaree_sans_valeur_est_refusee_en_la_nommant(self):
        for valeur in (None, '', {}, []):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ReglageInvalide) as refus:
                    normaliser_section_simulation(
                        {'mode_meteo': {'valeur': valeur,
                                        'source': 'societe'}})
                self.assertEqual(refus.exception.champ, 'mode_meteo')

    def test_une_enveloppe_avec_du_rabiot_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation(
                {'mode_meteo': {'valeur': 'tmy', 'source': 'societe',
                                'commentaire': 'au cas où'}})
        self.assertEqual(refus.exception.champ, 'mode_meteo')
        self.assertIn('commentaire', str(refus.exception))

    def test_une_reference_qui_n_est_pas_un_texte_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_simulation(
                {'mode_meteo': {'valeur': 'tmy', 'source': 'societe',
                                'reference': 2026}})
        self.assertEqual(refus.exception.champ, 'mode_meteo')

    def test_une_valeur_saisie_ressort_avec_sa_provenance(self):
        rendu = normaliser_section_simulation({
            'mode_meteo': {'valeur': '  pluriannuel  ', 'source': 'societe',
                           'reference': '  décision du 21/09/2026  '},
        })
        self.assertEqual(rendu, {
            'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe',
                           'reference': 'décision du 21/09/2026'},
        })

    def test_une_reference_absente_ressort_vide_jamais_devinee(self):
        rendu = normaliser_section_electrique_societe(
            {'cos_phi_par_defaut': {'valeur': 1.0, 'source': 'societe'}})
        self.assertEqual(rendu['cos_phi_par_defaut']['reference'], '')

    def test_une_valeur_peut_etre_une_table_entiere(self):
        """``thermique_par_pose`` est une table, pas un nombre : le registre
        ne dit pas le TYPE, il dit que la clé existe."""
        table = {'flush': {'uc_w_m2k': 20.0, 'uv_w_m3sk': 0.0,
                           'source': 'mesure', 'reference': 'essai chantier'}}
        rendu = normaliser_section_simulation(
            {'thermique_par_pose': {'valeur': table, 'source': 'mesure',
                                    'reference': 'essai chantier'}})
        self.assertEqual(rendu['thermique_par_pose']['valeur'], table)

    def test_une_cle_mise_a_null_est_retiree_sans_rien_deviner(self):
        rendu = normaliser_section_simulation({'mode_meteo': None})
        self.assertEqual(rendu, {})

    def test_toutes_les_provenances_admises_passent(self):
        for source in SOURCES_ADMISES:
            with self.subTest(source=source):
                rendu = normaliser_section_simulation(
                    {'annees_exploitation': {'valeur': 25, 'source': source}})
                self.assertEqual(
                    rendu['annees_exploitation']['source'], source)


class ContratTest(SimpleTestCase):
    """PACT10 : l'échantillon publié ne peut pas être refusé par son serveur."""

    def test_les_deux_sections_sont_dans_les_deux_etats(self):
        for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
            with self.subTest(section=section):
                self.assertIn(section, CONTRAT['exemple'])
                self.assertIn(section, CONTRAT['exemple_vide'])
                self.assertEqual(CONTRAT['exemple_vide'][section], {})

    def test_le_contrat_et_le_selecteur_declarent_les_memes_sections(self):
        self.assertEqual(
            sorted(cle for cle in CONTRAT['exemple']
                   if cle not in SECTIONS_LECTURE_SEULE),
            sorted(SECTIONS_PARAMETRES))

    def test_l_exemple_committe_traverse_les_normaliseurs(self):
        for section, normaliseur in (
                (SECTION_SIMULATION, normaliser_section_simulation),
                (SECTION_ELECTRIQUE_SOCIETE,
                 normaliser_section_electrique_societe)):
            with self.subTest(section=section):
                publiee = CONTRAT['exemple'][section]
                self.assertTrue(
                    publiee, 'le contrat ne décrit plus la section')
                self.assertEqual(normaliseur(publiee), publiee)

    def test_chaque_cle_de_l_exemple_est_au_registre(self):
        for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
            with self.subTest(section=section):
                admises = set(registre(section))
                self.assertEqual(
                    sorted(set(CONTRAT['exemple'][section]) - admises), [])


class EquivalenceTest(SimpleTestCase):
    """Une société sans réglage se comporte EXACTEMENT comme avant."""

    def test_le_selecteur_rend_les_deux_sections_vides(self):
        rendu = parametres_de_societe(None)
        self.assertEqual(rendu[SECTION_SIMULATION], {})
        self.assertEqual(rendu[SECTION_ELECTRIQUE_SOCIETE], {})

    def test_le_selecteur_rend_toutes_les_sections_admises(self):
        self.assertEqual(sorted(parametres_de_societe(None)),
                         sorted(SECTIONS_PARAMETRES))

    def test_les_deux_champs_naissent_vides(self):
        """Le défaut du modèle est ``dict`` : jamais ``null``, jamais une
        valeur — une instance neuve ne règle rien."""
        for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
            with self.subTest(section=section):
                champ = ParametresCalepinage._meta.get_field(section)
                self.assertIs(champ.default, dict)
                self.assertTrue(champ.blank)


class MigrationTest(SimpleTestCase):
    """``0010`` ajoute EXACTEMENT les deux champs, sur la tête réelle."""

    @staticmethod
    def _migration():
        module = importlib.import_module(
            'apps.calepinage.migrations.0010_calx145_parametres_simulation')
        return module.Migration

    def test_elle_chaine_sur_la_tete_reelle(self):
        self.assertEqual(self._migration().dependencies,
                         [('calepinage', '0009_cal212_pose_reelle')])

    def test_elle_ajoute_exactement_les_deux_champs(self):
        operations = self._migration().operations
        self.assertEqual(
            [(op.__class__.__name__, op.model_name, op.name)
             for op in operations],
            [('AddField', 'parametrescalepinage', 'electrique_societe'),
             ('AddField', 'parametrescalepinage', 'simulation')])

    def test_chaque_champ_se_deconstruit_comme_celui_du_modele(self):
        """Le piège qui rougit ``makemigrations --check`` en CI : un
        ``verbose_name`` ou un défaut qui diffère d'un caractère."""
        for operation in self._migration().operations:
            with self.subTest(champ=operation.name):
                du_modele = ParametresCalepinage._meta.get_field(
                    operation.name)
                self.assertEqual(du_modele.deconstruct()[1:],
                                 operation.field.deconstruct()[1:])


class EquivalenceSocieteTest(TestCase):
    """ORM — non exécuté sur l'hôte de lane (aucune base) ; gate = CI."""

    def setUp(self):
        from authentication.models import Company

        self.company = Company.objects.create(nom='Simulation Co',
                                              slug='simulation-co')

    def test_societe_jamais_reglee_rend_les_deux_sections_vides(self):
        rendu = parametres_de_societe(self.company)
        self.assertEqual(rendu[SECTION_SIMULATION], {})
        self.assertEqual(rendu[SECTION_ELECTRIQUE_SOCIETE], {})

    def test_un_enregistrement_partiel_laisse_les_autres_sections(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        enregistrer_parametres(self.company, {SECTION_SIMULATION: {
            'mode_meteo': {'valeur': 'tmy', 'source': 'societe'}}})
        rendu = parametres_de_societe(self.company)
        self.assertEqual(rendu[SECTION_SIMULATION]['mode_meteo']['valeur'],
                         'tmy')
        self.assertEqual(rendu['imagerie']['pays'], 'ma')
        self.assertEqual(rendu[SECTION_ELECTRIQUE_SOCIETE], {})

    def test_une_valeur_sans_source_est_refusee_a_l_enregistrement(self):
        with self.assertRaises(ReglageInvalide) as refus:
            enregistrer_parametres(self.company, {SECTION_SIMULATION: {
                'sigma_modele_pct': {'valeur': 3.0}}})
        self.assertEqual(refus.exception.champ, 'sigma_modele_pct')
