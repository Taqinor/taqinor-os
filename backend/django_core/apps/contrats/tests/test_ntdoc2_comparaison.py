"""Tests NTDOC2 — Diff entre la version contrepartie et la dernière VersionContrat.

Critère d'acceptation :
- deux textes avec 3 phrases modifiées affichent les lignes ajoutées/supprimées ;
- un format binaire NON SUPPORTÉ renvoie un message explicite SANS planter.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, DocumentContrepartie, VersionContrat

User = get_user_model()

BASE = '/api/django/contrats/contrats/'

TEXTE_INTERNE = (
    "Article 1 — Objet du contrat.\n"
    "Article 2 — Durée de douze mois.\n"
    "Article 3 — Paiement à trente jours.\n"
    "Article 4 — Juridiction de Casablanca.\n"
)
TEXTE_CONTREPARTIE = (
    "Article 1 — Objet du contrat.\n"
    "Article 2 — Durée de vingt-quatre mois.\n"
    "Article 3 — Paiement à soixante jours.\n"
    "Article 4 — Juridiction de Paris.\n"
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def patch_fetch(contenu, erreur=None):
    """Neutralise le stockage objet : ``fetch_attachment`` renvoie ``contenu``."""
    return mock.patch(
        'apps.records.storage.fetch_attachment',
        return_value=(contenu, erreur))


class ComparaisonContrepartieTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc2', 'Comparaison')
        self.admin = User.objects.create_user(
            username='ntdoc2-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat cadre', reference='CT-002')
        self.version = VersionContrat.objects.create(
            company=self.co, contrat=self.contrat, version=1,
            contenu=TEXTE_INTERNE, motif='envoi client')

    def _depot(self, nom_fichier='redline.txt'):
        return DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key=f'contrats/contreparties/{self.co.id}/x.bin',
            nom_fichier=nom_fichier)

    def test_trois_phrases_modifiees_donnent_ajouts_et_suppressions(self):
        """3 lignes modifiées → 3 lignes « + » et 3 lignes « - » dans le diff."""
        depot = self._depot()
        with patch_fetch(TEXTE_CONTREPARTIE.encode('utf-8')):
            res = services.comparer_contrepartie(self.contrat, depot)
        self.assertTrue(res['comparable'], res.get('message'))
        self.assertEqual(res['lignes_ajoutees'], 3)
        self.assertEqual(res['lignes_supprimees'], 3)
        diff = '\n'.join(res['diff_texte'])
        self.assertIn('-Article 2 — Durée de douze mois.', diff)
        self.assertIn('+Article 2 — Durée de vingt-quatre mois.', diff)

    def test_textes_identiques_diff_vide(self):
        depot = self._depot()
        with patch_fetch(TEXTE_INTERNE.encode('utf-8')):
            res = services.comparer_contrepartie(self.contrat, depot)
        self.assertTrue(res['comparable'])
        self.assertEqual(res['lignes_ajoutees'], 0)
        self.assertEqual(res['lignes_supprimees'], 0)

    def test_format_non_supporte_message_explicite_sans_planter(self):
        """Un format binaire non comparable dégrade proprement (pas d'exception)."""
        depot = self._depot(nom_fichier='scan.doc')
        with patch_fetch(b'\x00\x01\x02binaire'):
            res = services.comparer_contrepartie(self.contrat, depot)
        self.assertFalse(res['comparable'])
        self.assertIn('Comparaison indisponible', res['message'])
        self.assertIn('.doc', res['message'])
        self.assertEqual(res['diff_texte'], [])

    def test_fichier_introuvable_message_explicite(self):
        depot = self._depot()
        with patch_fetch(None, 'Fichier introuvable.'):
            res = services.comparer_contrepartie(self.contrat, depot)
        self.assertFalse(res['comparable'])
        self.assertIn('Comparaison indisponible', res['message'])

    def test_sans_version_figee_message_explicite(self):
        """Sans VersionContrat, le message nomme l'action à faire."""
        VersionContrat.objects.all().delete()
        depot = self._depot()
        with patch_fetch(TEXTE_CONTREPARTIE.encode('utf-8')):
            res = services.comparer_contrepartie(self.contrat, depot)
        self.assertFalse(res['comparable'])
        self.assertIn('creer-version', res['message'])
        self.assertIsNone(res['version_interne'])

    def test_docx_lu_par_le_repli_stdlib(self):
        """Un .docx est lisible SANS python-docx (repli zip+XML, zéro dépendance)."""
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr(
                'word/document.xml',
                '<w:document><w:body>'
                '<w:p><w:r><w:t>Article 1 &#8212; Objet du contrat.</w:t>'
                '</w:r></w:p>'
                '<w:p><w:r><w:t>Article 2 — Durée de vingt-quatre mois.</w:t>'
                '</w:r></w:p>'
                '</w:body></w:document>')
        depot = self._depot(nom_fichier='reponse.docx')
        with patch_fetch(buf.getvalue()):
            texte, raison = services.extraire_texte_contrepartie(depot)
        self.assertEqual(raison, '')
        self.assertIn('vingt-quatre mois', texte)

    def test_lecture_seule_rien_n_est_modifie(self):
        """La comparaison ne touche NI la version figée NI le dépôt."""
        depot = self._depot()
        with patch_fetch(TEXTE_CONTREPARTIE.encode('utf-8')):
            services.comparer_contrepartie(self.contrat, depot)
        self.version.refresh_from_db()
        depot.refresh_from_db()
        self.assertEqual(self.version.contenu, TEXTE_INTERNE)
        self.assertEqual(depot.statut, DocumentContrepartie.Statut.NOUVEAU)


class ComparaisonApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc2-api', 'API')
        self.autre = make_company('ntdoc2-api-b', 'B')
        self.admin = User.objects.create_user(
            username='ntdoc2-api-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(company=self.co, objet='C')
        VersionContrat.objects.create(
            company=self.co, contrat=self.contrat, version=1,
            contenu=TEXTE_INTERNE)
        self.depot = DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key='k/1.txt', nom_fichier='r.txt')

    def test_endpoint_renvoie_le_diff(self):
        api = auth(self.admin)
        with patch_fetch(TEXTE_CONTREPARTIE.encode('utf-8')):
            resp = api.get(
                f'{BASE}{self.contrat.id}/contreparties/'
                f'{self.depot.id}/comparer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['comparable'])
        self.assertEqual(resp.data['lignes_ajoutees'], 3)

    def test_depot_d_un_autre_contrat_404(self):
        autre_contrat = Contrat.objects.create(company=self.co, objet='Autre')
        api = auth(self.admin)
        resp = api.get(
            f'{BASE}{autre_contrat.id}/contreparties/'
            f'{self.depot.id}/comparer/')
        self.assertEqual(resp.status_code, 404)

    def test_contrat_d_une_autre_societe_404(self):
        user_b = User.objects.create_user(
            username='ntdoc2-b-admin', password='x', company=self.autre,
            role_legacy='admin')
        api = auth(user_b)
        resp = api.get(
            f'{BASE}{self.contrat.id}/contreparties/'
            f'{self.depot.id}/comparer/')
        self.assertEqual(resp.status_code, 404)
