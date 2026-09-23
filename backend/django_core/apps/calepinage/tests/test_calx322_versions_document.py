"""CALX322 — versionner les documents produits.

Ce qui est prouvé ici (essais PURS où c'est possible ; le reste EN BASE,
CI validera) :

* le NUMÉRO encodé dans un nom de fichier se relit exactement (essai pur) ;
* ``prochain_numero`` sur un calepinage non enregistré vaut ``1`` (essai
  pur, aucune base) ;
* ``enregistrer_version_document``/``versions_du_document`` refusent en
  NOMMANT le champ pour un calepinage non enregistré, un code manquant, un
  document vide — SANS toucher la base (essais purs) ;
* en base (CI) : deux téléchargements du rapport d'étude produisent les
  versions 1 puis 2 (jamais un ``count()+1``) ; une version porte
  l'empreinte du document qui l'a produite (son ``numero``/nom encodent le
  document exact) ; un calepinage d'une autre société ne voit AUCUNE
  version ; la taille stockée est non nulle ; ``GET …/documents/`` publie
  ces mêmes versions dans ``documents[].versions[]`` (CALX321).

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx322_versions_document.py -q
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.documents.versions_document import (
    VersionDocumentRefuse, _nom_fichier_version, _numero_depuis_nom,
    enregistrer_version_document, prochain_numero, versions_du_document,
)


class NomFichierEtNumeroTest(unittest.TestCase):
    """Le numéro encodé se relit exactement — essai PUR."""

    def test_le_numero_encode_se_relit(self):
        nom = _nom_fichier_version('rapport_etude', 7, 'fr', 'pdf')
        self.assertEqual(_numero_depuis_nom(nom), 7)

    def test_numero_zero_pour_un_nom_etranger_au_schema(self):
        self.assertEqual(_numero_depuis_nom('photo-toit-1234.jpg'), 0)

    def test_langue_assainie_dans_le_nom(self):
        nom = _nom_fichier_version('rapport_etude', 1, 'FR ', 'pdf')
        self.assertIn('__v001__fr.pdf', nom)


class CalepinageNonEnregistreTest(unittest.TestCase):
    """Aucun accès base tant que le calepinage n'a pas de ``pk`` réel —
    essais PURS."""

    class FauxNonEnregistre:
        pk = None
        company = None

    def test_prochain_numero_vaut_un(self):
        self.assertEqual(
            prochain_numero(self.FauxNonEnregistre(), 'rapport_etude'), 1)

    def test_versions_du_document_est_vide(self):
        self.assertEqual(
            versions_du_document(self.FauxNonEnregistre(), 'rapport_etude'),
            [])

    def test_enregistrer_refuse_en_nommant_calepinage(self):
        with self.assertRaises(VersionDocumentRefuse) as cm:
            enregistrer_version_document(
                self.FauxNonEnregistre(), code='rapport_etude',
                octets=b'%PDF-1.4 ...')
        self.assertEqual(cm.exception.champ, 'calepinage')

    def test_enregistrer_refuse_sur_calepinage_none(self):
        with self.assertRaises(VersionDocumentRefuse) as cm:
            enregistrer_version_document(None, code='rapport_etude',
                                         octets=b'%PDF-1.4 ...')
        self.assertEqual(cm.exception.champ, 'calepinage')


class RefusValidationTest(unittest.TestCase):
    """Code manquant / document vide — refusés AVANT tout accès base
    (essais PURS : la validation précède la résolution du ContentType)."""

    class FauxEnregistre:
        pk = 5
        company = None

    def test_code_manquant_est_refuse(self):
        with self.assertRaises(VersionDocumentRefuse) as cm:
            enregistrer_version_document(
                self.FauxEnregistre(), code='', octets=b'%PDF-1.4 ...')
        self.assertEqual(cm.exception.champ, 'code')

    def test_octets_vides_sont_refuses(self):
        with self.assertRaises(VersionDocumentRefuse) as cm:
            enregistrer_version_document(
                self.FauxEnregistre(), code='rapport_etude', octets=b'')
        self.assertEqual(cm.exception.champ, 'octets')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════
# EN BASE (CI) — deux versions, empreinte, société, taille
# ═══════════════════════════════════════════════════════════════════════
#
# Écrit ici mais NON EXÉCUTÉ localement (pas de MinIO/Postgres sur ce poste
# de lane, et ``store_attachment`` exige les deux) : la CI valide.

import copy  # noqa: E402 - après les essais purs
from unittest import mock  # noqa: E402

from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.records.models import Attachment  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402
from .test_cal171_planche import LAYOUT  # noqa: E402
from .test_calx308_diagramme_pertes_svg import RESULTAT  # noqa: E402

#: Un « PDF » RÉEL au sens des octets magiques (``store_attachment`` refuse
#: tout le reste) — le contenu lui-même n'est jamais inspecté au-delà.
_OCTETS_PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\n%%EOF'


class VersionnementEnBaseTest(BaseApiCalepinage):
    """Deux téléchargements du rapport d'étude → versions 1 puis 2 (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=copy.deepcopy(LAYOUT), layout_hash='a' * 64,
            resultat=copy.deepcopy(RESULTAT))
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Voisine',
            roof_layout=copy.deepcopy(LAYOUT),
            resultat=copy.deepcopy(RESULTAT))

    def _telecharger(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=copy.deepcopy(RESULTAT)):
            return self.api.get(
                f'{url_detail(self.calepinage.pk)}rapport-etude.pdf/')

    def test_deux_telechargements_produisent_les_versions_1_puis_2(self):
        self.assertEqual(self._telecharger().status_code, 200)
        self.assertEqual(self._telecharger().status_code, 200)
        versions = versions_du_document(self.calepinage, 'rapport_etude')
        self.assertEqual([v['numero'] for v in versions], [2, 1])

    def test_une_version_porte_l_empreinte_du_document(self):
        self.assertEqual(self._telecharger().status_code, 200)
        piece = Attachment.objects.get(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk)
        self.assertTrue(piece.filename.startswith('rapport_etude__v001__'))

    def test_taille_stockee_non_nulle(self):
        self.assertEqual(self._telecharger().status_code, 200)
        piece = Attachment.objects.get(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk)
        self.assertGreater(piece.size, 0)

    def test_une_autre_societe_ne_voit_aucune_version(self):
        self.assertEqual(self._telecharger().status_code, 200)
        self.assertEqual(
            versions_du_document(self.etranger, 'rapport_etude'), [])

    def test_l_inventaire_documents_publie_la_version(self):
        self.assertEqual(self._telecharger().status_code, 200)
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=copy.deepcopy(RESULTAT)):
            reponse = self.api.get(
                f'{url_detail(self.calepinage.pk)}documents/')
        rapport = next(d for d in reponse.data['documents']
                       if d['code'] == 'rapport_etude')
        self.assertEqual(len(rapport['versions']), 1)
        self.assertEqual(rapport['versions'][0]['numero'], 1)
