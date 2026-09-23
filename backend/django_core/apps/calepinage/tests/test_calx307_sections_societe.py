"""CALX307 — la société choisit les sections incluses dans ses rapports.

Ce qui est prouvé ici :

* un réglage ABSENT (société jamais passée par l'écran, ``documents``
  vide, ``sections`` à ``null``) rend ``None`` — le rapport d'aujourd'hui,
  octet pour octet (D12) ;
* une sélection valide est retournée dans l'ORDRE DU CONTRAT, jamais
  l'ordre saisi ;
* un code inconnu est refusé en le NOMMANT (``RapportRefuse``,
  ``champ='sections'``) ;
* le retrait d'une section ``obligatoire`` est refusé en la NOMMANT ;
* ``sections`` qui n'est pas une liste est refusé ;
* en base (CI) : ``ParametresCalepinage.full_clean()`` — donc l'écriture
  normale via ``enregistrer_parametres`` — refuse la MÊME chose, au même
  titre que les onze autres sections.

Run (partie pure) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx307_sections_societe.py -q
"""
import copy
import re
import unittest
from types import SimpleNamespace

from django.core.exceptions import ValidationError

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.parametres_cles import CODE_RAPPORT_ETUDE
from apps.calepinage.services.rapport import (
    RapportRefuse, construire_rapport, html_de_rapport, sections_declarees,
)
from apps.calepinage.services.rapport.sections_societe import (
    configuration_document, sections_retenues, valider_selection,
)

from .test_api_liste import BaseApiCalepinage

#: Les sept sections ``obligatoire`` du contrat — celles qu'une société ne
#: peut jamais décocher (``rapport_etude.json``).
OBLIGATOIRES = [s['code'] for s in sections_declarees() if s['obligatoire']]
#: Les trois sections FACULTATIVES.
FACULTATIVES = [s['code'] for s in sections_declarees() if not s['obligatoire']]

#: Un ``resultat`` minimal qui rend TOUTES les sections « disponibles »
#: (mêmes chemins que ``test_calx297_rapport_etude.py``).
RESULTAT = {
    'hash_entree': 'a' * 64, 'version_moteur': 'v1',
    'production': {'base': {'source': 'pvgis'},
                   'total': {'p50_kwh': 13000.0}, 'mensuel': [1, 2]},
    'pose': {'total_modules': 12, 'kwc': 6.0, 'pans': [{'pan': 'P1'}]},
    'ombrage': {'par_pan': [{'pan': 'P1', 'acces_solaire_pct': 95}]},
    'electrique': {'chainage': {'chaines': 1},
                   'verdicts': ['ok'], 'onduleurs': [{'reference': 'X'}]},
}
SITE = {'ville': 'Bouskoura'}
IDENTITE = {'titre_document': "Rapport d'étude", 'projet': 'Villa Anfa'}
STYLES = {'nom_affiche': 'Soleil Atlas'}
NU = SimpleNamespace(company=None, client_id=None, lead_id=None,
                     titre='Villa Anfa', resultat=None, pk=None)


class EquivalenceD12Test(unittest.TestCase):
    """Un réglage absent produit EXACTEMENT le rapport d'aujourd'hui."""

    def test_aucun_parametre_rend_none(self):
        self.assertIsNone(sections_retenues(None))

    def test_documents_vide_rend_none(self):
        self.assertIsNone(
            sections_retenues(SimpleNamespace(documents={})))

    def test_sections_a_null_rend_none(self):
        parametres = SimpleNamespace(
            documents={'rapport_etude': {'sections': None, 'langue': None}})
        self.assertIsNone(sections_retenues(parametres))

    def test_un_autre_document_ne_pollue_pas_rapport_etude(self):
        parametres = SimpleNamespace(
            documents={'autre_document': {'sections': ['garde']}})
        self.assertIsNone(sections_retenues(parametres))

    def test_le_rapport_est_octet_pour_octet_identique(self):
        rapport_sans_reglage = construire_rapport(
            NU, resultat=copy.deepcopy(RESULTAT), site=SITE,
            identite=IDENTITE, styles=STYLES,
            sections=sections_retenues(None))
        rapport_par_defaut = construire_rapport(
            NU, resultat=copy.deepcopy(RESULTAT), site=SITE,
            identite=IDENTITE, styles=STYLES)
        self.assertEqual(html_de_rapport(rapport_sans_reglage),
                         html_de_rapport(rapport_par_defaut))


class ConfigurationDocumentTest(unittest.TestCase):
    def test_lit_le_bon_code_document(self):
        parametres = SimpleNamespace(documents={
            'rapport_etude': {'sections': ['garde'], 'langue': 'en'},
            'autre_document': {'sections': ['x']},
        })
        self.assertEqual(configuration_document(parametres),
                         {'sections': ['garde'], 'langue': 'en'})
        self.assertEqual(
            configuration_document(parametres, code='autre_document'),
            {'sections': ['x']})

    def test_une_configuration_qui_n_est_pas_un_objet_rend_vide(self):
        parametres = SimpleNamespace(documents={'rapport_etude': ['garde']})
        self.assertEqual(configuration_document(parametres), {})


