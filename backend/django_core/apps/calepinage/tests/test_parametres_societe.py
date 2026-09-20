"""CAL45 — les réglages société : UNE base, sept extensions.

Ce qui est prouvé ici :

* **équivalence** — une société SANS aucun réglage obtient les sept sections à
  ``{}`` : comportement d'aujourd'hui, strictement inchangé, et aucune clé
  absente que l'écran devrait deviner ;
* la forme rendue est EXACTEMENT celle du contrat committé
  ``contract_samples/parametres_calepinage.json`` (PACT10) — mêmes clés, dans
  les DEUX états du serveur (réglé / jamais réglé) ;
* une section INCONNUE est refusée en NOMMANT la clé fautive (jamais un « non
  enregistré » générique) ;
* une section qui n'est pas un objet est refusée en nommant la section ;
* l'isolation société tient : les réglages d'une société ne fuient jamais vers
  une autre, et un deuxième jeu pour la même société est impossible ;
* un enregistrement PARTIEL laisse les autres sections intactes.

Run :
    python manage.py test apps.calepinage.tests.test_parametres_societe -v2
"""
import json
import pathlib

from django.test import TestCase

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import (
    SECTIONS_LECTURE_SEULE,
    SECTIONS_PARAMETRES,
    parametres_de_societe,
)
from apps.calepinage.services.parametres import (
    ReglageInvalide,
    enregistrer_parametres,
)
from authentication.models import Company

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'parametres_calepinage.json').read_text(encoding='utf-8'))


def _sections_ecrivables(exemple):
    """Le contrat PRIVÉ de ses clés en LECTURE SEULE.

    CAL246 a ajouté ``kits`` à la charge utile de l'endpoint : c'est un
    catalogue LU chez ``apps.ao`` (``SECTIONS_LECTURE_SEULE``), pas une
    section de réglages — ``parametres_de_societe`` ne le rend donc pas, et
    un PUT le refuse comme toute clé inconnue.
    """
    return {cle: valeur for cle, valeur in exemple.items()
            if cle not in SECTIONS_LECTURE_SEULE}


class ContratTest(TestCase):
    """La forme rendue EST celle du contrat publié (PACT10)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Réglages Co',
                                              slug='reglages-co')

    def test_contrat_et_selecteur_ont_les_memes_cles(self):
        self.assertEqual(sorted(CONTRAT['exemple']),
                         sorted(SECTIONS_PARAMETRES + SECTIONS_LECTURE_SEULE))

    def test_les_deux_etats_ont_les_memes_cles(self):
        self.assertEqual(sorted(CONTRAT['exemple']),
                         sorted(CONTRAT['exemple_vide']))

    def test_societe_jamais_reglee_rend_le_contrat_vide(self):
        rendu = parametres_de_societe(self.company)
        self.assertEqual(rendu, _sections_ecrivables(CONTRAT['exemple_vide']))

    def test_societe_reglee_rend_les_memes_cles(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        rendu = parametres_de_societe(self.company)
        self.assertEqual(sorted(rendu),
                         sorted(_sections_ecrivables(CONTRAT['exemple'])))
        # CAL47 — la section « imagerie » a désormais son propre domaine de
        # validité (contrat `site_imagerie.json`) : elle est NORMALISÉE à
        # l'écriture, donc elle porte ses huit clés. Ce qui compte ici reste
        # la forme des SEPT sections, pas le contenu de l'une d'elles.
        self.assertEqual(rendu['imagerie']['pays'], 'ma')

    def test_toutes_les_sections_du_contrat_sont_des_objets(self):
        for section, valeur in _sections_ecrivables(CONTRAT['exemple']).items():
            self.assertIsInstance(valeur, dict, section)


class EquivalenceTest(TestCase):
    """Une société sans réglage se comporte comme aujourd'hui."""

    def setUp(self):
        self.company = Company.objects.create(nom='Vierge Co',
                                              slug='vierge-co')

    def test_aucune_ecriture_a_la_lecture(self):
        """Un GET qui écrit en base est un GET qui ment."""
        parametres_de_societe(self.company)
        self.assertEqual(
            ParametresCalepinage.objects.filter(company=self.company).count(),
            0)

    def test_toutes_les_sections_vides(self):
        rendu = parametres_de_societe(self.company)
        # Le compte suit ``SECTIONS_PARAMETRES`` : les sections ajoutées
        # depuis CAL45 (norme_electrique, lestage) sont des sections, pas des
        # exceptions — un nombre épinglé ici ne prouvait que sa propre date.
        self.assertEqual(sorted(rendu), sorted(SECTIONS_PARAMETRES))
        for section in SECTIONS_PARAMETRES:
            self.assertEqual(rendu[section], {}, section)

    def test_sans_societe_rend_le_contrat_vide(self):
        self.assertEqual(parametres_de_societe(None),
                         _sections_ecrivables(CONTRAT['exemple_vide']))


