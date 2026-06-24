"""Tests PAIE13 — Salaire de base multi-profils + proration.

Couvre :
* ``calculer_salaire_base_periode`` pour les quatre types de rémunération :
  mensuel, journalier, forfait, horaire.
* Proration sur période incomplète (absences) pour mensuel, journalier, horaire.
* Heures travaillées déclarées (ElementVariable.TYPE_HEURES) pour horaire et
  journalier.
* Intégration dans ``calculer_bulletin`` : le salaire proraté remplace le
  salaire brut fixe.
* Les champs ``jours_travail_mensuel`` / ``heures_travail_mensuel`` sont
  exposés par l'API ProfilPaie et éditables.
* Isolation multi-tenant : un utilisateur de la société B ne voit pas les
  données de la société A.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    calculer_salaire_base_periode,
    ensure_defaults,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_dossier(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='Emp')


def make_profil(company, dossier, type_rem, salaire_base,
                jours=26, heures=191):
    return ProfilPaie.objects.create(
        company=company,
        employe=dossier,
        type_remuneration=type_rem,
        salaire_base=salaire_base,
        jours_travail_mensuel=jours,
        heures_travail_mensuel=heures,
    )


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


def add_element(company, periode, profil, type_, quantite=0, montant=0,
                libelle=''):
    return ElementVariable.objects.create(
        company=company, periode=periode, profil=profil,
        type=type_, quantite=quantite, montant=montant,
        libelle=libelle, source=ElementVariable.SOURCE_MANUEL)


# ── Tests unitaires de calculer_salaire_base_periode ───────────────────────

class SalaireBaseMensuelTests(TestCase):
    """Type MENSUEL — proration par jours d'absence."""

    def setUp(self):
        self.co = make_company('paie-sb-m', 'Mensuel')
        d = make_dossier(self.co, 'M1')
        self.profil = make_profil(
            self.co, d, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), jours=26)
        self.periode = make_periode(self.co, 2026, 1)

    def test_mois_complet_sans_absence(self):
        """Mois plein → salaire intégral."""
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=[])
        self.assertEqual(result, Decimal('10000.00'))

    def test_proration_absences(self):
        """5 jours d'absence sur 26 → proration 21/26."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=5)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        # 10000 × 21/26 = 8076.923... ≈ 8076.92
        expected = (Decimal('10000') * Decimal('21') / Decimal('26'))
        from decimal import ROUND_HALF_UP
        expected = expected.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(result, expected)

    def test_absences_superieures_normes_borne_zero(self):
        """Plus d'absences que de jours normes → 0 (jamais négatif)."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=30)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('0.00'))


class SalaireBaseForfaitTests(TestCase):
    """Type FORFAIT — montant fixe, aucune proration."""

    def setUp(self):
        self.co = make_company('paie-sb-f', 'Forfait')
        d = make_dossier(self.co, 'F1')
        self.profil = make_profil(
            self.co, d, ProfilPaie.TYPE_FORFAIT,
            salaire_base=Decimal('15000'))
        self.periode = make_periode(self.co, 2026, 2)

    def test_forfait_pas_de_proration(self):
        """Absences ignorées pour un forfait."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=10)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('15000.00'))

    def test_forfait_sans_absences(self):
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=[])
        self.assertEqual(result, Decimal('15000.00'))


class SalaireBaseJournalierTests(TestCase):
    """Type JOURNALIER — taux journalier × jours effectifs."""

    def setUp(self):
        self.co = make_company('paie-sb-j', 'Journalier')
        d = make_dossier(self.co, 'J1')
        # Taux journalier : 500 MAD/jour, norme 26 j/mois
        self.profil = make_profil(
            self.co, d, ProfilPaie.TYPE_JOURNALIER,
            salaire_base=Decimal('500'), jours=26)
        self.periode = make_periode(self.co, 2026, 3)

    def test_mois_complet_sans_absence(self):
        """26 jours × 500 = 13 000."""
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=[])
        self.assertEqual(result, Decimal('13000.00'))

    def test_proration_absences(self):
        """5 jours d'absence → 21 jours × 500 = 10 500."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=5)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('10500.00'))

    def test_heures_travaillees_converties_en_jours(self):
        """Déclaration de 130 heures travaillées (norme 191 h / 26 j ≈ 7.35 h/j)
        → 130 / 7.346... ≈ 17.7 jours × 500 MAD."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_HEURES, quantite=Decimal('130'))
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        # 130 / (191/26) × 500
        ratio = Decimal('191') / Decimal('26')
        jours = Decimal('130') / ratio
        expected_brut = Decimal('500') * jours
        from decimal import ROUND_HALF_UP
        expected = expected_brut.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(result, expected)

    def test_journalier_zero_si_toutes_absences(self):
        """Plus d'absences que de jours normes → 0."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=30)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('0.00'))


