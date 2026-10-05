"""SPL241 — golden de la découpe de ``public_views.py`` (SPL245-SPL253).

``public_views.py`` (4848 lignes, 16 endpoints publics) est découpé en neuf
régions déplacées vers le sous-paquet ``apps/ventes/public/``. Ce module porte
la preuve « move only » de chaque déplacement, capturée sur le code d'AVANT :

(a) ``golden/split_pv_<region>.json`` — empreinte AST normalisée
    (``split_golden.empreintes`` : ``ImportFrom.level`` ramené à 0) de chaque
    symbole de la région ;
(b) ``DEPLACEMENTS`` — une entrée par région. Tant que son SPL n'a pas atterri
    (``actif=False``), le golden doit rester IDENTIQUE à la source actuelle
    (une tâche étrangère qui édite un symbole avant son déplacement rougit
    ici : recapturer avant de déplacer). Le SPL de la région passe ``actif`` à
    ``True`` dans le MÊME commit que le déplacement : l'entrée est rouge
    avant (symboles encore dans la source), verte après ;
(c) ``golden/split_pv_comportement.json`` — digests de COMPORTEMENT des vues
    publiques (``proposal_data`` standard/confiance/calepinage/kit, ouverture,
    engagement, paiement, OTP) et ensemble des sites d'arrondi
    ``scripts/check_money_rounding`` du groupe ;
(d) le scanner ``core.public_endpoint_scan`` voit les 16 endpoints publics de
    ventes, tous throttlés — un déplacement vers un fichier non scanné est
    ROUGE, jamais silencieux.

Capture du golden de comportement (une fois, sur le code d'avant découpe —
identique après, puisque (a) prouve la copie fidèle) :
    SPLIT_GOLDEN_CAPTURE=1 python manage.py test \\
        apps.ventes.tests.test_split_devis_public.ComportementPublicTests

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_split_devis_public -v 2
"""
import importlib.util
import json
import os
import re
import uuid
from pathlib import Path

from django.forms.models import model_to_dict
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.ventes.tests import split_golden as sg
from apps.ventes.tests.test_l_niv_niveau import (
    add_kit_lines, make_client, make_company, make_devis, make_user,
    sample_layout,
)

SOURCE = 'apps/ventes/public_views.py'
GROUPE = ('public_views.py', 'public/*.py')

#: Une entrée par région : (golden, module cible, SPL qui la déplace, actif).
DEPLACEMENTS = {
    'noyau': ('split_pv_noyau', 'apps/ventes/public/noyau.py', 'SPL245', True),
    'lecture': ('split_pv_lecture', 'apps/ventes/public/lecture_views.py',
                'SPL246', True),
    'horaire': ('split_pv_horaire', 'apps/ventes/public/payload_horaire.py',
                'SPL247', True),
    'batterie': ('split_pv_batterie', 'apps/ventes/public/payload_batterie.py',
                 'SPL248', True),
    'variantes': ('split_pv_variantes',
                  'apps/ventes/public/payload_variantes.py', 'SPL249', False),
    'economie': ('split_pv_economie', 'apps/ventes/public/payload_economie.py',
                 'SPL250', False),
    'conditions': ('split_pv_conditions',
                   'apps/ventes/public/payload_conditions.py', 'SPL251', False),
    'paiement': ('split_pv_paiement', 'apps/ventes/public/paiement_views.py',
                 'SPL252', False),
    'signature': ('split_pv_signature',
                  'apps/ventes/public/signature_views.py', 'SPL253', False),
}

#: Les 16 endpoints publics de ventes (``public_urls.py``), par NOM de vue.
ENDPOINTS_PUBLICS = (
    'public_document', 'public_bcf_document', 'proposal_data', 'proposal_pdf',
    'proposal_taille_detail', 'proposal_contact_request',
    'proposal_request_otp', 'proposal_request_otp_lecture',
    'proposal_verify_otp_lecture', 'proposal_accept',
    'proposal_activate_option', 'proposal_engagement',
    'proposal_virement_declare', 'suivi_public', 'pay_page', 'pay_webhook',
)


