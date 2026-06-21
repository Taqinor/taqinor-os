"""Tests FG115/FG116/FG117 — clôture de période, OD manuelles, à-nouveaux.

Couvre :

* FG115 — verrouillage d'une période : une écriture/ligne/facture dont la date
  tombe dans une période close est IMMUABLE (création, modification, suppression
  refusées) ; la réouverture libère le verrou ; isolation par société.
* FG116 — écriture de régularisation manuelle (OD) sans document source :
  équilibrée, postée au grand livre, refusée si la période est verrouillée.
* FG117 — report des à-nouveaux : soldes de bilan de l'exercice clos reportés
  dans le nouvel exercice, idempotent, équilibré.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    EcritureComptable, Journal, PeriodeComptable,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


# ── FG115 — Clôture & verrouillage de période ──────────────────────────────

class ClotureVerrouillageTests(TestCase):
    def setUp(self):
        self.co = make_company('cloture', 'Cloture')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.get(company=self.co, code='VTE')
        self.clients = services.get_compte(self.co, '3421')
        self.ventes = services.get_compte(self.co, '7121')

    def _lignes(self, montant=Decimal('100')):
        return [
            {'compte': self.clients, 'debit': montant, 'credit': Decimal('0')},
            {'compte': self.ventes, 'debit': Decimal('0'), 'credit': montant},
        ]

    def _periode_janvier(self):
        return services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31),
            libelle='Janvier 2026')

    def test_cloturer_verrouille_la_periode(self):
        periode = self._periode_janvier()
        self.assertFalse(periode.verrouillee)
        services.cloturer_periode(periode)
        periode.refresh_from_db()
        self.assertTrue(periode.verrouillee)
        self.assertIsNotNone(periode.date_verrouillage)

    def test_ecriture_en_periode_close_refusee(self):
        periode = self._periode_janvier()
        services.cloturer_periode(periode)
        with self.assertRaises(ValidationError):
            services.creer_ecriture(
                self.co, self.journal, date(2026, 1, 15),
                'Tentative en période close', self._lignes())
        # Rien n'a été créé.
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_ecriture_hors_periode_close_autorisee(self):
        periode = self._periode_janvier()
        services.cloturer_periode(periode)
        # Février n'est pas verrouillé → OK.
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 2, 10), 'Février', self._lignes())
        self.assertTrue(ecr.est_equilibree)

    def test_modification_ecriture_en_periode_close_refusee(self):
        # Écriture créée AVANT la clôture, puis période verrouillée.
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 1, 10), 'Avant clôture',
            self._lignes())
        periode = self._periode_janvier()
        services.cloturer_periode(periode)
        ecr.libelle = 'Modifié après clôture'
        with self.assertRaises(ValidationError):
            ecr.save()

    def test_suppression_ecriture_en_periode_close_refusee(self):
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 1, 10), 'À supprimer',
            self._lignes())
        services.cloturer_periode(self._periode_janvier())
        with self.assertRaises(ValidationError):
            ecr.delete()
        self.assertTrue(
            EcritureComptable.objects.filter(id=ecr.id).exists())

    def test_modification_ligne_en_periode_close_refusee(self):
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 1, 10), 'Lignes',
            self._lignes())
        services.cloturer_periode(self._periode_janvier())
        ligne = ecr.lignes.first()
        ligne.libelle = 'Ligne modifiée'
        with self.assertRaises(ValidationError):
            ligne.save()

    def test_reouverture_libere_le_verrou(self):
        periode = self._periode_janvier()
        services.cloturer_periode(periode)
        services.rouvrir_periode(periode)
        periode.refresh_from_db()
        self.assertFalse(periode.verrouillee)
        # Maintenant on peut de nouveau écrire en janvier.
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 1, 20), 'Après réouverture',
            self._lignes())
        self.assertTrue(ecr.est_equilibree)

    def test_date_verrouillee_helper(self):
        services.cloturer_periode(self._periode_janvier())
        self.assertTrue(
            PeriodeComptable.date_verrouillee(self.co.id, date(2026, 1, 15)))
        self.assertFalse(
            PeriodeComptable.date_verrouillee(self.co.id, date(2026, 2, 15)))

    def test_verrou_isole_par_societe(self):
        # La clôture chez A ne fige rien chez B (même intervalle de dates).
        autre = make_company('cloture-b', 'Cloture B')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        services.cloturer_periode(self._periode_janvier())
        self.assertFalse(
            PeriodeComptable.date_verrouillee(autre.id, date(2026, 1, 15)))

    def test_facture_immutable_en_periode_close(self):
        services.cloturer_periode(self._periode_janvier())
        facture = type('F', (), {})()
        facture.company = self.co
        facture.date_emission = date(2026, 1, 15)
        with self.assertRaises(ValidationError):
            services.verifier_facture_modifiable(facture)
        # Une facture de février passe.
        facture.date_emission = date(2026, 2, 15)
        services.verifier_facture_modifiable(facture)  # ne lève pas


# ── FG116 — Écritures de régularisation / OD manuelles ─────────────────────

class EcritureODTests(TestCase):
    def setUp(self):
        self.co = make_company('od', 'OD')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.dotations = services.get_compte(self.co, '6191')  # charge
        self.amort = services.get_compte(self.co, '2832')      # passif/amort

    def test_od_creee_equilibree_sans_source(self):
        ecr = services.creer_ecriture_od(
            self.co, date(2026, 3, 31),
            "Dotation aux amortissements",
            [
                {'compte': self.dotations, 'debit': Decimal('500'),
                 'credit': Decimal('0')},
                {'compte': self.amort, 'debit': Decimal('0'),
                 'credit': Decimal('500')},
            ])
        self.assertTrue(ecr.est_equilibree)
        # Pas de document source : écriture purement manuelle.
        self.assertEqual(ecr.source_type, '')
        self.assertIsNone(ecr.source_id)
        # Passée au journal OD.
        self.assertEqual(ecr.journal.type_journal, Journal.Type.OPERATIONS_DIVERSES)

    def test_od_apparait_au_grand_livre(self):
        services.creer_ecriture_od(
            self.co, date(2026, 3, 31), "Provision",
            [
                {'compte': self.dotations, 'debit': Decimal('300'),
                 'credit': Decimal('0')},
                {'compte': self.amort, 'debit': Decimal('0'),
                 'credit': Decimal('300')},
            ])
        gl = {b['numero']: b for b in selectors.grand_livre(self.co)}
        self.assertEqual(gl['6191']['solde'], Decimal('300'))

    def test_od_desequilibree_refusee(self):
        with self.assertRaises(ValidationError):
            services.creer_ecriture_od(
                self.co, date(2026, 3, 31), "Bancale",
                [
                    {'compte': self.dotations, 'debit': Decimal('300'),
                     'credit': Decimal('0')},
                    {'compte': self.amort, 'debit': Decimal('0'),
                     'credit': Decimal('250')},
                ])
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_od_refusee_en_periode_close(self):
        periode = services.creer_periode(
            self.co, date(2026, 3, 1), date(2026, 3, 31))
        services.cloturer_periode(periode)
        with self.assertRaises(ValidationError):
            services.creer_ecriture_od(
                self.co, date(2026, 3, 31), "Trop tard",
                [
                    {'compte': self.dotations, 'debit': Decimal('100'),
                     'credit': Decimal('0')},
                    {'compte': self.amort, 'debit': Decimal('0'),
                     'credit': Decimal('100')},
                ])
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)


# ── FG117 — À-nouveaux / réouverture d'exercice ────────────────────────────

class ANouveauxTests(TestCase):
    def setUp(self):
        self.co = make_company('an', 'AN')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.get(company=self.co, code='VTE')
        self.clients = services.get_compte(self.co, '3421')
        self.banque = services.get_compte(self.co, '5141')
        self.ventes = services.get_compte(self.co, '7121')
        self.capital = services.get_compte(self.co, '1111')
        # Exercice 2025 clos : un solde de bilan (banque débitrice 1000,
        # capital créditeur 1000) à reporter en à-nouveau.
        services.creer_ecriture(
            self.co, self.journal, date(2025, 6, 1),
            "Apport en capital",
            [
                {'compte': self.banque, 'debit': Decimal('1000'),
                 'credit': Decimal('0')},
                {'compte': self.capital, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ])
        self.ex2025 = services.creer_exercice(
            self.co, date(2025, 1, 1), date(2025, 12, 31), libelle='2025')
        self.ex2026 = services.creer_exercice(
            self.co, date(2026, 1, 1), date(2026, 12, 31), libelle='2026')

    def test_report_a_nouveaux_reporte_les_soldes_de_bilan(self):
        services.cloturer_exercice(self.ex2025)
        ecr = services.reporter_a_nouveaux(self.ex2025, self.ex2026)
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.date_ecriture, date(2026, 1, 1))
        self.assertEqual(ecr.journal.type_journal, Journal.Type.A_NOUVEAUX)
        # Banque reportée au débit 1000, capital au crédit 1000.
        self.assertEqual(
            ecr.lignes.get(compte__numero='5141').debit, Decimal('1000'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='1111').credit, Decimal('1000'))
        # Les comptes de résultat (7xxx) ne sont PAS reportés.
        self.assertFalse(ecr.lignes.filter(compte__numero='7121').exists())

    def test_report_idempotent(self):
        services.cloturer_exercice(self.ex2025)
        a = services.reporter_a_nouveaux(self.ex2025, self.ex2026)
        b = services.reporter_a_nouveaux(self.ex2025, self.ex2026)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='a_nouveaux').count(), 1)
        self.ex2026.refresh_from_db()
        self.assertTrue(self.ex2026.an_reporte)

    def test_cloture_exercice_verrouille_ses_periodes(self):
        p = services.creer_periode(
            self.co, date(2025, 12, 1), date(2025, 12, 31),
            exercice=self.ex2025)
        services.cloturer_exercice(self.ex2025)
        p.refresh_from_db()
        self.ex2025.refresh_from_db()
        self.assertTrue(self.ex2025.est_cloture)
        self.assertTrue(p.verrouillee)

    def test_rouvrir_exercice_clos(self):
        services.cloturer_exercice(self.ex2025)
        services.rouvrir_exercice(self.ex2025)
        self.ex2025.refresh_from_db()
        self.assertFalse(self.ex2025.est_cloture)

    def test_report_refuse_societes_differentes(self):
        autre = make_company('an-b', 'AN B')
        ex_autre = services.creer_exercice(
            autre, date(2026, 1, 1), date(2026, 12, 31))
        with self.assertRaises(ValidationError):
            services.reporter_a_nouveaux(self.ex2025, ex_autre)

    def test_report_sans_solde_renvoie_none(self):
        # Société vierge : aucun solde de bilan → report None mais marqué fait.
        vierge = make_company('an-vide', 'AN Vide')
        services.seed_plan_comptable(vierge)
        services.seed_journaux(vierge)
        ex1 = services.creer_exercice(
            vierge, date(2025, 1, 1), date(2025, 12, 31))
        ex2 = services.creer_exercice(
            vierge, date(2026, 1, 1), date(2026, 12, 31))
        services.cloturer_exercice(ex1)
        res = services.reporter_a_nouveaux(ex1, ex2)
        self.assertIsNone(res)
        ex2.refresh_from_db()
        self.assertTrue(ex2.an_reporte)


# ── API FG115/FG116/FG117 ──────────────────────────────────────────────────

class _ApiBase(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        User = get_user_model()
        self.co = make_company('compta-clo-api', 'Compta Clo API')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = User.objects.create_user(
            username='clo-api', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class ClotureApiTests(_ApiBase):
    def _periode(self):
        return services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier')

    def test_cloturer_via_api(self):
        periode = self._periode()
        resp = self.api.post(
            f'/api/django/compta/periodes/{periode.id}/cloturer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['verrouillee'])
        periode.refresh_from_db()
        self.assertTrue(periode.verrouillee)

    def test_periode_company_posee_cote_serveur(self):
        resp = self.api.post(
            '/api/django/compta/periodes/',
            {'type_periode': 'mois', 'libelle': 'Test',
             'date_debut': '2026-02-01', 'date_fin': '2026-02-28'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        periode = PeriodeComptable.objects.get(id=resp.data['id'])
        self.assertEqual(periode.company, self.co)

    def test_ecriture_od_via_api(self):
        dotations = services.get_compte(self.co, '6191')
        amort = services.get_compte(self.co, '2832')
        resp = self.api.post(
            '/api/django/compta/exercices/ecriture-od/',
            {
                'date_ecriture': '2026-03-31',
                'libelle': 'Amortissement OD',
                'lignes': [
                    {'compte': dotations.id, 'debit': '500', 'credit': '0'},
                    {'compte': amort.id, 'debit': '0', 'credit': '500'},
                ],
            },
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ecr = EcritureComptable.objects.get(id=resp.data['id'])
        self.assertEqual(ecr.company, self.co)
        self.assertTrue(ecr.est_equilibree)

    def test_reporter_a_nouveaux_via_api(self):
        journal = Journal.objects.get(company=self.co, code='VTE')
        banque = services.get_compte(self.co, '5141')
        capital = services.get_compte(self.co, '1111')
        services.creer_ecriture(
            self.co, journal, date(2025, 6, 1), "Apport",
            [
                {'compte': banque, 'debit': Decimal('800'),
                 'credit': Decimal('0')},
                {'compte': capital, 'debit': Decimal('0'),
                 'credit': Decimal('800')},
            ])
        ex1 = services.creer_exercice(
            self.co, date(2025, 1, 1), date(2025, 12, 31))
        ex2 = services.creer_exercice(
            self.co, date(2026, 1, 1), date(2026, 12, 31))
        services.cloturer_exercice(ex1)
        resp = self.api.post(
            f'/api/django/compta/exercices/{ex1.id}/reporter-a-nouveaux/',
            {'exercice_cible': ex2.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['ecriture_id'])

    def test_acces_refuse_role_normal(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        User = get_user_model()
        normal = User.objects.create_user(
            username='clo-normal', password='x', company=self.co,
            role_legacy='normal')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(normal)}')
        resp = api.get('/api/django/compta/periodes/')
        self.assertEqual(resp.status_code, 403)
