"""
XFAC4 — Retenue à la source subie côté client (RAS TVA 2024 / RAS honoraires)
sur factures clients.

Une facture 10 000 TTC payée 9 250 + RAS 750 passe ``payee``, la retenue
apparaît dans l'état des attestations en attente, la réception de
l'attestation se coche avec justificatif, tests (solde exact, scoping).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac4_retenue_subie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, RetenueSubie

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac4-co', nom='XFAC4 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac4@example.com'):
    return Client.objects.create(
        company=company, nom='RAS', prenom='Client',
        email=email, telephone='+212600000052', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC4RetenueSubieTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac4_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'), created_by=self.admin,
        )

    def _url(self):
        return (f'/api/django/ventes/paiements/factures/{self.facture.id}/'
                'paiement-avec-retenue/')

    def test_paiement_avec_retenue_soldes_facture_exactly(self):
        """8 750 payé + 1 250 RAS-TVA (75 % de la TVA 1 666,67) soldent
        exactement 10 000.

        AFAC30 — la RAS se calcule sur son ASSIETTE (TVA × taux), plus sur
        « reste − montant » : l'ancien taux fabriqué (750 / 9 250) ne
        couvrait que 135 MAD de TVA réelle et soldait pourtant la facture."""
        r = self.api.post(self._url(), {
            'montant': '8750', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '75',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_du, Decimal('0'))
        retenue = RetenueSubie.objects.get(facture=self.facture)
        self.assertFalse(retenue.attestation_recue)

    def test_retenue_appears_in_attestations_en_attente(self):
        taux = Decimal('7.5')
        self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': str(taux),
        }, format='json')
        r = self.api.get(
            '/api/django/ventes/paiements/attestations-ras-en-attente/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertFalse(r.data[0]['attestation_recue'])

    def test_attestation_recue_marks_with_justificatif(self):
        self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '7.5',
        }, format='json')
        retenue = RetenueSubie.objects.get(facture=self.facture)
        r = self.api.post(
            f'/api/django/ventes/paiements/retenues/{retenue.id}/'
            'attestation-recue/',
            {'attestation_fichier': 'minio-key/attestation.pdf'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        retenue.refresh_from_db()
        self.assertTrue(retenue.attestation_recue)
        self.assertEqual(retenue.attestation_fichier, 'minio-key/attestation.pdf')
        self.assertIsNotNone(retenue.attestation_date)

    def test_entrees_invalides_ne_font_pas_planter(self):
        # ENF11 — id de facture / de retenue non entier : 404 (ValueError →
        # 500 avant) ; date d'attestation illisible ou justificatif trop long :
        # 400, la retenue reste « en attente ».
        base = '/api/django/ventes/paiements/'
        corps = {'montant': '10', 'date_paiement': '2026-01-01',
                 'taux': '5'}
        r = self.api.post(base + 'factures/abc/paiement-avec-retenue/',
                          corps, format='json')
        self.assertEqual(r.status_code, 404, r.data)
        r = self.api.post(base + 'retenues/abc/attestation-recue/', {},
                          format='json')
        self.assertEqual(r.status_code, 404, r.data)
        self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '7.5',
        }, format='json')
        retenue = RetenueSubie.objects.get(facture=self.facture)
        url = f'{base}retenues/{retenue.id}/attestation-recue/'
        for envoi in ({'attestation_date': 'pas-une-date'},
                      {'attestation_fichier': 'x' * 501}):
            r = self.api.post(url, envoi, format='json')
            self.assertEqual(r.status_code, 400, (envoi, r.data))
        retenue.refresh_from_db()
        self.assertFalse(retenue.attestation_recue)

    def test_cross_company_facture_404(self):
        other_company = make_company(slug='xfac4-other', nom='Other Co')
        other_admin = User.objects.create_user(
            username='xfac4_other_admin', password='x', role_legacy='admin',
            company=other_company,
        )
        other_api = auth(other_admin)
        r = other_api.post(self._url(), {
            'montant': '1000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '5',
        }, format='json')
        self.assertEqual(r.status_code, 404)

    def test_taux_out_of_range_rejected(self):
        r = self.api.post(self._url(), {
            'montant': '9000', 'date_paiement': timezone.now().date().isoformat(),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '150',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_montant_publie_au_seul_motif_positif(self):
        """api-fuzz-full 27/10 (moteur, « Failed Health Check ») — le champ
        publiait le motif décimal générique (signé) et la vue resserrait au
        motif positif : deux motifs sur un champ, que le générateur ne sait
        pas fusionner. Le champ publie LE motif positif, que le
        ``DecimalField`` (min 0,01, 12 chiffres) applique à l'identique."""
        import re
        from drf_spectacular.drainage import get_override
        from apps.ventes.domain.bornes import MOTIF_MONTANT_POSITIF
        from apps.ventes.serializers_facturation import (
            PaiementAvecRetenueEntreeSerializer)
        champ = PaiementAvecRetenueEntreeSerializer().fields['montant']
        self.assertEqual(get_override(champ, 'field')['pattern'],
                         MOTIF_MONTANT_POSITIF)
        motif = re.compile(MOTIF_MONTANT_POSITIF)
        for brut in ('0.01', '.5', '1.', '9999999999.99', '00012'):
            self.assertTrue(motif.fullmatch(brut), brut)
            champ.run_validation(brut)
        for brut in ('0', '0.00', '-1', '10000000000', '1.234'):
            self.assertIsNone(motif.fullmatch(brut), brut)
        # Plus de surcouche ``allOf`` qui répétait le motif sur l'opération.
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        from apps.ventes import urls as ventes_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/ventes/', include(ventes_urls)),
        ]).get_schema(request=None, public=True)
        corps = schema['paths'][
            '/api/django/ventes/paiements/factures/{facture_id}/'
            'paiement-avec-retenue/']['post']['requestBody']['content'][
            'application/json']['schema']
        self.assertEqual(corps, {
            '$ref': '#/components/schemas/PaiementAvecRetenueEntreeRequest'})
        props = schema['components']['schemas'][
            'PaiementAvecRetenueEntreeRequest']
        self.assertEqual(props['properties']['montant']['pattern'],
                         MOTIF_MONTANT_POSITIF)
        self.assertIn('montant', props['required'])
