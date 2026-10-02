"""QJR668 — décision fondateur (Reda, 01/10/2026) : « Figer le texte CGV à
l'envoi. À l'envoi (et à chaque correction après envoi), on fige le texte CGV
de la société, cases remplies avec les valeurs du devis. Le PDF de ce devis
imprime ensuite cette version figée : modifier les CGV plus tard ne change
plus un devis déjà envoyé ou signé. »

  * (a) LA fonction pure ``quote_engine.clauses_cgv.remplir_cgv`` remplit les
    cases — moteur et gel l'appellent tous les deux ;
  * (b) ``clauses_applicables_devis`` lit le texte CGV SOCIÉTÉ
    (``parametres.selectors.cgv_societe``) SANS patch : gel à l'envoi
    (``mark_devis_sent``), regel à chaque correction après envoi (QJR518),
    jamais de regel d'un accepté, rien pour une société sans CGV ;
  * (c) le PDF imprime la version figée dans le bloc « Conditions
    générales », UNE seule fois, au lieu du texte vivant.

Les tests « Clauses particulières » historiques (NTCPQ11) fournissent une
clause par affaire en patchant ``clauses_applicables_devis``.

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

from django.test import SimpleTestCase, TestCase, override_settings, tag
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
MOTEUR = (Path(__file__).resolve().parents[1] / 'quote_engine'
          / 'generate_devis_premium.py')


class RemplirCgvTests(SimpleTestCase):
    """(a) LA fonction pure qui remplit les cases du texte CGV."""

    def setUp(self):
        from apps.ventes.quote_engine.clauses_cgv import valeurs_cgv
        self.valeurs = valeurs_cgv(
            acompte=40, materiel=50, solde=10,
            tva_note='TVA 20 % appliquée', valid_until='31/10/2026')

    def test_toutes_les_cases_sont_remplies(self):
        from apps.ventes.quote_engine.clauses_cgv import remplir_cgv
        puces = remplir_cgv([
            '{validite_offre}', 'Acompte&#160;: {acompte}&#37;',
            '{materiel}&#37; à la réception', '{solde}&#37; à la fin',
            '{tva_note}'], self.valeurs)
        self.assertEqual(puces, [
            'Validit&#233; de l&#8217;offre&#160;: jusqu&#8217;au 31/10/2026',
            'Acompte&#160;: 40&#37;', '50&#37; à la réception',
            '10&#37; à la fin', 'TVA 20 % appliquée'])
        self.assertFalse([p for p in puces if '{' in p or '}' in p])

    def test_case_inconnue_jamais_imprimee_brute(self):
        from apps.ventes.quote_engine.clauses_cgv import remplir_cgv
        puces = remplir_cgv(['Garantie {garantie_ans} ans', '{}'],
                            self.valeurs)
        self.assertEqual(puces, ['Garantie  ans'])

    def test_puce_vide_omise_echeance_inconnue(self):
        from apps.ventes.quote_engine.clauses_cgv import (
            remplir_cgv, valeurs_cgv)
        valeurs = valeurs_cgv(acompte=30, materiel=60, solde=10,
                              tva_note='', valid_until='')
        self.assertEqual(
            remplir_cgv(['{validite_offre}', '{tva_note}', 'Fixe'], valeurs),
            ['Fixe'])

    def test_termes_affiches_gardent_la_decimale(self):
        from apps.ventes.quote_engine.clauses_cgv import (
            termes_paiement_affiches)
        self.assertEqual(termes_paiement_affiches(
            {'payment_terms': {'acompte': 33.5, 'materiel': '56.50',
                               'solde': None}}), (33.5, 56.5, 10))
        self.assertEqual(termes_paiement_affiches({}), (30, 60, 10))

    def test_le_moteur_appelle_la_fonction_partagee(self):
        """Une seule copie : ``_cgv_bullets_html`` ne formate plus lui-même."""
        arbre = ast.parse(MOTEUR.read_text(encoding='utf-8'))
        fonction = next(
            n for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef)
            and n.name == '_cgv_bullets_html')
        appels = {n.func.id for n in ast.walk(fonction)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        attributs = {n.func.attr for n in ast.walk(fonction)
                     if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute)}
        self.assertIn('remplir_cgv', appels)
        self.assertNotIn('format', attributs)


class SourceTests(SimpleTestCase):
    """ERR-QJR668-CLAUSES-CGV-SOURCE-PARQUEE — SANS patch de la source.

    L'ancienne source cherchait ``apps.cpq.selectors`` par import dynamique :
    module absent → ``None`` en silence. La source est désormais le texte CGV
    société, lu par le selector de ``apps.parametres`` (app fondation)."""

    def _fonction(self):
        arbre = ast.parse(CYCLE_VIE.read_text(encoding='utf-8'))
        return next(
            n for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef)
            and n.name == 'clauses_applicables_devis')

    def test_aucune_reference_a_cpq_dans_la_source(self):
        fonction = self._fonction()
        chaines = [n.value for n in ast.walk(fonction)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and n is not fonction.body[0].value]
        noms = {n.id for n in ast.walk(fonction) if isinstance(n, ast.Name)}
        self.assertFalse([c for c in chaines if 'cpq' in c], chaines)
        self.assertNotIn('importlib', noms)

    def test_la_source_est_le_selector_cgv_de_parametres(self):
        modules = {n.module for n in ast.walk(self._fonction())
                   if isinstance(n, ast.ImportFrom)}
        self.assertIn('apps.parametres.selectors', modules)
        self.assertIn('apps.ventes.quote_engine.clauses_cgv', modules)

    def test_un_module_cpq_present_n_est_pas_lu(self):
        """Même si un ``apps.cpq.selectors`` devenait importable, la
        fonction ne s'en sert pas : société sans CGV → ``None``."""
        from apps.ventes.domain.cycle_vie import clauses_applicables_devis
        faux = types.ModuleType('apps.cpq.selectors')
        faux.clauses_applicables = MagicMock(return_value=[CLAUSE])
        with patch.dict(sys.modules, {'apps.cpq.selectors': faux}), \
                patch('apps.parametres.selectors.cgv_societe',
                      return_value=None):
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
        """Société sans CGV : la source réelle rend None, le snapshot reste."""
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


