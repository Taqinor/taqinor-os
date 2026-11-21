"""CAL71 — les dégagements d'obstacle paramétrables, et leur justification.

Ce qui est prouvé ici :

* une société qui n'a RIEN saisi obtient les chiffres d'aujourd'hui, au
  centimètre près (équivalence stricte) — et la phrase de règle dit que la
  valeur est « valeur atelier actuelle, non sourcée », jamais qu'elle est une
  norme ;
* modifier un dégagement société change RÉELLEMENT le calepinage traduit
  (CAL78) ET la phrase de règle affichée à côté de l'obstacle ;
* la section refuse ce qu'elle ne sait pas ranger : clé inconnue, valeur qui
  n'est pas un nombre, valeur négative — chaque refus NOMME le champ fautif ;
* le plancher imposé par la PROVENANCE reste au-dessus du réglage société :
  une société ne peut pas, en baissant un dégagement, faire passer pour
  mesuré un obstacle venu du plan.

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_degagements -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.degagements import (
    DEGAGEMENT_ATELIER_DEFAUT_M, DEGAGEMENTS_ATELIER, MENTION_NON_SOURCEE,
    RETRAIT_ATELIER_M, TYPES_ARETE,
    SECTION, _degagement_du_type, normaliser_section_degagements,
    _retrait_perimetre, _types_admis,
)
from apps.calepinage.services.parametres import ReglageInvalide
from apps.calepinage.services.traduction import entree_depuis_layout

from .test_traduction_layout import _document_or


class SansReglageRienNeChange(SimpleTestCase):
    """ÉQUIVALENCE : les chiffres de l'atelier, annoncés comme tels."""

    def test_la_section_vide_reste_vide(self):
        self.assertEqual(normaliser_section_degagements({}), {})
        self.assertEqual(normaliser_section_degagements(None), {})

    def test_les_valeurs_de_l_atelier_sont_celles_d_aujourd_hui(self):
        attendu = {'cheminee': 0.50, 'ventilation': 0.30,
                   'chien_assis': 0.50, 'edicule': 0.50,
                   'antenne': 0.30, 'autre': 0.30}
        for nom, valeur in attendu.items():
            self.assertEqual(_degagement_du_type(nom, {})[0], valeur, nom)

    def test_un_obstacle_sans_type_garde_le_degagement_de_base(self):
        self.assertEqual(_degagement_du_type(None, {})[0],
                         DEGAGEMENT_ATELIER_DEFAUT_M)

    def test_le_retrait_de_perimetre_est_celui_de_l_atelier(self):
        self.assertEqual(_retrait_perimetre({})[0], RETRAIT_ATELIER_M)

    def test_la_phrase_annonce_une_valeur_non_sourcee(self):
        for nom, _valeur, _libelle in DEGAGEMENTS_ATELIER:
            self.assertIn(MENTION_NON_SOURCEE, _degagement_du_type(nom, {})[1])
        self.assertIn(MENTION_NON_SOURCEE, _retrait_perimetre({})[1])

    def test_aucune_phrase_ne_presente_la_valeur_comme_une_norme(self):
        for nom in _types_admis():
            phrase = _degagement_du_type(nom, {})[1].lower()
            self.assertNotIn('norme', phrase)
            self.assertNotIn('réglementaire', phrase)


class LeReglageSocieteChangeLeCalepinage(SimpleTestCase):

    def test_la_valeur_saisie_prime(self):
        valeur, phrase = _degagement_du_type('cheminee', {'cheminee': 0.80})
        self.assertEqual(valeur, 0.80)
        self.assertIn('votre société', phrase)
        self.assertNotIn(MENTION_NON_SOURCEE, phrase)

    def test_la_source_saisie_est_citee(self):
        section = {'cheminee': 0.80, 'source': 'Consigne de pose interne v3'}
        self.assertIn('Consigne de pose interne v3',
                      _degagement_du_type('cheminee', section)[1])

    def test_le_retrait_saisi_prime(self):
        valeur, phrase = _retrait_perimetre({'retrait_rive_m': 0.35})
        self.assertEqual(valeur, 0.35)
        self.assertIn('votre société', phrase)

    def test_le_document_traduit_porte_la_valeur_societe(self):
        """Le bout en bout : la société change le chiffre du moteur."""
        sans = entree_depuis_layout(_document_or()).document['obstacles'][0]
        avec = entree_depuis_layout(
            _document_or(),
            parametres={SECTION: {'cheminee': 0.90}},
        ).document['obstacles'][0]
        self.assertEqual(sans['degagement_m'], 0.50)
        self.assertEqual(avec['degagement_m'], 0.90)

    def test_le_document_traduit_porte_la_phrase_de_regle(self):
        avec = entree_depuis_layout(
            _document_or(),
            parametres={SECTION: {'cheminee': 0.90,
                                  'source': 'Consigne interne v3'}},
        ).document['obstacles'][0]
        self.assertIn('Consigne interne v3', avec['regle_appliquee'])

    def test_le_retrait_societe_change_les_rives_du_document(self):
        traduction = entree_depuis_layout(
            _document_or(),
            parametres={SECTION: {'retrait_rive_m': 0.35}})
        rives = traduction.document['parametres']['rives']
        self.assertEqual(rives['laterale_m'], 0.35)
        self.assertEqual(rives['extremite_m'], 0.35)
        self.assertIn('votre société', traduction.regle_retrait)

    def test_sans_reglage_le_document_garde_le_retrait_de_l_atelier(self):
        traduction = entree_depuis_layout(_document_or())
        self.assertEqual(traduction.document['parametres']['rives']
                         ['laterale_m'], RETRAIT_ATELIER_M)
        self.assertIn(MENTION_NON_SOURCEE, traduction.regle_retrait)


