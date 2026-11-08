"""NTAPI20 — document OpenAPI 3.1 servi par `GET /api/public/v1/openapi.json`.

Couvre : accessible sans clé API (document de découverte), structure OpenAPI
3.1 minimale valide (`openapi`/`info`/`paths`/`components`), et couverture à
100 % des endpoints publics réellement MONTÉS (`public_urls.py`) — une
divergence future entre les deux serait un bug détecté ICI, pas une note de
doc oubliée. Aucune fuite de `prix_achat`/marge dans le schéma généré.
"""
import json

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from . import docs_i18n
from .constants import EVENT_CHOICES
from .docs import public_api_reference, reference_langue
from .openapi import build_openapi_document, build_openapi_schema
from .portees import SCOPE_CHOICES
from .public_urls import router as public_router


class Ntapi20OpenApiSchemaTests(TestCase):
    def test_endpoint_accessible_without_api_key(self):
        resp = APIClient().get('/api/public/v1/openapi.json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['openapi'], '3.1.0')

    def test_minimal_openapi_structure(self):
        schema = build_openapi_schema()
        for key in ('openapi', 'info', 'servers', 'paths', 'components'):
            self.assertIn(key, schema)
        self.assertIn('securitySchemes', schema['components'])
        self.assertIn('ApiKeyAuth', schema['components']['securitySchemes'])
        self.assertIn('schemas', schema['components'])
        self.assertIn('ErrorEnvelope', schema['components']['schemas'])

    def test_covers_every_read_only_resource_list_and_detail(self):
        schema = build_openapi_schema()
        # Les ressources montées sur le routeur lecture seule, dérivées de
        # `public_urls.py` lui-même — jamais une liste dupliquée à la main qui
        # pourrait diverger silencieusement. NTAPI16 ajoute `public-job` (suivi
        # des jobs bulk, ReadOnlyModelViewSet) aux 5 ressources métier ;
        # NTUX33 ajoute 2 ressources UX (`read:vues`/`read:favoris`) ;
        # NTP2P39 ajoute 2 ressources Procure-to-Pay (`lecture_achats`), pour
        # 11 au total (CAL214 : `public-calepinage`) : on fige l'ENSEMBLE
        # exact (plus fort qu'un simple compte), donc un 12e enregistrement
        # resterait un choix délibéré, pas un accident. SOLMVP22 (2026-09-21)
        # a retiré les 2 ressources supply chain NTSCM38 (`read:scm`) et les
        # 4 ressources BTP/EPC NTCON31 (`read:btp`) : modules `scm`/
        # `btp_chantier` sortis du produit (Groupe SOLMVP).
        registered_basenames = {r[2] for r in public_router.registry}
        self.assertEqual(registered_basenames, {
            'public-lead', 'public-devis', 'public-facture',
            'public-chantier', 'public-produit', 'public-job',
            'public-favori', 'public-saved-view',
            # NTP2P39 — 2 ressources Procure-to-Pay (`lecture_achats` :
            # demandes d'achat FG310 et RFQ FG311, sans aucun prix d'achat).
            'public-achats-demande', 'public-achats-rfq',
            # CAL214 — les conceptions de toiture (`read:calepinages`).
            'public-calepinage',
        })
        for prefix, _viewset, _basename in public_router.registry:
            list_path = f'/api/public/v1/{prefix}/'
            detail_path = f'/api/public/v1/{prefix}/{{id}}/'
            self.assertIn(list_path, schema['paths'])
            self.assertIn('get', schema['paths'][list_path])
            self.assertIn(detail_path, schema['paths'])
            self.assertIn('get', schema['paths'][detail_path])

    def test_covers_every_write_endpoint(self):
        schema = build_openapi_schema()
        expected = {
            ('/api/public/v1/leads-write/', 'post'),
            ('/api/public/v1/leads-write/{id}/', 'patch'),
            ('/api/public/v1/leads-write/{id}/activites/', 'post'),
        }
        for path, method in expected:
            self.assertIn(path, schema['paths'])
            self.assertIn(method, schema['paths'][path])

    def test_no_undocumented_paths_beyond_mounted_surface(self):
        # SOLMVP-fix (2026-09-21) — SOLMVP22 avait re-fixé ce pin à 35 via
        # « 48 - 13 » (retrait des 2 ressources supply chain NTSCM38 + 4
        # BTP/EPC NTCON31, list+detail, -12, et de la lecture simple NTSCM38
        # « tableau de bord réappro », -1) : une ERREUR D'ARITHMÉTIQUE, pas une
        # vraie régression — le total RÉEL juste avant SOLMVP22 était 50 (la
        # ligne qu'il a remplacée disait littéralement
        # ``self.assertEqual(nb_operations, 50)``, CAL214 calepinages déjà
        # inclus), jamais 48 (un sous-total INTERMÉDIAIRE d'un ancien
        # commentaire, avant son propre « + 2 CAL214 »). 50 - 13 = 37, vérifié
        # en direct (``build_openapi_schema()`` compte bien 37 aujourd'hui) —
        # remis d'aplomb ici, calcul complet plutôt que rapiécé :
        #
        # 10 ressources en lecture seule (`docs.py::endpoints`) × 2
        # (list+detail) = 20 (5 métier [leads/devis/factures/chantiers/
        # produits] + CAL214 calepinages + 2 UX NTUX33 [favoris/saved-views] +
        # 2 Procure-to-Pay NTP2P39 [achats-demande/achats-rfq] — `public-job`
        # n'y est PAS : ses chemins viennent de `endpoints_bulk` ci-dessous)
        # + 5 écritures (leads-write POST/PATCH, activités POST, devis-write
        # POST, tickets-write POST) + 6 bulk (NTAPI14/15/16/43/30 : exports,
        # imports, jobs list/detail, jobs/<id>/relancer, exports/<entite>.csv)
        # + 1 lecture simple (NTADM42 statut de licence) + 3 (NTOBS27 —
        # surface « Fiabilité » en lecture seule : fiabilite/sauvegardes/,
        # fiabilite/sla/<periode>/, fiabilite/usage/, chacune un objet unique
        # en GET) + 2 (NTAPI17 flux d'évènements `events/` GET, NTAPI19 OAuth2
        # client_credentials `oauth/token/` POST — anciens, jamais comptés
        # explicitement ici, d'où l'écart avec les sous-totaux ci-dessus) =
        # 37 opérations, sur autant de chemins distincts (aucun chemin ne
        # cumule 2 méthodes ici) — jamais un chemin fantôme ajouté par erreur.
        # CALX369 (2026-09-24) : + 1 sous-ressource en lecture
        # (`docs.py::sous_ressources` — `calepinages/<id>/resultat/` GET,
        # scope `read:calepinages`) = 38.
        # NTI18N42 (2026-11-07) : + 1 lecture simple (`clients/{id}/langue/`,
        # scope `read:clients`) = 39.
        schema = build_openapi_schema()
        nb_operations = sum(len(ops) for ops in schema['paths'].values())
        self.assertEqual(nb_operations, 39)

    def test_covers_licence_statut_ntadm42(self):
        schema = build_openapi_schema()
        path = '/api/public/v1/licence/statut/'
        self.assertIn(path, schema['paths'])
        self.assertIn('get', schema['paths'][path])

    def test_never_exposes_purchase_price_or_margin_fields(self):
        import json
        blob = json.dumps(build_openapi_schema())
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_error_responses_use_stripe_like_envelope_schema(self):
        schema = build_openapi_schema()
        list_path = '/api/public/v1/leads/'
        error_400 = schema['paths'][list_path]['get']['responses']['400']
        ref = error_400['content']['application/json']['schema']['$ref']
        self.assertEqual(ref, '#/components/schemas/ErrorEnvelope')

    def test_rate_limit_headers_documented_on_success_and_429(self):
        schema = build_openapi_schema()
        list_op = schema['paths']['/api/public/v1/leads/']['get']
        self.assertIn('X-RateLimit-Limit', list_op['responses']['200']['headers'])
        self.assertIn('X-RateLimit-Remaining', list_op['responses']['429']['headers'])

# NTI18N44 — doc bilingue FR/EN : l'arbre EN doit égaler l'arbre FR (aucun
# champ perdu) ; couverture EN de chaque endpoint/scope/évènement/champ.


GROUPES = ('endpoints_ecriture', 'endpoints_bulk', 'endpoints_lecture_simple',
           'sous_ressources')


def _meme_arbre(testcase, fr, en, chemin='$'):
    """Même structure : mêmes clés, mêmes longueurs, mêmes feuilles non
    textuelles (une feuille textuelle peut différer — c'est la traduction)."""
    if isinstance(fr, dict):
        testcase.assertIsInstance(en, dict, chemin)
        testcase.assertEqual(set(fr), set(en), chemin)
        for cle in fr:
            _meme_arbre(testcase, fr[cle], en[cle], f'{chemin}.{cle}')
    elif isinstance(fr, list):
        testcase.assertIsInstance(en, list, chemin)
        testcase.assertEqual(len(fr), len(en), chemin)
        for i, (a, b) in enumerate(zip(fr, en)):
            _meme_arbre(testcase, a, b, f'{chemin}[{i}]')
    elif isinstance(fr, str):
        testcase.assertIsInstance(en, str, chemin)
    else:
        testcase.assertEqual(fr, en, chemin)


def _entrees(ref):
    toutes = list(ref['endpoints'])
    for groupe in GROUPES:
        toutes.extend(ref[groupe]['liste'])
    return toutes


class Nti18n44ReferenceTests(SimpleTestCase):
    def test_langue_par_defaut_et_inconnue_restent_francaises(self):
        fr = public_api_reference()
        self.assertEqual(fr, reference_langue('fr'))
        self.assertEqual(fr, reference_langue('xx'))
        self.assertEqual(fr, reference_langue(None))
        self.assertTrue(fr['titre'].startswith('API publique'))

    def test_la_reference_anglaise_garde_toute_la_structure(self):
        _meme_arbre(self, reference_langue('fr'), reference_langue('en'))

    def test_les_textes_sont_reellement_traduits(self):
        en = reference_langue('en')
        self.assertEqual(en['titre'], 'Taqinor public API — Reference')
        self.assertTrue(en['introduction'].startswith('REST API'))

    def test_chemins_scopes_et_codes_ne_sont_jamais_traduits(self):
        fr, en = reference_langue('fr'), reference_langue('en')
        for a, b in zip(_entrees(fr), _entrees(en)):
            self.assertEqual(a['chemin'], b['chemin'])
            self.assertEqual(a.get('scope'), b.get('scope'))
            self.assertEqual(a.get('filtres'), b.get('filtres'))
            self.assertEqual(a.get('tri'), b.get('tri'))
        self.assertEqual([s['code'] for s in fr['scopes']],
                         [s['code'] for s in en['scopes']])
        self.assertEqual([e['code'] for e in fr['webhooks']['evenements']],
                         [e['code'] for e in en['webhooks']['evenements']])

    def test_chaque_description_dendpoint_a_sa_version_anglaise(self):
        fr, en = reference_langue('fr'), reference_langue('en')
        for a, b in zip(_entrees(fr), _entrees(en)):
            self.assertIn(a['chemin'], docs_i18n.ENDPOINTS_EN, a['chemin'])
            self.assertNotEqual(a['description'], b['description'], a['chemin'])

    def test_chaque_scope_et_chaque_evenement_a_son_libelle_anglais(self):
        for code, _libelle in SCOPE_CHOICES:
            self.assertIn(code, docs_i18n.SCOPES_EN, code)
        for code, _libelle in EVENT_CHOICES:
            self.assertIn(code, docs_i18n.EVENEMENTS_EN, code)

    def test_chaque_champ_decrit_a_sa_version_anglaise(self):
        fr = reference_langue('fr')
        for entree in fr['sous_ressources']['liste']:
            for champ in entree['champs']:
                self.assertIn((entree['chemin'], champ['nom']),
                              docs_i18n.CHAMPS_EN)
        for charge in fr['webhooks']['charges_utiles']:
            self.assertIn(charge['code'], docs_i18n.CHARGES_UTILES_EN)
            for champ in charge['champs']:
                self.assertIn((charge['code'], champ['nom']),
                              docs_i18n.CHAMPS_EN)

    def test_aucune_traduction_orpheline(self):
        """Une clé de traduction qui ne vise plus rien (endpoint renommé)
        serait une doc EN fantôme : on l'attrape ici."""
        fr = reference_langue('fr')
        chemins = {e['chemin'] for e in _entrees(fr)}
        self.assertEqual(set(docs_i18n.ENDPOINTS_EN) - chemins, set())
        for cle in docs_i18n.TEXTES_EN:
            noeud = fr
            for morceau in cle.split('.'):
                self.assertIn(morceau, noeud, cle)
                noeud = noeud[morceau]
            self.assertIsInstance(noeud, str, cle)


class Nti18n44OpenApiTests(SimpleTestCase):
    def test_le_schema_anglais_garde_tous_les_chemins_et_champs(self):
        _meme_arbre(self, build_openapi_document('fr'), build_openapi_document('en'))

    def test_le_defaut_est_inchange(self):
        self.assertEqual(build_openapi_schema(), build_openapi_document('fr'))
        self.assertEqual(build_openapi_document('xx'), build_openapi_document('fr'))

    def test_plus_aucune_chaine_statique_francaise_en_anglais(self):
        rendu = json.dumps(build_openapi_document('en'), ensure_ascii=False)
        for texte_fr in docs_i18n.OPENAPI_EXACT_EN:
            self.assertNotIn(json.dumps(texte_fr, ensure_ascii=False), rendu)
        self.assertNotIn('(détail)', rendu)
        self.assertNotIn('Champs triables', rendu)

    def test_endpoint_http_lang_en(self):
        client = APIClient()
        en = client.get('/api/public/v1/openapi.json?lang=en')
        self.assertEqual(en.status_code, 200)
        self.assertEqual(en.data['info']['title'], 'Taqinor public API')
        self.assertTrue(en.data['info']['description'].startswith('REST API'))
        fr = client.get('/api/public/v1/openapi.json')
        self.assertEqual(fr.data['info']['title'], 'API publique Taqinor')
        self.assertEqual(set(fr.data['paths']), set(en.data['paths']))
