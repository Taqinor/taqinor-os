"""CAL192 — le pack de raccordement autoproduction (Maroc).

Le « Done » : « le pack se produit et se fusionne en GED ; en l'absence de
gabarit société, un message FR explique quoi déposer (jamais un gabarit
inventé) ».

Tests PURS : la GED et les rendus PDF sont passés en DOUBLURES (le service les
importe en FONCTION-LOCAL et accepte ses rendus par argument), donc aucun
Postgres, aucun MinIO, aucun WeasyPrint n'est nécessaire — et ce qui est
mesuré est la RÈGLE, pas la plomberie déjà éprouvée d'XGED10.
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

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


def _ged_double(journal):
    """Un faux ``apps.ged.services`` : enregistre, ne stocke rien."""

    def deposit_document(**kwargs):
        journal.setdefault('deposes', []).append(kwargs)
        return _Faux(pk=len(journal['deposes']), nom=kwargs['nom']), True

    def fusionner_pdf(documents, **kwargs):
        journal['fusion'] = {'documents': list(documents), **kwargs}
        return _Faux(pk=99, nom=kwargs.get('nom', ''))

    module = types.ModuleType('apps.ged.services')
    module.deposit_document = deposit_document
    module.fusionner_pdf = fusionner_pdf
    return module


class PackMarocTest(unittest.TestCase):

    def setUp(self):
        self.journal = {}
        self.patch = mock.patch.dict(
            sys.modules, {'apps.ged.services': _ged_double(self.journal)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.rendus = {
            'planche': lambda: b'%PDF-planche',
            'note_calcul': lambda: b'%PDF-note',
            'schema_unifilaire': lambda: b'%PDF-schema',
        }

    def test_pack_produit_et_fusionne(self):
        resultat = construire_pack_dossier(_dossier(), rendus=self.rendus)
        codes = [code for code, _libelle in resultat['pieces']]
        self.assertEqual(codes, [code for code, _l, _o in PIECES_PRODUITES])
        self.assertEqual(resultat['document'].pk, 99)
        self.assertEqual(resultat['signalements'], [])
        self.assertEqual(len(self.journal['fusion']['documents']), len(codes))

    def test_pieces_rangees_dans_leur_cabinet_ged(self):
        construire_pack_dossier(_dossier(), rendus=self.rendus)
        for depose in self.journal['deposes']:
            self.assertEqual(depose['cabinet_nom'], CABINET_GED)
            self.assertEqual(depose['folder_nom'], DOSSIER_GED)
            self.assertEqual(depose['mime'], 'application/pdf')

    def test_idempotence_ancree_sur_l_empreinte_du_layout(self):
        construire_pack_dossier(_dossier(), rendus=self.rendus)
        for depose in self.journal['deposes']:
            self.assertIn('11:', depose['source_id'])
            self.assertIn('a' * 12, depose['source_id'])

    def test_piece_facultative_absente_est_signalee_jamais_sautee(self):
        rendus = dict(self.rendus)

        def _absent():
            raise DossierRefuse("aucun schéma unifilaire n'est disponible")

        rendus['schema_unifilaire'] = _absent
        resultat = construire_pack_dossier(_dossier(), rendus=rendus)
        self.assertEqual(len(resultat['pieces']), len(PIECES_PRODUITES) - 1)
        self.assertEqual(len(resultat['signalements']), 1)
        self.assertIn('Schéma unifilaire', resultat['signalements'][0])

    def test_piece_obligatoire_qui_ne_se_rend_pas_refuse_le_pack(self):
        rendus = dict(self.rendus)
        rendus['note_calcul'] = lambda: b''
        with self.assertRaises(DossierRefuse) as capture:
            construire_pack_dossier(_dossier(), rendus=rendus)
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
