"""Perf audit fix — TicketViewSet N+1 regression test.

TicketViewSet.queryset previously did select_related('client', 'installation',
'equipement', 'equipement__produit', 'technicien_responsable') and
prefetch_related('interventions'), leaving TicketSerializer's taxonomy
fields un-optimized:
  - cause_nom / remede_nom / categorie_nom / equipe_nom /
    categorie_equipement_nom (all forward FKs: obj.cause, obj.remede,
    obj.categorie, obj.equipe, obj.categorie_equipement)
  - each intervention's technicien_nom (TicketInterventionSerializer reads
    obj.technicien per prefetched Intervention row)
  - nb_interventions previously called obj.interventions.count(), which
    re-queries even when interventions are prefetched

This test exercises the queryset DIRECTLY (not the full HTTP list endpoint)
so it isolates exactly what select_related/prefetch_related affects,
without being polluted by unrelated per-ticket computed fields the
serializer also carries (get_equipement_couvert queries
ContratMaintenance per row independent of this fix). It proves FLATNESS:
touching the same set of relations across 5 tickets vs 10 tickets must cost
the SAME number of queries.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import (
    CategorieEquipement, CategorieTicket, CauseDefaillance, EquipeMaintenance,
    RemedeDefaillance, Ticket,
)
from apps.sav.serializers import TicketSerializer
from apps.sav.views import TicketViewSet

User = get_user_model()


class TestTicketViewSetNPlusOne(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='perf-n1-tickets-co', defaults={'nom': 'Perf N1 Tickets Co'})
        self.tech = User.objects.create_user(
            username='perf_n1_tickets_tech', password='x',
            role_legacy='normal', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Perf',
            email='perf-n1-ticket@example.invalid')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-PERFN1', client=self.client_obj)
        self.cause = CauseDefaillance.objects.create(
            company=self.company, nom='Cause Perf')
        self.remede = RemedeDefaillance.objects.create(
            company=self.company, nom='Remede Perf')
        self.categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Categorie Perf')
        self.equipe = EquipeMaintenance.objects.create(
            company=self.company, nom='Equipe Perf')
        self.categorie_equipement = CategorieEquipement.objects.create(
            company=self.company, nom='Cat Equipement Perf')

    def _make_tickets(self, n, offset=0):
        ids = []
        for i in range(offset, offset + n):
            ticket = Ticket.objects.create(
                company=self.company, reference=f'TCK-PERFN1-{i:04d}',
                client=self.client_obj, installation=self.installation,
                cause=self.cause, remede=self.remede, categorie=self.categorie,
                equipe=self.equipe,
                categorie_equipement=self.categorie_equipement,
            )
            Intervention.objects.create(
                company=self.company, installation=self.installation,
                ticket=ticket, type_intervention=Intervention.Type.DEPANNAGE,
                technicien=self.tech,
            )
            ids.append(ticket.id)
        return ids

    def _touch_targeted_relations(self, qs):
        """Access exactly the relations this fix targets, for every row —
        mirrors what TicketSerializer's fields do, without the unrelated
        ContratMaintenance lookups in get_equipement_couvert/etc."""
        for ticket in qs:
            _ = ticket.cause.nom if ticket.cause_id else None
            _ = ticket.remede.nom if ticket.remede_id else None
            _ = ticket.categorie.libelle if ticket.categorie_id else None
            _ = ticket.equipe.nom if ticket.equipe_id else None
            _ = (ticket.categorie_equipement.nom
                 if ticket.categorie_equipement_id else None)
            for interv in ticket.interventions.all():
                _ = getattr(interv.technicien, 'username', None)

    def _query_count_for_targeted_relations(self, ticket_ids):
        qs = TicketViewSet.queryset.filter(id__in=ticket_ids).order_by('id')
        with CaptureQueriesContext(connection) as ctx:
            self._touch_targeted_relations(qs)
        return len(ctx.captured_queries)

    def test_query_count_flat_as_row_count_grows(self):
        ids_5 = self._make_tickets(5)
        count_5 = self._query_count_for_targeted_relations(ids_5)

        ids_10 = ids_5 + self._make_tickets(5, offset=5)
        count_10 = self._query_count_for_targeted_relations(ids_10)

        self.assertEqual(
            count_10, count_5,
            f"Query count grew from {count_5} (5 tickets) to {count_10} "
            f"(10 tickets) — N+1 regression on TicketViewSet.queryset "
            f"(missing select_related on cause/remede/categorie/equipe/"
            f"categorie_equipement or prefetch_related on "
            f"interventions__technicien)."
        )

    def test_nb_interventions_uses_prefetch_cache_not_count_query(self):
        """get_nb_interventions must reuse the prefetch cache (len(...))
        instead of re-querying with .count() — the latter defeats
        prefetch_related('interventions__technicien') on every row."""
        ids = self._make_tickets(3)
        qs = TicketViewSet.queryset.filter(id__in=ids).order_by('id')
        with CaptureQueriesContext(connection) as ctx:
            data = TicketSerializer(list(qs), many=True).data
        for row in data:
            self.assertEqual(row['nb_interventions'], 1)
        query_count_serializing = len(ctx.captured_queries)

        # Re-run against 6 rows (double): if nb_interventions (or anything
        # else this fix targets) still issued a query per row, the count
        # would grow; it must not.
        ids_more = ids + self._make_tickets(3, offset=3)
        qs_more = TicketViewSet.queryset.filter(id__in=ids_more).order_by('id')
        with CaptureQueriesContext(connection) as ctx2:
            data_more = TicketSerializer(list(qs_more), many=True).data
        for row in data_more:
            self.assertEqual(row['nb_interventions'], 1)
        query_count_serializing_more = len(ctx2.captured_queries)

        self.assertEqual(
            query_count_serializing_more, query_count_serializing,
            "Serializing 6 tickets cost more queries than 3 — "
            "get_nb_interventions is likely re-querying via .count() "
            "instead of reusing the prefetch cache."
        )

    def test_targeted_fields_actually_populated(self):
        """Sanity check the fixture wiring: the relations this fix targets
        are non-empty, so the flatness tests above are meaningful (not
        vacuously true because everything is NULL)."""
        ids = self._make_tickets(1)
        ticket = TicketViewSet.queryset.get(id=ids[0])
        self.assertEqual(ticket.cause.nom, 'Cause Perf')
        self.assertEqual(ticket.remede.nom, 'Remede Perf')
        self.assertEqual(ticket.categorie.libelle, 'Categorie Perf')
        self.assertEqual(ticket.equipe.nom, 'Equipe Perf')
        self.assertEqual(ticket.categorie_equipement.nom, 'Cat Equipement Perf')
        self.assertEqual(ticket.interventions.count(), 1)
        self.assertEqual(ticket.interventions.all()[0].technicien, self.tech)