class DeplacementsTests(SimpleTestCase):
    """(a)+(b) — identité AST de chaque région, rouge d'abord."""

    def test_neuf_regions_disjointes_et_non_vides(self):
        vus = {}
        for region, (golden, _cible, _spl, _actif) in DEPLACEMENTS.items():
            symboles = sg.charger_golden(golden)
            self.assertTrue(symboles, f'golden {golden} vide')
            for nom in symboles:
                self.assertNotIn(nom, vus, f'{nom} dans {region} et {vus.get(nom)}')
                vus[nom] = region
        self.assertEqual(len(vus), 99)

    def test_regions_en_attente_identiques_a_la_source(self):
        for region, (golden, _cible, spl, actif) in DEPLACEMENTS.items():
            if actif:
                continue
            with self.subTest(region=region, spl=spl):
                attendu = sg.charger_golden(golden)
                self.assertEqual(
                    sg.empreintes(SOURCE, sorted(attendu)), attendu,
                    f'{region} : symbole édité depuis la capture — recapturer '
                    f'le golden AVANT {spl}')

    def test_regions_deplacees_fideles(self):
        for region, (golden, cible, spl, actif) in DEPLACEMENTS.items():
            if not actif:
                continue
            with self.subTest(region=region, spl=spl):
                sg.verifier_deplacement(golden, cible, SOURCE)


class ScannerEndpointsPublicsTests(SimpleTestCase):
    """(d) — les 16 endpoints restent vus ET throttlés par le scanner."""

    def test_seize_endpoints_publics_vus_et_throttles(self):
        from core import public_endpoint_scan

        ventes = {}
        for entree in public_endpoint_scan.public_endpoints():
            fichier, _, nom = entree['id'].partition('::')
            if fichier.startswith('ventes/'):
                ventes[nom] = entree['throttled']
        manquants = sorted(set(ENDPOINTS_PUBLICS) - set(ventes))
        self.assertEqual(manquants, [], 'endpoints publics non scannés')
        non_throttles = sorted(n for n in ENDPOINTS_PUBLICS if not ventes[n])
        self.assertEqual(non_throttles, [])


def _check_money_rounding():
    """Le module ``scripts/check_money_rounding.py`` (dépôt complet : CI, hôte)."""
    for parent in Path(__file__).resolve().parents:
        chemin = parent / 'scripts' / 'check_money_rounding.py'
        if chemin.is_file():
            spec = importlib.util.spec_from_file_location('_cmr_split', chemin)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


def sites_arrondi_du_groupe():
    """Sites d'arrondi du groupe, sans le chemin : ``qualname::hash[#n]``."""
    cmr = _check_money_rounding()
    if cmr is None:
        return None
    sites = []
    for chemin in sg.fichiers_du_groupe(*GROUPE):
        for site in cmr.collect_sites_in_file(chemin):
            sites.append(f'{site.kind}::{site.key.split("::", 1)[1]}')
    return sorted(sites)


class SitesArrondiTests(SimpleTestCase):
    """(c) — les sites d'arrondi voyagent avec leur fonction, inchangés."""

    def test_sites_arrondi_identiques(self):
        sites = sites_arrondi_du_groupe()
        if sites is None:
            self.skipTest('scripts/ absent (harnais docker : backend seul) — '
                          'la CI et l\'hôte ont le dépôt complet')
        self.assertEqual(sites, sg.charger_golden('split_pv_comportement')
                         ['sites_arrondi'])


# ── (c) comportement des vues publiques ───────────────────────────────────
_RE_DATE = re.compile(r'\d{4}-\d{2}-\d{2}([T ][0-9:.]+)?(Z|[+-]\d{2}:?\d{2})?')


#: Clés portant une clé primaire (séquences : varient avec l'ordre des tests).
_CLES_PK = {'devis', 'company', 'client', 'produit', 'lead', 'facture',
            'created_by', 'share_link', 'variante_de', 'remplace_par'}


