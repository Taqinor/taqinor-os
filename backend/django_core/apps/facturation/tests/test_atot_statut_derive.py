"""ATOT8 (C-ATOT-006) — le statut de paiement d'une facture se DÉRIVE de son
reste dû par un service unique `recalculer_statut_paiement`, appelé après
création et annulation d'avoir : « payée » si et seulement si
`montant_du` ≤ 0.

Rejoue la sonde V1 TFAC-6 : aujourd'hui une facture payée grâce à un avoir
reste `payee` avec 30 000 dus quand l'avoir est annulé, et une facture que
l'avoir solde reste `emise` avec 0 dû. Endpoints réels, aucun mock (le
récepteur de test ne fait que COMPTER `facture_payee`).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_statut_derive"
"""
from datetime import date
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


class StatutDeriveTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT8 Co', slug=f'atot8-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Statut', prenom='ATOT8',
            email=f'atot8-{_nxt()}@example.invalid')
        self.admin = User.objects.create_user(
            username=f'atot8_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Remise ATOT8', sku=f'ATOT8-{_nxt()}',
            prix_vente=Decimal('0'), quantite_stock=0)
        # La ligne produit du devis porte son produit du catalogue
        # (`LigneFacture.produit` est NOT NULL : sans lui, facturer-complet → 500).
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT8', sku=f'ATOT8K-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.payees = []
        from core.events import facture_payee

        def _compter(sender, instance=None, **kwargs):
            self.payees.append(instance.pk)
        self._recepteur = _compter
        facture_payee.connect(_compter, weak=False)
        self.addCleanup(facture_payee.disconnect, _compter)

    def _facture(self, paiements=()):
        from apps.ventes.models import Devis, Facture, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT8-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': [
                {'montant': m, 'date_paiement': date.today().isoformat(),
                 'mode_paiement': 'virement'} for m in paiements]},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['facture_id'])

    def _avoir(self, facture, ht='25000'):
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'lignes': [{'designation': 'Avoir partiel', 'quantite': '1',
                         'prix_unitaire': ht, 'taux_tva': '20',
                         'produit': self.kit.id}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def test_recalcul_sans_date_client_a_delai_suit_le_beat(self):
        """AARG61 (C-AARG-VER1-305) — client à 90 j, émise il y a 45 j sans date
        d'échéance, paiement rejeté : ÉMISE au recalcul ET après le beat.
        Mutant : remettre ``echeance_exigible`` ⇒ EN RETARD au recalcul."""
        import datetime

        from apps.crm.models import Client
        from apps.ventes.models import Facture, Paiement
        from apps.ventes.scheduled import check_overdue_factures
        aujourdhui = datetime.date.today()
        client_90 = Client.objects.create(
            company=self.company, nom='Délai', prenom='AARG61',
            email=f'aarg61-{_nxt()}@example.invalid', delai_paiement_jours=90)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AARG61-{_nxt()}',
            client=client_90, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
            date_emission=aujourdhui - datetime.timedelta(days=45))
        self.assertIsNone(facture.date_echeance)
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('300'),
            date_paiement=aujourdhui, mode='virement', created_by=self.admin)
        r = self.api.post(f'/api/django/ventes/paiements/{paiement.id}/rejeter/',
                          {'motif': 'Chèque impayé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Facture.objects.get(pk=facture.pk).statut,
                         Facture.Statut.EMISE)
        check_overdue_factures()
        # CLAUSE PERSISTANCE — relu en base.
        self.assertEqual(Facture.objects.get(pk=facture.pk).statut,
                         Facture.Statut.EMISE)

    def test_recalcul_sans_date_echeance_suit_le_beat(self):
        """AARG56 (C-AARG-063) — émise il y a 45 j sans date d'échéance, payée
        300 puis paiement rejeté : EN RETARD, comme le beat ; l'échéance posée
        d'une émise ne s'efface pas (409) ; sur un brouillon : 200."""
        import datetime

        from apps.ventes.models import Facture, Paiement
        from apps.ventes.scheduled import check_overdue_factures
        aujourdhui = datetime.date.today()

        def emise(**extra):
            return Facture.objects.create(
                company=self.company, reference=f'FAC-AARG56-{_nxt()}',
                client=self.client_obj, statut=Facture.Statut.EMISE,
                taux_tva=Decimal('20.00'), montant_ht=Decimal('1000.00'),
                montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
                date_emission=aujourdhui - datetime.timedelta(days=45), **extra)
        facture = emise()
        self.assertIsNone(facture.date_echeance)
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('300'),
            date_paiement=aujourdhui, mode='virement', created_by=self.admin)
        r = self.api.post(f'/api/django/ventes/paiements/{paiement.id}/rejeter/',
                          {'motif': 'Chèque impayé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.EN_RETARD)
        # Le beat ne change plus rien : même statut.
        check_overdue_factures()
        self.assertEqual(Facture.objects.get(pk=facture.pk).statut,
                         Facture.Statut.EN_RETARD)
        self.assertIsNone(Facture.objects.get(pk=facture.pk).date_echeance)

        echeance = aujourdhui + datetime.timedelta(days=10)
        datee = emise(date_echeance=echeance)
        url = f'/api/django/ventes/factures/{datee.id}/'
        r = self.api.patch(url, {'date_echeance': None}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn("ne s'efface pas", str(r.data))
        self.assertEqual(Facture.objects.get(pk=datee.pk).date_echeance, echeance)
        # Reporter reste permis ; une émise sans date : rien à effacer.
        r = self.api.patch(url, {'date_echeance': str(
            echeance + datetime.timedelta(days=5))}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.patch(f'/api/django/ventes/factures/{facture.id}/',
                           {'date_echeance': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        Facture.objects.filter(pk=datee.pk).update(
            statut=Facture.Statut.BROUILLON)
        r = self.api.patch(url, {'date_echeance': None}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(Facture.objects.get(pk=datee.pk).date_echeance)

    def test_avoir_qui_solde_passe_payee(self):
        from apps.ventes.models import Facture
        facture = self._facture(paiements=['120000'])
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.montant_du, Decimal('30000.00'))
        self._avoir(facture)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertEqual(self.payees.count(facture.pk), 1)
        # Rejouer le recalcul : aucun second événement.
        from apps.ventes.domain.encaissements import recalculer_statut_paiement
        recalculer_statut_paiement(facture)
        self.assertEqual(self.payees.count(facture.pk), 1)

    def _annuler_en_gardant_l_avance(self):
        """Une facture payée 150 000, annulée `garder_en_avance` → (facture,
        id de l'avoir miroir, paiement détaché devenu avance)."""
        from apps.ventes.models import Avoir, Facture, Paiement
        facture = Facture.objects.get(
            pk=self._facture(paiements=['150000']).pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        paiement = Paiement.objects.get(facture=facture)
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            {'acompte': {'action': 'garder_en_avance'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return facture, Avoir.objects.get(facture=facture).id, paiement

    def test_annuler_avoir_miroir_rattache_l_avance(self):
        """AARG2 — l'avoir miroir annulé rend les paiements à la facture ;
        jamais « payée » à payé 0. Pas de second `facture_payee`."""
        from apps.ventes.models import Facture, Paiement
        facture, avoir_id, paiement = self._annuler_en_gardant_l_avance()
        self.assertEqual(self.payees.count(facture.pk), 1)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture = Facture.objects.get(pk=facture.pk)
        paiement.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_paye, Decimal('150000.00'))
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertEqual(paiement.facture_id, facture.pk)
        self.assertEqual(paiement.statut_affectation,
                         Paiement.StatutAffectation.AFFECTE)
        self.assertFalse(Paiement.objects.filter(
            client=self.client_obj, facture__isnull=True).exists())
        self.assertEqual(self.payees.count(facture.pk), 1)

    def test_annuler_avoir_miroir_avance_utilisee_409(self):
        """AARG2 — avance ventilée ailleurs : 409, rien d'écrit."""
        from apps.ventes.domain.encaissements import ventiler_avance
        from apps.ventes.models import Avoir, Facture
        facture, avoir_id, paiement = self._annuler_en_gardant_l_avance()
        autre = self._facture()
        ventiler_avance(paiement=paiement, facture=autre,
                        montant=Decimal('1000'), user=self.admin)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('a été utilisée', str(r.data))
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.ANNULEE)
        self.assertEqual(Avoir.objects.get(pk=avoir_id).statut,
                         Avoir.Statut.EMISE)
        paiement.refresh_from_db()
        self.assertIsNone(paiement.facture_id)

    def test_annuler_avoir_miroir_trace_ancienne_409(self):
        """AARG2 — une annulation ancienne ne nomme pas ses paiements : 409."""
        from apps.ventes.models import Facture, FactureActivity
        facture, avoir_id, _paiement = self._annuler_en_gardant_l_avance()
        FactureActivity.objects.filter(
            facture=facture, field='acompte').update(new_value=None)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(Facture.objects.get(pk=facture.pk).statut,
                         Facture.Statut.ANNULEE)

    def test_annuler_avoir_rouvre_payee(self):
        from apps.ventes.models import Facture
        facture = self._facture()
        avoir_id = self._avoir(facture)
        from apps.ventes.domain.encaissements import encaisser_sur_facture
        encaisser_sur_facture(
            facture=Facture.objects.get(pk=facture.pk),
            donnees={'montant': Decimal('120000.00'),
                     'date_paiement': date.today(), 'mode': 'virement',
                     'reference': ''},
            user=self.admin)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertIn(facture.statut,
                      (Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
        self.assertEqual(facture.montant_du, Decimal('30000.00'))

    def _soldee_puis_avoir_avec_surplus(self):
        """Facture payée 150 000, avoir 30 000 TTC : (facture, id de l'avoir,
        avance née du trop-perçu)."""
        from apps.ventes.models import Avoir, Paiement
        facture = self._facture(paiements=['150000'])
        avoir_id = self._avoir(facture)
        avance = Paiement.objects.get(
            client=self.client_obj, facture__isnull=True,
            reference=Avoir.objects.get(pk=avoir_id).reference)
        self.assertEqual(avance.montant, Decimal('30000.00'))
        return facture, avoir_id, avance

    def test_annuler_avoir_avec_surplus_rend_l_avance(self):
        """AARG59 (C-AARG-VER1-107) — annuler l'avoir laisse la facture payée,
        sans avance libre ni relance ; les deux lignes restent au journal.
        Mutant : retirer l'appel dans ``annuler`` ⇒ statut émise, avance libre."""
        from apps.ventes.models import Avoir, Facture, Paiement
        from apps.ventes.recouvrement import facture_relancable
        facture, avoir_id, avance = self._soldee_puis_avoir_avec_surplus()
        reference = avance.reference
        payees = self.payees.count(facture.pk)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # CLAUSE PERSISTANCE — relu en base.
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(Avoir.objects.get(pk=avoir_id).statut,
                         Avoir.Statut.ANNULEE)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_paye, Decimal('150000.00'))
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertFalse(facture_relancable(facture)[0])
        self.assertFalse(Paiement.objects.filter(
            client=self.client_obj, facture__isnull=True,
        ).exclude(statut__in=Paiement.STATUTS_NON_COMPTES).exists())
        journal = Paiement.objects.filter(reference=reference)
        self.assertEqual(journal.count(), 2)
        for ligne in journal:
            self.assertEqual(ligne.statut, Paiement.Statut.ANNULE_SAISIE)
            self.assertIn(reference, ligne.motif_annulation)
        self.assertEqual(self.payees.count(facture.pk), payees)

    def test_annuler_avoir_avec_surplus_avance_utilisee_409(self):
        """AARG59 — avance ventilée sur une autre facture : 409, rien d'écrit."""
        from apps.ventes.domain.encaissements import ventiler_avance
        from apps.ventes.models import Avoir, Facture, Paiement
        facture, avoir_id, avance = self._soldee_puis_avoir_avec_surplus()
        ventiler_avance(paiement=avance, facture=self._facture(),
                        montant=Decimal('1000'), user=self.admin)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('a été utilisée', str(r.data))
        self.assertEqual(Avoir.objects.get(pk=avoir_id).statut,
                         Avoir.Statut.EMISE)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_paye, Decimal('120000.00'))
        self.assertFalse(Paiement.objects.filter(
            reference=avance.reference,
            statut=Paiement.Statut.ANNULE_SAISIE).exists())
