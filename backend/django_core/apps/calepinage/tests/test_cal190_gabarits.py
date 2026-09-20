"""CAL190 — le gabarit de dossier réglementaire : AUCUNE pièce inventée.

Ce qui est prouvé ici, sans base de données (``SimpleTestCase`` : les refus
vivent dans ``clean()``, et la migration est relue comme un fichier) :

* une pièce SANS sa source (référence CERFA, notice Consuel, documentation
  Enedis, texte marocain…) est REFUSÉE en la nommant — c'est la garantie
  « aucune liste de pièces reproduite de mémoire » ;
* un gabarit sans intitulé, un pays mal écrit, un type de champ inconnu, un
  préremplissage inconnu sont refusés EN FRANÇAIS, en NOMMANT le champ ;
* un gabarit DÉCLARÉ mais dont le FICHIER n'a pas été déposé reste un objet
  valide : c'est le fichier qui manque, pas le dossier (contrat CAL247) ;
* la migration est ADDITIVE et SANS DONNÉE : aucune ``RunPython``, donc aucun
  gabarit fictif en base — une société sans gabarit déposé ne voit aucun
  dossier proposé.
"""
from __future__ import annotations

import pathlib

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.calepinage.models import (
    DossierReglementaire,
    GabaritDossierReglementaire,
)

PIECE = {
    'code': 'plan_masse',
    'intitule': 'Plan de masse — intitulé porté par le gabarit déposé',
    'obligatoire': True,
    'source_reference': 'Référence saisie par la société avec son gabarit',
}
CHAMP = {
    'code': 'reference_dossier',
    'libelle': 'Référence du dossier',
    'type': 'texte',
    'obligatoire': True,
}


def _gabarit(**surcharges):
    donnees = {
        'pays': 'ma',
        'code': 'raccordement-bt',
        'intitule': 'Dossier de raccordement — intitulé du gabarit déposé',
        'pieces_attendues': [dict(PIECE)],
        'champs': [dict(CHAMP)],
    }
    donnees.update(surcharges)
    return GabaritDossierReglementaire(**donnees)


class GabaritValideTest(SimpleTestCase):

    def test_gabarit_complet_accepte(self):
        _gabarit().clean()  # ne lève pas

    def test_pays_normalise_en_minuscules(self):
        gabarit = _gabarit(pays='FR')
        gabarit.clean()
        self.assertEqual(gabarit.pays, 'fr')

    def test_gabarit_sans_fichier_reste_valide_mais_dit_qu_il_manque(self):
        gabarit = _gabarit()
        gabarit.clean()
        self.assertFalse(gabarit.fichier_present)


class GabaritRefuseTest(SimpleTestCase):

    def _refus(self, **surcharges):
        with self.assertRaises(ValidationError) as capture:
            _gabarit(**surcharges).clean()
        return capture.exception.message_dict

    def test_piece_sans_source_refusee(self):
        piece = dict(PIECE)
        piece.pop('source_reference')
        erreurs = self._refus(pieces_attendues=[piece])
        self.assertIn('pieces_attendues', erreurs)
        message = erreurs['pieces_attendues'][0]
        self.assertIn('plan_masse', message)
        self.assertIn('SOURCE', message)
        self.assertIn('de mémoire', message)

    def test_piece_sans_intitule_refusee(self):
        piece = dict(PIECE, intitule='')
        self.assertIn('pieces_attendues',
                      self._refus(pieces_attendues=[piece]))

    def test_deux_pieces_de_meme_code_refusees(self):
        erreurs = self._refus(pieces_attendues=[dict(PIECE), dict(PIECE)])
        self.assertIn('même code', erreurs['pieces_attendues'][0])

    def test_pieces_en_objet_refusees(self):
        self.assertIn('pieces_attendues',
                      self._refus(pieces_attendues={'a': 1}))

    def test_pays_invalide_refuse(self):
        erreurs = self._refus(pays='maroc')
        self.assertIn('pays', erreurs)
        self.assertIn('ISO 3166-1', erreurs['pays'][0])

    def test_intitule_obligatoire(self):
        erreurs = self._refus(intitule='   ')
        self.assertIn('intitule', erreurs)

    def test_type_de_champ_inconnu_refuse(self):
        champ = dict(CHAMP, type='signature')
        erreurs = self._refus(champs=[champ])
        self.assertIn('signature', erreurs['champs'][0])

    def test_preremplissage_inconnu_refuse(self):
        champ = dict(CHAMP, cle_calepinage='marge_commerciale')
        erreurs = self._refus(champs=[champ])
        self.assertIn('marge_commerciale', erreurs['champs'][0])

    def test_preremplissage_connu_accepte(self):
        champ = dict(CHAMP, cle_calepinage='puissance_kwc')
        _gabarit(champs=[champ]).clean()


class DossierReglementaireTest(SimpleTestCase):

    def test_champs_saisis_en_liste_refuses(self):
        dossier = DossierReglementaire(champs_saisis=[], pieces_jointes={})
        with self.assertRaises(ValidationError) as capture:
            dossier.clean()
        self.assertIn('champs_saisis', capture.exception.message_dict)

    def test_unicite_par_calepinage_et_gabarit(self):
        noms = {c.name for c in DossierReglementaire._meta.constraints}
        self.assertIn('uniq_dossier_reglementaire_par_gabarit', noms)

    def test_unicite_du_gabarit_par_societe_et_pays(self):
        noms = {c.name
                for c in GabaritDossierReglementaire._meta.constraints}
        self.assertIn('uniq_gabarit_dossier_par_societe_pays', noms)


class MigrationSansDonneeTest(SimpleTestCase):
    """Pas de gabarit fictif en base : la migration ne CRÉE aucune donnée."""

    def test_migration_additive_et_vide(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'migrations' / '0008_cal190_dossiers_reglementaires.py')
        source = chemin.read_text(encoding='utf-8')
        self.assertNotIn('RunPython', source)
        self.assertNotIn('RunSQL', source)
        self.assertIn('CreateModel', source)
