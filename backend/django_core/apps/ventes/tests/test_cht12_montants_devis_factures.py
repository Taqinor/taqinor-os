"""CHT12 — Sélecteurs batch de montants ventes (devis + factures liées).

Couvre ``ventes.selectors.montants_devis`` et
``ventes.selectors.montants_factures_par_devis`` : lecture EN BATCH scopée
société, façon ``ca_devis_factures_par_clients`` — consommés par le P&L
projet (``gestion_projet``, CHT13) via ``installations.selectors.
devis_id_du_chantier``.

Run :
    python manage.py test apps.ventes.tests.test_cht12_montants_devis_factures -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis, Facture, LigneDevis
from apps.ventes.selectors import montants_devis, montants_factures_par_devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht12-co-{n}', defaults={'nom': nom or f'CHT12 Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT12',
        email=f'cht12-{company.id}-{n}@example.invalid')


def make_devis(company, client, *, montant_ht=None, statut=Devis.Statut.ENVOYE):
    n = next(_seq)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CHT12-{n}', client=client,
        statut=statut, taux_tva=Decimal('20'))
    if montant_ht is not None:
        LigneDevis.objects.create(
            devis=devis, designation='Panneaux CHT12',
            quantite=Decimal('1'), prix_unitaire=Decimal(str(montant_ht)))
    return devis


def make_facture(company, client, devis=None, *, montant_ht, montant_ttc,
                 statut=Facture.Statut.EMISE):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-CHT12-{n}', client=client,
        devis=devis, statut=statut, taux_tva=Decimal('20'),
        montant_ht=Decimal(str(montant_ht)),
        montant_ttc=Decimal(str(montant_ttc)))


class TestMontantsDevis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_batch_renvoie_ht_ttc_par_devis(self):
        d1 = make_devis(self.company, self.client_obj, montant_ht=1000)
        d2 = make_devis(self.company, self.client_obj, montant_ht=2000)
        out = montants_devis([d1.id, d2.id], self.company)
        self.assertEqual(set(out.keys()), {d1.id, d2.id})
        self.assertEqual(out[d1.id]['ht'], Decimal('1000'))
        self.assertEqual(out[d1.id]['ttc'], Decimal('1200'))
        self.assertEqual(out[d2.id]['ht'], Decimal('2000'))

    def test_devis_inconnu_absent_du_resultat(self):
        self.assertEqual(montants_devis([999999], self.company), {})

    def test_scoping_societe(self):
        autre = make_company()
        autre_client = make_client(autre)
        d_autre = make_devis(autre, autre_client, montant_ht=500)
        out = montants_devis([d_autre.id], self.company)
        self.assertEqual(out, {})

    def test_liste_vide_est_un_no_op(self):
        self.assertEqual(montants_devis([], self.company), {})


class TestMontantsFacturesParDevis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj, montant_ht=1000)

    def test_agrege_plusieurs_factures_du_meme_devis(self):
        make_facture(
            self.company, self.client_obj, self.devis,
            montant_ht=300, montant_ttc=360)
        make_facture(
            self.company, self.client_obj, self.devis,
            montant_ht=700, montant_ttc=840)
        out = montants_factures_par_devis([self.devis.id], self.company)
        self.assertEqual(out[self.devis.id]['ht'], Decimal('1000'))
        self.assertEqual(out[self.devis.id]['ttc'], Decimal('1200'))

    def test_facture_annulee_exclue_par_defaut(self):
        make_facture(
            self.company, self.client_obj, self.devis,
            montant_ht=300, montant_ttc=360)
        make_facture(
            self.company, self.client_obj, self.devis,
            montant_ht=700, montant_ttc=840, statut=Facture.Statut.ANNULEE)
        out = montants_factures_par_devis([self.devis.id], self.company)
        self.assertEqual(out[self.devis.id]['ht'], Decimal('300'))

    def test_exclure_annulee_false_inclut_tout(self):
        make_facture(
            self.company, self.client_obj, self.devis,
            montant_ht=300, montant_ttc=360, statut=Facture.Statut.ANNULEE)
        out = montants_factures_par_devis(
            [self.devis.id], self.company, exclure_annulee=False)
        self.assertEqual(out[self.devis.id]['ht'], Decimal('300'))

    def test_devis_sans_facture_absent_du_resultat(self):
        autre_devis = make_devis(self.company, self.client_obj, montant_ht=100)
        out = montants_factures_par_devis([autre_devis.id], self.company)
        self.assertEqual(out, {})

    def test_scoping_societe(self):
        autre = make_company()
        autre_client = make_client(autre)
        autre_devis = make_devis(autre, autre_client, montant_ht=100)
        make_facture(
            autre, autre_client, autre_devis, montant_ht=100, montant_ttc=120)
        out = montants_factures_par_devis([autre_devis.id], self.company)
        self.assertEqual(out, {})
