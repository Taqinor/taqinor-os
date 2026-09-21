"""Tests PAIE16 — Avantages en nature & indemnités imposables vs non (plafonds).

Couvre :
* ``repartir_avantage`` — répartition montant → (part exonérée, part imposable)
  selon le drapeau ``imposable`` et le ``plafond_exoneration`` de la rubrique :
  - rubrique absente → tout imposable ;
  - rubrique imposable sans plafond → tout imposable ;
  - rubrique non imposable sans plafond → tout exonéré ;
  - plafond renseigné → exonéré jusqu'au plafond, excédent imposable.
* ``calculer_bulletin`` — intégration : une indemnité sous son plafond
  n'augmente PAS la base imposable (donc pas l'IR) ; l'excédent au-delà du
  plafond la fait croître ; le brut reste l'intégralité du montant.
* Le catalogue standard (PAIE7) sème bien les plafonds et les avantages en
  nature, idempotent.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    ElementVariable,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
)
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    ensure_rubriques_standard,
    repartir_avantage,
)
from apps.rh.models import DossierEmploye


# ── Helpers ────────────────────────────────────────────────────────────────

def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_dossier(company, matricule='E1', date_embauche=None):
    return DossierEmploye.objects.create(
        company=company,
        matricule=matricule,
        nom='Test',
        prenom='Avantage',
        date_embauche=date_embauche,
    )


def make_profil(company, dossier, salaire_base=Decimal('10000')):
    return ProfilPaie.objects.create(
        company=company,
        employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=salaire_base,
        affilie_cnss=True,
        affilie_amo=True,
    )


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


def make_rubrique(company, code, imposable=False, plafond=None,
                  avantage_nature=False, ordre=99):
    return Rubrique.objects.create(
        company=company,
        code=code,
        libelle=code,
        type=Rubrique.TYPE_GAIN,
        imposable=imposable,
        plafond_exoneration=plafond,
        avantage_nature=avantage_nature,
        ordre=ordre,
    )


# ── repartir_avantage ──────────────────────────────────────────────────────

class RepartirAvantageTests(TestCase):
    """Répartition exonéré / imposable d'une indemnité ou d'un avantage."""

    def setUp(self):
        self.co = make_company('av-rep')

    def test_rubrique_none_tout_imposable(self):
        """Sans rubrique catalogue → tout imposable (comportement historique)."""
        ex, imp = repartir_avantage(None, Decimal('1000'))
        self.assertEqual(ex, Decimal('0.00'))
        self.assertEqual(imp, Decimal('1000.00'))

    def test_imposable_sans_plafond_tout_imposable(self):
        rub = make_rubrique(self.co, 'IMP', imposable=True, plafond=None)
        ex, imp = repartir_avantage(rub, Decimal('1500'))
        self.assertEqual(ex, Decimal('0.00'))
        self.assertEqual(imp, Decimal('1500.00'))

    def test_non_imposable_sans_plafond_tout_exonere(self):
        rub = make_rubrique(self.co, 'EXO', imposable=False, plafond=None)
        ex, imp = repartir_avantage(rub, Decimal('1500'))
        self.assertEqual(ex, Decimal('1500.00'))
        self.assertEqual(imp, Decimal('0.00'))

    def test_sous_plafond_tout_exonere(self):
        """Montant sous le plafond → entièrement exonéré."""
        rub = make_rubrique(self.co, 'TR', imposable=False, plafond=Decimal('500'))
        ex, imp = repartir_avantage(rub, Decimal('400'))
        self.assertEqual(ex, Decimal('400.00'))
        self.assertEqual(imp, Decimal('0.00'))

    def test_egal_plafond_tout_exonere(self):
        rub = make_rubrique(self.co, 'TR2', imposable=False, plafond=Decimal('500'))
        ex, imp = repartir_avantage(rub, Decimal('500'))
        self.assertEqual(ex, Decimal('500.00'))
        self.assertEqual(imp, Decimal('0.00'))

    def test_au_dessus_plafond_excedent_imposable(self):
        """Montant > plafond → exonéré jusqu'au plafond, excédent imposable."""
        rub = make_rubrique(self.co, 'TR3', imposable=False, plafond=Decimal('500'))
        ex, imp = repartir_avantage(rub, Decimal('800'))
        self.assertEqual(ex, Decimal('500.00'))
        self.assertEqual(imp, Decimal('300.00'))

    def test_plafond_prime_meme_si_imposable(self):
        """Une rubrique marquée imposable AVEC plafond suit quand même le plafond."""
        rub = make_rubrique(self.co, 'TR4', imposable=True, plafond=Decimal('500'))
        ex, imp = repartir_avantage(rub, Decimal('800'))
        self.assertEqual(ex, Decimal('500.00'))
        self.assertEqual(imp, Decimal('300.00'))

    def test_montant_nul(self):
        rub = make_rubrique(self.co, 'TR5', imposable=False, plafond=Decimal('500'))
        ex, imp = repartir_avantage(rub, Decimal('0'))
        self.assertEqual(ex, Decimal('0.00'))
        self.assertEqual(imp, Decimal('0.00'))

    def test_somme_des_parts_egale_montant(self):
        """La somme part exonérée + part imposable vaut toujours le montant."""
        rub = make_rubrique(self.co, 'TR6', imposable=False, plafond=Decimal('500'))
        for montant in (Decimal('100'), Decimal('500'), Decimal('900.50')):
            ex, imp = repartir_avantage(rub, montant)
            self.assertEqual(ex + imp, montant)


