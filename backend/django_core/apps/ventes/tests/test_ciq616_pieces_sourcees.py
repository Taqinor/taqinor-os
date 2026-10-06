"""CIQ616 — pièces du dossier 82-21 tirées du décret 2.25.100, par étape et
avec leur source ; « distributeur » au lieu d'« ONEE » ; l'ANRE n'est plus un
guichet ; code ``a_qualifier`` aligné sur le chantier.

Calcul PUR + métadonnées de modèle (SimpleTestCase, aucun accès base).
"""
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.ventes import regulatory_docs as rd
from apps.ventes.models import DossierChecklistItem, RegulatoryDossier

_CONTRAT = (Path(__file__).resolve().parent.parent
            / 'contract_samples' / 'dossier_8221.json')

_REGIMES_DEPOSABLES = ('declaration_bt', 'accord_raccordement',
                       'autorisation_anre')


def _codes(regime):
    return {p['code'] for p in rd.required_documents(regime)}


class PiecesSourceesTest(SimpleTestCase):
    def test_assurance_exigee_pour_l_accord_art_15(self):
        pieces = {p['code']: p
                  for p in rd.required_documents('accord_raccordement')}
        assurance = pieces['attestation_assurance']
        self.assertEqual(assurance['etape'], 'exploitation')
        self.assertIn('art. 15', assurance['source'])
        self.assertIn('certificat_organisme_agree', pieces)
        self.assertIn('preuve_propriete', pieces)

    def test_declaration_n_exige_pas_l_assurance(self):
        codes = _codes('declaration_bt')
        self.assertNotIn('attestation_assurance', codes)
        self.assertNotIn('certificat_organisme_agree', codes)

    def test_chaque_piece_a_une_source_et_une_etape_valide(self):
        etapes = set(DossierChecklistItem.Etape.values)
        for regime in rd.KNOWN_REGIMES + ('inconnu_xyz',):
            for piece in rd.required_documents(regime):
                self.assertTrue(piece['source'].strip(),
                                f"{regime}:{piece['code']} sans source")
                self.assertIn(piece['etape'], etapes,
                              f"{regime}:{piece['code']} étape inconnue")

    def test_aucun_libelle_anre_ni_onee_seul(self):
        libelles = [rd.regime_label(r) for r in rd.KNOWN_REGIMES]
        for regime in rd.KNOWN_REGIMES:
            libelles += [p['label'] for p in rd.required_documents(regime)]
        libelles += [label for _, label in
                     RegulatoryDossier._meta.get_field('regime_8221').choices]
        for libelle in libelles:
            self.assertNotIn('ANRE', libelle)
            if 'ONEE' in libelle:
                self.assertIn('SRM', libelle, libelle)

    def test_distributeur_onee_ou_srm(self):
        piece = next(p for p in rd.required_documents('accord_raccordement')
                     if p['code'] == 'contrat_onee')
        self.assertEqual(
            piece['label'],
            "Contrat / référence du distributeur (ONEE ou SRM régionale)")

    def test_pieces_du_decret_par_article(self):
        pieces = {p['code']: p
                  for p in rd.required_documents('accord_raccordement')}
        for code in ('cni_client', 'titre_droit_usage',
                     'engagement_non_cession'):
            self.assertIn('art. 1', pieces[code]['source'])
        for code in ('schema_unifilaire', 'plan_situation', 'coordonnees_gps',
                     'fiches_techniques', 'planning_travaux', 'conso_3_ans'):
            self.assertIn('art. 12', pieces[code]['source'])
        self.assertFalse(pieces['etude_impact']['obligatoire'])
        self.assertIn('à confirmer', pieces['etude_impact']['source'])
        self.assertEqual(pieces['etude_raccordement']['etape'], 'etude')
        self.assertIn('art. 27', pieces['reglages_etude']['source'])
        self.assertIn('art. 26', pieces['autres_autorisations']['source'])

    def test_aucune_piece_mt_de_decouplage(self):
        for regime in rd.KNOWN_REGIMES:
            for piece in rd.required_documents(regime):
                self.assertNotIn('decouplage', piece['code'])


class ACQualifierTest(SimpleTestCase):
    def test_a_qualifier_sans_piece_avec_motif(self):
        self.assertEqual(rd.required_documents('a_qualifier'), [])
        pack = rd.document_pack('a_qualifier')
        self.assertEqual(pack['regime_label'], "À qualifier")
        self.assertIn('à qualifier', pack['motif_pieces'].lower())

    def test_a_qualifier_choix_valide_du_dossier(self):
        champ = RegulatoryDossier._meta.get_field('regime_8221')
        self.assertIn('a_qualifier', dict(champ.choices))
        champ.clean('a_qualifier', None)  # ne lève pas
        with self.assertRaises(ValidationError):
            champ.clean('regime_invente', None)

    def test_etape_exploitation(self):
        self.assertIn('exploitation', DossierChecklistItem.Etape.values)


class ContratDossier8221Test(SimpleTestCase):
    """Sortie ``pieces`` conforme au contrat partagé ``dossier_8221.json``."""

    def test_cles_des_pieces_conformes(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        cles = set(contrat['exemple']['pieces'][0])
        for regime in _REGIMES_DEPOSABLES:
            for piece in rd.required_documents(regime):
                self.assertTrue(cles <= set(piece),
                                f"{regime}:{piece['code']} {set(piece)}")

    def test_etapes_du_contrat_connues(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        etapes = set(DossierChecklistItem.Etape.values)
        for exemple in ('exemple', 'exemple_mt'):
            for piece in contrat[exemple]['pieces']:
                self.assertIn(piece['etape'], etapes)