class UneSocieteNeBaissePasUnPlancherDeProvenance(SimpleTestCase):
    """Baisser un dégagement ne rend pas « mesuré » ce qui vient du plan."""

    def test_le_plancher_de_provenance_gagne(self):
        from core.calepinage.obstacles import degagement_par_provenance
        from core.calepinage.types import Provenance

        document = _document_or()
        document['zones'][0]['obstacles'][0]['provenance'] = 'DEVINE'
        obstacle = entree_depuis_layout(
            document, parametres={SECTION: {'cheminee': 0.05}},
        ).document['obstacles'][0]
        self.assertEqual(obstacle['degagement_m'],
                         degagement_par_provenance(Provenance.DEVINE))
        self.assertIn('provenance DEVINE', obstacle['regle_appliquee'])

    def test_le_regime_de_preuve_n_est_pas_adouci(self):
        document = _document_or()
        document['zones'][0]['obstacles'][0]['provenance'] = 'PLAN'
        traduction = entree_depuis_layout(
            document, parametres={SECTION: {'cheminee': 0.05}})
        self.assertFalse(traduction.engageable)


class LaSectionRefuseCeQuElleNeSaitPasRanger(SimpleTestCase):

    def test_une_cle_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({'velux': 0.4})
        self.assertEqual(refus.exception.champ, f'{SECTION}.velux')
        self.assertIn('velux', str(refus.exception))

    def test_une_valeur_qui_n_est_pas_un_nombre_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({'cheminee': 'large'})
        self.assertEqual(refus.exception.champ, f'{SECTION}.cheminee')

    def test_un_booleen_n_est_pas_un_nombre(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_degagements({'cheminee': True})

    def test_une_valeur_negative_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({'retrait_rive_m': -0.2})
        self.assertEqual(refus.exception.champ,
                         f'{SECTION}.retrait_rive_m')

    def test_une_section_qui_n_est_pas_un_objet_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements([0.3])
        self.assertEqual(refus.exception.champ, SECTION)

    def test_une_section_valide_est_rendue_en_nombres(self):
        propre = normaliser_section_degagements(
            {'cheminee': 1, 'retrait_rive_m': 0.35, 'source': '  v3 '})
        self.assertEqual(propre,
                         {'cheminee': 1.0, 'retrait_rive_m': 0.35,
                          'source': 'v3'})

    def test_les_cles_du_contrat_publie_sont_acceptees(self):
        """L'échantillon de contrat CAL45 doit traverser sans refus (PACT10)."""
        import io
        import json
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'parametres_calepinage.json')
        with io.open(chemin, encoding='utf-8') as fichier:
            contrat = json.load(fichier)
        publiee = contrat['exemple'][SECTION]
        self.assertTrue(publiee, 'le contrat ne décrit plus la section')
        normalisee = normaliser_section_degagements(publiee)
        for cle, valeur in publiee.items():
            self.assertIn(cle, normalisee)
            if isinstance(valeur, (int, float)):
                self.assertEqual(normalisee[cle], float(valeur))

    def test_l_allee_technique_du_contrat_alimente_le_moteur(self):
        traduction = entree_depuis_layout(
            _document_or(),
            parametres={SECTION: {'allee_technique_m': 0.9}})
        self.assertEqual(traduction.document['parametres']['allee_m'], 0.9)

    def test_une_source_vide_n_est_pas_enregistree(self):
        self.assertEqual(normaliser_section_degagements({'source': '   '}),
                         {})


