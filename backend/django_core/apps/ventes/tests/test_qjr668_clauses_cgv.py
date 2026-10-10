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
import ast
import html
import re
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings, tag
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis, ShareLink
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.clauses_cgv import cgv_imprimees
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

SOURCE = 'apps.ventes.domain.envoi.clauses_applicables_devis'
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


def _sans_gels_internes(clauses):
    """APDF20 — les entrées de ``clauses_appliquees`` hors gels internes
    (``doc_texts_geles`` est désormais posé à chaque gel, défauts compris)."""
    from apps.ventes.domain.envoi import TYPE_DOC_TEXTS_GELES
    return [c for c in (clauses or [])
            if not (isinstance(c, dict)
                    and c.get('type') == TYPE_DOC_TEXTS_GELES)]


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
        self.assertEqual(_sans_gels_internes(devis.clauses_appliquees),
                         [CLAUSE])

    def test_sans_catalogue_rien_n_est_ecrit_ni_efface(self):
        """cpq parqué : la source réelle rend None, le snapshot reste.
        APDF20 — seul le gel des textes contractuels s'ajoute (une fois)."""
        from apps.ventes.domain.envoi import (
            clauses_applicables_devis, figer_clauses_devis)
        devis = self._devis()
        self.assertIsNone(clauses_applicables_devis(devis))
        devis.clauses_appliquees = [CLAUSE]
        devis.save(update_fields=['clauses_appliquees'])
        figer_clauses_devis(devis)
        self.assertFalse(figer_clauses_devis(devis))
        devis.refresh_from_db()
        self.assertEqual(_sans_gels_internes(devis.clauses_appliquees),
                         [CLAUSE])

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
            _sans_gels_internes(devis.clauses_appliquees),
            [{'type': 'cgv_gelees', 'bullets': [
                'QJR668 livraison sous trente jours ouvrés',
                'Acompte {acompte} % à la commande']}])

    def test_les_cgv_gelees_sont_ecrites_une_seule_fois(self):
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.domain.envoi import figer_clauses_devis
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
        self.assertEqual(_sans_gels_internes(devis.clauses_appliquees),
                         [CLAUSE, CLAUSE_2])

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

    #: Le bloc « CGV standard » (puces de ``DocumentTemplates.cgv_bullets``,
    #: ``generate_devis_premium.page3``) n'existe que dans le moteur LEGACY —
    #: les pages premium résidentiel/commercial/industriel n'impriment que les
    #: « Clauses particulières ». Les gardes de CGV rendent donc le format
    #: legacy (``include_etude`` : ``is_residential`` l'écarte, cf.
    #: ``test_pdf_commercial_legacy_sections_options``).
    LEGACY = {'include_etude': True}

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
        texte, _ = self._texte(devis, self.LEGACY)
        self.assertEqual(texte.count('qjr668 livraison gelee trente jours'), 1)
        self.assertNotIn('quarante jours', texte)
        self.assertNotIn('clauses particulières', texte)

    def test_un_brouillon_imprime_les_cgv_vives(self):
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': ['QJR668 livraison vive vingt jours']})
        texte, _ = self._texte(self._devis(), self.LEGACY)
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
        texte, _ = self._texte(devis, self.LEGACY)
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


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PageSignatureCgvTests(_Base):
    """QJR668 — la page PUBLIQUE de signature (``proposal_data`` →
    ``conditions``) sert les CGV que le PDF de CE devis imprime : la version
    GELÉE à l'envoi quand elle existe, remplie par LA fonction du moteur
    (``clauses_cgv.remplir_cgv_bullets``) — jamais une seconde
    copie du remplissage."""

    def _conditions(self, devis):
        from apps.ventes.models import ShareLink
        lien = ShareLink.for_devis(devis)
        r = APIClient().get(f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return r.data.get('conditions')

    def _attendu_pdf(self, devis):
        """Les puces du bloc CGV du PDF de CE devis, en texte."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.clauses_cgv import (
            cgv_bullets_remplies)
        return [t for t in (html.unescape(str(p)).strip()
                            for p in cgv_bullets_remplies(
                                build_quote_data(devis, {'pdf_mode': 'full'})))
                if t]

    def test_envoye_puis_cgv_societe_modifiees_la_page_sert_les_puces_gelees(self):
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.services import mark_devis_sent
        modele, _ = DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': [
                'QJR668 livraison gelee trente jours',
                'QJR668 acompte gele {acompte}&#37; a la commande']})
        devis = self._devis()
        mark_devis_sent(devis=devis, user=self.user)
        modele.cgv_bullets = ['QJR668 livraison nouvelle quarante jours']
        modele.save()
        devis.refresh_from_db()
        conditions = self._conditions(devis)
        self.assertIsNotNone(conditions)
        joint = ' | '.join(conditions)
        self.assertIn('QJR668 livraison gelee trente jours', joint)
        self.assertNotIn('quarante jours', joint)
        acompte = [c for c in conditions if c.startswith('QJR668 acompte gele')]
        self.assertEqual(len(acompte), 1, conditions)
        self.assertNotIn('{', acompte[0])
        self.assertTrue(acompte[0].endswith('% a la commande'), acompte[0])
        # Exactement ce que le PDF de CE devis imprime.
        self.assertEqual(conditions, self._attendu_pdf(devis))

    def test_sans_gel_le_texte_vif_est_rempli_sans_case_brute(self):
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.objects.update_or_create(
            company=self.company,
            defaults={'cgv_bullets': [
                'QJR668 vif {acompte}&#37; puis {materiel}&#37; puis '
                '{solde}&#37;', '{tva_note}', '{validite_offre}']})
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self.assertFalse(devis.clauses_appliquees)
        conditions = self._conditions(devis)
        self.assertIsNotNone(conditions)
        joint = ' | '.join(conditions)
        self.assertIn('QJR668 vif ', joint)
        self.assertNotIn('{', joint)
        self.assertNotIn('&#', joint)
        self.assertEqual(conditions, self._attendu_pdf(devis))


class UneSeuleFonctionDeRemplissageTests(TestCase):
    """Garde AST : la page publique ne remplit plus les cases CGV elle-même."""

    VENTES = Path(__file__).resolve().parent.parent

    def _fonction(self, chemin, nom):
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef) and noeud.name == nom:
                return arbre, noeud
        self.fail(f'{nom} introuvable dans {chemin.name}')

    @staticmethod
    def _appels(noeud):
        noms = set()
        for n in ast.walk(noeud):
            if isinstance(n, ast.Call):
                f = n.func
                noms.add(f.attr if isinstance(f, ast.Attribute)
                         else getattr(f, 'id', None))
        return noms

    def test_conditions_publiques_sans_format_local(self):
        # SPL241 — ``public_views.py`` est découpé en ``public/*.py`` : la
        # fonction est cherchée dans le GROUPE (jamais vide).
        from apps.ventes.tests.split_golden import (
            fichiers_du_groupe, source_du_symbole)
        groupe = fichiers_du_groupe('public_views.py', 'public/*.py')
        fonction = ast.parse(
            source_du_symbole('_conditions_publiques', groupe)).body[0]
        appels = self._appels(fonction)
        self.assertNotIn('format', appels)
        # APDF19 — la page publique lit LA source du PDF, ``cgv_imprimees``
        # (APDF12), dont ``cgv_bullets_remplies`` est un détail.
        self.assertIn('cgv_imprimees', appels)
        definies = {n.name for chemin in groupe
                    for n in ast.walk(ast.parse(
                        chemin.read_text(encoding='utf-8')))
                    if isinstance(n, ast.FunctionDef)}
        self.assertNotIn('_pct_lisible', definies)

    def test_le_pdf_passe_par_la_meme_fonction(self):
        moteur = self.VENTES / 'quote_engine' / 'generate_devis_premium.py'
        _, html_cgv = self._fonction(moteur, '_cgv_bullets_html')
        appels = self._appels(html_cgv)
        self.assertIn('remplir_cgv_bullets', appels)
        self.assertNotIn('format', appels)
        # C20 — la famille pure des CGV vit dans ``clauses_cgv.py``.
        cgv = self.VENTES / 'quote_engine' / 'clauses_cgv.py'
        _, remplies = self._fonction(cgv, 'cgv_bullets_remplies')
        self.assertIn('remplir_cgv_bullets', self._appels(remplies))


TITRE_IND = 'CGV INDUSTRIEL SPECIFIQUES'
PUCES_IND = ['Echeancier {echeancier}', 'Retenue {retenue}',
             'Clause industrielle XYZ']
LIGNES_IND = [('Panneau mono 450W', '40', '1500'),
              ('Onduleur réseau 20 kW', '1', '30000')]


def _compact(texte):
    """Texte sans AUCUN blanc : le PDF coupe ses lignes où il veut (après
    « ONEE/ », avant « : »…) ; mot pour mot = mêmes caractères visibles."""
    return re.sub(r'\s+', '', str(texte))


#: Renvoi DÉCLARÉ de la page 3 résidentielle quand ses CGV dépassent le
#: budget (``residential.trust.puces_cgv_bornees``, libellé ``ci_cgv_suite``).
RENVOI = 'Suite des conditions : proposition en ligne'


def puces_attendues(devis):
    """Les puces du PDF de CE devis (``cgv_imprimees``), en texte."""
    return [html.unescape(str(p)).strip()
            for p in cgv_imprimees(build_quote_data(devis, {}))['puces']
            if str(p).strip()]


class ConditionsPubliquesParitePdfTests(TestCase):
    """APDF19 (C-APDF-005) — la page publique de signature sert les conditions
    générales du PDF de CE devis, brouillon comme envoyé.

    ``_conditions_publiques`` lit ``clauses_cgv.cgv_imprimees(data)``
    (APDF12), la source que le PDF imprime. Vrai GET
    ``/api/django/public/proposal/<jeton>/data/`` (client Django, jeton d'aperçu
    interne pour le brouillon — ADEV11 ne sert pas un brouillon au jeton client —,
    jeton client une fois le devis envoyé par ``mark_devis_sent``) ; texte du PDF
    réel lu par PyMuPDF (``test_pdf_apdf_identite.rendre_pdf``, MinIO en
    mémoire). Aucune doublure du moteur.

    Test-du-test : faire revenir ``_conditions_publiques`` à
    ``cgv_bullets_remplies`` ⇒ ``test_brouillon_industriel`` échoue (la page
    servait les puces résidentielles par défaut au lieu de la variante C&I).
    """

    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company(slug='apdf19-co', nom='APDF19')
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_par_mode = {'industriel': {
            'titre': TITRE_IND, 'bullets': list(PUCES_IND)}}
        modele.save()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                LIGNES_IND, reference='DEV-APDF19-IND')
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])
        self.lien = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _conditions(self, jeton):
        reponse = self.api.get(f'/api/django/public/proposal/{jeton}/data/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json().get('conditions')

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=devis)
        devis.refresh_from_db()

    def test_brouillon_industriel(self):
        conditions = self._conditions(self.lien.token_interne)
        self.assertIn('Clause industrielle XYZ', conditions)
        self.assertEqual(conditions, puces_attendues(self.devis))
        # Plus les puces résidentielles par défaut du moteur.
        self.assertFalse([p for p in conditions
                          if p.startswith('Acompte à la commande')])

    def test_envoye_industriel_marqueurs_substitues(self):
        self._envoyer(self.devis)
        conditions = self._conditions(self.lien.token)
        self.assertEqual(conditions, puces_attendues(self.devis))
        texte = ' '.join(conditions)
        self.assertNotIn('{echeancier}', texte)
        self.assertNotIn('{retenue}', texte)
        echeancier = [p for p in conditions if p.startswith('Echeancier')]
        self.assertEqual(len(echeancier), 1)
        self.assertIn('%', echeancier[0])

    def test_residentiel(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel)
        devis = devis_residentiel(self.company, 'DEV-APDF19-RES',
                                  user=self.user, client=self.client_obj)
        self._envoyer(devis)
        lien = ShareLink.for_devis(devis)
        conditions = self._conditions(lien.token)
        self.assertTrue(conditions)
        self.assertEqual(conditions, puces_attendues(devis))

    @tag('pdf')
    def test_pdf_imprime_les_memes_puces(self):
        """Parité PDF ⊂ page publique, mot pour mot : la page sert la liste
        COMPLÈTE ; le PDF imprime ce qui tient — tout en C&I, le budget de la
        page 3 en résidentiel (``puces_cgv_bornees``) avec le renvoi déclaré
        quand il tronque. Chaque puce IMPRIMÉE est dans la liste servie, la
        première servie est la première imprimée, et sans troncature aucun
        renvoi n'est imprimé (donc toutes les puces servies le sont)."""
        from apps.ventes.quote_engine.residential import trust
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel, rendre_pdf, texte_pdf)
        residentiel = devis_residentiel(self.company, 'DEV-APDF19-RES2',
                                        user=self.user, client=self.client_obj)

        def verifier(devis, jeton, borne):
            servies = self._conditions(jeton)
            self.assertTrue(servies)
            pdf = _compact(texte_pdf(rendre_pdf(devis)))
            imprimees = (trust.puces_cgv_bornees({}, servies) if borne
                         else list(servies))
            tronque = bool(imprimees) and imprimees[-1] == RENVOI
            if tronque:
                imprimees = imprimees[:-1]
            self.assertTrue(imprimees)
            self.assertEqual(imprimees[0], servies[0])
            self.assertEqual(imprimees, servies[:len(imprimees)])
            for puce in imprimees:
                self.assertIn(_compact(puce), pdf)
            self.assertEqual(_compact(RENVOI) in pdf, tronque)
            return pdf

        with self.subTest(etat='brouillon'):
            pdf = verifier(self.devis, self.lien.token_interne, borne=False)
            self.assertIn(_compact(TITRE_IND), pdf)
        self._envoyer(self.devis)
        self._envoyer(residentiel)
        with self.subTest(etat='envoye'):
            verifier(self.devis, self.lien.token, borne=False)
        with self.subTest(etat='residentiel'):
            verifier(residentiel, ShareLink.for_devis(residentiel).token,
                     borne=True)
