"""CAL192 — le pack de raccordement autoproduction (Maroc).

Le « Done » : « le pack se produit et se fusionne ; en l'absence de gabarit
société, un message FR explique quoi déposer (jamais un gabarit inventé) ».

Tests PURS : le DÉPÔT et les rendus PDF sont passés en DOUBLURES (le service
importe le dépôt en FONCTION-LOCAL et accepte ses rendus par argument), donc
aucun Postgres, aucun MinIO, aucun WeasyPrint n'est nécessaire — et ce qui est
mesuré est la RÈGLE, pas la plomberie déjà éprouvée.

SOLMVP15 — le dépôt et la fusion étaient ceux de la GED, qui sort du produit ;
ils sont ceux du module (``services/depot_pdf.py``). Ce qui est prouvé ici est
inchangé, y compris l'ancre d'idempotence.
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


def _depot_double(journal):
    """Un faux ``services.depot_pdf`` : enregistre, ne stocke rien."""

    def deposer_pdf(cible, octets, **kwargs):
        journal.setdefault('deposes', []).append(
            dict(kwargs, cible=cible, octets=octets))
        return _Faux(pk=len(journal['deposes']),
                     nom=kwargs['filename']), True

    def fusionner_pdf(parties):
        journal['fusion'] = {'parties': list(parties)}
        return b'%PDF-pack'

    class DepotRefuse(ValueError):
        pass

    module = types.ModuleType('apps.calepinage.services.depot_pdf')
    module.deposer_pdf = deposer_pdf
    module.fusionner_pdf = fusionner_pdf
    module.DepotRefuse = DepotRefuse
    return module


class PackMarocTest(unittest.TestCase):

    def setUp(self):
        self.journal = {}
        self.patch = mock.patch.dict(
            sys.modules,
            {'apps.calepinage.services.depot_pdf':
             _depot_double(self.journal)})
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
        # Le pack est la DERNIÈRE pièce déposée (les pièces, puis le pack).
        self.assertEqual(resultat['document'].pk,
                         len(self.journal['deposes']))
        self.assertEqual(resultat['signalements'], [])
        self.assertEqual(len(self.journal['fusion']['parties']), len(codes))

    def test_le_pack_garde_son_nom_de_rangement(self):
        """Les deux libellés de rangement restent PUBLIÉS : la recette de
        retour du référentiel documentaire (PHASE 2) en a besoin."""
        self.assertEqual(CABINET_GED, 'Calepinage')
        self.assertEqual(DOSSIER_GED, 'Dossiers réglementaires')
        construire_pack_dossier(_dossier(), rendus=self.rendus)
        for depose in self.journal['deposes']:
            self.assertTrue(depose['filename'].endswith('.pdf'))

    def test_idempotence_ancree_sur_l_empreinte_du_layout(self):
        construire_pack_dossier(_dossier(), rendus=self.rendus)
        for depose in self.journal['deposes']:
            self.assertIn('dossier-11-', depose['filename'])
            self.assertIn('a' * 12, depose['filename'])

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