class UnNouveauTypeLitLeReglageSociete(SimpleTestCase):
    """ACAL499 — lanterneau saisi : 1,8 m et la phrase de la société ; citerne
    non saisie : le recul de base, nommé comme tel."""

    def test_un_lanterneau_saisi_porte_la_valeur_et_la_source(self):
        section = normaliser_section_degagements(
            {'lanterneau': 1.8, 'source': 'DS 1-15 §2.1.1.4'})
        valeur, phrase = _degagement_du_type('lanterneau', section)
        self.assertEqual(valeur, 1.8)
        self.assertEqual(
            phrase, 'Lanterneau : 1.80 m (réglage de votre société — '
                    'DS 1-15 §2.1.1.4)')

    def test_une_citerne_sans_reglage_porte_le_recul_de_base_nomme(self):
        valeur, phrase = _degagement_du_type('citerne', {})
        self.assertEqual(valeur, DEGAGEMENT_ATELIER_DEFAUT_M)
        self.assertEqual(
            phrase, 'Citerne : 0.30 m (recul de base, aucun dégagement '
                    'société pour ce type)')

    def test_l_atelier_garde_six_lignes(self):
        self.assertEqual(len(DEGAGEMENTS_ATELIER), 6)

    def test_une_valeur_negative_est_refusee_sous_le_type(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({'lanterneau': -1})
        self.assertEqual(refus.exception.champ, f'{SECTION}.lanterneau')

    def test_un_texte_est_refuse_sous_le_type(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({'citerne': 'large'})
        self.assertEqual(refus.exception.champ, f'{SECTION}.citerne')

    def test_l_echantillon_du_contrat_est_admis(self):
        import io
        import json
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'parametres_calepinage.json')
        with io.open(chemin, encoding='utf-8') as fichier:
            contrat = json.load(fichier)
        exemple = contrat['exemple_degagement_type_neuf'][SECTION]
        propre = normaliser_section_degagements(exemple)
        self.assertEqual(propre['lanterneau'], 1.8)

    def test_un_type_vraiment_inconnu_reste_refuse(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_degagements({'velux': 0.4})


class LesRetraitsParTypeDAreteSontSources(SimpleTestCase):
    """ACAL561 — ``retraits_par_arete`` : un retrait SUPPLÉMENTAIRE par type
    d'arête, chacun avec sa source, vide par défaut."""

    def _section(self, *entrees):
        return {'retraits_par_arete': list(entrees)}

    def test_egout_avec_source_accepte(self):
        propre = normaliser_section_degagements(self._section(
            {'type': 'egout', 'retrait_m': 0.4, 'source': 'notice X',
             'reference': ''}))
        self.assertEqual(propre['retraits_par_arete'], [
            {'type': 'egout', 'retrait_m': 0.4, 'source': 'notice X',
             'reference': ''}])

    def test_sans_source_refuse_en_nommant_le_champ(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements(self._section(
                {'type': 'egout', 'retrait_m': 0.4, 'source': ''}))
        self.assertEqual(refus.exception.champ,
                         'degagements.retraits_par_arete[0].source')

    def test_type_inconnue_double_ou_cle_inconnue_refuses(self):
        for entrees in (
                [{'type': 'inconnue', 'retrait_m': 0.4, 'source': 's'}],
                [{'type': 'rive', 'retrait_m': 0.2, 'source': 's'},
                 {'type': 'rive', 'retrait_m': 0.3, 'source': 's'}],
                [{'type': 'rive', 'retrait_m': 0.2, 'source': 's', 'x': 1}],
                [{'type': 'rive', 'retrait_m': -0.2, 'source': 's'}]):
            with self.subTest(entrees=entrees):
                with self.assertRaises(ReglageInvalide):
                    normaliser_section_degagements(self._section(*entrees))

    def test_section_sans_la_cle_inchangee(self):
        section = {'retrait_rive_m': 0.4, 'source': 'DTU'}
        self.assertEqual(normaliser_section_degagements(section), section)
        self.assertEqual(TYPES_ARETE,
                         ('faitage', 'noue', 'arretier', 'egout', 'rive'))


class LaSectionEstBranchee(SimpleTestCase):
    """Le crochet de normalisation de CAL47 porte bien cette section."""

    def test_le_normaliseur_est_enregistre(self):
        from apps.calepinage.services.parametres import _normaliseurs

        self.assertIn(SECTION, _normaliseurs())

    def test_la_section_est_une_section_admise(self):
        from apps.calepinage.selectors import SECTIONS_PARAMETRES

        self.assertIn(SECTION, SECTIONS_PARAMETRES)
