"""CAL214 — ressource publique `calepinages` en LECTURE SEULE.

Couvre les quatre garanties du critère « Done » :

1. la ressource répond sous ``/api/public/v1/calepinages/`` (liste + détail) ;
2. elle ne FUITE rien — ni géométrie brute (``roof_layout``, plans/rangées du
   moteur), ni coût interne (``prix_achat``) ;
3. le scope ``read:calepinages`` est exigé, et la société vient de la CLÉ :
   un calepinage d'une autre société est introuvable (404), jamais « interdit » ;
4. elle est documentée (FG105/NTAPI20), donc ``tests_ntapi42_contract_consistency``
   reste vert — ce test-ci vérifie en plus que la doc porte bien le chemin.

Le modèle est obtenu par ``apps.get_model`` : ce module ne fait AUCUN import
statique de ``apps.calepinage.models`` — la frontière inter-apps (lecture par
``selectors.py``) vaut aussi pour les fixtures de test.
"""
from django.apps import apps as django_apps
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .constants import SCOPE_READ_CALEPINAGES, SCOPE_READ_LEADS
from .models import ApiKey

# Un résultat de moteur RÉALISTE : les deux grandeurs publiables (`kwc`,
# `total_modules`) ET de la géométrie qui, elle, ne doit jamais sortir.
RESULTAT = {
    'kwc': 8.64,
    'total_modules': 12,
    'plans': [{'surface': 'PAN-A', 'modules': 12}],
    'rangees': [{'surface': 'PAN-A', 'x0': 0.35, 'y0': 0.35}],
}
LAYOUT = {'schema_version': 2, 'zones': [{'points': [[0, 0], [1, 0], [1, 1]]}]}


def calepinage_model():
    return django_apps.get_model('calepinage', 'Calepinage')


def key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PublicCalepinageReadOnlyTests(TestCase):
    def setUp(self):
        self.co_a, _ = Company.objects.get_or_create(
            slug='pa-cal214-a', defaults={'nom': 'PA CAL214 A'})
        self.co_b, _ = Company.objects.get_or_create(
            slug='pa-cal214-b', defaults={'nom': 'PA CAL214 B'})
        self.key_a, self.raw_a = ApiKey.issue(
            company=self.co_a, label='A', scopes=[SCOPE_READ_CALEPINAGES])
        modele = calepinage_model()
        self.cal_a = modele.objects.create(
            company=self.co_a, lead_id=1, titre='Toiture A',
            roof_layout=LAYOUT, layout_hash='a' * 64,
            version_moteur='essai', resultat=RESULTAT)
        self.cal_neuf = modele.objects.create(
            company=self.co_a, lead_id=2, titre='Neuf, jamais calculé')
        self.cal_b = modele.objects.create(
            company=self.co_b, lead_id=3, titre='Toiture B (autre société)')

    # ── 1. La ressource répond ───────────────────────────────────────────────
    def test_liste_repond_et_ne_montre_que_la_societe_de_la_cle(self):
        resp = key_client(self.raw_a).get('/api/public/v1/calepinages/')
        self.assertEqual(resp.status_code, 200)
        ids = {ligne['id'] for ligne in rows(resp)}
        self.assertEqual(ids, {self.cal_a.id, self.cal_neuf.id})

    def test_detail_repond_avec_les_grandeurs_reellement_calculees(self):
        resp = key_client(self.raw_a).get(
            f'/api/public/v1/calepinages/{self.cal_a.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['titre'], 'Toiture A')
        self.assertEqual(resp.data['kwc'], 8.64)
        self.assertEqual(resp.data['modules'], 12)
        self.assertEqual(resp.data['layout_hash'], 'a' * 64)
        self.assertEqual(resp.data['lead_id'], 1)
        self.assertIn('apercu', resp.data['liens'])

    def test_calepinage_neuf_rend_null_jamais_zero(self):
        """Rien de calculé ⇒ `null`. Un `0` ferait lire « toiture vide »."""
        resp = key_client(self.raw_a).get(
            f'/api/public/v1/calepinages/{self.cal_neuf.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['kwc'])
        self.assertIsNone(resp.data['modules'])
        self.assertIsNone(resp.data['liens']['apercu'])

    # ── 2. Aucune fuite ──────────────────────────────────────────────────────
    def test_ne_fuite_ni_geometrie_brute_ni_prix_achat(self):
        resp = key_client(self.raw_a).get(
            f'/api/public/v1/calepinages/{self.cal_a.id}/')
        for interdit in ('roof_layout', 'resultat', 'plans', 'rangees',
                         'prix_achat', 'roof_image'):
            self.assertNotIn(interdit, resp.data)
        brut = str(resp.content)
        self.assertNotIn('PAN-A', brut)
        self.assertNotIn('prix_achat', brut)

    def test_les_cles_publiees_sont_exactement_le_contrat(self):
        resp = key_client(self.raw_a).get(
            f'/api/public/v1/calepinages/{self.cal_a.id}/')
        self.assertEqual(set(resp.data.keys()), {
            'id', 'titre', 'statut', 'statut_libelle', 'lead_id', 'client_id',
            'devis_id', 'appel_offre_id', 'layout_hash', 'version_moteur',
            'kwc', 'modules', 'liens', 'created_at', 'updated_at',
        })

    # ── 3. Scope + isolation société ─────────────────────────────────────────
    def test_scope_requis(self):
        _, raw = ApiKey.issue(
            company=self.co_a, label='sans scope', scopes=[SCOPE_READ_LEADS])
        resp = key_client(raw).get('/api/public/v1/calepinages/')
        self.assertEqual(resp.status_code, 403)

    def test_sans_cle_401(self):
        resp = APIClient().get('/api/public/v1/calepinages/')
        self.assertEqual(resp.status_code, 401)

    def test_calepinage_d_une_autre_societe_est_introuvable(self):
        resp = key_client(self.raw_a).get(
            f'/api/public/v1/calepinages/{self.cal_b.id}/')
        self.assertEqual(resp.status_code, 404)

    # ── 4. Filtres / tri / doc ───────────────────────────────────────────────
    def test_filtre_inconnu_refuse_en_400(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/calepinages/?roof_layout=x')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_liste_blanche(self):
        resp = key_client(self.raw_a).get(
            '/api/public/v1/calepinages/?lead_id=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([ligne['id'] for ligne in rows(resp)],
                         [self.cal_a.id])

    def test_la_ressource_est_documentee(self):
        from .docs import public_api_reference

        reference = public_api_reference()
        chemins = {e['chemin'] for e in reference['endpoints']}
        self.assertIn('/api/public/v1/calepinages/', chemins)
        codes = {s['code'] for s in reference['scopes']}
        self.assertIn(SCOPE_READ_CALEPINAGES, codes)
