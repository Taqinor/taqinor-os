"""Tests NTPAY5 — Registre des dépôts déclaratifs & accusés.

Couvre : téléverser un récépissé crée un ``DepotDeclaratif`` LIÉ à l'échéance
et la bascule en « déposée » ; un dépôt REJETÉ conserve son motif et n'avance
JAMAIS l'échéance ; un rejet sans motif est refusé en nommant le champ ; le
type et la période sont recopiés de l'échéance (jamais saisis à part) ;
l'endpoint et l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import DepotDeclaratif, EcheanceDeclarative, PeriodePaie
from apps.paie.services import (
    enregistrer_depot_declaratif,
    ensure_defaults,
    generer_echeances_periode,
)


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class DepotDeclaratifTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay5')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        generer_echeances_periode(self.periode)
        self.echeance_bds = EcheanceDeclarative.objects.get(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS)

    def test_depot_bascule_l_echeance_en_deposee(self):
        depot = enregistrer_depot_declaratif(
            self.echeance_bds,
            reference_depot='DAM-2026-06-001',
            date_depot=date(2026, 7, 8),
            fichier_key='attachments/1/abc.pdf',
            montant_declare=Decimal('12345.67'))
        self.echeance_bds.refresh_from_db()
        self.assertEqual(self.echeance_bds.statut,
                         EcheanceDeclarative.STATUT_DEPOSEE)
        self.assertEqual(depot.echeance_id, self.echeance_bds.id)
        self.assertEqual(depot.company_id, self.co.id)
        self.assertEqual(depot.reference_depot, 'DAM-2026-06-001')
        self.assertEqual(depot.fichier_key, 'attachments/1/abc.pdf')
        self.assertEqual(depot.montant_declare, Decimal('12345.67'))

    def test_type_et_periode_recopies_de_l_echeance(self):
        depot = enregistrer_depot_declaratif(self.echeance_bds)
        self.assertEqual(depot.type_declaration, EcheanceDeclarative.TYPE_BDS)
        self.assertEqual(depot.annee, 2026)
        self.assertEqual(depot.mois, 6)

    def test_etat_9421_est_annuel_sans_mois(self):
        echeance = EcheanceDeclarative.objects.filter(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_9421).first()
        if echeance is None:  # l'échéance annuelle n'existe pas tous les mois
            echeance = EcheanceDeclarative.objects.create(
                company=self.co, periode=self.periode,
                type_echeance=EcheanceDeclarative.TYPE_9421,
                date_limite=date(2027, 2, 28))
        depot = enregistrer_depot_declaratif(echeance)
        self.assertIsNone(depot.mois)
        self.assertEqual(depot.annee, 2026)

    def test_rejet_conserve_le_motif_et_n_avance_pas_l_echeance(self):
        statut_avant = self.echeance_bds.statut
        depot = enregistrer_depot_declaratif(
            self.echeance_bds,
            statut=DepotDeclaratif.STATUT_REJETE,
            motif_rejet='Numéro d’affiliation inconnu.')
        self.echeance_bds.refresh_from_db()
        self.assertEqual(depot.statut, DepotDeclaratif.STATUT_REJETE)
        self.assertEqual(depot.motif_rejet, 'Numéro d’affiliation inconnu.')
        self.assertEqual(self.echeance_bds.statut, statut_avant)

    def test_rejet_sans_motif_refuse_en_nommant_le_champ(self):
        with self.assertRaises(DjangoValidationError) as ctx:
            enregistrer_depot_declaratif(
                self.echeance_bds, statut=DepotDeclaratif.STATUT_REJETE)
        self.assertIn('motif_rejet', ctx.exception.message_dict)

    def test_statut_inconnu_refuse(self):
        with self.assertRaises(DjangoValidationError) as ctx:
            enregistrer_depot_declaratif(self.echeance_bds, statut='zzz')
        self.assertIn('statut', ctx.exception.message_dict)

    def test_echeance_payee_ne_redescend_jamais(self):
        self.echeance_bds.statut = EcheanceDeclarative.STATUT_PAYEE
        self.echeance_bds.save(update_fields=['statut'])
        enregistrer_depot_declaratif(self.echeance_bds)
        self.echeance_bds.refresh_from_db()
        self.assertEqual(self.echeance_bds.statut,
                         EcheanceDeclarative.STATUT_PAYEE)

    def test_plusieurs_depots_successifs_sont_conserves(self):
        enregistrer_depot_declaratif(
            self.echeance_bds, statut=DepotDeclaratif.STATUT_REJETE,
            motif_rejet='Fichier illisible.')
        enregistrer_depot_declaratif(
            self.echeance_bds, reference_depot='DAM-2')
        self.assertEqual(self.echeance_bds.depots.count(), 2)


class DepotDeclaratifApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay5-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay5-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        generer_echeances_periode(self.periode)
        self.echeance = EcheanceDeclarative.objects.get(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS)
        self.url = (
            f'/api/django/paie/echeances-declaratives/{self.echeance.id}'
            '/depots/')

    def test_post_cle_deja_stockee(self):
        rep = self.api.post(self.url, {
            'reference_depot': 'DAM-42',
            'fichier_key': 'attachments/9/recu.pdf',
            'montant_declare': '1000.50',
            'date_depot': '2026-07-09',
        }, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual(rep.data['echeance']['statut'], 'deposee')
        self.assertEqual(rep.data['depot']['reference_depot'], 'DAM-42')

    def test_post_rejet_sans_motif_400(self):
        rep = self.api.post(self.url, {'statut': 'rejete'}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('motif_rejet', rep.data)

    def test_post_date_invalide_400(self):
        rep = self.api.post(self.url, {'date_depot': '09/07/2026'},
                            format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('date_depot', rep.data)

    def test_get_liste_les_depots(self):
        self.api.post(self.url, {'reference_depot': 'A'}, format='json')
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data), 1)

    def test_isolation_societe(self):
        autre = make_company('ntpay5-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        generer_echeances_periode(periode_autre)
        echeance_autre = EcheanceDeclarative.objects.filter(
            company=autre, periode=periode_autre).first()
        rep = self.api.post(
            f'/api/django/paie/echeances-declaratives/{echeance_autre.id}'
            '/depots/', {'reference_depot': 'X'}, format='json')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(
            DepotDeclaratif.objects.filter(company=autre).count(), 0)
