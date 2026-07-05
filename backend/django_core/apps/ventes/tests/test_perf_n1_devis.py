"""Perf audit fix — DevisViewSet N+1 regression test.

DevisViewSet.queryset previously only did
select_related('client', 'created_by').prefetch_related('lignes'), leaving
several relations touched by DevisSerializer un-optimized:
  - obj.lead (lead_nom / lead_facture_hiver / lead_type_installation)
  - obj.superseded_by / obj.version_parent (superseded_by_ref/version_parent_ref)
  - obj.factures (get_factures_liees, related_name='factures')
  - obj.bon_commande (get_bon_commande_etat, reverse OneToOne)
  - obj.signature (signature_info / est_signe, reverse OneToOne)
  - obj.share_links (_active_share_link, related_name='share_links')

This test exercises the queryset DIRECTLY (not the full HTTP list endpoint)
so it isolates exactly what select_related/prefetch_related affects, without
being polluted by unrelated per-devis computed fields the serializer also
carries (e.g. `solde`/`total_affiche` route through the quote engine and
option/echeancier helpers, which build their own sub-querysets independent
of this fix). Rather than pin an exact query count, it proves FLATNESS:
touching the same set of relations across 5 rows vs 10 rows must cost the
SAME number of queries. Before the fix, each extra devis added a query per
relation (lead, superseded_by, version_parent, factures, bon_commande,
signature, share_links); after the fix, select_related folds the forward/
O2O relations into the base query and prefetch_related issues one extra
query per relation for ALL rows combined, not per row.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import BonCommande, Devis, DevisSignature, Facture, ShareLink
from apps.ventes.views.devis import DevisViewSet

User = get_user_model()


class TestDevisViewSetNPlusOne(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='perf-n1-devis-co', defaults={'nom': 'Perf N1 Devis Co'})
        self.admin = User.objects.create_user(
            username='perf_n1_devis_admin', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Perf',
            email='perf-n1-devis@example.invalid')

    def _make_devis(self, n, offset=0):
        ids = []
        for i in range(offset, offset + n):
            lead = Lead.objects.create(
                company=self.company, nom=f'LeadPerfDevis{i}', stage='SIGNED',
                client=self.client_obj)
            parent = Devis.objects.create(
                company=self.company, reference=f'DEV-PERFN1-PARENT-{i:04d}',
                client=self.client_obj, statut=Devis.Statut.REFUSE,
                taux_tva=Decimal('20'))
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-PERFN1-{i:04d}',
                client=self.client_obj, created_by=self.admin, lead=lead,
                statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
                version_parent=parent,
            )
            parent.superseded_by = devis
            parent.save(update_fields=['superseded_by'])

            BonCommande.objects.create(
                company=self.company, reference=f'BC-PERFN1-{i:04d}',
                devis=devis, client=self.client_obj,
                statut=BonCommande.Statut.CONFIRME,
            )
            Facture.objects.create(
                company=self.company, reference=f'FAC-PERFN1-{i:04d}',
                devis=devis, client=self.client_obj,
                statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            )
            DevisSignature.objects.create(
                company=self.company, devis=devis,
                signataire_nom='Perf Signataire',
                consentement_explicite=True, signed_at=timezone.now(),
            )
            ShareLink.objects.create(company=self.company, devis=devis)
            ids.append(devis.id)
        return ids

    def _touch_targeted_relations(self, qs):
        """Access exactly the relations this fix targets, for every row —
        mirrors what DevisSerializer's SerializerMethodFields do, without
        the unrelated quote-engine/echeancier computed fields."""
        total = 0
        for devis in qs:
            _ = devis.lead.nom if devis.lead_id else None
            _ = devis.superseded_by.reference if devis.superseded_by_id else None
            _ = devis.version_parent.reference if devis.version_parent_id else None
            try:
                bc = devis.bon_commande
            except BonCommande.DoesNotExist:
                bc = None
            _ = bc.statut if bc else None
            try:
                sig = devis.signature
            except DevisSignature.DoesNotExist:
                sig = None
            _ = sig.signataire_nom if sig else None
            total += len(list(devis.factures.all()))
            total += len(list(devis.share_links.all()))
        return total

    def _query_count_for_targeted_relations(self, devis_ids):
        qs = DevisViewSet.queryset.filter(id__in=devis_ids).order_by('id')
        with CaptureQueriesContext(connection) as ctx:
            self._touch_targeted_relations(qs)
        return len(ctx.captured_queries)

    def test_query_count_flat_as_row_count_grows(self):
        ids_5 = self._make_devis(5)
        count_5 = self._query_count_for_targeted_relations(ids_5)

        ids_10 = ids_5 + self._make_devis(5, offset=5)
        count_10 = self._query_count_for_targeted_relations(ids_10)

        self.assertEqual(
            count_10, count_5,
            f"Query count grew from {count_5} (5 devis) to {count_10} "
            f"(10 devis) — N+1 regression on DevisViewSet.queryset "
            f"(missing select_related/prefetch_related on lead/"
            f"bon_commande/signature/superseded_by/version_parent/factures/"
            f"share_links)."
        )

    def test_targeted_fields_actually_populated(self):
        """Sanity check the fixture wiring: the relations this fix targets
        are non-empty, so the flatness test above is meaningful (not
        vacuously true because everything is NULL)."""
        ids = self._make_devis(1)
        devis = DevisViewSet.queryset.get(id=ids[0])
        self.assertIsNotNone(devis.lead)
        self.assertIsNotNone(devis.version_parent)
        self.assertIsNotNone(devis.version_parent.superseded_by)
        self.assertEqual(devis.bon_commande.statut, BonCommande.Statut.CONFIRME)
        self.assertEqual(devis.signature.signataire_nom, 'Perf Signataire')
        self.assertEqual(devis.factures.count(), 1)
        self.assertEqual(devis.share_links.count(), 1)
