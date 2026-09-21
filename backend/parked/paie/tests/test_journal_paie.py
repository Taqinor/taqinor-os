"""Tests PAIE33 — Livre de paie + journal de paie → écritures (via compta).

Couvre :
* ``livre_de_paie`` — registre récapitulatif des bulletins VALIDÉS + totaux.
* ``journal_de_paie`` — crée UNE écriture comptable ÉQUILIBRÉE via
  ``compta.services`` (cross-app par la couche services, jamais les models) ;
  None si aucun bulletin validé.
* Multi-tenant — isolation société.
* AUD708 — idempotence du postage (source stable + contrainte DB) et
  ventilation des charges 100 % patronales aux comptes ORGANISMES (444x) au
  lieu du compte 4432 « Rémunérations dues au personnel ».
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    etat_des_charges,
    generer_bulletin,
    journal_de_paie,
    journal_de_paie_ventile,
    livre_de_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class JournalPaieTests(TestCase):
    def setUp(self):
        self.co = make_company('jp')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_livre_de_paie(self):
        b1 = self._bulletin_valide('A1')
        b2 = self._bulletin_valide('A2')
        livre = livre_de_paie(self.periode)
        self.assertEqual(livre['nombre_salaries'], 2)
        self.assertEqual(livre['totaux']['brut'], b1.brut + b2.brut)
        self.assertEqual(
            livre['totaux']['net_a_payer'], b1.net_a_payer + b2.net_a_payer)

    def test_journal_de_paie_ecriture_equilibree(self):
        self._bulletin_valide('B1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        # L'écriture est équilibrée : Σ débit = Σ crédit.
        lignes = list(ecriture.lignes.all())
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertGreater(debit, Decimal('0'))
        self.assertEqual(ecriture.company, self.co)
        self.assertEqual(ecriture.reference, 'PAIE-2026-06')

    def test_journal_de_paie_sans_bulletin(self):
        # Aucun bulletin validé → rien à comptabiliser.
        self.assertIsNone(journal_de_paie(self.periode))

    # ── DC21 — aucun numéro de compte écrit en dur : tout passe par le
    #          référentiel `compta.CompteComptable` (plan comptable unique). ──

    def test_journal_resout_les_comptes_du_referentiel(self):
        """Chaque ligne de l'écriture porte un FK `CompteComptable` réel.

        DC21 : la paie ne stocke jamais un numéro de compte en dur ; elle
        RÉSOUT chaque compte d'imputation par ``compta.services.get_compte``
        contre le plan comptable canonique. On vérifie qu'aucune ligne ne porte
        un compte « inventé » hors référentiel.
        """
        from apps.compta.models import CompteComptable

        self._bulletin_valide('C1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        comptes_referentiel = set(
            CompteComptable.objects
            .filter(company=self.co)
            .values_list('id', flat=True))
        lignes = list(ecriture.lignes.all())
        self.assertGreater(len(lignes), 0)
        for ligne in lignes:
            # Le compte est un FK réel (jamais None / jamais une chaîne brute).
            self.assertIsNotNone(ligne.compte_id)
            self.assertIn(ligne.compte_id, comptes_referentiel)
            self.assertEqual(ligne.compte.company_id, self.co.id)

    def test_comptes_paie_existent_dans_le_plan(self):
        """Tous les comptes d'imputation paie sont des numéros du référentiel.

        Garantit que les clés ``_COMPTE_*`` sont de simples NUMÉROS résolus
        contre le plan comptable (semé au besoin), pas des comptes ad-hoc.
        """
        from apps.compta.services import get_compte
        from apps.paie import services as paie_services

        numeros = [
            paie_services._COMPTE_REMUNERATION,
            paie_services._COMPTE_CHARGES_SOCIALES,
            paie_services._COMPTE_CNSS,
            paie_services._COMPTE_IR,
            paie_services._COMPTE_CIMR,
            paie_services._COMPTE_NET,
        ]
        # Déclenche le seed idempotent via une écriture, puis vérifie.
        self._bulletin_valide('D1')
        journal_de_paie(self.periode)
        for num in numeros:
            self.assertIsNotNone(
                get_compte(self.co, num),
                f'Compte {num} absent du plan comptable (référentiel DC21).')


class JournalPaieIdempotenceTests(TestCase):
    """AUD708 — le journal de paie ne peut plus être posté deux fois."""

    def setUp(self):
        self.co = make_company('jp-idem')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.user = make_user(self.co, 'jp-idem-user')

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_ecriture_porte_sa_source(self):
        """La source stable (période) réarme la contrainte DB d'idempotence."""
        self._bulletin_valide('I0')
        ecriture = journal_de_paie(self.periode)
        self.assertEqual(ecriture.source_type, 'paie_journal')
        self.assertEqual(ecriture.source_id, self.periode.id)

    def test_second_postage_refuse(self):
        from apps.compta.models import EcritureComptable

        self._bulletin_valide('I1')
        premiere = journal_de_paie(self.periode)
        self.assertIsNotNone(premiere)
        with self.assertRaises(DjangoValidationError):
            journal_de_paie(self.periode)
        # UNE seule écriture au grand livre, jamais deux.
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='paie_journal',
                source_id=self.periode.id).count(), 1)

    def test_journal_ventile_apres_journal_simple_refuse(self):
        """Les deux journaux décrivent le MÊME run : poster les deux doublerait."""
        self._bulletin_valide('I2')
        journal_de_paie(self.periode)
        with self.assertRaises(DjangoValidationError):
            journal_de_paie_ventile(self.periode)

    def test_api_double_post_renvoie_400(self):
        self._bulletin_valide('I3')
        api = auth(self.user)
        url = f'/api/django/paie/periodes/{self.periode.id}/journal-de-paie/'
        premier = api.post(url, {}, format='json')
        self.assertEqual(premier.status_code, 200, premier.data)
        second = api.post(url, {}, format='json')
        self.assertEqual(second.status_code, 400, second.data)

    def test_api_journal_ventile_periode_verrouillee_400(self):
        """Une période comptable verrouillée → 400 explicite, jamais un 500."""
        from apps.compta.models import PeriodeComptable

        self._bulletin_valide('I4')
        PeriodeComptable.objects.create(
            company=self.co, date_debut='2026-06-01', date_fin='2026-06-30',
            verrouillee=True, libelle='Juin 2026')
        resp = auth(self.user).post(
            f'/api/django/paie/periodes/{self.periode.id}/journal-ventile/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class JournalPaieVentilationOrganismesTests(TestCase):
    """AUD708 — allocations familiales + taxe formation aux organismes 444x."""

    def setUp(self):
        self.co = make_company('jp-vent')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V1', nom='NV1', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True)
        self.bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(self.bulletin)

    def test_charges_patronales_hors_net_creditees_aux_organismes(self):
        """Le crédit 4432 = net à payer exactement (plus le net + ~800 MAD).

        Sur un brut de 10 000 MAD : allocations familiales (6,4 %) + taxe de
        formation professionnelle (1,6 %) = 800 MAD tombaient dans le solde
        équilibrant du compte 4432 (dette envers le PERSONNEL) faute de crédit
        organisme.
        """
        from apps.compta.services import get_compte

        ecart = (Decimal(self.bulletin.allocations_familiales)
                 + Decimal(self.bulletin.formation_professionnelle))
        self.assertEqual(ecart, Decimal('800.00'))  # 6,4 % + 1,6 % de 10 000

        ecriture = journal_de_paie(self.periode)
        lignes = list(ecriture.lignes.all())
        compte_net = get_compte(self.co, '4432')
        compte_cnss = get_compte(self.co, '4441')
        credit_net = sum(
            (lig.credit for lig in lignes if lig.compte_id == compte_net.id),
            Decimal('0'))
        credit_organismes = sum(
            (lig.credit for lig in lignes if lig.compte_id == compte_cnss.id),
            Decimal('0'))

        self.assertEqual(credit_net, self.bulletin.net_a_payer)
        # Les 800 MAD sont désormais DANS le crédit organismes.
        attendu_organismes = (
            Decimal(self.bulletin.cnss_salariale)
            + Decimal(self.bulletin.cnss_patronale)
            + Decimal(self.bulletin.amo_salariale)
            + Decimal(self.bulletin.amo_patronale) + ecart)
        self.assertEqual(credit_organismes, attendu_organismes)
        # L'écriture reste équilibrée.
        self.assertEqual(
            sum((lig.debit for lig in lignes), Decimal('0')),
            sum((lig.credit for lig in lignes), Decimal('0')))

    def test_etat_des_charges_suit_le_gl(self):
        """``etat_des_charges`` inclut les mêmes montants : aucun faux écart."""
        etat = etat_des_charges(self.periode)
        cnss = next(
            o for o in etat['organismes'] if o['code'] == 'cnss_amo')
        self.assertEqual(
            cnss['patronal'],
            Decimal(self.bulletin.cnss_patronale)
            + Decimal(self.bulletin.amo_patronale)
            + Decimal(self.bulletin.allocations_familiales)
            + Decimal(self.bulletin.formation_professionnelle))
