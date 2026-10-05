# -*- coding: utf-8 -*-
"""ACAL163 — la pièce « schéma unifilaire » du dossier réglementaire et le
bloc du rapport sont produits par le schéma NATIF du calepinage.

LE CONSTAT (C-ACAL-061)
-----------------------
``reglementaire._rendus_du_module._schema`` et
``rapport/electrique.py::bloc_schema_unifilaire`` lisaient
``schema_unifilaire_svg(devis=…)`` : sans devis lié, la pièce refusait (« il
se produit depuis le devis lié ») ; avec un devis, l'édition du schéma faite
dans l'atelier (``sld_edition``) n'était jamais imprimée. Désormais UNE
fonction (``bloc_schema_unifilaire``) lit ``sld.schema_du_calepinage`` —
conception réelle, édition appliquée — et le dossier l'appelle.

Aucune doublure : Produit et FicheTechnique créés en base, entrée posée par
``enregistrer_entree`` (patron ``BaseConceptionReelle``, ACAL55). Les essais
qui rendent un PDF (WeasyPrint + PyMuPDF réels) portent ``@tag('pdf')``.
"""
from __future__ import annotations

import unittest

from django.test import tag

from apps.calepinage.models import Calepinage
from apps.calepinage.services.rapport.electrique import (
    MOTIF_SCHEMA_INDISPONIBLE, bloc_schema_unifilaire,
)
from apps.calepinage.services.reglementaire import (
    DossierRefuse, _rendus_du_module,
)
from apps.calepinage.services.sld import (
    enregistrer_edition_sld, schema_du_calepinage,
)
from apps.ventes.models import Devis

from .test_acal_sld_conception_reelle import BaseConceptionReelle

LIBELLE_EDITE = 'Champ PV toiture sud ACAL163'


def _textes_pdf(octets):
    import fitz

    document = fitz.open(stream=octets, filetype='pdf')
    try:
        return ''.join(page.get_text() for page in document)
    finally:
        document.close()


def _piece_schema(calepinage):
    return _rendus_du_module(calepinage, calepinage.company)[
        'schema_unifilaire']()


class SchemaIndisponible(BaseConceptionReelle):
    """``svg`` None : le signalement reprend bloquants/manquantes."""

    def test_svg_none_signale_bloquants(self):
        # Aucun matériel désigné ; sans épingle, aucun appel météo.
        sans_epingle = {cle: valeur for cle, valeur
                        in self.calepinage.roof_layout.items() if cle != 'pin'}
        muet = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans matériel',
            roof_layout=sans_epingle)
        schema = schema_du_calepinage(muet)
        self.assertIsNone(schema['svg'])
        raisons = list(schema['bloquants']) + list(schema['manquantes'])
        self.assertTrue(raisons)
        with self.assertRaises(DossierRefuse) as refus:
            _piece_schema(muet)
        self.assertEqual(refus.exception.piece, 'schema_unifilaire')
        message = str(refus.exception)
        self.assertTrue(message.startswith(MOTIF_SCHEMA_INDISPONIBLE[:-1]))
        for raison in raisons:
            self.assertIn(str(raison), message)
        # Le rapport lit la MÊME phrase (une seule fonction la compose).
        octets, motif = bloc_schema_unifilaire(muet)
        self.assertIsNone(octets)
        self.assertEqual(motif, message)
        self.assertNotIn('devis lié', message)


@tag('pdf')
class SchemaDuDossier(BaseConceptionReelle):

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 - bibliothèques natives absentes
            raise unittest.SkipTest('WeasyPrint ou PyMuPDF indisponible')
        super().setUp()
        self._norme_francaise()

    def test_sans_devis_la_piece_est_rendue(self):
        self.assertIsNone(self.calepinage.devis_id)
        premier = _piece_schema(self.calepinage)
        self.assertTrue(premier.startswith(b'%PDF'))
        # Aucune écriture : deux générations ⇒ même schéma imprimé.
        second = _piece_schema(self.calepinage)
        self.assertEqual(_textes_pdf(premier), _textes_pdf(second))

    def test_libelle_edite_present(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL163-1')
        self.calepinage.devis = devis
        self.calepinage.save()
        enregistrer_edition_sld(self.calepinage,
                                {'libelles': {'champ': LIBELLE_EDITE}})
        self.calepinage.refresh_from_db()
        texte = _textes_pdf(_piece_schema(self.calepinage))
        self.assertIn(LIBELLE_EDITE, texte)

    def test_rapport_bloc_schema_natif(self):
        octets, motif = bloc_schema_unifilaire(self.calepinage)
        self.assertIsNone(motif)
        self.assertEqual(_textes_pdf(octets),
                         _textes_pdf(_piece_schema(self.calepinage)))
