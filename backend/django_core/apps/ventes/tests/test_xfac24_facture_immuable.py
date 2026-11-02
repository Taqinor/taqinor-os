"""
XFAC24 — Immutabilité de la facture émise (opt-in) — correction par avoir
uniquement.

Toggle ON : PATCH d'un montant sur une facture émise = 400 explicite, mais
avoir/annulation/paiement passent. Toggle OFF : zéro changement. Le
changement de toggle est journalisé (SettingsAuditLog).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac24_facture_immuable -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac24-co', nom='XFAC24 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac24@example.com'):
    return Client.objects.create(
        company=company, nom='Immuable', prenom='Client',
        email=email, telephone='+212600000067', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC24FactureImmuableTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac24_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='SKU-XFAC24',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10,
        )
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-7001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), created_by=self.admin,
        )
        self.ligne = LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Panneau', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'),
        )

    def _activate(self):
        profile = CompanyProfile.get(company=self.company)
        profile.factures_immuables = True
        profile.save(update_fields=['factures_immuables'])

    def test_devis_et_bc_non_detachables_apres_emission(self):
        """AARG28 (C-AARG-022) — PATCH à nul de `devis` et de `bon_commande`
        sur une facture émise : 409, rien d'écrit ; sur un brouillon : 200."""
        from apps.ventes.models import BonCommande, Devis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-7001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-7001',
            client=self.client_obj, statut=BonCommande.Statut.CONFIRME)
        Facture.objects.filter(pk=self.facture.pk).update(
            devis=devis, bon_commande=bc)
        url = f'/api/django/ventes/factures/{self.facture.id}/'
        for corps in ({'devis': None}, {'bon_commande': None}):
            with self.subTest(corps=corps):
                r = self.api.patch(url, corps, format='json')
                self.assertEqual(r.status_code, 409, r.data)
                self.assertIn('Montant figé après émission', str(r.data))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.devis_id, devis.pk)
        self.assertEqual(self.facture.bon_commande_id, bc.pk)
        Facture.objects.filter(pk=self.facture.pk).update(
            statut=Facture.Statut.BROUILLON)
        for corps in ({'devis': None}, {'bon_commande': None}):
            r = self.api.patch(url, corps, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertIsNone(self.facture.devis_id)
        self.assertIsNone(self.facture.bon_commande_id)

    def test_libelle_et_date_livraison_figes_apres_emission(self):
        """AARG49 (C-AARG-052) — imprimés sur le PDF envoyé : 409 dès que la
        valeur change hors brouillon ; le PUT du formulaire inchangé passe."""
        from datetime import date
        Facture.objects.filter(pk=self.facture.pk).update(
            libelle='Installation 6 kWc', date_livraison=date(2026, 10, 20))
        url = f'/api/django/ventes/factures/{self.facture.id}/'
        for corps in ({'date_livraison': '2026-11-01'}, {'libelle': 'Autre'},
                      {'date_livraison': None}):
            with self.subTest(corps=corps):
                r = self.api.patch(url, corps, format='json')
                self.assertEqual(r.status_code, 409, r.data)
                self.assertIn('Montant figé après émission', str(r.data))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.libelle, 'Installation 6 kWc')
        self.assertEqual(self.facture.date_livraison, date(2026, 10, 20))
        # Forme de `FactureForm.jsx` : les valeurs relues, inchangées.
        r = self.api.put(url, {
            'client': self.client_obj.id, 'bon_commande': None,
            'statut': self.facture.statut, 'date_echeance': None,
            'taux_tva': '20.00', 'remise_globale': '0.00',
            'statut_teledeclaration': self.facture.statut_teledeclaration,
            'note': None, 'reference_commande_client': '',
            'conditions_paiement': '', 'libelle': 'Installation 6 kWc',
            'date_livraison': '2026-10-20'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        Facture.objects.filter(pk=self.facture.pk).update(
            statut=Facture.Statut.BROUILLON)
        for corps in ({'date_livraison': '2026-11-01'}, {'libelle': 'Autre'}):
            r = self.api.patch(url, corps, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.libelle, 'Autre')
        self.assertEqual(self.facture.date_livraison, date(2026, 11, 1))

    def test_flag_off_facture_freely_editable_byte_identical(self):
        # ATOT9 — comportement INVERSÉ par la tâche (D-ATOT-1) : flag OFF, un
        # champ d'ARGENT d'une facture émise reste figé (409, rien écrit) ;
        # un champ non financier reste librement modifiable.
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'remise_globale': '10'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.remise_globale, Decimal('0'))
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'conditions_paiement': 'Virement à 30 jours'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_flag_on_financial_field_patch_refused_on_emise(self):
        self._activate()
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'remise_globale': '10'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.remise_globale, Decimal('0'))

    def test_flag_on_non_financial_field_still_editable(self):
        self._activate()
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'conditions_paiement': 'Virement à 30 jours'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(
            self.facture.conditions_paiement, 'Virement à 30 jours')

    def test_flag_on_brouillon_still_freely_editable(self):
        self._activate()
        self.facture.statut = Facture.Statut.BROUILLON
        self.facture.save(update_fields=['statut'])
        r = self.api.patch(
            f'/api/django/ventes/factures/{self.facture.id}/',
            {'remise_globale': '10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_flag_on_ligne_facture_update_refused(self):
        self._activate()
        r = self.api.patch(
            f'/api/django/ventes/factures-lignes/{self.ligne.id}/',
            {'quantite': '5'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)

    def test_flag_on_ligne_facture_delete_refused(self):
        self._activate()
        r = self.api.delete(
            f'/api/django/ventes/factures-lignes/{self.ligne.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(
            LigneFacture.objects.filter(pk=self.ligne.pk).exists())

    def test_flag_on_paiement_and_avoir_still_pass(self):
        self._activate()
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'enregistrer-paiement/',
            {'montant': '1200', 'date_paiement': timezone.now().date().isoformat(),
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)

    def test_toggle_change_is_audited(self):
        SettingsAuditLog.objects.all().delete()
        r = self.api.patch(
            '/api/django/parametres/update/', {'factures_immuables': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(SettingsAuditLog.objects.filter(
            field='factures_immuables').exists())
