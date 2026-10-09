"""ACHT2 (C-ACHT-002, C-ACHT-003, D-ACHT-2) — la machine d'états du chantier
est gardée par le SERVEUR dans la chaîne unique `_raisons_transition` :
aucun pas en avant ne saute un rang canonique, un chantier annulé ne change
plus de statut, et la création naît « Signé ».

Rejoue CCRE-2 (PATCH signé → réceptionné : 200, sortie 0, parc créé ; POST
statut=cloture : 201) et CCRE-3 (chantier annulé avancé 5×200, rappel de
solde émis).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_machine_etats"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, JalonProjet, StockReservation,
)
from apps.installations.services import notifier_jalon_a_facturer
from apps.stock.models import MouvementStock, Produit
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
BASE = '/api/django/installations/chantiers/'


class MachineEtatsChantierTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht2', defaults={'nom': 'Co ACHT2'})
        self.user = User.objects.create_user(
            username='resp-acht2', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT2', sku='PAN-ACHT2',
            prix_vente=Decimal('100'), quantite_stock=50)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT2', sku='OND-ACHT2',
            prix_vente=Decimal('1000'), quantite_stock=5)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht2@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT2-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')
        self.inst = Installation.objects.get(devis=devis)
        self.assertEqual(self.inst.statut, Installation.Statut.SIGNE)

    # ── helpers ──────────────────────────────────────────────────────────
    def _patch(self, statut, inst=None):
        inst = inst or self.inst
        return self.api.patch(f'{BASE}{inst.id}/', {'statut': statut},
                              format='json')

    def _sortie(self):
        return (MouvementStock.objects
                .filter(reference=self.inst.reference,
                        type_mouvement=MouvementStock.TypeMouvement.SORTIE)
                .aggregate(t=Sum('quantite'))['t']) or 0

    def _resas(self):
        return sorted(StockReservation.objects.filter(
            installation=self.inst).values_list(
                'produit_id', 'quantite', 'active', 'consomme'))

    def _jalons_reception(self):
        return JalonProjet.objects.filter(
            installation=self.inst, phase=JalonProjet.Phase.RECEPTION,
            atteint=True).count()

    def _assert_rien_ecrit(self, statut_attendu, resas_avant):
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, statut_attendu)
        self.assertEqual(self._sortie(), 0)
        self.assertEqual(self._resas(), resas_avant)
        self.assertEqual(self._jalons_reception(), 0)
        self.assertIsNone(self.inst.date_reception)

    def _annuler(self):
        r = self.api.post(f'{BASE}{self.inst.id}/annuler/',
                          {'motif': 'test ACHT2'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    # ── tests ────────────────────────────────────────────────────────────
    def test_patch_saut_refuse(self):
        resas = self._resas()
        r = self._patch(Installation.Statut.RECEPTIONNE)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Passage de Signé à Réceptionné refusé : un pas à la '
                      'fois', str(r.data))
        self._assert_rien_ecrit(Installation.Statut.SIGNE, resas)

    def test_mise_en_service_depuis_signe_refusee(self):
        resas = self._resas()
        r = self.api.post(f'{BASE}{self.inst.id}/mise-en-service/',
                          {'date_mise_en_service': '2026-10-08'},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('un pas à la fois', str(r.data))
        self._assert_rien_ecrit(Installation.Statut.SIGNE, resas)

    def test_creation_nait_signe(self):
        for statut in (Installation.Statut.CLOTURE,
                       Installation.Statut.RECEPTIONNE):
            r = self.api.post(BASE, {'statut': statut}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            cree = Installation.objects.get(pk=r.data['id'])
            self.assertEqual(cree.statut, Installation.Statut.SIGNE)

    def test_annule_ne_change_plus_de_statut(self):
        self._annuler()
        resas = self._resas()
        r = self._patch(Installation.Statut.MATERIEL_COMMANDE)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Chantier annulé : réactivez-le avant de changer son '
                      'statut', str(r.data))
        r = self.api.post(f'{BASE}{self.inst.id}/mise-en-service/', {},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self._assert_rien_ecrit(Installation.Statut.SIGNE, resas)

    def test_rappel_solde_muet_si_annule(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.RECEPTION, libelle='Réception',
            atteint=True, tranche_echeancier=JalonProjet.TRANCHE_SOLDE)
        Installation.objects.filter(pk=self.inst.pk).update(annule=True)
        jalon.refresh_from_db()
        self.assertFalse(notifier_jalon_a_facturer(jalon, self.user))
        jalon.refresh_from_db()
        self.assertFalse(jalon.rappel_facturation_envoye)

    def test_temoin_pas_a_pas(self):
        for statut in (Installation.Statut.MATERIEL_COMMANDE,
                       Installation.Statut.PLANIFIE,
                       Installation.Statut.EN_COURS,
                       Installation.Statut.INSTALLE,
                       Installation.Statut.RECEPTIONNE):
            r = self._patch(statut)
            self.assertEqual(r.status_code, 200, (statut, r.data))
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.RECEPTIONNE)
        self.assertEqual(
            (MouvementStock.objects
             .filter(reference=self.inst.reference, produit=self.panneau,
                     type_mouvement=MouvementStock.TypeMouvement.SORTIE)
             .aggregate(t=Sum('quantite'))['t']), 10)

    def test_recul_reste_permis(self):
        Installation.objects.filter(pk=self.inst.pk).update(
            statut=Installation.Statut.EN_COURS)
        r = self._patch(Installation.Statut.MATERIEL_COMMANDE)
        self.assertEqual(r.status_code, 200, r.data)
