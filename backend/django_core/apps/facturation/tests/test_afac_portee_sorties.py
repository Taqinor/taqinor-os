"""AFAC54 (C-AFAC-048) — la portée de visibilité de ``FactureViewSet``
(``scope_queryset(created_by)``, portée équipe) s'applique aux sorties hors
viewset : lettre de relance PDF, lettre de relance premium, prévision de
trésorerie et alerte crédit client.

Rejoue les sondes FDOC-9 / FEVT-3 (viewset 404 mais lettre premium 200,
cash-flow avec la facture et le client du collègue, credit-warning 200).
APIClient, rôles réels (``records_scope_equipe``, sans superviseur commun),
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_portee_sorties"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


class PorteeSortiesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        from apps.ventes.models import Facture, FollowupLevel
        from authentication.models import Company
        cls.company = Company.objects.create(nom='AFAC54', slug='afac54-co')
        role_equipe = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_equipe'],
            est_systeme=False)
        cls.a = User.objects.create_user(
            username='afac54_a', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.b = User.objects.create_user(
            username='afac54_b', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.admin = User.objects.create_user(
            username='afac54_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_b = Client.objects.create(
            company=cls.company, nom='Client de B', prenom='AFAC54',
            email='afac54-b@example.invalid')
        cls.facture_b = Facture.objects.create(
            company=cls.company, reference='FAC-AFAC54-B', client=cls.client_b,
            statut=Facture.Statut.EN_RETARD, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), created_by=cls.b,
            date_echeance=timezone.now().date() - timedelta(days=40))
        FollowupLevel.objects.create(
            company=cls.company, ordre=1, nom='Rappel', delai_jours=7)

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _lettre_premium(self, user):
        return self._api(user).get(
            f'/api/django/ventes/factures/{self.facture_b.id}/'
            'lettre-relance-premium/?niveau=2')

    def _lettre_pdf(self, user):
        return self._api(user).get(
            f'/api/django/ventes/factures/{self.facture_b.id}/'
            'lettre-relance-pdf/')

    def _cash_flow_refs(self, user):
        r = self._api(user).get('/api/django/ventes/insights/cash-flow/')
        self.assertEqual(r.status_code, 200, r.data)
        return [row['facture_reference'] for row in r.data['rows']]

    def _credit(self, user):
        return self._api(user).get(
            f'/api/django/ventes/clients/{self.client_b.id}/credit-warning/')

    def test_viewset_deja_hors_portee(self):
        r = self._api(self.a).get(
            f'/api/django/ventes/factures/{self.facture_b.id}/')
        self.assertEqual(r.status_code, 404)

    def test_lettre_premium_hors_portee_404(self):
        self.assertEqual(self._lettre_premium(self.a).status_code, 404)

    def test_lettre_relance_pdf_hors_portee_404(self):
        self.assertEqual(self._lettre_pdf(self.a).status_code, 404)

    def test_cash_flow_borne_portee(self):
        self.assertNotIn('FAC-AFAC54-B', self._cash_flow_refs(self.a))
        self.assertIn('FAC-AFAC54-B', self._cash_flow_refs(self.b))

    def test_credit_warning_hors_portee_404(self):
        self.assertEqual(self._credit(self.a).status_code, 404)

    def test_fiche_remise_chantier_annule_ou_non_installe_409(self):
        """ACSV99 : la fiche de remise / garantie applique la garde d'état des
        documents de chantier (annulé ou pas installé ⇒ 409 nommé)."""
        from apps.installations.models import Installation
        chantier = Installation.objects.create(
            company=self.company, reference='CH-ACSV99', client=self.client_b,
            statut=Installation.Statut.SIGNE)
        url = f'/api/django/ventes/chantiers/{chantier.id}/fiche-remise-premium/'
        r = self._api(self.admin).get(url)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('installé', r.data['detail'])
        Installation.objects.filter(pk=chantier.pk).update(
            statut=Installation.Statut.INSTALLE, annule=True)
        r = self._api(self.admin).get(url)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data['detail'], 'Chantier annulé')
        Installation.objects.filter(pk=chantier.pk).update(
            annule=False, statut=Installation.Statut.RECEPTIONNE)
        self.assertEqual(self._api(self.admin).get(url).status_code, 200)

    def test_fiche_remise_exige_la_lecture_du_chantier(self):
        """ADRG8 (C-ADRG-022, D-APFS-4) — la fiche de remise d'un chantier
        installé : 403 sans PDF pour un rôle sans lecture du module chantiers
        ni ``ventes_voir`` (Commercial terrain, Admin RH) ; le Responsable
        (dans la portée de la fiche chantier) obtient toujours le PDF.
        Mutant : retirer la garde de lecture ⇒ échec."""
        from apps.installations.models import Installation
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ADMIN_RH_PERMISSIONS, COMMERCIAL_TERRAIN_PERMISSIONS,
            RESPONSABLE_PERMISSIONS)

        def compte(nom, permissions, legacy):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=list(permissions),
                                       est_systeme=False)
            return User.objects.create_user(
                username=f'adrg8_{nom}', password='x', role=role,
                role_legacy=legacy, company=self.company)

        responsable = compte('Responsable', RESPONSABLE_PERMISSIONS,
                             'responsable')
        chantier = Installation.objects.create(
            company=self.company, reference='CH-ADRG8', client=self.client_b,
            statut=Installation.Statut.RECEPTIONNE, created_by=responsable)
        url = f'/api/django/ventes/chantiers/{chantier.id}/fiche-remise-premium/'
        for nom, perms in (('Terrain', COMMERCIAL_TERRAIN_PERMISSIONS),
                           ('AdminRH', ADMIN_RH_PERMISSIONS)):
            with self.subTest(role=nom):
                r = self._api(compte(nom, perms, 'normal')).get(url)
                self.assertEqual(r.status_code, 403)
                self.assertNotEqual(r.get('Content-Type'), 'application/pdf')
        r = self._api(responsable).get(url)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_admin_inchange(self):
        self.assertIn('FAC-AFAC54-B', self._cash_flow_refs(self.admin))
        self.assertEqual(self._credit(self.admin).status_code, 200)
        self.assertEqual(self._credit(self.b).status_code, 200)
        # La lettre n'est plus un 404 pour le propriétaire et l'admin (le
        # rendu lui-même est hors du constat).
        self.assertNotEqual(self._lettre_premium(self.admin).status_code, 404)
        self.assertNotEqual(self._lettre_pdf(self.b).status_code, 404)

    def test_telephone_client_masque_sans_client_pii_voir(self):
        """APFS27 (C-APFS-028) — sans ``client_pii_voir`` : téléphone client
        null sur la fiche facture et les relances (deux routes) ; Responsable
        témoin et compte hérité : présent."""
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        Client.objects.filter(pk=self.client_b.pk).update(
            telephone='0661028028')

        def compte(nom, permissions):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=permissions,
                                       est_systeme=False)
            return User.objects.create_user(
                username=f'apfs27_{len(nom)}', password='x', role=role,
                role_legacy='responsable', company=self.company)
        sans = compte('Responsable sans client_pii_voir', [
            p for p in RESPONSABLE_PERMISSIONS if p != 'client_pii_voir'])
        temoin = compte('Responsable', list(RESPONSABLE_PERMISSIONS))

        def telephones(user):
            api = self._api(user)
            fiche = api.get(f'/api/django/ventes/factures/{self.facture_b.id}/')
            self.assertEqual(fiche.status_code, 200, fiche.content)
            vus = [fiche.data['client_telephone']]
            for url in ('/api/django/facturation/relances/',
                        '/api/django/ventes/relances/'):
                r = api.get(url)
                self.assertEqual(r.status_code, 200, r.content)
                vus.append(next(x for x in r.data
                                if x['id'] == self.facture_b.id)
                           ['client_telephone'])
            return vus
        self.assertEqual(telephones(sans), [None] * 3)
        self.assertEqual(telephones(temoin), ['0661028028'] * 3)
        self.assertEqual(telephones(self.admin), ['0661028028'] * 3)
