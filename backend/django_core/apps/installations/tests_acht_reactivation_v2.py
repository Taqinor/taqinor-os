"""ACHT7 (C-ACHT-006) — un chantier ANNULÉ rattaché à une V2 garde la
nomenclature V1 (le réalignement ASTK177 l'ignore tant qu'il est annulé) :
`reactiver` (et `reserver-stock`) le réalignent sur la V2 avant de réamorcer
les réservations. ACHT114 (C-ACHT-VER-005) : la ré-acceptation d'un devis
dés-accepté (lead sorti de « Signé ») réaligne de même.

Rejoue CCRE-7 : V1 (10 panneaux + 1 onduleur) → chantier → annuler ; V2
(14 panneaux + 1 batterie, sans onduleur) acceptée ; POST reactiver. ROUGE
AVANT : bom [Panneau 10, Onduleur 1], réservations OND 1 / PAN 10.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_reactivation_v2"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

import apps.crm.stages as stages
from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, InstallationActivity, StockReservation,
)
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()


class ReactivationV2Tests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht7', defaults={'nom': 'Co ACHT7'})
        self.user = User.objects.create_user(
            username='resp-acht7', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT7', sku='PAN-ACHT7',
            prix_vente=Decimal('100'), quantite_stock=50)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT7', sku='OND-ACHT7',
            prix_vente=Decimal('1000'), quantite_stock=5)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie ACHT7', sku='BAT-ACHT7',
            prix_vente=Decimal('2000'), quantite_stock=5)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht7@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ACHT7-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=self.v1, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        LigneDevis.objects.create(
            devis=self.v1, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        self._accepter(self.v1)
        self.inst = Installation.objects.get(devis=self.v1)

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def _v2(self):
        v2 = reviser_devis(self.v1, user=self.user)
        LigneDevis.objects.filter(devis=v2, produit=self.onduleur).delete()
        LigneDevis.objects.filter(devis=v2, produit=self.panneau).update(
            quantite=Decimal('14'))
        LigneDevis.objects.create(
            devis=v2, produit=self.batterie, designation='Batterie',
            quantite=Decimal('1'), prix_unitaire=Decimal('2000'))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        v2 = Devis.objects.get(pk=v2.pk)
        self._accepter(v2)
        return v2

    def _url(self, action):
        return f'/api/django/installations/chantiers/{self.inst.id}/{action}/'

    def _actives(self):
        return dict(StockReservation.objects.filter(
            installation=self.inst, active=True).values_list(
                'produit_id', 'quantite'))

    def _bom(self):
        self.inst.refresh_from_db()
        return {li['produit_id']: li['quantite'] for li in self.inst.bom}

    def _attendu_v2(self):
        self.assertEqual(self._bom(),
                         {self.panneau.id: 14.0, self.batterie.id: 1.0})
        self.assertEqual(self._actives(),
                         {self.panneau.id: 14, self.batterie.id: 1})
        resa_ond = StockReservation.objects.get(
            installation=self.inst, produit=self.onduleur)
        self.assertFalse(resa_ond.active)

    def test_v2_sans_annulation(self):
        """Témoin : V2 acceptée sur un chantier vivant = PAN 14 / BAT 1."""
        self._v2()
        self._attendu_v2()

    def test_annule_v2_reactive(self):
        r = self.api.post(self._url('annuler'), {'motif': 'test'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        v2 = self._v2()
        # Annulé : la nomenclature V1 est restée (réalignement différé).
        self.assertEqual(self._bom(),
                         {self.panneau.id: 10.0, self.onduleur.id: 1.0})
        r = self.api.post(self._url('reactiver'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._attendu_v2()
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst,
            body__contains=f'nomenclature réalignée sur {v2.reference} '
                           'à la réactivation').exists())

    def test_reserver_stock_realigne(self):
        r = self.api.post(self._url('annuler'), {'motif': 'test'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._v2()
        # Réactivation « à la main » sans passer par l'action (donnée
        # historique) : `reserver-stock` réaligne aussi.
        Installation.objects.filter(pk=self.inst.pk).update(annule=False)
        r = self.api.post(self._url('reserver-stock'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._attendu_v2()

    def test_reacceptation_apres_sortie_signe_realigne(self):
        """ACHT114 — sonde C-ACHT-VER-005 rejouée par HTTP : accepter (PAN
        10) → lead sorti de « Signé » → ligne 10 → 14 → ré-accepter."""
        lead = Lead.objects.create(
            company=self.company, nom='Ré-accept', prenom='Client',
            stage=stages.FOLLOW_UP, type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT114-1',
            client=self.v1.client, lead=lead, statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now(), taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))

        def accepter():
            r = self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                              {'nom': 'M. Client'}, format='json')
            self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

        def sortir_de_signe():
            r = self.api.patch(
                f'/api/django/crm/leads/{lead.id}/',
                {'stage': stages.FOLLOW_UP, 'confirme_recul': True},
                format='json')
            self.assertEqual(r.status_code, 200, r.data)

        def notes_realignement():
            return InstallationActivity.objects.filter(
                installation=self.inst,
                body__contains='nomenclature réalignée sur DEV-ACHT114-1 '
                               'à la ré-acceptation').count()

        accepter()
        self.inst = Installation.objects.get(devis=devis)
        self.assertEqual(self._bom(), {self.panneau.id: 10.0})
        sortir_de_signe()
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.annule)
        LigneDevis.objects.filter(devis=devis).update(quantite=Decimal('14'))
        accepter()
        chantiers = Installation.objects.filter(devis=devis)
        self.assertEqual(chantiers.count(), 1)
        self.assertFalse(chantiers.get().annule)
        self.assertEqual(self._bom(), {self.panneau.id: 14.0})
        self.assertEqual(self._actives(), {self.panneau.id: 14})
        self.assertEqual(notes_realignement(), 1)
        # Idempotent : nouvelle sortie + ré-acceptation SANS changement de
        # ligne → nomenclature inchangée, aucune nouvelle note, réservations
        # réamorcées à l'identique.
        sortir_de_signe()
        accepter()
        self.assertEqual(self._bom(), {self.panneau.id: 14.0})
        self.assertEqual(self._actives(), {self.panneau.id: 14})
        self.assertEqual(notes_realignement(), 1)
