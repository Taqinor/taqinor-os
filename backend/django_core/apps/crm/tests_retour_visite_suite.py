"""Retour terrain : la notification dit la suite RÉELLE, la confirmation se tait.

Relevés du vérificateur (25/09/2026) sur la décision fondateur du 24/09/2026 :

* la notification « Retour de visite » du responsable disait toujours
  « Rappeler le client sous 24-48 h pour conclure » — alors que, sans devis
  parti, ``appliquer_retour_visite`` pose « Préparer et envoyer le devis ».
  Le texte est désormais lu sur l'étape RENDUE par le service
  (``services.phrase_notification_retour_visite``), jamais deviné ;
* une étape « Confirmer la visite (veille) » encore ouverte au retour terrain
  (visite faite avant qu'on ait coché la confirmation) n'avait plus d'objet et
  restait dans la file : elle est annulée par le moteur, note « visite
  effectuée ».

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_visite
from apps.crm import cadence_reperes
from apps.crm.models import Client, Lead, RelanceEtape
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
VISITE_LE = datetime.date(2026, 9, 28)
RETOUR = {'notes': 'Toiture saine.', 'commentaires_photos': [], 'nb_photos': 0}

A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE


class _Base(TestCase):
    slug = 'rvs'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.owner = User.objects.create_user(
            username=f'{self.slug}-owner', password='x', company=self.company)
        self.terrain = User.objects.create_user(
            username=f'{self.slug}-terrain', password='x',
            company=self.company, role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            stage=stages.CONTACTED, owner=self.owner,
            telephone='+212661000432')

    def _devis_envoye(self):
        from apps.ventes.models import Devis

        client = Client.objects.create(company=self.company, nom='Idrissi',
                                       email=f'{self.slug}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug.upper()}-1',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=5))

    def _emettre_retour(self):
        from core.events import visite_terminee

        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=VISITE_LE,
            retour_terrain=RETOUR['notes'])
        visite_terminee.send(
            sender=VisiteTerrain, visite=visite, lead_id=self.lead.id,
            user=self.terrain, retour=RETOUR, qualification=None)

    def _notification(self):
        return Notification.objects.get(
            recipient=self.owner, event_type=EventType.VISITE_RETOUR_TERRAIN)


class NotificationSuiteReelleTests(_Base):
    slug = 'rvs-notif'

    def test_reterminer_apres_renvoi_ne_double_rien(self):
        # ACVI61 — le 1er retour a posé sa touche (close ici) et notifié ;
        # re-terminer après renvoi re-prévient le bureau d'études, c'est tout.
        bureau = User.objects.create_user(
            username=f'{self.slug}-bureau', password='x',
            company=self.company, role_legacy='responsable')
        self._emettre_retour()
        etape = self.lead.relance_etapes.get(
            libelle=cadence_reperes.FILET_JOINT_LIBELLE, statut=A_FAIRE)
        RelanceEtape.objects.filter(pk=etape.pk).update(
            statut=RelanceEtape.Statut.FAIT)
        visite = VisiteTerrain.objects.get(lead=self.lead)
        visite.statut = VisiteTerrain.Statut.A_REFAIRE
        visite.save(update_fields=['statut'])
        etapes_avant = self.lead.relance_etapes.count()
        api = APIClient()
        api.force_authenticate(self.terrain)

        with mock.patch('apps.visites.selectors.visite_terrain_manquants',
                        return_value=[]):
            resp = api.post(
                f'/api/django/visites/visites/{visite.pk}/terminer/', {},
                format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.lead.relance_etapes.count(), etapes_avant)
        self.assertFalse(self.lead.relance_etapes.filter(
            libelle=cadence_reperes.FILET_JOINT_LIBELLE,
            statut=A_FAIRE).exists())
        self.assertEqual(Notification.objects.filter(
            recipient=self.owner,
            event_type=EventType.VISITE_RETOUR_TERRAIN).count(), 1)
        self.assertEqual(Notification.objects.filter(
            recipient=bureau,
            event_type=EventType.VISITE_TERRAIN_A_VALIDER).count(), 1)
        self.assertEqual(self.lead.activites.filter(
            body__startswith='Visite technique terminée de nouveau').count(), 1)

    def test_sans_devis_la_notification_dit_preparer_le_devis(self):
        self._emettre_retour()

        etape = self.lead.relance_etapes.get(
            libelle=cadence_reperes.FILET_JOINT_LIBELLE, statut=A_FAIRE)
        corps = self._notification().body
        self.assertIn('préparer et envoyer le devis', corps)
        self.assertIn(f'{etape.due_date:%d/%m}', corps)
        self.assertNotIn('24-48', corps)

    def test_avec_devis_envoye_la_notification_dit_rappeler(self):
        self._devis_envoye()

        self._emettre_retour()

        self.assertEqual(self._notification().body,
                         cadence_visite.NOTIF_RETOUR_VISITE_RAPPELER)

    def test_la_phrase_se_lit_sur_l_etape_rendue(self):
        self.assertEqual(cadence_visite.phrase_notification_retour_visite(None),
                         cadence_visite.NOTIF_RETOUR_VISITE_RAPPELER)
        debrief = RelanceEtape(libelle=cadence_reperes.VISITE_DEBRIEF_LIBELLE,
                               due_date=datetime.date(2026, 9, 24))
        self.assertEqual(cadence_visite.phrase_notification_retour_visite(debrief),
                         cadence_visite.NOTIF_RETOUR_VISITE_RAPPELER)


class ConfirmationAnnuleeAuRetourTests(_Base):
    slug = 'rvs-conf'

    def test_la_confirmation_encore_ouverte_est_annulee(self):
        cadence_visite.appliquer_visite_planifiee(
            self.lead, self.terrain, VISITE_LE, commercial_nom='Youssef')
        confirmation = self.lead.relance_etapes.get(
            libelle=cadence_reperes.VISITE_CONFIRMATION_LIBELLE, statut=A_FAIRE)

        cadence_visite.appliquer_retour_visite(self.lead, self.terrain, RETOUR)

        confirmation.refresh_from_db()
        self.assertEqual(confirmation.statut, ANNULEE)
        self.assertEqual(confirmation.note,
                         cadence_visite.NOTE_CONFIRMATION_VISITE_FAITE)
        self.assertIsNone(confirmation.traite_par)
        self.assertIsNotNone(confirmation.traite_le)

    def test_avec_devis_envoye_aussi(self):
        self._devis_envoye()
        cadence_visite.appliquer_visite_planifiee(
            self.lead, self.terrain, VISITE_LE, commercial_nom='Youssef')

        cadence_visite.appliquer_retour_visite(self.lead, self.terrain, RETOUR)

        self.assertFalse(self.lead.relance_etapes.filter(
            libelle=cadence_reperes.VISITE_CONFIRMATION_LIBELLE,
            statut=A_FAIRE).exists())
        # Le débrief, lui, reste la suite.
        self.assertTrue(self.lead.relance_etapes.filter(
            libelle=cadence_reperes.VISITE_DEBRIEF_LIBELLE, statut=A_FAIRE).exists())

    def test_une_confirmation_deja_faite_n_est_pas_touchee(self):
        cadence_visite.appliquer_visite_planifiee(
            self.lead, self.terrain, VISITE_LE, commercial_nom='Youssef')
        confirmation = self.lead.relance_etapes.get(
            libelle=cadence_reperes.VISITE_CONFIRMATION_LIBELLE, statut=A_FAIRE)
        confirmation.statut = RelanceEtape.Statut.FAIT
        confirmation.save(update_fields=['statut'])

        cadence_visite.appliquer_retour_visite(self.lead, self.terrain, RETOUR)

        confirmation.refresh_from_db()
        self.assertEqual(confirmation.statut, RelanceEtape.Statut.FAIT)