class RefusTest(TestCase):
    """Les refus NOMMENT la clé fautive, en français."""

    def setUp(self):
        self.company = Company.objects.create(nom='Refus Co',
                                              slug='refus-co')

    def test_section_inconnue_nommee(self):
        with self.assertRaises(ReglageInvalide) as capture:
            enregistrer_parametres(self.company,
                                   {'couleur_du_toit': {'teinte': 'ardoise'}})
        self.assertEqual(capture.exception.champ, 'couleur_du_toit')
        self.assertIn('couleur_du_toit', str(capture.exception))

    def test_section_inconnue_n_ecrit_rien(self):
        with self.assertRaises(ReglageInvalide):
            enregistrer_parametres(self.company, {'inconnue': {}})
        self.assertEqual(
            ParametresCalepinage.objects.filter(company=self.company).count(),
            0)

    def test_section_non_objet_nommee(self):
        with self.assertRaises(ReglageInvalide) as capture:
            enregistrer_parametres(self.company, {'degagements': ['0.5']})
        self.assertEqual(capture.exception.champ, 'degagements')
        self.assertIn('degagements', str(capture.exception))

    def test_sans_societe_refuse(self):
        with self.assertRaises(ReglageInvalide) as capture:
            enregistrer_parametres(None, {'imagerie': {}})
        self.assertEqual(capture.exception.champ, 'company')


class EcritureTest(TestCase):
    """Mise à jour partielle, remplacement explicite, isolation société."""

    def setUp(self):
        self.company = Company.objects.create(nom='Écriture Co',
                                              slug='ecriture-co')
        self.autre = Company.objects.create(nom='Autre Co', slug='autre-co-45')

    def test_mise_a_jour_partielle_preserve_le_reste(self):
        enregistrer_parametres(self.company, {
            'imagerie': {'pays': 'ma'},
            'degagements': {'retrait_rive_m': 0.5},
        })
        enregistrer_parametres(self.company, {'presets': {'villa': {}}})
        rendu = parametres_de_societe(self.company)
        self.assertEqual(rendu['imagerie']['pays'], 'ma')   # CAL47 : normalisée
        self.assertEqual(rendu['degagements'], {'retrait_rive_m': 0.5})
        self.assertEqual(rendu['presets'], {'villa': {}})

    def test_remplacer_vide_les_sections_absentes(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'},
                                              'presets': {'villa': {}}})
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'fr'}},
                               remplacer=True)
        rendu = parametres_de_societe(self.company)
        self.assertEqual(rendu['imagerie']['pays'], 'fr')   # CAL47 : normalisée
        self.assertEqual(rendu['presets'], {})

    def test_un_seul_enregistrement_par_societe(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        enregistrer_parametres(self.company, {'presets': {}})
        self.assertEqual(
            ParametresCalepinage.objects.filter(company=self.company).count(),
            1)

    def test_isolation_societe(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        self.assertEqual(parametres_de_societe(self.autre),
                         _sections_ecrivables(CONTRAT['exemple_vide']))