class SalaireBaseHoraireTests(TestCase):
    """Type HORAIRE — taux horaire × heures effectivement travaillées."""

    def setUp(self):
        self.co = make_company('paie-sb-h', 'Horaire')
        d = make_dossier(self.co, 'H1')
        # Taux horaire : 60 MAD/h, norme 191 h/mois, 26 j/mois
        self.profil = make_profil(
            self.co, d, ProfilPaie.TYPE_HORAIRE,
            salaire_base=Decimal('60'), jours=26, heures=191)
        self.periode = make_periode(self.co, 2026, 4)

    def test_mois_complet_sans_absence(self):
        """191 h × 60 = 11 460."""
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=[])
        self.assertEqual(result, Decimal('11460.00'))

    def test_heures_travaillees_declarees(self):
        """150 heures déclarées × 60 = 9 000."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_HEURES, quantite=Decimal('150'))
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('9000.00'))

    def test_proration_absences_en_heures(self):
        """3 jours d'absence (3 × 191/26 ≈ 22.04 h) → 191 − 22.04 h × 60."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_ABSENCE, quantite=3)
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        ratio = Decimal('191') / Decimal('26')
        heures_abs = Decimal('3') * ratio
        heures_eff = max(Decimal('0'), Decimal('191') - heures_abs)
        from decimal import ROUND_HALF_UP
        expected = (Decimal('60') * heures_eff).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(result, expected)

    def test_horaire_zero_si_zero_heures(self):
        """0 heures déclarées → 0 brut."""
        add_element(self.co, self.periode, self.profil,
                    ElementVariable.TYPE_HEURES, quantite=Decimal('0'))
        elements = list(ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil))
        result = calculer_salaire_base_periode(
            self.profil, self.periode, elements=elements)
        self.assertEqual(result, Decimal('0.00'))


# ── Intégration dans calculer_bulletin ────────────────────────────────────

class SalaireBaseBulletinIntegrationTests(TestCase):
    """Vérifie que calculer_bulletin utilise le salaire proraté (PAIE13)."""

    def setUp(self):
        self.co = make_company('paie-sb-int', 'Integration')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'INT1')
        self.periode = make_periode(self.co, 2026, 6)

    def test_bulletin_mensuel_avec_absence_reduit_brut(self):
        """Bulletin mensuel avec 5 j d'absence → brut réduit."""
        profil = make_profil(
            self.co, self.dossier, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), jours=26)
        add_element(self.co, self.periode, profil,
                    ElementVariable.TYPE_ABSENCE, quantite=5)
        res = calculer_bulletin(profil, self.periode)
        # brut = 10000 × 21/26 ≈ 8076.92
        from decimal import ROUND_HALF_UP
        expected_sb = (
            Decimal('10000') * Decimal('21') / Decimal('26')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(res['brut'], expected_sb)
        self.assertLess(res['brut'], Decimal('10000'))

    def test_bulletin_journalier_brut_taux_fois_jours(self):
        """Bulletin journalier (500 × 26) → brut = 13 000."""
        dossier2 = make_dossier(self.co, 'INT2')
        profil = make_profil(
            self.co, dossier2, ProfilPaie.TYPE_JOURNALIER,
            salaire_base=Decimal('500'), jours=26)
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['brut'], Decimal('13000.00'))

    def test_bulletin_forfait_brut_inchange(self):
        """Bulletin forfait avec absences → brut inchangé."""
        dossier3 = make_dossier(self.co, 'INT3')
        profil = make_profil(
            self.co, dossier3, ProfilPaie.TYPE_FORFAIT,
            salaire_base=Decimal('12000'))
        add_element(self.co, self.periode, profil,
                    ElementVariable.TYPE_ABSENCE, quantite=8)
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['brut'], Decimal('12000.00'))

    def test_bulletin_horaire_brut_taux_fois_heures(self):
        """Bulletin horaire (60 × 150 h) → brut = 9 000."""
        dossier4 = make_dossier(self.co, 'INT4')
        profil = make_profil(
            self.co, dossier4, ProfilPaie.TYPE_HORAIRE,
            salaire_base=Decimal('60'), heures=191)
        add_element(self.co, self.periode, profil,
                    ElementVariable.TYPE_HEURES, quantite=Decimal('150'))
        res = calculer_bulletin(profil, self.periode)
        self.assertEqual(res['brut'], Decimal('9000.00'))


