"""CAL192 — le pack de raccordement autoproduction (Maroc).

Le « Done » : « le pack se produit et se fusionne en GED ; en l'absence de
gabarit société, un message FR explique quoi déposer (jamais un gabarit
inventé) ».

Tests PURS : la GED est passée en DOUBLURE (le service l'importe en
FONCTION-LOCAL) et les rendus sont de VRAIS PDF construits par PyMuPDF
(ACAL236 : la fusion est faite localement, pages contrôlées), donc aucun
Postgres, aucun MinIO, aucun WeasyPrint n'est nécessaire. Le dépôt GED RÉEL
est prouvé en base par ``test_acal_depot_ged_dossiers``.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

try:
    import fitz
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None

from apps.calepinage.services.reglementaire import (
    CABINET_GED,
    DOSSIER_GED,
    PIECES_PRODUITES,
    DossierRefuse,
    construire_pack_dossier,
)


class _Faux:
    """Un objet nu qui porte les attributs qu'on lui donne."""

    def __init__(self, **attributs):
        self.__dict__.update(attributs)

    def __str__(self):
        return self.__dict__.get('nom', 'objet')


def _dossier(*, fichier_present=True):
    company = _Faux(pk=1, nom="Taqinor SARL")
    calepinage = _Faux(pk=7, company=company, layout_hash='a' * 64,
                       devis_id=None, nom='Calepinage 7')
    gabarit = _Faux(pk=3, intitule='Dossier de raccordement (gabarit déposé)',
                    fichier_present=fichier_present)
    return _Faux(pk=11, calepinage=calepinage, company=company,
                 gabarit=gabarit)


def _pdf(pages=1):
    """Un VRAI PDF de ``pages`` pages (PyMuPDF) — jamais un octet inventé."""
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    octets = document.tobytes()
    document.close()
    return octets


EMPREINTE = 'e' * 64


def _ged_double(journal):
    """Un faux ``apps.ged.services`` : enregistre, ne stocke rien.

    ACAL236 — l'appelant cherche d'abord le dossier par son ancre, puis le
    dépose UNE fois (fusionné localement)."""

    def find_document_by_source(company, **kwargs):
        journal.setdefault('recherches', []).append(kwargs)
        return None

    def deposit_document(**kwargs):
        journal.setdefault('deposes', []).append(kwargs)
        return _Faux(pk=99, nom=kwargs['nom']), True

    def _jamais(*_args, **_kwargs):  # pragma: no cover - premier dépôt
        raise AssertionError('premier dépôt : aucune version ajoutée')

    module = types.ModuleType('apps.ged.services')
    module.find_document_by_source = find_document_by_source
    module.deposit_document = deposit_document
    module.selectors_latest_version = _jamais
    module.assert_not_archive_legalement = _jamais
    module.add_version = _jamais
    module.compute_checksum = _jamais
    return module


@unittest.skipIf(fitz is None, 'PyMuPDF absent de cet environnement')
class PackMarocTest(unittest.TestCase):

    def setUp(self):
        self.journal = {}
        self.patch = mock.patch.dict(
            sys.modules, {'apps.ged.services': _ged_double(self.journal)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.rendus = {
            'planche': lambda: _pdf(1),
            'note_calcul': lambda: _pdf(2),
            'schema_unifilaire': lambda: _pdf(1),
        }

    def _construire(self, rendus=None):
        return construire_pack_dossier(
            _dossier(), rendus=rendus if rendus is not None else self.rendus,
            empreinte=EMPREINTE)

    def test_pack_produit_et_fusionne(self):
        resultat = self._construire()
        codes = [code for code, _libelle in resultat['pieces']]
        self.assertEqual(codes, [code for code, _l, _o in PIECES_PRODUITES])
        self.assertEqual(resultat['document'].pk, 99)
        self.assertEqual(resultat['signalements'], [])
        # UN dépôt : les trois pièces fusionnées localement (1 + 2 + 1 pages).
        self.assertEqual(len(self.journal['deposes']), 1)
        fusionne = fitz.open(stream=self.journal['deposes'][0]['contenu_bytes'],
                             filetype='pdf')
        try:
            self.assertEqual(fusionne.page_count, 4)
        finally:
            fusionne.close()

    def test_pieces_rangees_dans_leur_cabinet_ged(self):
        self._construire()
        for depose in self.journal['deposes']:
            self.assertEqual(depose['cabinet_nom'], CABINET_GED)
            self.assertEqual(depose['folder_nom'], DOSSIER_GED)
            self.assertEqual(depose['mime'], 'application/pdf')

    def test_idempotence_ancree_sur_l_empreinte_des_entrees(self):
        # ACAL236 — ancre STABLE par dossier ; l'empreinte des ENTRÉES (pas
        # layout_hash) nomme la version déposée.
        self._construire()
        for depose in self.journal['deposes']:
            self.assertEqual(depose['source_id'], '11:dossier_reglementaire')
            self.assertIn('e' * 16, depose['filename'])
            self.assertNotIn('a' * 12, depose['filename'])

    def test_piece_facultative_absente_est_signalee_jamais_sautee(self):
        rendus = dict(self.rendus)

        def _absent():
            raise DossierRefuse("aucun schéma unifilaire n'est disponible")

        rendus['schema_unifilaire'] = _absent
        resultat = self._construire(rendus)
        self.assertEqual(len(resultat['pieces']), len(PIECES_PRODUITES) - 1)
        self.assertEqual(len(resultat['signalements']), 1)
        self.assertIn('Schéma unifilaire', resultat['signalements'][0])

    def test_piece_obligatoire_qui_ne_se_rend_pas_refuse_le_pack(self):
        rendus = dict(self.rendus)
        rendus['note_calcul'] = lambda: b''
        with self.assertRaises(DossierRefuse) as capture:
            self._construire(rendus)
        self.assertEqual(capture.exception.piece, 'note_calcul')
        self.assertIn('Note de calcul', str(capture.exception))


class GabaritManquantTest(unittest.TestCase):

    def test_sans_fichier_de_gabarit_le_pack_refuse_et_dit_quoi_deposer(self):
        with self.assertRaises(DossierRefuse) as capture:
            construire_pack_dossier(_dossier(fichier_present=False))
        message = str(capture.exception)
        self.assertEqual(capture.exception.piece, 'gabarit')
        self.assertIn('déposez le document fourni par l', message.lower())
        self.assertIn("qu'il n'a pas reçu", message)

    def test_sans_societe_le_pack_refuse(self):
        dossier = _dossier()
        dossier.company = None
        dossier.calepinage.company = None
        with self.assertRaises(DossierRefuse) as capture:
            construire_pack_dossier(dossier)
        self.assertEqual(capture.exception.piece, 'company')
