"""NTAPI4 — catalogue d'erreurs consultable + `GET /api/public/v1/errors/`.

Critère d'acceptation, dans les deux sens :
  * CHAQUE code d'erreur réellement émis par le handler NTAPI3 existe au
    catalogue (test de cohérence) — et aucune explication fantôme ne traîne ;
  * l'endpoint les LISTE, en français, sans clé d'API (document de découverte).

Vérifie en plus l'alignement avec `errors.py` : le `doc_url` posé dans une
enveloppe d'erreur RÉELLE pointe bien vers une ancre que le catalogue sert.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .constants import SCOPE_READ_LEADS
from .error_catalog import catalogue, codes_documentes, codes_emis
from .models import ApiKey


class Ntapi4ErrorCatalogRegistryTests(TestCase):
    """Le registre lui-même (aucune requête HTTP)."""

    def test_tout_code_emis_est_documente(self):
        manquants = codes_emis() - codes_documentes()
        self.assertEqual(
            manquants, set(),
            f"Code(s) émis sans explication au catalogue : {sorted(manquants)}")

    def test_aucune_explication_fantome(self):
        fantomes = codes_documentes() - codes_emis()
        self.assertEqual(
            fantomes, set(),
            f"Explication(s) sans code émis correspondant : {sorted(fantomes)}")

    def test_chaque_entree_est_complete_et_en_francais(self):
        for entree in catalogue():
            for champ in ('code', 'titre', 'description', 'action',
                          'http_status', 'doc_url'):
                self.assertIn(champ, entree)
                self.assertTrue(
                    entree[champ] not in ('', None),
                    f"Champ « {champ} » vide pour le code {entree['code']}.")
            self.assertEqual(
                entree['doc_url'], f"/api/public/v1/errors/#{entree['code']}")
            self.assertIsInstance(entree['http_status'], int)

    def test_codes_cles_presents(self):
        """Les codes structurants du contrat public sont bien couverts."""
        documentes = codes_documentes()
        for code in ('validation_error', 'not_authenticated',
                     'permission_denied', 'not_found', 'throttled',
                     'idempotency_conflict', 'server_error'):
            self.assertIn(code, documentes)


class Ntapi4ErrorCatalogEndpointTests(TestCase):
    """`GET /api/public/v1/errors/` — sans clé, et aligné sur le registre."""

    def test_liste_sans_cle_dapi(self):
        resp = APIClient().get('/api/public/v1/errors/')
        self.assertEqual(resp.status_code, 200)
        codes = {e['code'] for e in resp.json()['results']}
        self.assertEqual(codes, codes_documentes())

    def test_filtre_par_code(self):
        resp = APIClient().get('/api/public/v1/errors/?code=not_found')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['code'], 'not_found')
        self.assertTrue(results[0]['titre'])

    def test_code_inconnu_renvoie_404_sans_inventer(self):
        resp = APIClient().get('/api/public/v1/errors/?code=code_bidon')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error']['code'], 'not_found')

    def test_doc_url_dune_vraie_erreur_pointe_vers_le_catalogue(self):
        """Une erreur RÉELLE (403 hors scope) porte un `doc_url` dont l'ancre
        est un code que le catalogue sert — jamais une ancre morte."""
        co, _ = Company.objects.get_or_create(
            slug='ntapi4', defaults={'nom': 'NTAPI4'})
        _key, raw = ApiKey.issue(
            company=co, label='cat', scopes=[SCOPE_READ_LEADS])
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw}')
        resp = api.get('/api/public/v1/devis/')  # hors scope → 403
        self.assertEqual(resp.status_code, 403)
        erreur = resp.json()['error']
        self.assertEqual(
            erreur['doc_url'], f"/api/public/v1/errors/#{erreur['code']}")
        self.assertIn(erreur['code'], codes_documentes())
