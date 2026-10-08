"""ASEC29 (C-ASEC-004, D-ASEC-1 ; frère LCOUT-1 = C-ALEA-001) — les gestes
d'argent (`abandonner-solde`, `enregistrer-paiement`, `facturer-complet`,
création d'avoir) sont réservés au code `encaisser` (Administrateur,
Directeur, Commercial et Commercial responsable par défaut), et
`FactureViewSet.get_permissions` respecte la garde déclarée par l'@action.

Rouge sur 51f22174f (V6 : Commercial terrain et Admin RH → `abandonner-solde`
200, facture → `payee`). Rôles système réels (`init_roles`), endpoints réels,
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_asec29_gestes_argent"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

User = get_user_model()

AUTORISES = ('Directeur', 'Commercial')
REFUSES = ('Commercial sans encaisser', 'Commercial terrain', 'Technicien',
           'Admin RH')
GESTES = ('abandonner_solde', 'enregistrer_paiement', 'facturer_complet',
          'creer_avoir')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class GestesArgentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(nom='ASEC29', slug='asec29-co')
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.company)}
        commercial = roles['Commercial']
        sans = Role.objects.create(
            company=self.company, nom='Commercial sans encaisser',
            permissions=[c for c in commercial.permissions
                         if c != 'encaisser'])
        roles['Commercial sans encaisser'] = sans
        self.users = {}
        for nom in AUTORISES + REFUSES:
            self.users[nom] = User.objects.create_user(
                username=f'asec29-{_nxt()}', password='x',
                role_legacy='normal', role=roles[nom], company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Argent', prenom='ASEC29',
            email='asec29@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Avoir ASEC29', sku='ASEC29-P',
            prix_vente=Decimal('0'), quantite_stock=0)
        # Produit de la ligne du devis : facturer-complet décompte le stock.
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ASEC29', sku='ASEC29-K',
            prix_vente=Decimal('1000'), quantite_stock=1000)

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _facture(self, user):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-ASEC29-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), created_by=user)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Centrale',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return facture

    def _devis(self, user):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASEC29-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), created_by=user)
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return devis

    def _geste(self, geste, user):
        """Joue le geste ; renvoie (réponse, objet relu pour la persistance)."""
        api = self._api(user)
        if geste == 'facturer_complet':
            devis = self._devis(user)
            r = api.post(
                f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
                {'paiements': []}, format='json')
            return r, devis
        facture = self._facture(user)
        base = f'/api/django/ventes/factures/{facture.id}/'
        if geste == 'abandonner_solde':
            r = api.post(base + 'abandonner-solde/',
                         {'motif': 'geste_commercial'}, format='json')
        elif geste == 'enregistrer_paiement':
            r = api.post(base + 'enregistrer-paiement/', {
                'montant': '100', 'date_paiement': date.today().isoformat(),
                'mode': 'virement'}, format='json')
        else:
            r = api.post(base + 'creer-avoir/', {
                'lignes': [{'designation': 'Geste', 'quantite': '1',
                            'prix_unitaire': '100', 'taux_tva': '20',
                            'produit': self.produit.id}]}, format='json')
        return r, facture

    def test_matrice_role_geste(self):
        from apps.ventes.models import Avoir, Facture, Paiement
        for geste in GESTES:
            for nom in AUTORISES:
                with self.subTest(geste=geste, role=nom):
                    r, _ = self._geste(geste, self.users[nom])
                    self.assertIn(r.status_code, (200, 201), r.data)
            for nom in REFUSES:
                with self.subTest(geste=geste, role=nom):
                    r, objet = self._geste(geste, self.users[nom])
                    self.assertEqual(r.status_code, 403, r.data)
                    if geste == 'facturer_complet':
                        self.assertFalse(
                            Facture.objects.filter(devis=objet).exists())
                        continue
                    objet.refresh_from_db()
                    self.assertEqual(objet.statut, Facture.Statut.EMISE)
                    self.assertFalse(
                        Paiement.objects.filter(facture=objet).exists())
                    self.assertFalse(
                        Avoir.objects.filter(facture=objet).exists())
                    self.assertFalse(objet.abandon_montant)

    def test_get_permissions_respecte_action(self):
        from apps.ventes.views.facture import FactureViewSet, PeutEncaisser
        fabrique = APIRequestFactory()
        for action in ('enregistrer_paiement', 'abandonner_solde',
                       'creer_avoir', 'encaissement_groupe'):
            with self.subTest(action=action):
                vue = FactureViewSet()
                vue.action = action
                vue.request = Request(fabrique.post('/'))
                gardes = vue.get_permissions()
                self.assertEqual([type(p) for p in gardes], [PeutEncaisser])
