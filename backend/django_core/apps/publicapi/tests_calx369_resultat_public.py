"""CALX369 — ``GET /api/public/v1/calepinages/<id>/resultat/``.

La sous-ressource publique du résultat de SIMULATION d'un calepinage : un
serializer PLAT qui déclare champ par champ ce qui sort, sous le scope
EXISTANT ``read:calepinages``. Garanties couvertes (patron de
``tests_cal214_calepinage.py``) :

1. la forme publiée est EXACTEMENT celle déclarée (serializer, ``docs.py`` et
   OpenAPI disent la même chose) ;
2. ni ``roof_layout``, ni rangées, ni électrique, ni coût ne sortent ;
3. non simulé (ou simulation périmée) ⇒ toutes les grandeurs à ``null`` avec
   le motif, jamais ``0`` ; la série horaire n'est jamais publiée ;
4. scope exigé, société imposée par la clé (404 ailleurs).

Les entrées des tests purs sont les échantillons COMMITTÉS du module
(``calepinage_resultat.json`` pour les trois états servis,
``calepinage_simulation.json`` pour un document réellement déposé) : le test
affirme le contrat, jamais des valeurs réinventées. Les classes dont le nom
contient « EnBase » exigent la base de données et tournent en CI.
"""
import copy
import json
import pathlib
from unittest import mock

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase

from .constants import EVENT_CALEPINAGE_SIMULE, SCOPE_READ_CALEPINAGES
from .public_serializers import (
    MOTIF_RESULTAT_NON_SIMULE, PublicCalepinageResultatSerializer,
    PublicPostePerteSerializer, resultat_calepinage_public,
)

ECHANTILLONS = (pathlib.Path(django_apps.get_app_config('calepinage').path)
                / 'contract_samples')
CONTRAT_RESULTAT = json.loads(
    (ECHANTILLONS / 'calepinage_resultat.json').read_text(encoding='utf-8'))
SIMULATION = json.loads(
    (ECHANTILLONS / 'calepinage_simulation.json').read_text(encoding='utf-8'))

CHAMPS = ('calepinage_id', 'simule', 'production_annuelle_kwh',
          'rendement_specifique_kwh_kwc', 'ratio_performance', 'p50_kwh',
          'p75_kwh', 'p90_kwh', 'pertes', 'calcule_le', 'simulation_perimee',
          'motif')
GRANDEURS = ('production_annuelle_kwh', 'rendement_specifique_kwh_kwc',
             'ratio_performance', 'p50_kwh', 'p75_kwh', 'p90_kwh')
CHAMPS_POSTE = ('code', 'libelle', 'pourcentage', 'source', 'gain', 'motif')

#: Ce qui ne doit JAMAIS sortir, même quand le résultat servi le porte.
INTERDITS = ('roof_layout', 'rangees', 'affectation', 'electrique', 'pose',
             'serie_horaire', 'nomenclature', 'troncons', 'prix_achat',
             'prix', 'cout', 'marge')


def _publie(servi, calepinage_id=7):
    return PublicCalepinageResultatSerializer(
        resultat_calepinage_public(calepinage_id, servi)).data


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA FORME — déclarée champ par champ, identique partout
# ═══════════════════════════════════════════════════════════════════════════

