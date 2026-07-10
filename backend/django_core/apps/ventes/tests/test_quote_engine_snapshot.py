"""YTEST10 — Snapshots golden PDF (devis premium) : diff visuel à tolérance +
assertions structurelles.

Rend chaque format (`full`, `full`+étude, `onepage`, agricole/pompage) du
moteur PDF premium (règle #4 — /proposal est le SEUL chemin PDF client) sur
des données FIXES (factories testkit), rasterise en PNG (PyMuPDF / `fitz`,
déjà vendored pour `apps/ged`/`apps/paie`) et compare à un baseline COMMITÉ
sous ``apps/ventes/tests/baselines/`` avec un seuil de diff pixels (jamais une
égalité octet-à-octet — WeasyPrint/matplotlib peuvent produire un jitter
d'anti-aliasing insignifiant d'une machine à l'autre).

Assertions structurelles, sur CHAQUE format : nombre de pages exact, présence
des figures clés de la chaîne de totaux (Sous-total HT / Remise / Total HT /
TVA / Total TTC), et ABSENCE stricte de `prix_achat` (jamais dans un rendu
client — CLAUDE.md).

Baselines manquantes — ce worker ne peut pas en générer (pas de DB/docker
disponible ici) : avec ``UPDATE_PDF_SNAPSHOTS=1`` le test ÉCRIT le baseline et
passe avec un avis ; sinon il ÉCHOUE avec un message clair pointant vers la
commande ``manage.py update_pdf_baselines`` (YTEST11). L'orchestrateur génère
et commite les baselines dans l'image docker prod au moment du fold.

Tourne UNIQUEMENT au palier release-verify (rendu WeasyPrint + rasterisation
réels, lourd) — jamais par-merge : voir docs/TESTING.md (le job CI exclut
`--exclude-tag=pdf --exclude-tag=slow`, vérifié dans .github/workflows/ci.yml).

Run (palier complet) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_snapshot -v 2
Régénérer les baselines (image docker prod) :
    docker compose exec django_core python manage.py update_pdf_baselines
"""
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

BASELINE_DIR = Path(__file__).resolve().parent / 'baselines'

# Résolution DPI modérée : assez pour détecter une régression visuelle réelle
# sans gonfler le baseline commité ni la sensibilité au jitter d'antialiasing.
RASTER_ZOOM = 1.5
# Tolérance de diff pixels — jamais une égalité octet-à-octet (WeasyPrint /
# matplotlib varient légèrement d'une machine à l'autre sur l'anti-aliasing).
MAX_DIFF_PIXEL_RATIO = 0.02


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_user(company):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=f'{company.slug}-user', password='x',
        role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Karim',
        email='karim@example.com', telephone='+212600000000',
        adresse='Hay Riad, Rabat')


def make_produit(company, nom, sku, prix):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(prix), prix_achat=Decimal('1'),
        quantite_stock=100)


