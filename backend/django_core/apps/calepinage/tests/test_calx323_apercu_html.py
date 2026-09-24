"""CALX323 — servir un aperçu HTML avant le PDF.

Ce qui est prouvé ici :

* ``?code=`` absent, ou un code SANS mise en page enregistrée, rend 400 en
  NOMMANT ``code`` — le message reste un texte FRANÇAIS propre, jamais
  ré-encapsulé entre guillemets par ``KeyError.__str__`` (essais PURS —
  aucun accès base : le refus part AVANT toute résolution de document) ;
* en base (CI) : l'aperçu sert du ``text/html`` ; un document indisponible
  rend 400 avec le motif RÉEL (identique au PDF) ; aucun accès réseau dans
  le HTML servi (ni ``http://`` ni ``@import``) ; l'aperçu ET le PDF
  appellent la MÊME fonction de mise en page (test qui espionne la
  fonction) ; borné société et permission comme le reste du module.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx323_apercu_html.py -q
"""
from __future__ import annotations

import unittest

from apps.calepinage.views.documents import apercu_document


class FauxRequest:
    def __init__(self, params=None):
        self.query_params = params or {}


class FauxSelf:
    """Un ``self`` de viewset minimal : ``get_object()`` rend le calepinage
    FOURNI — aucun DRF, aucune base."""

    def __init__(self, calepinage):
        self._calepinage = calepinage

    def get_object(self):
        return self._calepinage


class FauxCalepinage:
    pk = 1
    company = None


class RefusAvantResolutionTest(unittest.TestCase):
    """Le refus (``code`` absent/inconnu) part AVANT toute résolution du
    document — essais PURS, aucun accès base."""

    def test_code_absent_400_nommant_code(self):
        reponse = apercu_document(FauxSelf(FauxCalepinage()), FauxRequest(),
                                  pk=1)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('code', reponse.data)
        self.assertTrue(reponse.data['code'])

    def test_code_inconnu_400_message_propre_sans_guillemets_python(self):
        reponse = apercu_document(
            FauxSelf(FauxCalepinage()),
            FauxRequest({'code': 'document_inexistant'}), pk=1)
        self.assertEqual(reponse.status_code, 400)
        message = reponse.data['code']
        self.assertIn('document_inexistant', message)
        # KeyError.__str__() ré-encapsule entre guillemets Python (repr) —
        # le message servi ne doit JAMAIS commencer par l'un d'eux.
        self.assertFalse(message.startswith("'"))
        self.assertFalse(message.startswith('"'))

    def test_code_avec_espaces_est_assaini_avant_la_recherche(self):
        reponse = apercu_document(
            FauxSelf(FauxCalepinage()), FauxRequest({'code': '  '}), pk=1)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('code', reponse.data)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════
# EN BASE (CI) — rendu réel, refus réel, société, partage de fonction
# ═══════════════════════════════════════════════════════════════════════
#
# Écrit ici mais NON EXÉCUTÉ localement (pas de Postgres sur ce poste de
# lane) : la CI valide.

import copy  # noqa: E402 - après les essais purs
from unittest import mock  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.calepinage.services.documents import mise_en_page  # noqa: E402
from apps.calepinage.services.rapport import html_du_rapport  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402
from .test_cal171_planche import LAYOUT  # noqa: E402
from .test_calx308_diagramme_pertes_svg import RESULTAT  # noqa: E402

MIME_HTML_ATTENDU = 'text/html; charset=utf-8'


class ApercuDocumentEnBaseTest(BaseApiCalepinage):
    """``GET …/apercu-document/?code=`` — câblage, société, refus (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=copy.deepcopy(LAYOUT), layout_hash='a' * 64,
            resultat=copy.deepcopy(RESULTAT))
        self.sans_resultat = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Vide',
            roof_layout=copy.deepcopy(LAYOUT))
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Voisine',
            roof_layout=copy.deepcopy(LAYOUT), resultat=copy.deepcopy(RESULTAT))

    def _apercu(self, calepinage, code='rapport_etude', servi=None):
        servi = copy.deepcopy(RESULTAT) if servi is None else servi
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=servi):
            return self.api.get(
                f'{url_detail(calepinage.pk)}apercu-document/?code={code}')

    def test_apercu_sert_du_html(self):
        reponse = self._apercu(self.calepinage)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], MIME_HTML_ATTENDU)
        self.assertIn('<html', reponse.content.decode('utf-8').lower())

    def test_code_inconnu_400_le_nommant(self):
        reponse = self._apercu(self.calepinage, code='document_inexistant')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('document_inexistant', reponse.data['code'])

    def test_document_indisponible_400_avec_le_motif_reel(self):
        reponse = self._apercu(self.sans_resultat)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('resultat', reponse.data)

    def test_aucun_acces_reseau_dans_le_html_servi(self):
        html = self._apercu(self.calepinage).content.decode('utf-8')
        self.assertNotIn('http://', html)
        self.assertNotIn('@import', html)

    def test_une_autre_societe_est_introuvable(self):
        reponse = self._apercu(self.etranger)
        self.assertEqual(reponse.status_code, 404)

    def test_technicien_sans_droit_est_refuse_403(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=copy.deepcopy(RESULTAT)):
            reponse = self.api_sans.get(
                f'{url_detail(self.calepinage.pk)}apercu-document/'
                '?code=rapport_etude')
        self.assertEqual(reponse.status_code, 403)

    def test_apercu_et_pdf_partagent_le_meme_appel_de_mise_en_page(self):
        """Le test qui ESPIONNE la fonction : PDF et aperçu appellent la
        MÊME ``html_du_rapport`` — aucun second gabarit qui pourrait
        diverger."""
        self.assertIs(mise_en_page('rapport_etude'), html_du_rapport)
        html_simule = '<html><body>x</body></html>'
        with (
            mock.patch('apps.calepinage.services.rapport.html_du_rapport',
                       return_value=html_simule) as espion,
            mock.patch('core.pdf.render_pdf', return_value=b'%PDF-simule'),
        ):
            reponse_pdf = self.api.get(
                f'{url_detail(self.calepinage.pk)}rapport-etude.pdf/')
            reponse_apercu = self.api.get(
                f'{url_detail(self.calepinage.pk)}apercu-document/'
                '?code=rapport_etude')
        self.assertEqual(reponse_pdf.status_code, 200)
        self.assertEqual(reponse_apercu.status_code, 200)
        self.assertEqual(espion.call_count, 2)
        self.assertEqual(reponse_apercu.content.decode('utf-8'),
                         '<html><body>x</body></html>')