def _figer(obj):
    """Fige ce qui varie d'un run à l'autre (dates ISO, clés primaires)."""
    if isinstance(obj, dict):
        return {k: ('<id>' if (str(k).endswith('_id') or str(k) in _CLES_PK)
                    and isinstance(v, int) and not isinstance(v, bool)
                    else _figer(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_figer(v) for v in obj]
    if isinstance(obj, str):
        return _RE_DATE.sub('<date>', obj)
    return obj


def _reponse(resp):
    try:
        corps = resp.json()
    except (ValueError, TypeError):
        corps = resp.content.decode('utf-8', 'replace')
    return {'status': resp.status_code, 'corps': _figer(corps)}


class ComportementPublicTests(TestCase):
    """Digests de comportement des vues publiques — identiques avant/après."""

    def setUp(self):
        self.company = make_company('split-pv')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.http = DjangoClient()

    def _lien(self, devis, niveau='standard'):
        from apps.ventes.models import ShareLink
        token = str(uuid.uuid4())
        return ShareLink.objects.create(
            company=self.company, devis=devis, token=token, niveau=niveau)

    def _data(self, lien):
        return self.http.get(f'/api/django/public/proposal/{lien.token}/data/')

    def _scenarios(self):
        res = {}
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-SPLPV-0001')
        lien = self._lien(devis)
        res['data_standard'] = _reponse(self._data(lien))
        lien.refresh_from_db()
        res['ouverture_lien'] = _figer(json.loads(json.dumps(
            {k: v for k, v in model_to_dict(lien).items()
             if not lien._meta.get_field(k).is_relation}, default=str)))
        res['data_standard_reouverture'] = _reponse(self._data(lien))
        res['data_confiance'] = _reponse(self._data(
            self._lien(devis, 'confiance')))

        devis_layout = make_devis(self.company, self.user, self.client_obj,
                                  'DEV-SPLPV-0002', roof_layout=sample_layout())
        res['data_confiance_calepinage'] = _reponse(self._data(
            self._lien(devis_layout, 'confiance')))

        devis_kit = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj, 'DEV-SPLPV-0003'))
        res['data_standard_kit'] = _reponse(self._data(self._lien(devis_kit)))

        res['data_jeton_inconnu'] = _reponse(self.http.get(
            '/api/django/public/proposal/inconnu/data/'))

        url_eng = f'/api/django/public/proposal/{lien.token}/engagement/'
        res['engagement_valide'] = _reponse(self.http.post(
            url_eng, {'section': 'prix', 'seconds': 25, 'visit_id': 'v1'},
            content_type='application/json'))
        res['engagement_section_inconnue'] = _reponse(self.http.post(
            url_eng, {'section': 'inconnue', 'seconds': 5},
            content_type='application/json'))
        lien.refresh_from_db()
        res['engagement_cumul'] = _figer(json.loads(json.dumps(
            lien.engagement, default=str)))

        res['otp_demande'] = _reponse(self.http.post(
            f'/api/django/public/proposal/{lien.token}/otp/', {},
            content_type='application/json'))
        res['pay_page_inconnu'] = _reponse(self.http.get(
            '/api/django/public/pay/inconnu/'))
        res['pay_webhook_inconnu'] = _reponse(self.http.post(
            '/api/django/public/pay/inconnu/webhook/', {},
            content_type='application/json'))
        return res

    def test_digests_identiques(self):
        digests = {nom: sg.digest(val) for nom, val in self._scenarios().items()}
        if os.environ.get('SPLIT_GOLDEN_CAPTURE') == '1':
            golden = sg.charger_golden('split_pv_comportement')
            golden['comportement'] = digests
            sg.ecrire_golden('split_pv_comportement', golden)
        attendu = sg.charger_golden('split_pv_comportement').get('comportement')
        self.assertTrue(
            attendu, 'golden de comportement non capturé : lancer une fois '
            'SPLIT_GOLDEN_CAPTURE=1 sur ce module (voir la docstring)')
        self.assertEqual(digests, attendu)