class FormeDeclareeTests(SimpleTestCase):
    def test_le_serializer_declare_exactement_ces_champs(self):
        self.assertEqual(tuple(PublicCalepinageResultatSerializer().fields),
                         CHAMPS)
        self.assertEqual(tuple(PublicPostePerteSerializer().fields),
                         CHAMPS_POSTE)

    def test_la_doc_decrit_les_memes_champs_dans_le_meme_ordre(self):
        from .docs import CHAMPS_RESULTAT_CALEPINAGE, public_api_reference

        self.assertEqual(
            tuple(c['nom'] for c in CHAMPS_RESULTAT_CALEPINAGE), CHAMPS)
        sous = public_api_reference()['sous_ressources']['liste']
        entree = next(e for e in sous
                      if e['chemin'].endswith('/calepinages/<id>/resultat/'))
        self.assertEqual(entree['scope'], SCOPE_READ_CALEPINAGES)
        self.assertEqual(entree['methode'], 'GET')
        self.assertIn("NI d'écrire NI de lancer une simulation",
                      entree['description'])
        self.assertIn('série horaire', entree['description'])

    def test_l_openapi_declare_la_forme_et_pas_un_objet_vide(self):
        from .openapi import build_openapi_schema

        schema = build_openapi_schema()
        chemin = '/api/public/v1/calepinages/{id}/resultat/'
        self.assertIn(chemin, schema['paths'])
        reponse = schema['paths'][chemin]['get']['responses']['200']
        forme = reponse['content']['application/json']['schema']
        self.assertEqual(tuple(forme['properties']), CHAMPS)
        self.assertEqual(forme['properties']['p50_kwh']['type'],
                         ['number', 'null'])
        self.assertEqual(forme['properties']['simule']['type'], 'boolean')
        parametres = {p['name'] for p in schema['paths'][chemin]['get']
                      ['parameters']}
        self.assertEqual(parametres, {'id'})

    def test_l_openapi_decrit_le_webhook_calepinage_simule(self):
        from .calepinage_event_receivers import CLES_CHARGE_SIMULE
        from .docs import CHARGE_CALEPINAGE_SIMULE
        from .openapi import build_openapi_schema

        self.assertEqual(tuple(c['nom'] for c in CHARGE_CALEPINAGE_SIMULE),
                         CLES_CHARGE_SIMULE)
        webhook = build_openapi_schema()['webhooks'][EVENT_CALEPINAGE_SIMULE]
        corps = webhook['post']['requestBody']['content']['application/json']
        proprietes = set(corps['schema']['properties'])
        self.assertEqual(proprietes, set(CLES_CHARGE_SIMULE) | {'event_id'})

    def test_le_schema_ne_publie_ni_prix_ni_marge(self):
        from .openapi import build_openapi_schema

        blob = json.dumps(build_openapi_schema())
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)


# ═══════════════════════════════════════════════════════════════════════════
# 2. LES TROIS ÉTATS SERVIS PAR LE MODULE (contrat calepinage_resultat.json)
# ═══════════════════════════════════════════════════════════════════════════

class EtatsServisTests(SimpleTestCase):
    def test_simule_les_grandeurs_sont_celles_du_resultat(self):
        servi = CONTRAT_RESULTAT['exemple']
        total = servi['production']['total']
        data = _publie(servi)
        self.assertEqual(tuple(data), CHAMPS)
        self.assertTrue(data['simule'])
        self.assertEqual(data['p50_kwh'], total['p50_kwh'])
        self.assertEqual(data['production_annuelle_kwh'], total['p50_kwh'])
        self.assertEqual(data['p75_kwh'], total['p75_kwh'])
        self.assertEqual(data['p90_kwh'], total['p90_kwh'])
        self.assertEqual(data['ratio_performance'],
                         total['performance_ratio'])
        self.assertEqual(data['rendement_specifique_kwh_kwc'],
                         total['specific_yield_kwh_kwc'])
        self.assertEqual(data['calcule_le'], servi['calcule_le'])
        self.assertFalse(data['simulation_perimee'])
        self.assertEqual(data['motif'], '')

    def test_les_postes_sont_la_cascade_appliquee(self):
        servi = CONTRAT_RESULTAT['exemple']
        data = _publie(servi)
        etapes = servi['cascade']['etapes']
        self.assertEqual([p['code'] for p in data['pertes']],
                         [e['etape'] for e in etapes])
        for poste, etape in zip(data['pertes'], etapes):
            self.assertEqual(tuple(poste), CHAMPS_POSTE)
            self.assertEqual(poste['libelle'], etape['libelle'])
            self.assertEqual(poste['pourcentage'], etape['perte_pct'])
            self.assertEqual(poste['source'], etape['source'])
        omises = [p for p in data['pertes'] if p['pourcentage'] is None]
        for poste in omises:
            self.assertTrue(poste['motif'].strip(), poste)

    def test_sans_cascade_la_liste_plate_des_postes_est_publiee(self):
        servi = copy.deepcopy(CONTRAT_RESULTAT['exemple'])
        servi['cascade'] = None
        data = _publie(servi)
        self.assertEqual([p['code'] for p in data['pertes']],
                         [p['poste'] for p in servi['pertes']])
        self.assertEqual(data['pertes'][0]['pourcentage'],
                         servi['pertes'][0]['pct'])
        self.assertEqual(data['pertes'][0]['source'],
                         servi['pertes'][0]['source'])

    def test_jamais_simule_tout_est_null_avec_le_motif(self):
        data = _publie(CONTRAT_RESULTAT['exemple_vide'])
        self.assertFalse(data['simule'])
        for cle in GRANDEURS:
            self.assertIsNone(data[cle], cle)
        self.assertIsNone(data['pertes'])
        self.assertIsNone(data['calcule_le'])
        self.assertEqual(data['motif'], MOTIF_RESULTAT_NON_SIMULE)
        # Le squelette du module porte kWc — la pose est un fait — mais une
        # grandeur de production non calculée ne devient JAMAIS 0.
        self.assertNotIn(0, [data[cle] for cle in GRANDEURS])

    def test_perime_tout_est_null_et_le_motif_nomme_la_peremption(self):
        servi = CONTRAT_RESULTAT['exemple_perime']
        data = _publie(servi)
        self.assertFalse(data['simule'])
        self.assertTrue(data['simulation_perimee'])
        for cle in GRANDEURS:
            self.assertIsNone(data[cle], cle)
        self.assertIsNone(data['pertes'])
        self.assertEqual(data['motif'], servi['motif'])
        self.assertIn('périmée', data['motif'])

    def test_rien_de_ce_qui_est_interdit_ne_sort(self):
        servi = copy.deepcopy(CONTRAT_RESULTAT['exemple'])
        servi['roof_layout'] = {'zones': [{'label': 'GEOMETRIE-SECRETE'}]}
        servi['serie_horaire'] = {'points': [{'p_ac_kw': 424242.0}]}
        servi['rangees'] = [{'surface': 'PAN-SECRET'}]
        data = _publie(servi)
        texte = json.dumps(data, ensure_ascii=False)
        for secret in ('GEOMETRIE-SECRETE', 'PAN-SECRET', '424242'):
            self.assertNotIn(secret, texte)
        for cle in data:
            for interdit in INTERDITS:
                self.assertNotEqual(cle, interdit)
            self.assertFalse(cle.startswith(('prix', 'cout', 'marge')), cle)


