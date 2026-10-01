"""QJR668 (décision fondateur 01/10/2026 : « les brancher ») — les clauses/CGV
propres à chaque affaire (NTCPQ11, ``Devis.clauses_appliquees``) sont :

  * GELÉES sur le chemin d'envoi (``mark_devis_sent``) ;
  * RE-GELÉES à chaque correction sur place d'un envoyé (QJR518) ;
  * IMPRIMÉES par tous les gabarits (résidentiel, industriel, commercial,
    une page) — et un devis sans clause reste sans bloc.

Le catalogue (app ``cpq``) est PARQUÉ et le périmètre MVP n'a AUCUNE autre
source de clauses par affaire (ERR-QJR668-CLAUSES-CGV-SOURCE-PARQUEE : l'import
dynamique inerte de ``apps.cpq.selectors`` est retiré, ``SourceTests`` le
prouve SANS patch). Sans source, le gel n'écrit rien et n'efface jamais un
snapshot déjà posé. Les tests de gel/impression fournissent une source en
patchant ``clauses_applicables_devis``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr668_clauses_cgv"
"""
import ast
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, tag
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

SOURCE = 'apps.ventes.domain.cycle_vie.clauses_applicables_devis'
CLAUSE = {'clause_id': 1, 'nom': 'Garantie de production',
          'corps_texte': 'QJR668 production garantie quatre-vingt-dix pour cent',
          'type_deal': 'residentiel', 'ordre': 0}
CLAUSE_2 = {'clause_id': 2, 'nom': 'Pénalités de retard',
            'corps_texte': 'QJR668 pénalité un pour mille par jour',
            'type_deal': '', 'ordre': 1}
ETUDE_INDUSTRIEL = {
    'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
    'taux_autoconso': 92, 'taux_couverture': 61,
    'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
    'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
}


def _norm(texte):
    return re.sub(r'\s+', ' ', texte).strip().lower()


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, mode='residentiel', etude=None, statut=None):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500', '10'),
            ('Onduleur réseau 5kW', '1', '9000', '20'),
        ], reference=f'DEV-{timezone.now():%Y%m}-668{self.n}',
            etude_params=etude)
        devis.mode_installation = mode
        champs = ['mode_installation']
        if statut:
            devis.statut = statut
            champs.append('statut')
        devis.save(update_fields=champs)
        return devis


CYCLE_VIE = (Path(__file__).resolve().parents[1] / 'domain' / 'cycle_vie.py')


class SourceTests(SimpleTestCase):
    """ERR-QJR668-CLAUSES-CGV-SOURCE-PARQUEE — SANS patch de la source.

    L'ancienne source cherchait ``apps.cpq.selectors`` par import dynamique :
    module absent → ``None`` en silence, d'où un gel qui semblait branché sans
    jamais rien écrire. Plus aucune référence à ``cpq`` ni ``importlib``."""

    def test_aucune_reference_a_cpq_dans_la_source(self):
        arbre = ast.parse(CYCLE_VIE.read_text(encoding='utf-8'))
        fonction = next(
            n for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef)
            and n.name == 'clauses_applicables_devis')
        chaines = [n.value for n in ast.walk(fonction)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and n is not fonction.body[0].value]
        noms = {n.id for n in ast.walk(fonction) if isinstance(n, ast.Name)}
        self.assertFalse([c for c in chaines if 'cpq' in c], chaines)
        self.assertNotIn('importlib', noms)

    def test_un_module_cpq_present_n_est_pas_lu(self):
        """Même si un ``apps.cpq.selectors`` devenait importable, la
        fonction ne s'en sert pas : aucune source n'a été désignée."""
        from apps.ventes.domain.cycle_vie import clauses_applicables_devis
        faux = types.ModuleType('apps.cpq.selectors')
        faux.clauses_applicables = MagicMock(return_value=[CLAUSE])
        contexte = 'apps.ventes.domain.cycle_vie.contexte_clauses_devis'
        with patch.dict(sys.modules, {'apps.cpq.selectors': faux}), \
                patch(contexte, return_value={}):
            self.assertIsNone(clauses_applicables_devis(MagicMock()))
        faux.clauses_applicables.assert_not_called()


