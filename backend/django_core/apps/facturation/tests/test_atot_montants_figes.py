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
        self.assertEqual(r.status_code, 409, r.data)
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
        self.assertEqual(r.status_code, 409, r.data)
        ligne = LigneFacture.objects.filter(facture=facture).first()
        r = self.api.patch(f'/api/django/ventes/factures-lignes/{ligne.id}/',
                           {'prix_unitaire': '1'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(
            list(LigneFacture.objects.filter(facture=facture)
                 .values_list('id', 'quantite', 'prix_unitaire')), avant)

    def test_ligne_ne_change_pas_de_facture(self):
        """ATOT40 — ``PATCH {facture}`` ne déplace jamais une ligne."""
        from apps.ventes.models import Facture, LigneFacture
        emise = self._facture(
            Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'))
        brouillon = self._facture(Facture.Statut.BROUILLON)
        autre = self._facture(Facture.Statut.BROUILLON)
        ligne = LigneFacture.objects.get(facture=brouillon)
        LigneFacture.objects.filter(pk=ligne.pk).update(
            prix_unitaire=Decimal('500'))
        url = f'/api/django/ventes/factures-lignes/{ligne.id}/'
        for cible in (emise, autre):
            r = self.api.patch(url, {'facture': cible.id}, format='json')
            self.assertEqual(r.status_code, 409, r.data)
            self.assertIn('ne change pas de facture', str(r.data))
        ligne.refresh_from_db()
        self.assertEqual(ligne.facture_id, brouillon.id)
        self.assertEqual(LigneFacture.objects.filter(facture=emise).count(), 1)
        self.assertEqual(LigneFacture.objects.filter(facture=autre).count(), 1)
        emise.refresh_from_db()
        self.assertEqual(emise.montant_ttc, Decimal('1200.00'))
        r = self.api.patch(url, {'facture': brouillon.id, 'quantite': '2'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, Decimal('2'))

    def test_identite_et_retenue_figees_sur_emise(self):
        """ATOT41 — client, retenue, devise figés hors brouillon, réglage
        OFF comme ON ; corps inchangé et note acceptés ; brouillon libre."""
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Facture
        client_b = Client.objects.create(
            company=self.company, nom='Autre', prenom='B',
            email=f'atot41-{_nxt()}@example.invalid')
        facture = self._facture(
            Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'))
        url = f'/api/django/ventes/factures/{facture.id}/'
        profile = CompanyProfile.get(company=self.company)
        for flag in (False, True):
            profile.factures_immuables = flag
            profile.save(update_fields=['factures_immuables'])
            for corps, champ in (({'client': client_b.id}, 'client'),
                                 ({'retenue_garantie_mad': '500'},
                                  'retenue_garantie_mad'),
                                 ({'devise': 'EUR'}, 'devise')):
                with self.subTest(flag=flag, champ=champ):
                    r = self.api.patch(url, corps, format='json')
                    self.assertEqual(r.status_code, 409, r.data)
                    self.assertEqual(r.data['champs_refuses'], [champ])
                    self.assertIn('Montant figé', str(r.data))
            inchange = {'client': self.client_obj.id, 'devise': facture.devise,
                        'montant_ttc': '1200.00', 'taux_tva': '20.00',
                        'type_facture': facture.type_facture}
            r = self.api.patch(url, inchange, format='json')
            self.assertEqual(r.status_code, 200, r.data)
            r = self.api.patch(url, {'note': 'x'}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.client_id, self.client_obj.id)
        self.assertEqual(facture.retenue_garantie_mad or Decimal('0'),
                         Decimal('0'))
        self.assertEqual(facture.devise, 'MAD')
        self.assertEqual(facture.montant_ttc, Decimal('1200.00'))
        brouillon = self._facture(Facture.Statut.BROUILLON)
        r = self.api.patch(f'/api/django/ventes/factures/{brouillon.id}/',
                           {'client': client_b.id, 'devise': 'EUR'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)

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


class MontantTrancheBrouillonTests(TestCase):
    """VNT67 — ``factures/<id>/montant-tranche/`` : le brouillon d'acompte du
    388 (14 700) passe à 15 000 au prorata du plan, l'échéancier est réécrit
    (Σ = TTC) ; une facture émise est refusée (409) ; un Commercial 403."""

    def setUp(self):
        from apps.ventes.domain.facturation_vente import (
            creer_brouillon_tranche)
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        from apps.ventes.tests.test_qjr_echeancier_validation import (
            ECHEANCIER_30_60_10)
        from apps.ventes.vente_facturation import plan_facturation
        self.company = make_company()
        self.user = make_user(self.company)
        self.devis = creer_devis_388(
            self.company, self.user, make_client(self.company),
            'DEV-VNT67-10', ECHEANCIER_30_60_10)
        self.brouillon = creer_brouillon_tranche(
            self.devis, plan_facturation(self.devis)['prochaine'], self.user)

    def _post(self, facture, montant, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.user)}'))
        return api.post(
            f'/api/django/ventes/factures/{facture.id}/montant-tranche/',
            {'montant_ttc': montant}, format='json')

    def test_brouillon_14700_vers_15000_au_prorata_echeancier_reecrit(self):
        self.assertEqual(self.brouillon.total_ttc, Decimal('14700.00'))
        r = self._post(self.brouillon, '15000')
        self.assertEqual(r.status_code, 200, r.data)
        self.brouillon.refresh_from_db()
        self.assertEqual(
            (self.brouillon.montant_ttc, self.brouillon.montant_ht,
             self.brouillon.montant_tva),
            (Decimal('15000.00'), Decimal('12720.41'), Decimal('2279.59')))
        self.devis.refresh_from_db()
        self.assertEqual(
            [Decimal(str(e['pct_or_montant'])) for e in self.devis.echeancier],
            [Decimal('15000'), Decimal('60'), Decimal('4600')])

    def test_facture_emise_409(self):
        from apps.ventes.models import Facture
        Facture.objects.filter(pk=self.brouillon.pk).update(
            statut=Facture.Statut.EMISE)
        self.brouillon.refresh_from_db()
        r = self._post(self.brouillon, '15000')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'facture_emise')

    def test_commercial_403(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
        role = Role.objects.create(company=self.company, nom='Commercial 67',
                                   permissions=list(COMMERCIAL_PERMISSIONS))
        commercial = User.objects.create_user(
            username=f'vnt67_com_{_nxt()}', password='x', role=role,
            role_legacy='normal', company=self.company)
        r = self._post(self.brouillon, '15000', user=commercial)
        self.assertEqual(r.status_code, 403, r.data)
        self.brouillon.refresh_from_db()
        self.assertEqual(self.brouillon.total_ttc, Decimal('14700.00'))


class TotalStockeTests(TestCase):
    """ATOT55 — ``total_ht_stocke``/``total_ttc_stocke`` égalent
    ``total_ht``/``total_ttc`` sur toute facture (remise globale, TVA
    mêlées 10/20, palier ARRONDI-100, ×N villas, tranche figée) et suivent
    chaque écriture de ligne ou de remise ; la migration facturation 0024
    remplit une facture existante. Rouge avant : colonne absente."""

    setUp = MontantsFigesTests.setUp
    _facture = MontantsFigesTests._facture

    def _egal(self, facture):
        from apps.ventes.models import Facture
        relue = Facture.objects.get(pk=facture.pk)
        self.assertEqual(relue.total_ht_stocke, relue.total_ht)
        self.assertEqual(relue.total_ttc_stocke, relue.total_ttc)
        return relue

    def _ligne(self, facture, pu, taux=None):
        from apps.ventes.models import LigneFacture
        return LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='L',
            quantite=Decimal('3'), prix_unitaire=Decimal(pu),
            remise=Decimal('7.5'), taux_tva=taux)

    def test_stocke_egal_au_noyau_cas_typiques(self):
        from apps.ventes.models import Facture
        cas = [
            {},
            {'remise_globale': Decimal('12.5')},
            {'remise_globale': Decimal('3'), 'arrondi_pas': 100},
            {'arrondi_pas': 100, 'arrondi_unites': 2},
        ]
        for extra in cas:
            with self.subTest(**{k: str(v) for k, v in extra.items()}):
                facture = self._facture(Facture.Statut.BROUILLON, **extra)
                self._ligne(facture, '1234.57', Decimal('10'))
                relue = self._egal(facture)
                self.assertGreater(relue.total_ttc_stocke, Decimal('0'))
                if extra.get('arrondi_pas'):
                    self.assertEqual(relue.total_ttc_stocke % 100, 0)
        tranche = self._facture(
            Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
            type_facture=Facture.TypeFacture.ACOMPTE,
            pourcentage=Decimal('30'))
        relue = self._egal(tranche)
        self.assertEqual(relue.total_ttc_stocke, Decimal('1200.00'))

    def test_suit_ligne_et_remise(self):
        from apps.ventes.models import Facture
        facture = self._facture(Facture.Statut.BROUILLON)
        avant = self._egal(facture).total_ttc_stocke
        ligne = self._ligne(facture, '499.99', Decimal('10'))
        ajoutee = self._egal(facture).total_ttc_stocke
        self.assertGreater(ajoutee, avant)
        url = f'/api/django/ventes/factures-lignes/{ligne.id}/'
        r = self.api.patch(url, {'quantite': '5'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreater(self._egal(facture).total_ttc_stocke, ajoutee)
        r = self.api.patch(f'/api/django/ventes/factures/{facture.id}/',
                           {'remise_globale': '10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        remisee = self._egal(facture)
        self.assertEqual(remisee.remise_globale, Decimal('10'))
        # Suppression de ligne : le signal post_delete rafraîchit le stocké
        # (la suppression API est réservée à un autre rôle que ce responsable).
        ligne.delete()
        self.assertLess(self._egal(facture).total_ttc_stocke,
                        remisee.total_ttc_stocke)

    def test_migration_0024_remplit_les_existantes(self):
        import importlib

        from django.apps import apps as registre

        from apps.ventes.models import Facture
        migration = importlib.import_module(
            'apps.facturation.migrations.0024_atot55_total_stocke')
        facture = self._facture(Facture.Statut.BROUILLON,
                                remise_globale=Decimal('5'), arrondi_pas=100)
        self._ligne(facture, '777.77', Decimal('10'))
        Facture.objects.filter(pk=facture.pk).update(
            total_ht_stocke=None, total_ttc_stocke=None)
        migration.remplir(registre, None)
        self.assertIsNotNone(self._egal(facture).total_ht_stocke)
