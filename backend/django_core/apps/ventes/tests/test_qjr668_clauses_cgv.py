"""QJR668 (décision fondateur 01/10/2026 : « les brancher ») — les clauses/CGV
propres à chaque affaire (NTCPQ11, ``Devis.clauses_appliquees``) sont :

  * GELÉES sur le chemin d'envoi (``mark_devis_sent``) ;
  * RE-GELÉES à chaque correction sur place d'un envoyé (QJR518) ;
  * IMPRIMÉES par tous les gabarits (résidentiel, industriel, commercial,
    une page) — et un devis sans clause reste sans bloc.

ERR-QJR668 : la source réelle est DocumentTemplates.cgv_bullets (Paramètres) ;
le catalogue (app ``cpq``) est PARQUÉ : sans source, le gel n'écrit rien et
n'efface jamais un snapshot déjà posé. Les tests fournissent la source en
patchant ``clauses_applicables_devis``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr668_clauses_cgv"
"""
import re
from unittest.mock import patch

from django.test import TestCase, tag
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
        """cpq parqué : la source réelle rend None, le snapshot reste."""
        from apps.ventes.domain.cycle_vie import (
            clauses_applicables_devis, figer_clauses_devis)
        devis = self._devis()
        self.assertIsNone(clauses_applicables_devis(devis))
        devis.clauses_appliquees = [CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        self.assertFalse(figer_clauses_devis(devis))
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees, [CLAUSE])

    def test_envoi_gele_les_cgv_de_la_societe_sans_patch(self):
        """ERR-QJR668 — SANS patch de ``clauses_applicables_devis`` : les CGV
        renseignées dans Paramètres sont la source réelle du gel."""
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.services import mark_devis_sent
        DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': [
                'QJR668 livraison sous trente jours ouvrés',
                'Acompte {acompte} % à la commande']})
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        # Les puces de la société sont gelées TELLES QUELLES (marqueur
        # {acompte} conservé) dans UNE entrée dédiée, pas en clause
        # particulière.
        self.assertEqual(
            devis.clauses_appliquees,
            [{'type': 'cgv_gelees', 'bullets': [
                'QJR668 livraison sous trente jours ouvrés',
                'Acompte {acompte} % à la commande']}])

    def test_les_cgv_gelees_sont_ecrites_une_seule_fois(self):
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.domain.cycle_vie import figer_clauses_devis
        modele = DocumentTemplates.objects.create(
            company=self.company, cgv_bullets=['QJR668 avant'])
        devis = self._devis()
        self.assertTrue(figer_clauses_devis(devis))
        modele.cgv_bullets = ['QJR668 apres']
        modele.save()
        self.assertFalse(figer_clauses_devis(devis))
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees[0]['bullets'],
                         ['QJR668 avant'])

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

    def test_cgv_gelees_imprimees_une_fois_et_figees_apres_edition(self):
        """ERR-QJR668 — envoi → la société édite ses CGV → le PDF imprime le
        texte GELÉ, UNE seule fois, dans le bloc CGV standard (jamais dans
        « Clauses particulières »)."""
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.services import mark_devis_sent
        modele, _ = DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': ['QJR668 livraison gelee trente jours']})
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        modele.cgv_bullets = ['QJR668 livraison nouvelle quarante jours']
        modele.save()
        devis.refresh_from_db()
        texte, _ = self._texte(devis)
        self.assertEqual(texte.count('qjr668 livraison gelee trente jours'), 1)
        self.assertNotIn('quarante jours', texte)
        self.assertNotIn('clauses particulières', texte)

    def test_un_brouillon_imprime_les_cgv_vives(self):
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': ['QJR668 livraison vive vingt jours']})
        texte, _ = self._texte(self._devis())
        self.assertEqual(texte.count('qjr668 livraison vive vingt jours'), 1)
        self.assertNotIn('clauses particulières', texte)

    def test_cgv_gelees_et_clause_particuliere_coexistent_sans_doublon(self):
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': ['QJR668 livraison gelee trente jours']})
        devis = self._gele(self._devis(), [
            CLAUSE, {'type': 'cgv_gelees',
                     'bullets': ['QJR668 livraison gelee trente jours']}])
        texte, _ = self._texte(devis)
        self.assertEqual(texte.count('qjr668 livraison gelee trente jours'), 1)
        self.assertEqual(texte.count(_norm(CLAUSE['corps_texte'])), 1)
        self.assertIn('clauses particulières', texte)

    def test_clause_echappee(self):
        clause = dict(CLAUSE, corps_texte='QJR668 <b>a & b</b> < c')
        texte, _ = self._texte(self._gele(self._devis(), [clause]))
        self.assertIn('qjr668 <b>a & b</b> < c', texte)

    def test_sans_clause_aucun_bloc(self):
        texte, _ = self._texte(self._devis())
        self.assertNotIn('clauses particulières', texte)
