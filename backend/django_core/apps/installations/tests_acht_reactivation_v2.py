"""ACHT7 (C-ACHT-006) — un chantier ANNULÉ rattaché à une V2 garde la
nomenclature V1 (le réalignement ASTK177 l'ignore tant qu'il est annulé) :
`reactiver` (et `reserver-stock`) le réalignent sur la V2 avant de réamorcer
les réservations.

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
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.services import creer_bcf_depuis_lignes
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

    def _devis_accepte_avec_bcf(self, reference):
        lead = Lead.objects.create(
            company=self.company, nom='Bcf', prenom='Client',
            stage=stages.FOLLOW_UP, type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=reference,
            client=self.v1.client, lead=lead, statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now(), taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        r = self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                          {'nom': 'M. Client'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        inst = Installation.objects.get(devis=devis)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {reference}')
        bon = creer_bcf_depuis_lignes(
            company=self.company, user=self.user, fournisseur=fournisseur,
            lignes=[(self.panneau.id, 'Panneau', Decimal('10'),
                     Decimal('70'))],
            chantier_origine=inst)
        return lead, devis, inst, bon

    def _sortir_de_signe(self, lead):
        return self.api.patch(f'/api/django/crm/leads/{lead.id}/', {
            'stage': stages.FOLLOW_UP, 'confirme_recul': True}, format='json')

    def test_bcf_envoye_bloque_la_sortie_de_signe(self):
        """ADVS40 (C-ADVS-027, D-ADVS-5 = refuser_409) — un BCF ENVOYÉ du
        chantier né de la vente bloque la sortie de « Signé » : 409 nommant le
        BCF, rien d'écrit ; une fois annulé, la sortie passe.
        ROUGE AVANT : 200, chantier annulé, BCF envoyé orphelin."""
        lead, devis, inst, bon = self._devis_accepte_avec_bcf('DEV-ADVS40-1')
        Statut = BonCommandeFournisseur.Statut
        BonCommandeFournisseur.objects.filter(pk=bon.pk).update(
            statut=Statut.ENVOYE)

        r = self._sortir_de_signe(lead)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(f'le bon de commande fournisseur {bon.reference} '
                      "est envoyé : annulez-le d'abord.", r.data['detail'])
        lead.refresh_from_db()
        devis.refresh_from_db()
        inst.refresh_from_db()
        bon.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertFalse(inst.annule)
        self.assertEqual(bon.statut, Statut.ENVOYE)

        BonCommandeFournisseur.objects.filter(pk=bon.pk).update(
            statut=Statut.ANNULE)
        r = self._sortir_de_signe(lead)
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertTrue(inst.annule)

    def test_bcf_brouillon_ne_bloque_pas_la_sortie_de_signe(self):
        """ADVS40 — un BCF encore en brouillon ne bloque rien."""
        lead, _devis, inst, bon = self._devis_accepte_avec_bcf('DEV-ADVS40-2')
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.BROUILLON)
        r = self._sortir_de_signe(lead)
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertTrue(inst.annule)

    def test_reacceptation_apres_sortie_signe_realigne(self):
        """ACHT114 (C-ACHT-VER-005) — rejoue la sonde par HTTP : devis envoyé
        PAN × 10 accepté, lead sorti de « Signé », ligne corrigée à 14,
        ré-accepté ⇒ un seul chantier actif, bom et réservations à 14, note de
        réalignement ; 2e aller-retour sans changement ⇒ aucune nouvelle note.
        ROUGE AVANT : bom resté {PAN : 10}."""
        lead = Lead.objects.create(
            company=self.company, nom='Reaccept', prenom='Client',
            stage=stages.FOLLOW_UP, type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT114-1',
            client=self.v1.client, lead=lead, statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now(), taux_tva=Decimal('20'),
            mode_installation='residentiel')
        ligne = LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))

        def accepter():
            r = self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                              {'nom': 'M. Client'}, format='json')
            self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

        def sortir_de_signe():
            r = self.api.patch(f'/api/django/crm/leads/{lead.id}/', {
                'stage': stages.FOLLOW_UP, 'confirme_recul': True},
                format='json')
            self.assertEqual(r.status_code, 200, r.data)

        def notes_realignement(inst):
            return InstallationActivity.objects.filter(
                installation=inst,
                body__contains=f'nomenclature réalignée sur {devis.reference} '
                               'à la ré-acceptation').count()

        accepter()
        inst = Installation.objects.get(devis=devis)
        sortir_de_signe()
        inst.refresh_from_db()
        self.assertTrue(inst.annule)
        LigneDevis.objects.filter(pk=ligne.pk).update(quantite=Decimal('14'))
        accepter()
        chantiers = Installation.objects.filter(devis=devis)
        self.assertEqual(chantiers.count(), 1)
        inst = chantiers.get()
        self.assertFalse(inst.annule)
        self.assertEqual(
            {li['produit_id']: li['quantite'] for li in inst.bom},
            {self.panneau.id: 14.0})
        self.assertEqual(dict(StockReservation.objects.filter(
            installation=inst, active=True).values_list(
                'produit_id', 'quantite')), {self.panneau.id: 14})
        self.assertEqual(notes_realignement(inst), 1)
        # Idempotent : nouvel aller-retour sans changement de ligne.
        sortir_de_signe()
        accepter()
        inst.refresh_from_db()
        self.assertFalse(inst.annule)
        self.assertEqual(notes_realignement(inst), 1)
        self.assertEqual(dict(StockReservation.objects.filter(
            installation=inst, active=True).values_list(
                'produit_id', 'quantite')), {self.panneau.id: 14})

    def test_v2_acceptee_apres_sortie_signe_reactive(self):
        """ACSV1 (C-ACSV-001) — V1 (PAN × 10) acceptée, lead sorti de
        « Signé » (chantier annulé, motif-marqueur), révisée en V2 (× 12)
        acceptée ⇒ UN chantier actif rattaché à V2, bom et réservations à 12,
        note « Chantier réactivé ». ROUGE AVANT : `annule` True, bom 10."""
        lead, devis, inst, _bon = self._devis_accepte_avec_bcf('DEV-ACSV1-1')
        r = self._sortir_de_signe(lead)
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertTrue(inst.annule)
        devis.refresh_from_db()
        v2 = reviser_devis(devis, user=self.user)
        LigneDevis.objects.filter(devis=v2, produit=self.panneau).update(
            quantite=Decimal('12'))
        Devis.objects.filter(pk=v2.pk).update(
            statut=Devis.Statut.ENVOYE, date_envoi=timezone.now())
        r = self.api.post(f'/api/django/ventes/devis/{v2.id}/accepter/',
                          {'nom': 'M. Client'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        chantiers = Installation.objects.filter(
            company=self.company, devis_id__in=[devis.id, v2.id])
        self.assertEqual(chantiers.count(), 1)
        inst.refresh_from_db()
        self.assertFalse(inst.annule)
        self.assertIsNone(inst.motif_annulation)
        self.assertEqual(inst.devis_id, v2.id)
        self.assertEqual({li['produit_id']: li['quantite'] for li in inst.bom},
                         {self.panneau.id: 12.0})
        self.assertEqual(dict(StockReservation.objects.filter(
            installation=inst, active=True).values_list(
                'produit_id', 'quantite')), {self.panneau.id: 12})
        self.assertTrue(InstallationActivity.objects.filter(
            installation=inst, body__startswith='Chantier réactivé').exists())

    def test_reactiver_refuse_devis_non_accepte(self):
        """ACSV2 (C-ACSV-002) — après la sortie de « Signé » (devis
        « envoyé »), « Réactiver » rend 409 nommant le devis : le chantier
        reste annulé, 0 réservation active. ROUGE AVANT : 200, 10 réservés."""
        lead, devis, inst, _bon = self._devis_accepte_avec_bcf('DEV-ACSV2-1')
        r = self._sortir_de_signe(lead)
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst.id}/reactiver/', {},
            format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(
            r.data['detail'],
            f"Le devis {devis.reference} n'est plus accepté : ré-acceptez-le "
            'pour réactiver le chantier.')
        inst.refresh_from_db()
        devis.refresh_from_db()
        self.assertTrue(inst.annule)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(StockReservation.objects.filter(
            installation=inst, active=True).exists())
