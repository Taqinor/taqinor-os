"""DC5 — CompanyProfile est la SOURCE UNIQUE des repères ROI/tarifaires.

Le tarif ONEE et le productible étaient dupliqués (CompanyProfile vs
TariffSettings). DÉCISION : CompanyProfile est canonique (déjà consommé par le
moteur de devis via DC2). Tout lecteur passe par un accesseur UNIQUE,
``parametres.selectors.tariff_for``, qui lit CompanyProfile — et NON
TariffSettings — pour ces repères. Ces tests verrouillent ce choix.
"""
import itertools
import re
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.parametres.models import CompanyProfile
from apps.parametres.models_tariff import TariffSettings
from apps.parametres.selectors import tariff_for


# Compteur de tenants : une société NEUVE à chaque appel sans slug.
_company_seq = itertools.count(1)


def _company(slug=None, nom=None):
    """Une société neuve par appel — passer ``slug`` pour la nommer.

    Sans compteur, ``get_or_create`` tapait toujours le même slug fixe
    ('dc5-co') : deux appels rendaient la MÊME société, rendant tout
    test cross-tenant vide de sens.
    """
    n = next(_company_seq)
    c, _ = Company.objects.get_or_create(
        slug=slug or f'dc5-co-{n}',
        defaults={'nom': nom or f'DC5 Co {n}'})
    return c


class TestDC5TariffSelector(TestCase):
    def test_tariff_for_reads_company_profile(self):
        company = _company()
        p = CompanyProfile.get(company=company)
        p.onee_tarif_kwh = Decimal('2.10')
        p.productible_kwh_kwc = Decimal('1750.0')
        p.rendement_global = Decimal('0.85')
        p.save()
        t = tariff_for(company)
        self.assertAlmostEqual(t['onee_tarif_kwh'], 2.10, places=3)
        self.assertAlmostEqual(t['productible_kwh_kwc'], 1750.0, places=1)
        self.assertAlmostEqual(t['rendement_global'], 0.85, places=3)

    def test_tariff_for_defaults_when_no_profile_fields(self):
        # profil vierge (défauts du modèle : 1.75 / vide / 0.8) — AMOT64 :
        # productible vide ⇒ None (le moteur lit le PVGIS de la ville).
        t = tariff_for(_company())
        self.assertAlmostEqual(t['onee_tarif_kwh'], 1.75, places=3)
        self.assertIsNone(t['productible_kwh_kwc'])
        self.assertAlmostEqual(t['rendement_global'], 0.8, places=3)

    def test_tariff_settings_edit_does_not_leak_into_tariff_for(self):
        # Le champ TariffSettings.productible_manuel n'est PAS la source du
        # repère ROI du devis : seul CompanyProfile l'est (source unique).
        company = _company()
        ts = TariffSettings.get(company=company)
        ts.productible_manuel_kwh_kwc = Decimal('1234.0')
        ts.save()
        t = tariff_for(company)
        self.assertIsNone(t['productible_kwh_kwc'])


RACINE = Path(__file__).resolve().parents[4]
ECRAN_AVANCE = RACINE / 'frontend' / 'src' / 'pages' / 'parametres' / 'AvanceSection.jsx'


def _textes_lecteurs():
    """Code qui LIT un réglage hors ``parametres`` : backend (apps hors
    parametres, authentication, core — sans migrations ni tests) + écrans
    (frontend/src hors pages/parametres, sans tests)."""
    textes = []
    back = RACINE / 'backend' / 'django_core'
    for dossier in ('apps', 'authentication', 'core'):
        for f in (back / dossier).rglob('*.py'):
            chemin = f.as_posix()
            if ('/apps/parametres/' in chemin or '/migrations/' in chemin
                    or '/tests/' in chemin or f.name.startswith('test')):
                continue
            textes.append(f.read_text(encoding='utf-8', errors='ignore'))
    for f in (RACINE / 'frontend' / 'src').rglob('*'):
        chemin = f.as_posix()
        if ('/pages/parametres/' in chemin or '.test.' in f.name
                or f.suffix not in ('.js', '.jsx', '.ts', '.tsx', '.mjs')):
            continue
        textes.append(f.read_text(encoding='utf-8', errors='ignore'))
    return '\n'.join(textes)


class TestAMOT64ReglagesEcranOntUnLecteur(SimpleTestCase):
    """AMOT64 (D-AMOT-3 = a) — tout champ de ``CompanyProfile`` exposé à
    l'écran Paramètres → Avancé a un lecteur hors ``parametres`` ou est
    étiqueté « repli » ; ``rendement_global`` n'est plus à l'écran."""

    def test_tout_champ_expose_a_un_lecteur_ou_est_un_repli(self):
        ecran = ECRAN_AVANCE.read_text(encoding='utf-8')
        champs = {f.name for f in CompanyProfile._meta.get_fields()}
        exposes = [m for m in re.finditer(r'name="(\w+)"', ecran)
                   if m.group(1) in champs]
        self.assertTrue(exposes, 'aucun champ CompanyProfile trouvé')
        lecteurs = _textes_lecteurs()
        orphelins = []
        for m in exposes:
            nom = m.group(1)
            labels = re.findall(r'label="([^"]*)"', ecran[:m.start()])
            repli = bool(labels) and 'repli' in labels[-1].lower()
            if not repli and not re.search(r'\b%s\b' % nom, lecteurs):
                orphelins.append(nom)
        self.assertEqual(orphelins, [], 'réglages affichés sans lecteur')

    def test_rendement_global_retire_et_tarif_libelle_repli(self):
        ecran = ECRAN_AVANCE.read_text(encoding='utf-8')
        self.assertNotIn('name="rendement_global"', ecran)
        self.assertRegex(
            ecran, r'label="[^"]*repli sans distributeur[^"]*"'
                   r' htmlFor="pe-onee"')
