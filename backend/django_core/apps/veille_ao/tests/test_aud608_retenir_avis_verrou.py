"""AUD608 — « Retenir un avis » relit son état SOUS VERROU.

``retenir_avis`` décidait « déjà converti ? » sur l'instance Python qu'on lui
passait, hors transaction. Deux clics simultanés sur « Retenir » — ou deux
requêtes HTTP parallèles, chacune avec SA copie de l'avis — lisaient donc
toutes les deux « pas encore converti » et faisaient créer DEUX appels d'offres
pour un seul avis, avec deux références AO consommées.

Le test simule le double-clic SANS threads : deux instances distinctes du même
avis, la seconde chargée AVANT la conversion (donc périmée), exactement comme
la seconde requête HTTP d'un double-clic.

Run :
    python manage.py test apps.veille_ao.tests.test_aud608_retenir_avis_verrou -v2
"""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.ao.models import AppelOffre
from apps.records.models import Activity
from apps.veille_ao.models import AvisMarche, SourceVeille, TypeSource
from apps.veille_ao.services import retenir_avis
from authentication.models import Company


class BaseAvis(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD608 Veille',
                                              slug='aud608-veille')
        self.source = SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau partenaire',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        self.avis = AvisMarche.objects.create(
            company=self.company, source=self.source,
            objet='Centrale photovoltaïque en toiture',
            acheteur='Commune de Test',
            reference_avis='AO-2026-608',
            date_limite_remise=timezone.now() + timedelta(days=20))


class TestDoubleClicSimule(BaseAvis):
    def test_le_second_clic_ne_rejoue_pas_la_conversion(self):
        """LE cas : la seconde requête tient une COPIE périmée de l'avis.

        Sans relecture sous verrou, elle traverse toute la conversion —
        transitions de statut, notes de chatter, appel cross-app — pour un avis
        DÉJÀ converti. Le court-circuit d'idempotence était aveugle.
        """
        perimee = AvisMarche.objects.get(pk=self.avis.pk)  # copie du 2e clic

        _avis, premier_id, cree1 = retenir_avis(self.avis)
        self.assertTrue(cree1)
        activites_apres_premier = Activity.objects.count()

        _avis2, second_id, cree2 = retenir_avis(perimee)
        self.assertFalse(cree2)
        self.assertEqual(second_id, premier_id)
        self.assertEqual(
            Activity.objects.count(), activites_apres_premier,
            'Le second clic REJOUE la conversion (transitions + chatter) sur '
            "un avis déjà converti : l'idempotence lit une instance périmée.")

    def test_une_seule_affaire_pour_un_avis(self):
        perimee = AvisMarche.objects.get(pk=self.avis.pk)
        retenir_avis(self.avis)
        retenir_avis(perimee)
        self.assertEqual(
            AppelOffre.objects.filter(company=self.company).count(), 1)


class TestVerrouPose(BaseAvis):
    def test_la_ligne_d_avis_est_verrouillee(self):
        with CaptureQueriesContext(connection) as capture:
            retenir_avis(self.avis)
        verrous = [q['sql'] for q in capture.captured_queries
                   if 'FOR UPDATE' in q['sql'].upper()
                   and 'veille_ao' in q['sql'].lower()]
        self.assertTrue(
            verrous,
            "Aucun SELECT ... FOR UPDATE sur l'avis : la lecture "
            "d'idempotence reste une course.")