class SelectionValideTest(unittest.TestCase):
    def test_une_selection_valide_suit_l_ordre_du_contrat(self):
        # Saisie dans le désordre : le rendu doit rester celui du contrat.
        demande = list(reversed(OBLIGATOIRES))
        self.assertNotEqual(demande, OBLIGATOIRES)
        self.assertEqual(valider_selection(demande), OBLIGATOIRES)

    def test_les_sections_facultatives_peuvent_etre_toutes_decochees(self):
        # Aucune facultative choisie : reste exactement les obligatoires.
        self.assertEqual(valider_selection(OBLIGATOIRES), OBLIGATOIRES)
        for code in FACULTATIVES:
            self.assertNotIn(code, valider_selection(OBLIGATOIRES))

    def test_une_facultative_ajoutee_reste_a_sa_place_de_contrat(self):
        codes = [s['code'] for s in sections_declarees()]
        demande = OBLIGATOIRES + ['ombrage']
        attendu = [c for c in codes if c in demande]
        self.assertEqual(valider_selection(demande), attendu)

    def test_sections_retenues_delegue_a_valider_selection(self):
        parametres = SimpleNamespace(
            documents={'rapport_etude': {'sections': OBLIGATOIRES}})
        self.assertEqual(sections_retenues(parametres), OBLIGATOIRES)


class CodeInconnuTest(unittest.TestCase):
    def test_un_code_inconnu_est_refuse_en_le_nommant(self):
        with self.assertRaises(RapportRefuse) as capture:
            valider_selection(OBLIGATOIRES + ['section_fantome'])
        self.assertEqual(capture.exception.champ, 'sections')
        self.assertIn('section_fantome', str(capture.exception))

    def test_le_refus_remonte_depuis_sections_retenues(self):
        parametres = SimpleNamespace(
            documents={'rapport_etude': {'sections': ['section_fantome']}})
        with self.assertRaises(RapportRefuse) as capture:
            sections_retenues(parametres)
        self.assertIn('section_fantome', str(capture.exception))


class SectionObligatoireDecocheeTest(unittest.TestCase):
    def test_decocher_une_section_obligatoire_est_refuse(self):
        for code in OBLIGATOIRES:
            with self.subTest(section=code):
                demande = [c for c in OBLIGATOIRES if c != code]
                with self.assertRaises(RapportRefuse) as capture:
                    valider_selection(demande)
                self.assertEqual(capture.exception.champ, code)
                self.assertIn(code, str(capture.exception))

    def test_toutes_les_obligatoires_retirees_nomme_la_premiere(self):
        with self.assertRaises(RapportRefuse) as capture:
            valider_selection(['ombrage'])
        self.assertEqual(capture.exception.champ, OBLIGATOIRES[0])


class SectionsNonListeTest(unittest.TestCase):
    def test_une_valeur_qui_n_est_pas_une_liste_est_refusee(self):
        parametres = SimpleNamespace(
            documents={'rapport_etude': {'sections': 'garde'}})
        with self.assertRaises(RapportRefuse) as capture:
            sections_retenues(parametres)
        self.assertEqual(capture.exception.champ, 'sections')
        self.assertIn('str', str(capture.exception))


class MiseEnPageAvecSelectionTest(unittest.TestCase):
    """Le rapport, restreint aux SEULES sections obligatoires."""

    def test_seules_les_sections_choisies_sont_imprimees(self):
        rapport = construire_rapport(
            NU, resultat=copy.deepcopy(RESULTAT), site=SITE,
            identite=IDENTITE, styles=STYLES,
            sections=valider_selection(OBLIGATOIRES))
        html = html_de_rapport(rapport)
        imprimees = re.findall(r'data-section="([a-z_]+)"', html)
        self.assertEqual(imprimees,
                         [c for c in OBLIGATOIRES if c != 'garde'])
        for facultative in FACULTATIVES:
            self.assertNotIn('data-section="%s"' % facultative, html)


# ── En base (CI) — ParametresCalepinage.full_clean() refuse la MÊME chose ──
#
# Ce fichier importe `apps.calepinage.models` (ci-dessus) : il exige Django
# settings configurées, donc NE SE COLLECTE PAS dans ce worktree (aucun
# DJANGO_SETTINGS_MODULE) — même situation que
# `test_calx297_rapport_etude.py`. Les classes PURES ci-dessus ont été
# vérifiées séparément (script du scratchpad, mêmes assertions, sans cet
# import) ; la CI valide le fichier entier via `python manage.py test`.

class EcritureNormaleRefuseAussiTest(BaseApiCalepinage):
    """``enregistrer_parametres`` → ``full_clean`` refuse comme ci-dessus."""

    def test_un_code_inconnu_est_refuse_a_l_ecriture(self):
        config = {'sections': ['section_fantome']}
        with self.assertRaises(ValidationError):
            enregistrer_parametres(self.company, {
                'documents': {CODE_RAPPORT_ETUDE: config}})

    def test_une_section_obligatoire_decochee_est_refusee(self):
        demande = [c for c in OBLIGATOIRES if c != 'production']
        with self.assertRaises(ValidationError):
            enregistrer_parametres(self.company, {
                'documents': {CODE_RAPPORT_ETUDE: {'sections': demande}}})

    def test_une_selection_valide_est_enregistree(self):
        enregistrer_parametres(self.company, {
            'documents': {CODE_RAPPORT_ETUDE: {'sections': OBLIGATOIRES}}})
        reglages = ParametresCalepinage.objects.get(company=self.company)
        self.assertEqual(
            reglages.documents[CODE_RAPPORT_ETUDE]['sections'], OBLIGATOIRES)

    def test_reglage_absent_ne_change_rien_a_une_societe_existante(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        reglages = ParametresCalepinage.objects.get(company=self.company)
        self.assertEqual(reglages.documents, {})
        self.assertIsNone(sections_retenues(reglages))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