class GelCgvSocieteTests(_Base):
    """(b) SANS patch de ``clauses_applicables_devis`` : le texte CGV de la
    SOCIÉTÉ est figé, cases remplies, à l'envoi et à chaque correction."""

    def _cgv(self, puces, titre='CGV QJR668', company=None):
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=company or self.company)
        tpl.cgv_titre = titre
        tpl.cgv_bullets = puces
        tpl.save()
        return tpl

    def _attendu(self, devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.clauses_cgv import (
            termes_paiement_affiches)
        data = build_quote_data(devis)
        return termes_paiement_affiches(data), data['tva_note']

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_envoi_fige_le_texte_cgv_cases_remplies(self):
        from apps.ventes.services import mark_devis_sent
        self._cgv(['Acompte QJR668 {acompte}&#37; puis {materiel}&#37;',
                   'Solde QJR668 {solde}&#37;', '{tva_note}',
                   'Puce fixe QJR668'])
        devis = self._devis()
        (acompte, materiel, solde), tva_note = self._attendu(devis)
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(len(devis.clauses_appliquees), 1)
        fige = devis.clauses_appliquees[0]
        self.assertEqual(fige['source'], 'cgv_societe')
        self.assertEqual(fige['nom'], 'CGV QJR668')
        self.assertEqual(fige['puces'], [
            f'Acompte QJR668 {acompte}&#37; puis {materiel}&#37;',
            f'Solde QJR668 {solde}&#37;', tva_note, 'Puce fixe QJR668'])
        self.assertFalse(
            [p for p in fige['puces'] if '{' in p or '}' in p], fige)

    def test_titre_vide_fige_le_titre_par_defaut(self):
        from apps.ventes.quote_engine.clauses_cgv import CGV_TITRE_DEFAUT
        from apps.ventes.services import mark_devis_sent
        self._cgv(['Puce QJR668'], titre='')
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees[0]['nom'],
                         CGV_TITRE_DEFAUT)

    def test_correction_apres_envoi_regele_le_texte_courant(self):
        from apps.ventes.services import mark_devis_sent
        tpl = self._cgv(['Ancienne puce QJR668'])
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        tpl.cgv_bullets = ['Nouvelle puce QJR668 {acompte}&#37;']
        tpl.save()
        r = self._api().patch(f'/api/django/ventes/devis/{devis.id}/',
                              {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        (acompte, _, _), _ = self._attendu(devis)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.clauses_appliquees[0]['puces'],
                         [f'Nouvelle puce QJR668 {acompte}&#37;'])

    def test_devis_accepte_jamais_regele(self):
        from apps.ventes.domain.cycle_vie import figer_clauses_devis
        self._cgv(['Puce courante QJR668'])
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        signe = [{'clause_id': None, 'source': 'cgv_societe',
                  'nom': 'CGV signée', 'corps_texte': '',
                  'puces': ['Puce signée QJR668'], 'type_deal': '',
                  'ordre': 0, 'version': 1}]
        devis.clauses_appliquees = signe
        devis.save(update_fields=['clauses_appliquees'])
        self.assertFalse(figer_clauses_devis(devis))
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees, signe)

    def test_societe_sans_cgv_rien_n_est_fige(self):
        """Ni gabarit, ni titre seul, ni CGV d'une AUTRE société."""
        from apps.ventes.services import mark_devis_sent
        autre = make_company()
        self._cgv(['CGV autre société QJR668'], company=autre)
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertFalse(devis.clauses_appliquees)
        self._cgv(None, titre='Titre seul QJR668')
        devis2 = self._devis()
        mark_devis_sent(devis=devis2, user=self.user)
        devis2.refresh_from_db()
        self.assertFalse(devis2.clauses_appliquees)


