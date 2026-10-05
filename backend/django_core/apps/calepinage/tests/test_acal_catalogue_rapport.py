# -*- coding: utf-8 -*-
"""ACAL288 — le catalogue des sections du rapport d'étude, servi par
``GET parametres/`` (clé dérivée ``documents.catalogue_rapport``), et la
sélection de la société APPLIQUÉE au rapport.

LE CONSTAT (C-ACAL-145)
-----------------------
L'écran n'avait aucune source pour savoir quelles sections cocher ; le PUT
d'une section obligatoire décochée sortait en 500 (``ValidationError`` de
``full_clean`` non attrapée) ; et ``GET rapport-etude.pdf`` passait le dict
de ``parametres_de_societe`` à ``sections_retenues``, qui ne lisait qu'un
ATTRIBUT ``documents`` : la sélection n'était JAMAIS appliquée.

Route HTTP réelle, ORM réel ; le rapport est construit par l'assembleur réel
avec EXACTEMENT ce que la vue du PDF lui passe.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import parametres_de_societe
from apps.calepinage.services.parametres_cles import CODE_RAPPORT_ETUDE
from apps.calepinage.services.rapport import construire_rapport, html_de_rapport
from apps.calepinage.services.rapport.sections_societe import (
    sections_retenues,
)

from .test_api_liste import BaseApiCalepinage
from .test_calx307_sections_societe import (
    FACULTATIVES, IDENTITE, NU, OBLIGATOIRES, RESULTAT, SITE, STYLES,
)

URL = '/api/django/calepinage/parametres/'
ECHANTILLONS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'


def _echantillon(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


class CatalogueRapportTest(BaseApiCalepinage):

    def _put(self, corps):
        return self.api.put(URL, corps, format='json')

    def test_get_parametres_sert_le_catalogue_dans_l_ordre_du_contrat(self):
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        catalogue = reponse.data['documents']['catalogue_rapport']
        sections = sorted(_echantillon('rapport_etude.json')['exemple']
                          ['sections'], key=lambda s: s['ordre'])
        self.assertEqual(catalogue, [
            {'code': s['code'], 'titre': s['titre'],
             'obligatoire': s['obligatoire']} for s in sections])
        forme = _echantillon('parametres_calepinage.json')['exemple']
        self.assertEqual(sorted(catalogue[0]),
                         sorted(forme['documents']['catalogue_rapport'][0]))
        # Jamais stockée : la lecture n'écrit rien.
        self.assertFalse(ParametresCalepinage.objects
                         .filter(company=self.company).exists())

    def test_put_refuse_le_retrait_d_une_section_obligatoire_en_nommant_le_champ(self):
        demande = [code for code in OBLIGATOIRES if code != 'production']
        reponse = self._put({'documents': {
            CODE_RAPPORT_ETUDE: {'sections': demande}}})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('production', reponse.data['documents'])
        self.assertIsNone(sections_retenues(
            parametres_de_societe(self.company)))

        derivee = self._put({'documents': {'catalogue_rapport': []}})
        self.assertEqual(derivee.status_code, 400, derivee.data)
        attendu = _echantillon('parametres_calepinage.json')[
            'exemple_refus_catalogue_rapport']
        self.assertEqual(derivee.data['documents'], attendu['documents'])

    def test_selection_appliquee_au_rapport(self):
        reponse = self._put({'documents': {
            CODE_RAPPORT_ETUDE: {'sections': OBLIGATOIRES}}})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        relu = self.api.get(URL).data['documents']
        self.assertEqual(relu[CODE_RAPPORT_ETUDE]['sections'], OBLIGATOIRES)

        # EXACTEMENT ce que GET rapport-etude.pdf passe à l'assembleur.
        retenues = sections_retenues(parametres_de_societe(self.company))
        self.assertEqual(retenues, OBLIGATOIRES)
        html = html_de_rapport(construire_rapport(
            NU, resultat=copy.deepcopy(RESULTAT), site=SITE,
            identite=IDENTITE, styles=STYLES, sections=retenues))
        imprimees = re.findall(r'data-section="([a-z_]+)"', html)
        for facultative in FACULTATIVES:
            self.assertNotIn(facultative, imprimees)

        # ``null`` = toutes les sections (équivalence) ; le reste de la
        # section ``documents`` n'est jamais remplacé par le catalogue.
        self._put({'documents': {CODE_RAPPORT_ETUDE: {'sections': None}}})
        self.assertIsNone(sections_retenues(
            parametres_de_societe(self.company)))
