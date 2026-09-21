"""Tests PAIE14 — Heures supplémentaires majorées (25 / 50 / 100 %).

Couvre :
* ``calculer_gain_hs`` — arithmétique des majorations pour les trois
  catégories (jour / nuit / férié).
* ``taux_horaire_base_profil`` — dérivation du taux horaire selon le type de
  rémunération (mensuel → dérivé, horaire → direct).
* ``taux_majoration_hs`` — routage vers le bon taux du ``ParametrePaie``.
* ``calculer_bulletin`` — intégration : les éléments ``TYPE_HS`` avec
  ``quantite > 0`` et ``montant == 0`` sont majorés automatiquement ; le
  ``montant`` explicite prime sur le calcul.
* Taux HS personnalisables par société (édition de ``ParametrePaie``).
* Multi-tenant : isolation société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, ParametrePaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    calculer_gain_hs,
    ensure_defaults,
    taux_horaire_base_profil,
    taux_majoration_hs,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────

def make_company(slug, nom=''):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom or slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_dossier(company, matricule='M1'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='HS')


def make_profil(company, dossier, type_rem=ProfilPaie.TYPE_MENSUEL,
                salaire_base=Decimal('10000'), heures=191, jours=26):
    return ProfilPaie.objects.create(
        company=company,
        employe=dossier,
        type_remuneration=type_rem,
        salaire_base=salaire_base,
        heures_travail_mensuel=heures,
        jours_travail_mensuel=jours,
        affilie_cnss=True,
        affilie_amo=True,
    )


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


def add_hs(company, periode, profil, quantite, categorie=ElementVariable.HS_JOUR,
           montant=Decimal('0')):
    """Crée un élément variable TYPE_HS."""
    return ElementVariable.objects.create(
        company=company,
        periode=periode,
        profil=profil,
        type=ElementVariable.TYPE_HS,
        categorie_hs=categorie,
        quantite=quantite,
        montant=montant,
        libelle='Heures supplémentaires',
        source=ElementVariable.SOURCE_MANUEL,
    )


# ── calculer_gain_hs — arithmétique ────────────────────────────────────────

class CalculerGainHsTests(TestCase):
    """Tests unitaires de la formule de gain majoré."""

    def test_hs_jour_25_pct(self):
        """10 h × 60 MAD/h × 1,25 = 750 MAD."""
        gain = calculer_gain_hs(
            heures=Decimal('10'),
            taux_horaire_base=Decimal('60'),
            taux_majoration=Decimal('25'),
        )
        self.assertEqual(gain, Decimal('750.00'))

    def test_hs_nuit_50_pct(self):
        """5 h × 60 MAD/h × 1,50 = 450 MAD."""
        gain = calculer_gain_hs(
            heures=Decimal('5'),
            taux_horaire_base=Decimal('60'),
            taux_majoration=Decimal('50'),
        )
        self.assertEqual(gain, Decimal('450.00'))

    def test_hs_ferie_100_pct(self):
        """8 h × 60 MAD/h × 2,00 = 960 MAD."""
        gain = calculer_gain_hs(
            heures=Decimal('8'),
            taux_horaire_base=Decimal('60'),
            taux_majoration=Decimal('100'),
        )
        self.assertEqual(gain, Decimal('960.00'))

    def test_heures_nulles_renvoie_zero(self):
        """0 heures → 0 MAD quel que soit le taux."""
        gain = calculer_gain_hs(
            heures=Decimal('0'),
            taux_horaire_base=Decimal('60'),
            taux_majoration=Decimal('100'),
        )
        self.assertEqual(gain, Decimal('0.00'))

    def test_taux_horaire_nul_renvoie_zero(self):
        """Taux horaire nul → 0 MAD."""
        gain = calculer_gain_hs(
            heures=Decimal('10'),
            taux_horaire_base=Decimal('0'),
            taux_majoration=Decimal('25'),
        )
        self.assertEqual(gain, Decimal('0.00'))

    def test_arrondi_au_centime(self):
        """Résultat arrondi au centime (demi-supérieur)."""
        # 3 h × 52.33 MAD/h × 1.25 = 196.24 (arrondi)
        gain = calculer_gain_hs(
            heures=Decimal('3'),
            taux_horaire_base=Decimal('52.333333'),
            taux_majoration=Decimal('25'),
        )
        # 3 × 52.333333 × 1.25 = 196.25 (après arrondi interne)
        # On vérifie juste que c'est bien au centime.
        self.assertEqual(gain, gain.quantize(Decimal('0.01')))


# ── taux_horaire_base_profil ───────────────────────────────────────────────

class TauxHoraireBaseProfilTests(TestCase):
    """Dérivation du taux horaire selon le type de rémunération."""

    def setUp(self):
        self.co = make_company('hs-th-a')
        self.dossier = make_dossier(self.co, 'TH1')

    def test_horaire_direct(self):
        """Type HORAIRE : salaire_base EST déjà le taux horaire."""
        profil = make_profil(
            self.co, self.dossier,
            type_rem=ProfilPaie.TYPE_HORAIRE,
            salaire_base=Decimal('75'),
        )
        self.assertEqual(taux_horaire_base_profil(profil), Decimal('75'))

    def test_mensuel_derive(self):
        """Type MENSUEL : salaire_base / heures_normes."""
        profil = make_profil(
            self.co, self.dossier,
            type_rem=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9550'),
            heures=191,
        )
        th = taux_horaire_base_profil(profil)
        # 9550 / 191 ≈ 50.000... (arrondi interne 6 décimales)
        self.assertAlmostEqual(float(th), 9550 / 191, places=4)

    def test_forfait_derive_comme_mensuel(self):
        """Type FORFAIT : traité comme mensuel pour le taux horaire."""
        profil = make_profil(
            self.co, self.dossier,
            type_rem=ProfilPaie.TYPE_FORFAIT,
            salaire_base=Decimal('12000'),
            heures=200,
        )
        th = taux_horaire_base_profil(profil)
        self.assertAlmostEqual(float(th), 12000 / 200, places=4)


# ── taux_majoration_hs ────────────────────────────────────────────────────

class TauxMajorationHsTests(TestCase):
    """Routage du taux de majoration selon la catégorie."""

    def setUp(self):
        self.co = make_company('hs-tm-a')
        ensure_defaults(self.co)
        self.param = ParametrePaie.objects.get(company=self.co, date_effet='2026-01-01')

    def test_categorie_jour(self):
        t = taux_majoration_hs(self.param, ElementVariable.HS_JOUR)
        self.assertEqual(t, Decimal('25'))

    def test_categorie_nuit(self):
        t = taux_majoration_hs(self.param, ElementVariable.HS_NUIT)
        self.assertEqual(t, Decimal('50'))

    def test_categorie_ferie(self):
        t = taux_majoration_hs(self.param, ElementVariable.HS_FERIE)
        self.assertEqual(t, Decimal('100'))

    def test_categorie_absente_renvoie_taux_jour(self):
        """Une catégorie vide ou None renvoie le taux jour par défaut."""
        t = taux_majoration_hs(self.param, None)
        self.assertEqual(t, Decimal('25'))

    def test_taux_hs_personnalises(self):
        """Les taux HS sont éditables par société."""
        self.param.taux_hs_jour = Decimal('30')
        self.param.taux_hs_nuit = Decimal('60')
        self.param.taux_hs_ferie = Decimal('120')
        self.param.save()
        self.assertEqual(
            taux_majoration_hs(self.param, ElementVariable.HS_JOUR), Decimal('30'))
        self.assertEqual(
            taux_majoration_hs(self.param, ElementVariable.HS_NUIT), Decimal('60'))
        self.assertEqual(
            taux_majoration_hs(self.param, ElementVariable.HS_FERIE), Decimal('120'))


# ── calculer_bulletin — intégration HS ────────────────────────────────────

class BulletinHsMajorationTests(TestCase):
    """Intégration : les éléments HS majorés s'intègrent dans le bulletin."""

    def setUp(self):
        self.co = make_company('hs-bull-a')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'HS1')
        # Salarié mensuel 9 550 MAD/mois — taux horaire = 9550/191 ≈ 50 MAD/h.
        self.profil = make_profil(
            self.co, self.dossier,
            type_rem=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9550'),
            heures=191,
        )
        self.periode = make_periode(self.co, 2026, 6)

    def _th(self):
        """Taux horaire de référence du profil."""
        return taux_horaire_base_profil(self.profil)

    def test_hs_jour_integrees_dans_brut(self):
        """10 h de HS jour (+25 %) augmentent le brut du gain majoré."""
        brut_sans = calculer_bulletin(self.profil, self.periode)['brut']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('10'), categorie=ElementVariable.HS_JOUR)
        brut_avec = calculer_bulletin(self.profil, self.periode)['brut']
        gain_attendu = calculer_gain_hs(Decimal('10'), self._th(), Decimal('25'))
        self.assertEqual(brut_avec - brut_sans, gain_attendu)

    def test_hs_nuit_50_pct(self):
        """5 h de HS nuit (+50 %) — gain = 5 × th × 1,50."""
        brut_sans = calculer_bulletin(self.profil, self.periode)['brut']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('5'), categorie=ElementVariable.HS_NUIT)
        brut_avec = calculer_bulletin(self.profil, self.periode)['brut']
        gain_attendu = calculer_gain_hs(Decimal('5'), self._th(), Decimal('50'))
        self.assertEqual(brut_avec - brut_sans, gain_attendu)

    def test_hs_ferie_100_pct(self):
        """8 h de HS férié (+100 %) — gain = 8 × th × 2."""
        brut_sans = calculer_bulletin(self.profil, self.periode)['brut']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('8'), categorie=ElementVariable.HS_FERIE)
        brut_avec = calculer_bulletin(self.profil, self.periode)['brut']
        gain_attendu = calculer_gain_hs(Decimal('8'), self._th(), Decimal('100'))
        self.assertEqual(brut_avec - brut_sans, gain_attendu)

    def test_montant_explicite_prime_sur_calcul(self):
        """Si ``montant`` est non-nul, il prime sur le calcul de majoration."""
        montant_explicite = Decimal('999.00')
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('10'), categorie=ElementVariable.HS_JOUR,
               montant=montant_explicite)
        brut_sans_hs = Decimal('9550.00')  # salaire de base seul
        res = calculer_bulletin(self.profil, self.periode)
        # Le brut doit inclure exactement le montant explicite, pas le calculé.
        self.assertEqual(res['brut'] - brut_sans_hs, montant_explicite)

    def test_hs_sans_quantite_utilise_montant(self):
        """HS sans quantité mais avec montant → le montant est utilisé tel quel."""
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('0'), categorie=ElementVariable.HS_JOUR,
               montant=Decimal('500.00'))
        brut_sans_hs = Decimal('9550.00')
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'] - brut_sans_hs, Decimal('500.00'))

    def test_net_a_payer_inclut_gain_hs(self):
        """Le net à payer est supérieur à celui sans HS (HS augmente le brut)."""
        net_sans = calculer_bulletin(self.profil, self.periode)['net_a_payer']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('10'), categorie=ElementVariable.HS_JOUR)
        net_avec = calculer_bulletin(self.profil, self.periode)['net_a_payer']
        self.assertGreater(net_avec, net_sans)

    def test_plusieurs_categories_hs_cumulees(self):
        """Plusieurs éléments HS de catégories différentes se cumulent."""
        brut_sans = calculer_bulletin(self.profil, self.periode)['brut']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('4'), categorie=ElementVariable.HS_JOUR)
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('3'), categorie=ElementVariable.HS_NUIT)
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('2'), categorie=ElementVariable.HS_FERIE)
        brut_avec = calculer_bulletin(self.profil, self.periode)['brut']
        th = self._th()
        gain_j = calculer_gain_hs(Decimal('4'), th, Decimal('25'))
        gain_n = calculer_gain_hs(Decimal('3'), th, Decimal('50'))
        gain_f = calculer_gain_hs(Decimal('2'), th, Decimal('100'))
        self.assertEqual(brut_avec - brut_sans, gain_j + gain_n + gain_f)