CGV_FIGEE = {'clause_id': None, 'source': 'cgv_societe',
             'nom': 'Titre CGV figé QJR668', 'corps_texte': '',
             'puces': ['Puce CGV figée QJR668 unique', 'Acompte 40&#37;'],
             'type_deal': '', 'ordre': 0, 'version': 3}


class RenduCgvFigeeTests(_Base):
    """(b)/(c) — le HTML EXACT du moteur legacy (bloc « Conditions
    générales ») imprime la version FIGÉE, une seule fois, au lieu du texte
    vivant de la société."""

    def _cgv(self, puces, titre):
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.cgv_titre = titre
        tpl.cgv_bullets = puces
        tpl.save()
        return tpl

    def _html(self, devis):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine.builder import build_quote_data
        devis.refresh_from_db()
        return G.render_html_for(build_quote_data(devis))

    def test_modifier_les_cgv_apres_envoi_ne_change_pas_le_pdf(self):
        from apps.ventes.services import mark_devis_sent
        tpl = self._cgv(['Puce envoyée QJR668 acompte {acompte}&#37;'],
                        'Titre envoyé QJR668')
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        avant = self._html(devis)
        tpl.cgv_titre = 'Titre modifié QJR668'
        tpl.cgv_bullets = ['Puce modifiée QJR668']
        tpl.save()
        apres = self._html(devis)
        for html in (avant, apres):
            self.assertEqual(html.count('Puce envoyée QJR668 acompte'), 1)
            self.assertEqual(html.count('Titre envoyé QJR668'), 1)
            self.assertNotIn('Puce modifiée QJR668', html)
            self.assertNotIn('Titre modifié QJR668', html)
            self.assertNotIn('{acompte}', html)
        # Un brouillon de la même société, lui, suit le texte vivant.
        brouillon = self._html(self._devis())
        self.assertIn('Puce modifiée QJR668', brouillon)
        self.assertNotIn('Puce envoyée QJR668', brouillon)

    def test_texte_fige_imprime_une_seule_fois(self):
        from apps.ventes.quote_engine.clauses_cgv import TITRE
        self._cgv(['Puce vivante QJR668'], 'Titre vivant QJR668')
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        devis.clauses_appliquees = [CGV_FIGEE]
        devis.save(update_fields=['clauses_appliquees'])
        html = self._html(devis)
        self.assertEqual(html.count('Puce CGV figée QJR668 unique'), 1)
        self.assertEqual(html.count('Titre CGV figé QJR668'), 1)
        self.assertNotIn('Puce vivante QJR668', html)
        self.assertNotIn('Titre vivant QJR668', html)
        # Jamais réimprimé dans « Clauses particulières ».
        self.assertNotIn(TITRE, html)

    def test_builder_separe_cgv_figee_et_clauses_particulieres(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        devis.clauses_appliquees = [CGV_FIGEE, CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        data = build_quote_data(devis)
        self.assertEqual(data['cgv_figees'], {
            'titre': CGV_FIGEE['nom'], 'puces': CGV_FIGEE['puces']})
        self.assertEqual([c['nom'] for c in data['clauses_cgv']],
                         [CLAUSE['nom']])

    def test_sans_snapshot_texte_vivant_inchange(self):
        self._cgv(['Puce vivante QJR668 {acompte}&#37;'], 'Titre vivant')
        html = self._html(self._devis())
        self.assertIn('Titre vivant', html)
        self.assertIn('Puce vivante QJR668', html)
        self.assertNotIn('{acompte}', html)


PUBLIC_VIEWS = Path(__file__).resolve().parents[1] / 'public_views.py'


class PageSignatureSourceTests(SimpleTestCase):
    """(d) UNE seule fonction de remplissage : la page publique de signature
    (``public_views._conditions_publiques``) n'a plus sa propre copie
    (``.format`` + ``_pct_lisible``) — elle appelle ``remplir_cgv``."""

    def _arbre(self):
        return ast.parse(PUBLIC_VIEWS.read_text(encoding='utf-8'))

    def test_conditions_publiques_appelle_la_fonction_partagee(self):
        fonction = next(
            n for n in ast.walk(self._arbre())
            if isinstance(n, ast.FunctionDef)
            and n.name == '_conditions_publiques')
        appels = {n.func.id for n in ast.walk(fonction)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        attributs = {n.func.attr for n in ast.walk(fonction)
                     if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute)}
        self.assertIn('remplir_cgv', appels)
        self.assertNotIn('format', attributs)

    def test_plus_de_formateur_local_des_pourcentages(self):
        noms = {n.name for n in ast.walk(self._arbre())
                if isinstance(n, ast.FunctionDef)}
        self.assertNotIn('_pct_lisible', noms)


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PageSignatureCgvFigeeTests(_Base):
    """(d) Décision fondateur 01/10/2026 — la page publique de signature
    (« J'accepte … les conditions générales de vente ») sert la CGV FIGÉE du
    devis, celle que son PDF imprime ; jamais le texte vivant modifié après
    l'envoi."""

    def _cgv(self, puces, titre):
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.cgv_titre = titre
        tpl.cgv_bullets = puces
        tpl.save()
        return tpl

    def _conditions(self, devis):
        from apps.ventes.models import ShareLink
        lien = ShareLink.for_devis(devis)
        resp = APIClient().get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        return resp.data['conditions']

    def _acompte_pdf(self, devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.clauses_cgv import (
            termes_paiement_affiches)
        return termes_paiement_affiches(build_quote_data(devis))[0]

    def test_cgv_modifiees_apres_envoi_la_page_sert_la_version_figee(self):
        from apps.ventes.services import mark_devis_sent
        tpl = self._cgv(['Puce envoyée QJR668 acompte {acompte}&#37;',
                         'Puce fixe envoyée QJR668'], 'Titre envoyé QJR668')
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        acompte = self._acompte_pdf(devis)
        attendu = [f'Puce envoyée QJR668 acompte {acompte}%',
                   'Puce fixe envoyée QJR668']
        self.assertEqual(self._conditions(devis), attendu)
        tpl.cgv_titre = 'Titre modifié QJR668'
        tpl.cgv_bullets = ['Puce modifiée QJR668 {acompte}&#37;']
        tpl.save()
        apres = self._conditions(devis)
        self.assertEqual(apres, attendu)
        self.assertNotIn('Puce modifiée', ' | '.join(apres))

    def test_snapshot_fige_servi_tel_quel(self):
        """Les puces figées (entités HTML comprises) partent dé-échappées,
        à l'identique — le texte vivant n'est pas lu."""
        self._cgv(['Puce vivante QJR668'], 'Titre vivant QJR668')
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        devis.clauses_appliquees = [CGV_FIGEE, CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        self.assertEqual(self._conditions(devis),
                         ['Puce CGV figée QJR668 unique', 'Acompte 40%'])

    def test_sans_gel_texte_vivant_rempli_sans_case_brute(self):
        """Devis sans snapshot : le texte VIVANT de la société, rempli par
        ``remplir_cgv`` — une case inconnue n'est jamais servie brute
        (l'ancien ``.format`` local renvoyait la puce telle quelle)."""
        self._cgv(['Puce vivante QJR668 acompte {acompte}&#37;',
                   'Garantie QJR668 {inconnue} ans'], 'Titre vivant')
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self.assertFalse(devis.clauses_appliquees)
        acompte = self._acompte_pdf(devis)
        conditions = self._conditions(devis)
        self.assertEqual(conditions, [
            f'Puce vivante QJR668 acompte {acompte}%',
            'Garantie QJR668  ans'])
        joint = ' | '.join(conditions)
        self.assertNotIn('{', joint)
        self.assertNotIn('}', joint)


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

    def test_cgv_figee_hors_clauses_particulieres_residentiel(self):
        """Le gabarit résidentiel n'a pas de bloc CGV : la CGV figée n'y est
        pas réimprimée en « Clauses particulières », et il reste à 3 pages."""
        texte, pages = self._texte(self._gele(self._devis(), [CGV_FIGEE]))
        self.assertNotIn('clauses particulières', texte)
        self.assertNotIn(_norm('Puce CGV figée QJR668 unique'), texte)
        self.assertEqual(pages, 3)