# ── calculer_bulletin — intégration ────────────────────────────────────────

class BulletinAvantagesTests(TestCase):
    """L'exonération plafonnée se reflète dans la base imposable et l'IR."""

    def setUp(self):
        self.co = make_company('av-bull')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'AV1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)

    def _ajouter_indemnite(self, rubrique, montant):
        return ElementVariable.objects.create(
            company=self.co,
            periode=self.periode,
            profil=self.profil,
            type=ElementVariable.TYPE_PRIME,
            rubrique=rubrique,
            libelle=rubrique.code,
            montant=montant,
        )

    def test_indemnite_sous_plafond_pas_dans_imposable(self):
        """Indemnité de transport 400 < plafond 500 → 0 dans le brut imposable."""
        rub = make_rubrique(self.co, 'TRANSPORT', imposable=False,
                            plafond=Decimal('500'))
        self._ajouter_indemnite(rub, Decimal('400'))
        res = calculer_bulletin(self.profil, self.periode)
        # Brut = 10 000 + 400 = 10 400, mais brut imposable reste 10 000.
        self.assertEqual(res['brut'], Decimal('10400.00'))
        self.assertEqual(res['brut_imposable'], Decimal('10000.00'))

    def test_indemnite_au_dessus_plafond_excedent_imposable(self):
        """Indemnité 800 > plafond 500 → 300 réintégrés dans le brut imposable."""
        rub = make_rubrique(self.co, 'TRANSPORT', imposable=False,
                            plafond=Decimal('500'))
        self._ajouter_indemnite(rub, Decimal('800'))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('10800.00'))
        # 10 000 (SB) + 300 (excédent) = 10 300.
        self.assertEqual(res['brut_imposable'], Decimal('10300.00'))

    def test_excedent_augmente_ir(self):
        """L'excédent imposable fait croître l'IR ; le sous-plafond ne le change pas."""
        rub_exo = make_rubrique(self.co, 'TRANSPORT', imposable=False,
                                plafond=Decimal('500'))
        self._ajouter_indemnite(rub_exo, Decimal('400'))
        ir_exo = calculer_bulletin(self.profil, self.periode)['ir']

        # Nouvelle période : même profil, indemnité au-dessus du plafond.
        periode2 = make_periode(self.co, 2026, 7)
        ElementVariable.objects.create(
            company=self.co, periode=periode2, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, rubrique=rub_exo,
            libelle='TRANSPORT', montant=Decimal('3000'))
        ir_excedent = calculer_bulletin(self.profil, periode2)['ir']

        self.assertGreater(ir_excedent, ir_exo)

    def test_avantage_nature_imposable_entierement(self):
        """Avantage en nature imposable sans plafond → entièrement imposable."""
        rub = make_rubrique(self.co, 'AV_LOGEMENT', imposable=True,
                            plafond=None, avantage_nature=True)
        self._ajouter_indemnite(rub, Decimal('2000'))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('12000.00'))
        self.assertEqual(res['brut_imposable'], Decimal('12000.00'))

    def test_indemnite_exoneree_sans_plafond_pas_imposable(self):
        """Indemnité non imposable sans plafond → jamais dans le brut imposable."""
        rub = make_rubrique(self.co, 'EXO_FULL', imposable=False, plafond=None)
        self._ajouter_indemnite(rub, Decimal('1000'))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('11000.00'))
        self.assertEqual(res['brut_imposable'], Decimal('10000.00'))