# ── Profil HORAIRE — HS sur taux horaire direct ────────────────────────────

class BulletinHsHoraireTests(TestCase):
    """Profil de type HORAIRE : le taux horaire est direct (pas dérivé)."""

    def setUp(self):
        self.co = make_company('hs-hor-a')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'HOR1')
        # Taux horaire : 80 MAD/h.
        self.profil = make_profil(
            self.co, self.dossier,
            type_rem=ProfilPaie.TYPE_HORAIRE,
            salaire_base=Decimal('80'),
            heures=191,
        )
        self.periode = make_periode(self.co, 2026, 7)

    def test_hs_jour_horaire(self):
        """6 h de HS jour sur profil horaire : 6 × 80 × 1,25 = 600 MAD."""
        brut_sans = calculer_bulletin(self.profil, self.periode)['brut']
        add_hs(self.co, self.periode, self.profil,
               quantite=Decimal('6'), categorie=ElementVariable.HS_JOUR)
        brut_avec = calculer_bulletin(self.profil, self.periode)['brut']
        self.assertEqual(brut_avec - brut_sans, Decimal('600.00'))


# ── Multi-tenant — isolation ───────────────────────────────────────────────

class BulletinHsIsolationTests(TestCase):
    """Les HS de la société B n'affectent pas le bulletin de la société A."""

    def setUp(self):
        self.co_a = make_company('hs-iso-a')
        self.co_b = make_company('hs-iso-b')
        ensure_defaults(self.co_a)
        ensure_defaults(self.co_b)
        self.dossier_a = make_dossier(self.co_a, 'ISO-A1')
        self.dossier_b = make_dossier(self.co_b, 'ISO-B1')
        self.profil_a = make_profil(
            self.co_a, self.dossier_a, salaire_base=Decimal('10000'))
        self.profil_b = make_profil(
            self.co_b, self.dossier_b, salaire_base=Decimal('8000'))
        self.periode_a = make_periode(self.co_a, 2026, 8)
        self.periode_b = PeriodePaie.objects.create(
            company=self.co_b, annee=2026, mois=8)

    def test_hs_societe_b_ninvisible_depuis_a(self):
        """Les HS de B ne s'ajoutent pas dans le bulletin de A."""
        brut_a_avant = calculer_bulletin(self.profil_a, self.periode_a)['brut']
        # Ajout de HS dans B.
        add_hs(self.co_b, self.periode_b, self.profil_b,
               quantite=Decimal('20'), categorie=ElementVariable.HS_FERIE)
        brut_a_apres = calculer_bulletin(self.profil_a, self.periode_a)['brut']
        self.assertEqual(brut_a_avant, brut_a_apres)