# ═══════════════════════════════════════════════════════════════════════════
# 3. DE BOUT EN BOUT SANS BASE — le résultat RÉELLEMENT servi par le module
# ═══════════════════════════════════════════════════════════════════════════

class ChaineDuModuleTests(SimpleTestCase):
    """``resultat_calepinage`` (CALX70) → aplatissement public → serializer.

    Le pivot et le matériel viennent du harnais de CALX70 : aucune base.
    """

    def _harnais(self):
        from apps.calepinage.tests import (
            test_calx70_resultat_sert_la_simulation as calx70,
        )
        return calx70

    def test_une_simulation_fraiche_est_publiee(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        calx70 = self._harnais()
        empreinte = calx70._empreinte_du_document(calx70.LAYOUT)
        pivot = calx70._Calepinage(
            calx70.LAYOUT, resultat=calx70._document_simule(empreinte))
        data = _publie(resultat_calepinage(pivot, materiel=calx70.MATERIEL),
                       calepinage_id=1)
        attendu = SIMULATION['exemple']['production']['total']
        self.assertTrue(data['simule'])
        self.assertEqual(data['p50_kwh'], attendu['p50_kwh'])
        self.assertEqual(data['p90_kwh'], attendu['p90_kwh'])
        self.assertEqual(data['calcule_le'], '2026-09-19T11:30:00Z')
        # La série horaire est DANS le document déposé ; elle ne sort pas.
        self.assertNotIn('serie_horaire', json.dumps(data))

    def test_un_document_modifie_depuis_le_calcul_ne_publie_rien(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        calx70 = self._harnais()
        empreinte = calx70._empreinte_du_document(calx70.LAYOUT)
        pivot = calx70._Calepinage(
            calx70.LAYOUT_MODIFIE,
            resultat=calx70._document_simule(empreinte))
        data = _publie(resultat_calepinage(pivot, materiel=calx70.MATERIEL),
                       calepinage_id=1)
        self.assertFalse(data['simule'])
        self.assertTrue(data['simulation_perimee'])
        for cle in GRANDEURS:
            self.assertIsNone(data[cle], cle)
        self.assertIn('19/09/2026', data['motif'])

    def test_le_selecteur_rend_un_refus_nomme_sans_exception(self):
        from apps.calepinage import selectors
        from apps.calepinage.services import electrique

        refus = electrique.TemperaturesInvalides('températures illisibles')
        with mock.patch.object(electrique, 'resultat_calepinage',
                               side_effect=refus):
            servi = selectors.resultat_servi(object())
        data = _publie(servi)
        self.assertFalse(data['simule'])
        self.assertEqual(data['motif'], 'températures illisibles')
        for cle in GRANDEURS:
            self.assertIsNone(data[cle], cle)


# ═══════════════════════════════════════════════════════════════════════════
# 4. LA VUE — portée, société, périmètre (docstring = contrat écrit)
# ═══════════════════════════════════════════════════════════════════════════

class VueDocumenteeTests(SimpleTestCase):
    def test_la_docstring_nomme_la_portee_future_et_la_serie_horaire(self):
        from .public_views import PublicCalepinageViewSet

        texte = PublicCalepinageViewSet.resultat.__doc__
        self.assertIn('read:calepinages', texte)
        self.assertIn('calepinages:simuler', texte)
        self.assertIn("n'est PAS créée", texte)
        self.assertIn('run_design_automation', texte)
        self.assertIn('LA SÉRIE HORAIRE N\'EST PAS PUBLIÉE ICI', texte)

    def test_la_portee_future_n_existe_pas(self):
        from .constants import ALL_SCOPES

        self.assertNotIn('calepinages:simuler', ALL_SCOPES)

    def test_la_sous_ressource_est_en_lecture_seule(self):
        from .public_views import PublicCalepinageViewSet

        action = PublicCalepinageViewSet.resultat
        self.assertEqual(set(action.mapping), {'get'})
        self.assertTrue(action.detail)
        self.assertEqual(action.url_path, 'resultat')
        self.assertEqual(PublicCalepinageViewSet.required_scope,
                         SCOPE_READ_CALEPINAGES)


# ═══════════════════════════════════════════════════════════════════════════
# 5. PAR HTTP, EN BASE (CI) — clé, scope, société, fuite
# ═══════════════════════════════════════════════════════════════════════════

class ResultatPublicEnBaseTests(TestCase):
    def setUp(self):
        from authentication.models import Company

        from .models import ApiKey

        self.co_a, _ = Company.objects.get_or_create(
            slug='pa-calx369-a', defaults={'nom': 'PA CALX369 A'})
        self.co_b, _ = Company.objects.get_or_create(
            slug='pa-calx369-b', defaults={'nom': 'PA CALX369 B'})
        _cle, self.brute = ApiKey.issue(
            company=self.co_a, label='A', scopes=[SCOPE_READ_CALEPINAGES])
        modele = django_apps.get_model('calepinage', 'Calepinage')
        from apps.calepinage.tests import (
            test_calx70_resultat_sert_la_simulation as calx70,
        )
        self.calx70 = calx70
        self.cal = modele.objects.create(
            company=self.co_a, lead_id=1, titre='Toiture A',
            roof_layout=calx70.LAYOUT, layout_hash='a' * 64)
        self.cal_b = modele.objects.create(
            company=self.co_b, lead_id=2, titre='Toiture B')

    def _client(self, brute=None):
        from rest_framework.test import APIClient

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute or self.brute}')
        return client

    def _url(self, calepinage):
        return f'/api/public/v1/calepinages/{calepinage.pk}/resultat/'

    def test_jamais_simule_null_et_motif(self):
        resp = self._client().get(self._url(self.cal))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(tuple(resp.data), CHAMPS)
        self.assertFalse(resp.data['simule'])
        for cle in GRANDEURS:
            self.assertIsNone(resp.data[cle], cle)
        self.assertTrue(resp.data['motif'])

    def test_simulation_fraiche_publiee_sans_geometrie_ni_cout(self):
        from apps.calepinage.selectors import resultat_servi

        empreinte = resultat_servi(self.cal)['hash_entree']
        depose = self.calx70._document_simule(empreinte)
        depose['rangees'] = [{'surface': 'PAN-SECRET'}]
        self.cal.resultat = depose
        self.cal.save(update_fields=['resultat'])

        resp = self._client().get(self._url(self.cal))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['simule'])
        self.assertEqual(
            resp.data['p50_kwh'],
            SIMULATION['exemple']['production']['total']['p50_kwh'])
        brut = resp.content.decode('utf-8')
        for secret in ('PAN-SECRET', 'roof_layout', 'prix_achat',
                       'serie_horaire', 'PAN-A'):
            self.assertNotIn(secret, brut)

    def test_scope_requis(self):
        from .constants import SCOPE_READ_LEADS
        from .models import ApiKey

        _cle, brute = ApiKey.issue(company=self.co_a, label='sans',
                                   scopes=[SCOPE_READ_LEADS])
        resp = self._client(brute).get(self._url(self.cal))
        self.assertEqual(resp.status_code, 403)

    def test_calepinage_d_une_autre_societe_introuvable(self):
        resp = self._client().get(self._url(self.cal_b))
        self.assertEqual(resp.status_code, 404)

    def test_aucune_ecriture_par_cette_porte(self):
        resp = self._client().post(self._url(self.cal), {}, format='json')
        self.assertEqual(resp.status_code, 405)
