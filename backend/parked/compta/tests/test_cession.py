"""Tests FG120 — cession / mise au rebut d'immobilisation + écritures de sortie.

Couvre :

* Calcul de la VNC (coût − amortissements cumulés à la date de cession),
  amortissements lus depuis le plan FG119.
* Plus-value (prix > VNC) vs moins-value (prix < VNC) et mise au rebut (VNC pure
  moins-value).
* Écriture de sortie ÉQUILIBRÉE (reprise amort. classe 28 + sortie classe 2 +
  résultat 6513/7513), idempotente, marquant la cession ``posted``.
* Verrou de période : poster dans une période verrouillée est REFUSÉ.
* L'immobilisation est marquée inactive à la cession.
* Multi-société : isolation ; l'API pose ``company`` côté serveur, 404 en
  cross-société, 403 pour un rôle normal.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CessionImmobilisation, EcritureComptable, Immobilisation,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_immo(company, **kwargs):
    defaults = dict(
        libelle='Camionnette',
        categorie=Immobilisation.Categorie.VEHICULE,
        cout=Decimal('100000'),
        taux_tva=Decimal('20.00'),
        date_acquisition=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Immobilisation.objects.create(company=company, **defaults)


# ── Calcul VNC / résultat de cession ────────────────────────────────────────

class CalculCessionTests(TestCase):
    def setUp(self):
        self.co = make_company('cess-calc', 'Cess Calc')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_vnc_sans_plan_egale_le_cout(self):
        # Aucun amortissement → VNC = coût d'acquisition.
        immo = make_immo(self.co, cout=Decimal('100000'))
        calc = services.calculer_cession(immo, date(2026, 6, 30),
                                         Decimal('40000'))
        self.assertEqual(calc['amortissements_cumules'], Decimal('0.00'))
        self.assertEqual(calc['valeur_nette_comptable'], Decimal('100000.00'))
        # 40000 − 100000 = −60000 → moins-value.
        self.assertEqual(calc['resultat_cession'], Decimal('-60000.00'))

    def test_vnc_deduit_amortissements_postes(self):
        # Plan linéaire 5 ans sur 100000 → 20000/an. Deux dotations 31/12/2026 &
        # 31/12/2027 ⇒ cumul 40000 à une cession en 2028 → VNC 60000.
        immo = make_immo(self.co, cout=Decimal('100000'),
                         date_acquisition=date(2026, 1, 1))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        for dot in plan.dotations.filter(annee__in=[2026, 2027]):
            services.poster_dotation(dot)
        calc = services.calculer_cession(immo, date(2028, 6, 30),
                                         Decimal('70000'))
        self.assertEqual(calc['amortissements_cumules'], Decimal('40000.00'))
        self.assertEqual(calc['valeur_nette_comptable'], Decimal('60000.00'))
        # 70000 − 60000 = 10000 → plus-value.
        self.assertEqual(calc['resultat_cession'], Decimal('10000.00'))

    def test_amortissements_apres_cession_exclus(self):
        # Les dotations au 31/12/2028+ ne comptent PAS pour une cession au
        # 30/06/2028 (date_dotation > date de cession) ; seules 2026 + 2027
        # (31/12 ≤ 30/06/2028) sont retenues → cumul 40000.
        immo = make_immo(self.co, cout=Decimal('100000'),
                         date_acquisition=date(2026, 1, 1))
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        calc = services.calculer_cession(immo, date(2028, 6, 30),
                                         Decimal('70000'))
        self.assertEqual(calc['amortissements_cumules'], Decimal('40000.00'))


# ── Plus-value vs moins-value vs rebut ──────────────────────────────────────

class ResultatCessionTests(TestCase):
    def setUp(self):
        self.co = make_company('cess-res', 'Cess Res')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_plus_value(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('60000'))
        # VNC 50000, prix 60000 → +10000.
        self.assertEqual(cession.resultat_cession, Decimal('10000.00'))
        self.assertEqual(cession.plus_value, Decimal('10000.00'))
        self.assertEqual(cession.moins_value, Decimal('0'))
        self.assertEqual(cession.type_cession,
                         CessionImmobilisation.Type.VENTE)

    def test_moins_value(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('30000'))
        # VNC 50000, prix 30000 → −20000.
        self.assertEqual(cession.resultat_cession, Decimal('-20000.00'))
        self.assertEqual(cession.moins_value, Decimal('20000.00'))
        self.assertEqual(cession.plus_value, Decimal('0'))

    def test_rebut_prix_zero_deduit_type_et_moins_value(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30))
        self.assertEqual(cession.type_cession,
                         CessionImmobilisation.Type.REBUT)
        self.assertEqual(cession.prix_cession, Decimal('0'))
        # Mise au rebut d'un bien non amorti → moins-value = VNC entière.
        self.assertEqual(cession.resultat_cession, Decimal('-50000.00'))
        self.assertEqual(cession.moins_value, Decimal('50000.00'))


# ── Écriture de sortie postée au grand livre ────────────────────────────────

class PostingCessionTests(TestCase):
    def setUp(self):
        self.co = make_company('cess-post', 'Cess Post')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_ecriture_equilibree_moins_value_sans_amort(self):
        immo = make_immo(self.co, cout=Decimal('100000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('40000'))
        ecriture = services.poster_cession(cession)
        self.assertTrue(ecriture.est_equilibree)
        # Sans amort. : débit créance 40000 + moins-value 60000 = crédit immo
        # 100000.
        self.assertEqual(ecriture.total_debit, Decimal('100000.00'))
        self.assertEqual(ecriture.total_credit, Decimal('100000.00'))
        # Crédit du compte d'immobilisation brute (classe 2) pour le coût.
        credits = [lig for lig in ecriture.lignes.all() if lig.credit]
        immo_lines = [lig for lig in credits if lig.compte.classe == 2]
        self.assertEqual(len(immo_lines), 1)
        self.assertEqual(immo_lines[0].credit, Decimal('100000.00'))
        # Moins-value au débit du 6513 (charge classe 6).
        debits = [lig for lig in ecriture.lignes.all() if lig.debit]
        mv = [lig for lig in debits if lig.compte.numero == '6513']
        self.assertEqual(len(mv), 1)
        self.assertEqual(mv[0].debit, Decimal('60000.00'))

    def test_ecriture_equilibree_plus_value_avec_amort(self):
        immo = make_immo(self.co, cout=Decimal('100000'),
                         date_acquisition=date(2026, 1, 1))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        for dot in plan.dotations.filter(annee__in=[2026, 2027]):
            services.poster_dotation(dot)
        cession = services.enregistrer_cession(
            immo, date_cession=date(2028, 6, 30),
            prix_cession=Decimal('70000'))
        ecriture = services.poster_cession(cession)
        self.assertTrue(ecriture.est_equilibree)
        # Reprise amort. 40000 (débit 28xx) + créance 70000 = sortie immo 100000
        # (crédit) + plus-value 10000 (crédit 7513).
        self.assertEqual(ecriture.total_debit, Decimal('110000.00'))
        self.assertEqual(ecriture.total_credit, Decimal('110000.00'))
        # Reprise des amortissements : débit d'un compte de classe 28.
        debits = [lig for lig in ecriture.lignes.all() if lig.debit]
        amort = [lig for lig in debits if lig.compte.numero.startswith('28')]
        self.assertEqual(len(amort), 1)
        self.assertEqual(amort[0].debit, Decimal('40000.00'))
        # Plus-value au crédit du 7513 (produit classe 7).
        credits = [lig for lig in ecriture.lignes.all() if lig.credit]
        pv = [lig for lig in credits if lig.compte.numero == '7513']
        self.assertEqual(len(pv), 1)
        self.assertEqual(pv[0].credit, Decimal('10000.00'))

    def test_poster_marque_cession_postee_et_lie_ecriture(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('30000'))
        services.poster_cession(cession)
        cession.refresh_from_db()
        self.assertTrue(cession.posted)
        self.assertIsNotNone(cession.ecriture_id)

    def test_poster_marque_immobilisation_inactive(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        self.assertTrue(immo.actif)
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('30000'))
        services.poster_cession(cession)
        immo.refresh_from_db()
        self.assertFalse(immo.actif)

    def test_poster_idempotent(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('30000'))
        e1 = services.poster_cession(cession)
        e2 = services.poster_cession(cession)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='cession_immobilisation').count(), 1)

    def test_poster_dans_periode_verrouillee_refuse(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        cession = services.enregistrer_cession(
            immo, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('30000'))
        periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 12, 31),
            type_periode='exercice', libelle='Exercice 2026')
        services.cloturer_periode(periode)
        with self.assertRaises(ValidationError):
            services.poster_cession(cession)
        cession.refresh_from_db()
        self.assertFalse(cession.posted)
        immo.refresh_from_db()
        # Immobilisation NON sortie tant que la cession n'est pas postée.
        self.assertTrue(immo.actif)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='cession_immobilisation').count(), 0)


# ── Isolation multi-société ─────────────────────────────────────────────────

class IsolationCessionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cess-a', 'Cess A')
        self.co_b = make_company('cess-b', 'Cess B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)

    def test_cessions_isolees_par_societe(self):
        immo_a = make_immo(self.co_a, cout=Decimal('10000'))
        immo_b = make_immo(self.co_b, cout=Decimal('20000'))
        services.enregistrer_cession(
            immo_a, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('5000'))
        services.enregistrer_cession(
            immo_b, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('5000'))
        self.assertEqual(
            CessionImmobilisation.objects.filter(company=self.co_a).count(), 1)
        self.assertEqual(
            CessionImmobilisation.objects.filter(company=self.co_b).count(), 1)


# ── API ─────────────────────────────────────────────────────────────────────

class CessionApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cess-api-a', 'Cess API A')
        self.co_b = make_company('cess-api-b', 'Cess API B')
        self.user_a = make_user(self.co_a, 'cess-user-a')
        self.user_b = make_user(self.co_b, 'cess-user-b')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.immo_a = make_immo(self.co_a, cout=Decimal('100000'))

    def _ceder_url(self, immo):
        return f'/api/django/compta/immobilisations/{immo.id}/ceder/'

    def test_ceder_via_api_pose_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(
            self._ceder_url(self.immo_a),
            {'date_cession': '2026-06-30', 'prix_cession': '40000'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cession = CessionImmobilisation.objects.get(id=resp.data['id'])
        self.assertEqual(cession.company, self.co_a)  # posée côté serveur.
        self.assertTrue(cession.posted)
        self.assertEqual(resp.data['resultat_cession'], '-60000.00')
        # L'immobilisation est sortie (inactive).
        self.immo_a.refresh_from_db()
        self.assertFalse(self.immo_a.actif)

    def test_ceder_cross_company_404(self):
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        api_a = auth(self.user_a)
        resp = api_a.post(
            self._ceder_url(immo_b),
            {'date_cession': '2026-06-30', 'prix_cession': '40000'},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_ceder_periode_verrouillee_400(self):
        periode = services.creer_periode(
            self.co_a, date(2026, 1, 1), date(2026, 12, 31),
            type_periode='exercice', libelle='Exercice 2026')
        services.cloturer_periode(periode)
        api = auth(self.user_a)
        resp = api.post(
            self._ceder_url(self.immo_a),
            {'date_cession': '2026-06-30', 'prix_cession': '40000'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            CessionImmobilisation.objects.filter(
                company=self.co_a, posted=True).count(), 0)

    def test_cessions_isolees_dans_liste(self):
        services.enregistrer_cession(
            self.immo_a, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('40000'))
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        services.enregistrer_cession(
            immo_b, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('20000'))
        api_a = auth(self.user_a)
        resp = api_a.get('/api/django/compta/cessions/')
        self.assertEqual(resp.status_code, 200)
        immo_ids = {r['immobilisation'] for r in rows(resp)}
        self.assertTrue(immo_ids <= {self.immo_a.id})

    def test_poster_cession_cross_company_404(self):
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        cession_b = services.enregistrer_cession(
            immo_b, date_cession=date(2026, 6, 30),
            prix_cession=Decimal('20000'))
        api_a = auth(self.user_a)
        resp = api_a.post(
            f'/api/django/compta/cessions/{cession_b.id}/poster/', format='json')
        self.assertEqual(resp.status_code, 404)

    def test_acces_refuse_role_normal(self):
        normal = make_user(self.co_a, 'cess-normal', role='normal')
        api = auth(normal)
        resp = api.get('/api/django/compta/cessions/')
        self.assertEqual(resp.status_code, 403)