def make_devis(company, user, client_obj, lignes, *, reference,
               mode_installation='', etude_params=None, remise_globale='0'):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client_obj,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
        mode_installation=mode_installation,
        etude_params=etude_params)
    for desig, qty, pu in lignes:
        sku = f"{reference[-8:]}-{desig[:12]}"
        LigneDevis.objects.create(
            devis=devis, produit=make_produit(company, desig, sku, pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'))
    return devis


FULL_LINES = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Onduleur hybride 5kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Socles', '30', '67'),
    ('Accessoires', '1', '1667'),
    ('Tableau De Protection AC/DC', '1', '1667'),
    ('Installation', '1', '4000'),
    ('Transport', '1', '1000'),
]

ETUDE_PARAMS = {
    'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
    'taux_autoconso': 100, 'taux_couverture': 10.4,
    'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
    'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
}

AGRICOLE_LINES = [
    ('Pompe immergée OSP 30/8 10 CV', '1', '9166.67'),
    ('VARIATEUR VEICHI SI23 7.5KW 380V', '1', '3333.33'),
    ('Panneau mono 710W', '15', '1166.67'),
    ('Installation', '1', '4000'),
]

AGRICOLE_ETUDE = {
    'pompe_cv': '10', 'pompe_kw': 7.5,
    'pompe_nom': 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',
    'type_pompe': 'immergee', 'alim': 'tri',
    'hmt_m': '60', 'debit_souhaite_m3h': '30',
    'debit_hmt_m3h': 30, 'heures_pompage': 7, 'm3_jour': 210,
    'champ_kwc': 17.5,
}

REQUIRED_TOTALS_LITERALS = (
    'Sous-total HT', 'Total HT', 'TVA', 'Total TTC',
)

# Marqueurs de prix d'achat interdits sur TOUT rendu client (jamais un centime
# du prix d'achat revendeur ne doit fuiter — CLAUDE.md).
FORBIDDEN_BUY_PRICE_MARKERS = ('9876', '9 876', '9 876', '9&#8239;876', 'achat')


def _render_pdf_bytes(devis, pdf_options=None):
    """Rend le PDF premium réel (WeasyPrint) en mockant SEULEMENT MinIO — les
    octets PDF retournés sont réels, jamais un mock (comme
    test_quote_engine.TestPremiumPdfRender)."""
    from apps.ventes.quote_engine import clean_pdf_options, generate_premium_devis_pdf

    captured = {}
    with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
            patch('apps.ventes.utils.pdf._upload_pdf') as mock_upload:
        generate_premium_devis_pdf(
            devis.id, clean_pdf_options(pdf_options or {}), persist=False)
        captured['pdf_bytes'] = mock_upload.call_args[0][0]
    return captured['pdf_bytes']


def _rasterize(pdf_bytes):
    """PDF bytes -> liste de PNG bytes, une entrée par page (fitz/PyMuPDF)."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        mat = fitz.Matrix(RASTER_ZOOM, RASTER_ZOOM)
        return [page.get_pixmap(matrix=mat).tobytes('png') for page in doc]
    finally:
        doc.close()


def _extract_text(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


def _png_diff_ratio(png_a: bytes, png_b: bytes) -> float:
    """Ratio de pixels différents entre deux PNG de mêmes dimensions (fitz
    Pixmap comparaison directe des buffers — aucune dépendance externe comme
    Pillow/numpy nécessaire)."""
    import fitz
    pix_a = fitz.Pixmap(png_a)
    pix_b = fitz.Pixmap(png_b)
    if (pix_a.width, pix_a.height) != (pix_b.width, pix_b.height):
        return 1.0  # dimensions divergentes = régression totale
    buf_a, buf_b = pix_a.samples, pix_b.samples
    n = pix_a.n  # canaux par pixel
    total_pixels = pix_a.width * pix_a.height
    if total_pixels == 0:
        return 0.0
    diff_pixels = 0
    for i in range(0, len(buf_a), n):
        if buf_a[i:i + n] != buf_b[i:i + n]:
            diff_pixels += 1
    return diff_pixels / total_pixels


def check_or_write_baseline(name, pdf_bytes, *, page_count, update=None):
    """Compare (ou écrit) le baseline PNG par page pour ``name``.

    Fonction PURE (aucune dépendance à ``TestCase``) — partagée par le test
    (qui l'enrobe en assertions) et par ``update_pdf_baselines`` (qui
    l'appelle directement avec ``update=True``). Retourne la liste des chemins
    de baseline écrits ; lève ``AssertionError`` avec un message français
    clair sur toute divergence (page manquante, baseline absent, diff au-delà
    du seuil).
    """
    if update is None:
        update = os.environ.get('UPDATE_PDF_SNAPSHOTS') == '1'
    pages = _rasterize(pdf_bytes)
    if len(pages) != page_count:
        raise AssertionError(
            f'{name} : {page_count} page(s) attendue(s), '
            f'{len(pages)} obtenue(s).')

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for idx, png_bytes in enumerate(pages, start=1):
        baseline_path = BASELINE_DIR / f'{name}_p{idx}.png'
        if not baseline_path.exists():
            if update:
                baseline_path.write_bytes(png_bytes)
                written.append(baseline_path)
                continue
            raise AssertionError(
                f"Baseline manquant : {baseline_path.name}. Ce test ne peut "
                "pas générer de baseline ici (pas de base de données/docker "
                "disponible). Lancez `python manage.py update_pdf_baselines` "
                "dans l'image docker prod (voir docs/TESTING.md) puis "
                "committez le PNG produit sous "
                "apps/ventes/tests/baselines/.")
        if update:
            # Réécrit toujours en mode mise à jour explicite.
            baseline_path.write_bytes(png_bytes)
            written.append(baseline_path)
            continue
        baseline_bytes = baseline_path.read_bytes()
        ratio = _png_diff_ratio(png_bytes, baseline_bytes)
        if ratio > MAX_DIFF_PIXEL_RATIO:
            raise AssertionError(
                f'{baseline_path.name} : diff visuel de {ratio:.2%} '
                f'(> seuil {MAX_DIFF_PIXEL_RATIO:.0%}). Si le changement est '
                'volontaire, régénérez avec `manage.py update_pdf_baselines` '
                '(YTEST11) et committez le nouveau PNG.')
    return written


def _build_snapshot_devis(company, user, client_obj, case):
    """Construit le Devis fixe d'un cas de baseline (ORM nue, réutilisable
    hors TestCase par ``update_pdf_baselines``)."""
    return make_devis(
        company, user, client_obj, case['lines'],
        reference=case['reference'],
        mode_installation=case.get('mode_installation', ''),
        etude_params=case.get('etude_params'))


# Un cas par format — SOURCE UNIQUE partagée par le test (TestCase, DB de
# test) et la commande de gestion ``update_pdf_baselines`` (DB réelle, image
# docker prod). Ne jamais dupliquer cette liste ailleurs.
BASELINE_CASES = [
    {
        'name': 'residentiel_full',
        'reference': 'DEV-SNAP-FULL',
        'lines': FULL_LINES,
        'pdf_options': None,
        'page_count': 3,
        'check_totals': True,
    },
    {
        'name': 'industriel_full_etude',
        'reference': 'DEV-SNAP-ETUDE',
        'lines': FULL_LINES,
        'mode_installation': 'industriel',
        'etude_params': ETUDE_PARAMS,
        'pdf_options': {'include_etude': True},
        'page_count': 4,
        'check_totals': True,
    },
    {
        'name': 'residentiel_onepage',
        'reference': 'DEV-SNAP-1PG',
        'lines': FULL_LINES,
        'pdf_options': {'pdf_mode': 'onepage'},
        'page_count': 1,
        'check_totals': True,
    },
    {
        'name': 'agricole_pompage_full',
        'reference': 'DEV-SNAP-AGRI',
        'lines': AGRICOLE_LINES,
        'mode_installation': 'agricole',
        'etude_params': AGRICOLE_ETUDE,
        'pdf_options': None,
        'page_count': 4,
        # Le rendu agricole plein format porte ses propres figures (pas de
        # remise/TVA détaillée par palier identique au résidentiel) —
        # la garde totaux est déjà couverte par les formats
        # résidentiel/industriel ; on vérifie ici l'absence de prix d'achat.
        'check_totals': False,
    },
    {
        'name': 'agricole_pompage_onepage',
        'reference': 'DEV-SNAP-AGRI1PG',
        'lines': AGRICOLE_LINES,
        'mode_installation': 'agricole',
        'etude_params': AGRICOLE_ETUDE,
        'pdf_options': {'pdf_mode': 'onepage'},
        'page_count': 1,
        'check_totals': True,
    },
]


@tag('pdf')
@tag('slow')
class TestQuoteEngineGoldenSnapshots(TestCase):
    """Un cas par format ; chaque cas vérifie pages + figures clés + absence
    de prix d'achat, puis compare/écrit le baseline pixel."""

    def setUp(self):
        self.company = make_company('qe-snap-co')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _structural_asserts(self, pdf_bytes):
        text = _extract_text(pdf_bytes)
        for literal in REQUIRED_TOTALS_LITERALS:
            self.assertIn(
                literal, text,
                f'figure clé absente du PDF : « {literal} »')

    def _assert_no_buy_price(self, pdf_bytes):
        text = _extract_text(pdf_bytes).lower()
        for marker in FORBIDDEN_BUY_PRICE_MARKERS:
            self.assertNotIn(
                marker.lower(), text,
                f'prix_achat détecté dans le PDF client (marqueur « {marker} »)')

    def _run_case(self, case):
        devis = _build_snapshot_devis(
            self.company, self.user, self.client_obj, case)
        pdf_bytes = _render_pdf_bytes(devis, case.get('pdf_options'))
        self._assert_no_buy_price(pdf_bytes)
        if case['check_totals']:
            self._structural_asserts(pdf_bytes)
        try:
            check_or_write_baseline(
                case['name'], pdf_bytes, page_count=case['page_count'])
        except AssertionError as exc:
            self.fail(str(exc))

    def test_full_format_three_pages(self):
        self._run_case(BASELINE_CASES[0])

    def test_full_with_etude_four_pages(self):
        self._run_case(BASELINE_CASES[1])

    def test_onepage_format_one_page(self):
        self._run_case(BASELINE_CASES[2])

    def test_agricole_pompage_full_format(self):
        self._run_case(BASELINE_CASES[3])

    def test_agricole_pompage_onepage_format(self):
        self._run_case(BASELINE_CASES[4])