class GelTests(_Base):

    def test_envoi_gele_les_clauses(self):
        from apps.ventes.services import mark_devis_sent
        devis = self._devis()
        with patch(SOURCE, return_value=[CLAUSE]):
            mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.clauses_appliquees, [CLAUSE])

    def test_sans_catalogue_rien_n_est_ecrit_ni_efface(self):
        """Aucune source MVP : la source réelle rend None, le snapshot reste."""
        from apps.ventes.domain.cycle_vie import (
            clauses_applicables_devis, figer_clauses_devis)
        devis = self._devis()
        self.assertIsNone(clauses_applicables_devis(devis))
        devis.clauses_appliquees = [CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        self.assertFalse(figer_clauses_devis(devis))
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees, [CLAUSE])

    def test_correction_apres_envoi_regele(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        devis.clauses_appliquees = [CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        with patch(SOURCE, return_value=[CLAUSE, CLAUSE_2]):
            r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                          {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.clauses_appliquees, [CLAUSE, CLAUSE_2])

    def test_un_brouillon_modifie_ne_gele_rien(self):
        devis = self._devis()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        with patch(SOURCE, return_value=[CLAUSE]):
            r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                          {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertFalse(devis.clauses_appliquees)


@tag('pdf')
class ImpressionTests(_Base):

    def _gele(self, devis, clauses):
        devis.clauses_appliquees = clauses
        devis.save(update_fields=['clauses_appliquees'])
        return devis

    def _texte(self, devis, options=None):
        import fitz
        from apps.ventes.quote_engine import (
            clean_pdf_options, generate_premium_devis_pdf,
        )
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload:
            generate_premium_devis_pdf(
                devis.id, clean_pdf_options(options or {}), persist=False)
        doc = fitz.open(stream=upload.call_args[0][0], filetype='pdf')
        return _norm('\n'.join(p.get_text() for p in doc)), len(doc)

    def test_builder_expose_les_clauses(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._gele(self._devis(), [CLAUSE])
        self.assertEqual(build_quote_data(devis)['clauses_cgv'][0]['nom'],
                         CLAUSE['nom'])

    def test_residentiel_imprime_les_clauses_sur_3_pages(self):
        texte, pages = self._texte(self._gele(self._devis(), [CLAUSE]))
        self.assertIn('clauses particulières', texte)
        self.assertIn(_norm(CLAUSE['corps_texte']), texte)
        self.assertEqual(pages, 3)

    def test_industriel_imprime_les_clauses(self):
        devis = self._gele(
            self._devis(mode='industriel', etude=dict(ETUDE_INDUSTRIEL)),
            [CLAUSE])
        texte, _ = self._texte(devis)
        self.assertIn(_norm(CLAUSE['corps_texte']), texte)

    def test_commercial_imprime_les_clauses(self):
        # Sans étude : le renderer commercial maison (avec étude → legacy).
        devis = self._gele(self._devis(mode='commercial'), [CLAUSE])
        texte, _ = self._texte(devis)
        self.assertIn(_norm(CLAUSE['corps_texte']), texte)

    def test_une_page_imprime_les_clauses(self):
        devis = self._gele(self._devis(), [CLAUSE])
        texte, pages = self._texte(devis, {'pdf_mode': 'onepage'})
        self.assertIn(_norm(CLAUSE['corps_texte']), texte)
        self.assertEqual(pages, 1)

    def test_clause_echappee(self):
        clause = dict(CLAUSE, corps_texte='QJR668 <b>a & b</b> < c')
        texte, _ = self._texte(self._gele(self._devis(), [clause]))
        self.assertIn('qjr668 <b>a & b</b> < c', texte)

    def test_sans_clause_aucun_bloc(self):
        texte, _ = self._texte(self._devis())
        self.assertNotIn('clauses particulières', texte)
