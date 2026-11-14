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

    def test_lignes_facture_hors_portee_404(self):
        """ALEC25 (C-ALEC-021) — les lignes de facture suivent la portée de
        ``FactureViewSet`` sur les deux routes montées : A ne liste pas la
        ligne de la facture brouillon de B, détail et PATCH 404, ligne
        inchangée ; l'admin lit (200). Mutant : retirer ``scope_queryset``
        ⇒ échec."""
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        produit = Produit.objects.create(
            company=self.company, nom='Kit ALEC25', sku='ALEC25-K',
            prix_vente=Decimal('1000'), quantite_stock=0)
        brouillon = Facture.objects.create(
            company=self.company, reference='BROUILLON-ALEC25',
            client=self.client_b, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.b)
        ligne = LigneFacture.objects.create(
            facture=brouillon, produit=produit, designation='Ligne de B',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        # ALEC44 (C-ALEC-VER1-103) — même preuve avec deux comptes au
        # Commercial LIVRÉ (codes de ``CANONICAL_SYSTEM_ROLES``, portée
        # « soi », sans superviseur commun) ; B2 liste sa ligne.
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        livre = Role.objects.create(
            company=self.company, nom='Commercial livré ALEC44',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Commercial']))
        a2, b2 = (User.objects.create_user(
            username=f'alec44_{n}', password='x', role=livre,
            role_legacy='normal', company=self.company) for n in ('a2', 'b2'))
        ligne2 = LigneFacture.objects.create(
            facture=Facture.objects.create(
                company=self.company, reference='BROUILLON-ALEC44',
                client=self.client_b, statut=Facture.Statut.BROUILLON,
                taux_tva=Decimal('20'), created_by=b2),
            produit=produit, designation='Ligne de B2',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        def ids(user, base):
            r = self._api(user).get(base)
            self.assertEqual(r.status_code, 200, r.data)
            return [x['id'] for x in (r.data['results'] if isinstance(r.data, dict) else r.data)]
        for lecteur, proprio, cible, nom in ((self.a, self.b, ligne, 'Ligne de B'),
                                             (a2, b2, ligne2, 'Ligne de B2')):
            api = self._api(lecteur)
            for base in ('/api/django/ventes/factures-lignes/',
                         '/api/django/facturation/factures-lignes/'):
                with self.subTest(base=base, lecteur=lecteur.username):
                    self.assertNotIn(cible.pk, ids(lecteur, base))
                    self.assertEqual(api.get(f'{base}{cible.pk}/').status_code,
                                     404)
                    if proprio is b2:
                        self.assertIn(cible.pk, ids(proprio, base))
            r = api.patch(f'/api/django/ventes/factures-lignes/{cible.pk}/',
                          {'designation': 'Pirate'}, format='json')
            self.assertEqual(r.status_code, 404)
            cible.refresh_from_db()
            self.assertEqual(cible.designation, nom)
        r = self._api(self.admin).get(
            f'/api/django/ventes/factures-lignes/{ligne.pk}/')
        self.assertEqual(r.status_code, 200, r.data)

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

    def test_releve_et_emission_masquent_les_coordonnees(self):
        """ALEC33 (C-ALEC-030) — sans ``client_pii_voir`` : e-mail, téléphone
        et adresse du relevé à ``null`` et ``client_telephone`` à ``null``
        dans la réponse d'émission (sérialiseur rendu AVEC la requête) ; un
        Responsable témoin les reçoit ; le relevé interne (``user=None``)
        inchangé. Mutant : retirer ``context=`` d'``emettre`` ⇒ échec."""
        from apps.crm.models import Client
        from apps.facturation.recouvrement import _releve_data
        from apps.roles.models import Role
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        Client.objects.filter(pk=self.client_b.pk).update(
            telephone='0661028028', adresse='12 rue ALEC33')
        self.client_b.refresh_from_db()
        produit = Produit.objects.create(
            company=self.company, nom='Kit ALEC33', sku='ALEC33-K',
            prix_vente=Decimal('1000'), quantite_stock=100)

        def compte(nom, permissions):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=permissions + ['encaisser'],
                                       est_systeme=False)
            return User.objects.create_user(
                username=f'alec33_{len(nom)}', password='x', role=role,
                role_legacy='responsable', company=self.company)
        sans = compte('Responsable sans client_pii_voir', [
            p for p in RESPONSABLE_PERMISSIONS if p != 'client_pii_voir'])
        temoin = compte('Responsable', list(RESPONSABLE_PERMISSIONS))
        url = f'/api/django/facturation/clients/{self.client_b.id}/releve/'
        attendus = ((sans, None), (temoin, '0661028028'))
        for user, tel in attendus:
            with self.subTest(user=user.username):
                r = self._api(user).get(url)
                self.assertEqual(r.status_code, 200, r.data)
                coord = r.data['client']
                self.assertEqual(coord['telephone'], tel)
                self.assertEqual(coord['email'] is None, tel is None)
                self.assertEqual(coord['adresse'] is None, tel is None)
                brouillon = Facture.objects.create(
                    company=self.company, reference=f'BROUILLON-A33-{user.pk}',
                    client=self.client_b, statut=Facture.Statut.BROUILLON,
                    taux_tva=Decimal('20'), created_by=user)
                LigneFacture.objects.create(
                    facture=brouillon, produit=produit, designation='Kit',
                    quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
                r = self._api(user).post(
                    f'/api/django/ventes/factures/{brouillon.id}/emettre/')
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data['client_telephone'], tel)
                self.assertEqual(Facture.objects.get(pk=brouillon.pk).statut,
                                 Facture.Statut.EMISE)
        interne = _releve_data(self.client_b)['client']
        self.assertEqual(interne['telephone'], '0661028028')
        self.assertEqual(interne['adresse'], '12 rue ALEC33')
