"""ATOT9 (C-ATOT-007) — les champs d'argent d'une facture (`montant_ht/tva/
ttc`, `remise_globale`, `taux_tva`, `pourcentage`, `arrondi_*`) et ses lignes
ne sont plus modifiables hors BROUILLON, quel que soit `factures_immuables`
(défaut OFF) : la correction passe par un avoir ou `remettre-brouillon`.

Rejoue la sonde V1 TFAC-7 : aujourd'hui PATCH `montant_ttc=1.00` sur une
facture émise = 200, ligne ajoutée à une facture payée = 201, aucune trace.
Endpoints réels, aucun mock. Appelants front relevés (grep
`updateFacture|factures-lignes`) : FactureForm.jsx, ventesSlice.js,
ventesApi.js, OcrUpload.jsx — éditions de brouillon, aucune écriture
d'argent sur une facture émise attendue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_montants_figes"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class MontantsFigesTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT9 Co', slug=f'atot9-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Fige', prenom='ATOT9',
            email=f'atot9-{_nxt()}@example.invalid')
        self.user = User.objects.create_user(
            username=f'atot9_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ATOT9', sku=f'ATOT9-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _facture(self, statut, **extra):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-ATOT9-{_nxt()}',
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20.00'), created_by=self.user, **extra)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        return facture

    def test_patch_montant_emise_refuse(self):
        from apps.ventes.models import Facture
        facture = self._facture(
            Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
            type_facture=Facture.TypeFacture.ACOMPTE,
            pourcentage=Decimal('30'))
        r = self.api.patch(f'/api/django/ventes/factures/{facture.id}/',
                           {'montant_ttc': '1.00'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Montant figé', str(r.data))
        facture.refresh_from_db()
        self.assertEqual(facture.montant_ttc, Decimal('1200.00'))
        # Un champ non financier reste accepté.
        r = self.api.patch(f'/api/django/ventes/factures/{facture.id}/',
                           {'note': 'Relancé par téléphone'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_ligne_sur_payee_refusee(self):
        from apps.ventes.models import Facture, LigneFacture
        facture = self._facture(Facture.Statut.PAYEE)
        avant = list(LigneFacture.objects.filter(facture=facture)
                     .values_list('id', 'quantite', 'prix_unitaire'))
        r = self.api.post('/api/django/ventes/factures-lignes/', {
            'facture': facture.id, 'produit': self.produit.id,
            'designation': 'Ajout tardif', 'quantite': '1',
            'prix_unitaire': '500'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        ligne = LigneFacture.objects.filter(facture=facture).first()
        r = self.api.patch(f'/api/django/ventes/factures-lignes/{ligne.id}/',
                           {'prix_unitaire': '1'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(
            list(LigneFacture.objects.filter(facture=facture)
                 .values_list('id', 'quantite', 'prix_unitaire')), avant)

    def test_brouillon_modifiable_trace(self):
        from apps.ventes.models import Facture, FactureActivity
        facture = self._facture(Facture.Statut.BROUILLON)
        r = self.api.patch(f'/api/django/ventes/factures/{facture.id}/',
                           {'remise_globale': '5'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.remise_globale, Decimal('5'))
        trace = FactureActivity.objects.get(facture=facture,
                                            field='remise_globale')
        self.assertEqual(Decimal(trace.new_value), Decimal('5'))
        self.assertEqual(Decimal(trace.old_value or '0'), Decimal('0'))
