"""ZMKT14 — Types d'événements + modèles + étapes de pipeline (salons /
portes ouvertes / webinaires).

Couvre : créer un événement depuis un type pré-remplit ses données,
l'événement avance dans les étapes configurables, la Kanban groupe par
étape company-scoped, migration additive, tests.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import EvenementMarketing, TypeEvenement


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TypesEvenementPipelineTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt14', 'ZMKT14')

    def test_creer_evenement_depuis_type(self):
        type_evt = TypeEvenement.objects.create(
            company=self.co, nom='Salon type', type_evenement_defaut='salon')
        evenement = services.creer_evenement_depuis_type(
            type_evt, nom='SIAM 2026',
            date_debut=timezone.now() + datetime.timedelta(days=5))
        self.assertEqual(evenement.type_evenement, 'salon')
        self.assertEqual(evenement.type_modele_id, type_evt.id)

    def test_defaut_etape_nouveau(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E', date_debut=timezone.now())
        self.assertEqual(evt.etape, EvenementMarketing.Etape.NOUVEAU)

    def test_avancer_etape(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E2', date_debut=timezone.now())
        services.avancer_etape_evenement(evt, EvenementMarketing.Etape.CONFIRME)
        evt.refresh_from_db()
        self.assertEqual(evt.etape, EvenementMarketing.Etape.CONFIRME)

    def test_kanban_groupe_par_etape(self):
        EvenementMarketing.objects.create(
            company=self.co, nom='E3', date_debut=timezone.now())
        evt2 = EvenementMarketing.objects.create(
            company=self.co, nom='E4', date_debut=timezone.now())
        services.avancer_etape_evenement(evt2, EvenementMarketing.Etape.TERMINE)
        kanban = services.evenements_par_etape(self.co)
        self.assertEqual(len(kanban[EvenementMarketing.Etape.NOUVEAU]), 1)
        self.assertEqual(len(kanban[EvenementMarketing.Etape.TERMINE]), 1)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt14-b', 'ZMKT14-B')
        EvenementMarketing.objects.create(
            company=self.co, nom='Mine', date_debut=timezone.now())
        kanban_other = services.evenements_par_etape(other)
        self.assertEqual(len(kanban_other[EvenementMarketing.Etape.NOUVEAU]), 0)

    def test_etape_jamais_les_cles_stages_py(self):
        cles_etape = {c[0] for c in EvenementMarketing.Etape.choices}
        from apps.crm.stages import STAGES
        self.assertEqual(cles_etape.intersection(set(STAGES)), set())