# ── Catalogue standard (PAIE7/PAIE16) ──────────────────────────────────────

class CatalogueAvantagesTests(TestCase):
    """Le catalogue standard sème plafonds + avantages en nature, idempotent."""

    def setUp(self):
        self.co = make_company('av-cat')

    def test_seed_pose_les_plafonds(self):
        ensure_rubriques_standard(self.co)
        transport = Rubrique.objects.get(company=self.co, code='TRANSPORT')
        self.assertFalse(transport.imposable)
        self.assertEqual(transport.plafond_exoneration, Decimal('500'))
        self.assertFalse(transport.avantage_nature)

    def test_seed_pose_les_avantages_nature(self):
        ensure_rubriques_standard(self.co)
        voiture = Rubrique.objects.get(company=self.co, code='AV_VOITURE')
        self.assertTrue(voiture.avantage_nature)
        self.assertTrue(voiture.imposable)

    def test_seed_idempotent(self):
        ensure_rubriques_standard(self.co)
        avant = Rubrique.objects.filter(company=self.co).count()
        # Édition fondateur sur un plafond : un re-seed ne doit pas l'écraser.
        transport = Rubrique.objects.get(company=self.co, code='TRANSPORT')
        transport.plafond_exoneration = Decimal('750')
        transport.save()
        ensure_rubriques_standard(self.co)
        apres = Rubrique.objects.filter(company=self.co).count()
        self.assertEqual(avant, apres)
        transport.refresh_from_db()
        self.assertEqual(transport.plafond_exoneration, Decimal('750'))


# ── Multi-tenant ───────────────────────────────────────────────────────────

class AvantagesIsolationTests(TestCase):
    """Le plafond de la société A ne s'applique pas à la société B."""

    def test_isolation_societes(self):
        co_a = make_company('av-iso-a')
        co_b = make_company('av-iso-b')
        ensure_defaults(co_a)
        ensure_defaults(co_b)

        # A : plafond 500.
        dos_a = make_dossier(co_a, 'IA1')
        profil_a = make_profil(co_a, dos_a, Decimal('10000'))
        periode_a = make_periode(co_a, 2026, 6)
        rub_a = make_rubrique(co_a, 'TRANSPORT', imposable=False,
                              plafond=Decimal('500'))
        ElementVariable.objects.create(
            company=co_a, periode=periode_a, profil=profil_a,
            type=ElementVariable.TYPE_PRIME, rubrique=rub_a,
            libelle='TRANSPORT', montant=Decimal('800'))

        # B : même indemnité mais plafond 1000 (tout exonéré).
        dos_b = make_dossier(co_b, 'IB1')
        profil_b = make_profil(co_b, dos_b, Decimal('10000'))
        periode_b = make_periode(co_b, 2026, 6)
        rub_b = make_rubrique(co_b, 'TRANSPORT', imposable=False,
                              plafond=Decimal('1000'))
        ElementVariable.objects.create(
            company=co_b, periode=periode_b, profil=profil_b,
            type=ElementVariable.TYPE_PRIME, rubrique=rub_b,
            libelle='TRANSPORT', montant=Decimal('800'))

        # A : 300 d'excédent imposable → brut imposable 10 300.
        res_a = calculer_bulletin(profil_a, periode_a)
        self.assertEqual(res_a['brut_imposable'], Decimal('10300.00'))
        # B : tout sous plafond → brut imposable 10 000.
        res_b = calculer_bulletin(profil_b, periode_b)
        self.assertEqual(res_b['brut_imposable'], Decimal('10000.00'))