# ── API — champs jours/heures exposés et éditables ─────────────────────────

class ProfilPaieNormesAPITests(TestCase):
    """PAIE13 — jours_travail_mensuel et heures_travail_mensuel sur l'API."""
    BASE = '/api/django/paie/profils/'

    def setUp(self):
        self.co = make_company('paie-sb-api', 'API')
        self.user = make_user(self.co, 'paie-sb-api')
        self.dossier = make_dossier(self.co, 'API1')

    def test_create_avec_normes_personnalisees(self):
        api = auth_client(self.user)
        resp = api.post(self.BASE, {
            'employe': self.dossier.id,
            'type_remuneration': 'horaire',
            'salaire_base': '75.00',
            'jours_travail_mensuel': 22,
            'heures_travail_mensuel': 176,
            'affilie_cnss': True,
            'affilie_amo': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['jours_travail_mensuel'], 22)
        self.assertEqual(resp.data['heures_travail_mensuel'], 176)
        obj = ProfilPaie.objects.get(id=resp.data['id'])
        self.assertEqual(obj.jours_travail_mensuel, 22)
        self.assertEqual(obj.heures_travail_mensuel, 176)

    def test_normes_defaut_dans_response(self):
        api = auth_client(self.user)
        resp = api.post(self.BASE, {
            'employe': self.dossier.id,
            'type_remuneration': 'mensuel',
            'salaire_base': '8000.00',
            'affilie_cnss': True,
            'affilie_amo': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['jours_travail_mensuel'], 26)
        self.assertEqual(resp.data['heures_travail_mensuel'], 191)

    def test_patch_normes(self):
        profil = make_profil(
            self.co, self.dossier, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        api = auth_client(self.user)
        resp = api.patch(f'{self.BASE}{profil.id}/', {
            'jours_travail_mensuel': 20,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['jours_travail_mensuel'], 20)


# ── Isolation multi-tenant ─────────────────────────────────────────────────

class SalaireBaseIsolationTests(TestCase):
    """Un utilisateur de la société B ne doit pas voir les profils de A."""

    def setUp(self):
        self.co_a = make_company('paie-sb-isol-a', 'A')
        self.co_b = make_company('paie-sb-isol-b', 'B')
        self.user_a = make_user(self.co_a, 'paie-sb-isol-a')
        self.user_b = make_user(self.co_b, 'paie-sb-isol-b')
        self.dossier_a = make_dossier(self.co_a, 'ISO-A1')

    def test_profil_societe_a_invisible_depuis_b(self):
        profil = make_profil(
            self.co_a, self.dossier_a, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        api = auth_client(self.user_b)
        resp = api.get('/api/django/paie/profils/')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in (
            resp.data.get('results', resp.data)
            if isinstance(resp.data, dict) else resp.data
        )]
        self.assertNotIn(profil.id, ids)

    def test_calcul_salaire_scopé_société(self):
        """calculer_salaire_base_periode fonctionne pour les données de la
        société A sans interférence de B."""
        dossier_b = make_dossier(self.co_b, 'ISO-B1')
        profil_a = make_profil(
            self.co_a, self.dossier_a, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))
        profil_b = make_profil(
            self.co_b, dossier_b, ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('5000'))
        periode_a = make_periode(self.co_a, 2026, 5)
        periode_b = PeriodePaie.objects.create(
            company=self.co_b, annee=2026, mois=5)
        # Absence dans B n'affecte pas A.
        add_element(self.co_b, periode_b, profil_b,
                    ElementVariable.TYPE_ABSENCE, quantite=10)
        res_a = calculer_salaire_base_periode(profil_a, periode_a)
        res_b = calculer_salaire_base_periode(profil_b, periode_b)
        self.assertEqual(res_a, Decimal('10000.00'))
        self.assertLess(res_b, Decimal('5000'))
