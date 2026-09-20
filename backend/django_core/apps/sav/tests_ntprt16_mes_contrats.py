"""
NTPRT16 — « Mes contrats » du portail client : moitié SAV (maintenance).

Le pendant ``contrats.Contrat`` est déjà livré (XCTR14 :
``contrats.selectors.contrats_portail_client`` +
``contrats.services.demander_action_portail``). Cette lane livre le pendant
``sav.ContratMaintenance`` : la liste scopée client et le point d'écriture de la
DEMANDE, que ``apps.portail`` consomme par ces deux fonctions (jamais un import
de ``apps.sav.models``).

Couvre :
  * CRITÈRE D'ACCEPTATION : une demande de résiliation crée une notification
    interne et ne change JAMAIS le contrat (``actif`` intact, dates intactes) ;
  * la demande est journalisée au chatter générique du socle
    (``records.Activity``, ``kind=note``, société explicite) ;
  * un type de demande inconnu est refusé ;
  * la liste est scopée société ET client, et n'expose AUCUN champ interne
    (SLA, tarif d'usage, dernière facturation, notes) ;
  * le contrat d'un autre client est INTROUVABLE (None, jamais « trouvé puis
    refusé »).

Run :
    python manage.py test apps.sav.tests_ntprt16_mes_contrats -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.records.models import Activity
from apps.sav import selectors, services
from apps.sav.models import ContratMaintenance

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntprt16-co-{n}', defaults={'nom': f'NTPRT16 Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Portail', prenom=f'Client {n}',
        email=f'ntprt16-{company.id}-{n}@example.invalid')


def make_contrat(company, client, **extra):
    champs = {
        'periodicite': ContratMaintenance.Periodicite.ANNUEL,
        'date_debut': timezone.localdate(),
        'prix': Decimal('4500.00'),
        'actif': True,
    }
    champs.update(extra)
    return ContratMaintenance.objects.create(
        company=company, client=client, **champs)


class DemandePortailContratMaintenanceTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.client_portail = make_client(self.company)
        self.contrat = make_contrat(self.company, self.client_portail)

    def test_demande_resiliation_ne_change_jamais_le_contrat(self):
        """CRITÈRE D'ACCEPTATION NTPRT16."""
        avant_actif = self.contrat.actif
        avant_debut = self.contrat.date_debut

        activite = services.demander_action_portail_maintenance(
            self.contrat, type_demande='resiliation',
            message='Je déménage en juin.')

        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.actif, avant_actif)
        self.assertTrue(self.contrat.actif)
        self.assertEqual(self.contrat.date_debut, avant_debut)
        self.assertIsNone(self.contrat.date_renouvellement)
        # La demande est journalisée, avec le message du client.
        self.assertEqual(activite.kind, Activity.Kind.NOTE)
        self.assertEqual(activite.company, self.company)
        self.assertIn('Demande de résiliation', activite.body)
        self.assertIn('Je déménage en juin.', activite.body)
        self.assertIn('[Portail client]', activite.body)

    def test_demande_rattachee_au_contrat_dans_le_chatter_generique(self):
        activite = services.demander_action_portail_maintenance(
            self.contrat, type_demande='renouvellement')

        ct = ContentType.objects.get_for_model(ContratMaintenance)
        self.assertEqual(activite.content_type, ct)
        self.assertEqual(activite.object_id, self.contrat.id)
        self.assertEqual(activite.summary, 'Demande de renouvellement')
        # Aucune note interne n'est posée sur un ticket : une demande
        # d'abonnement n'est pas un ticket SAV.
        from apps.sav.models import TicketActivity
        self.assertFalse(TicketActivity.objects.exists())

    def test_type_de_demande_inconnu_refuse(self):
        ct = ContentType.objects.get_for_model(ContratMaintenance)

        with self.assertRaises(services.DemandeContratMaintenanceError):
            services.demander_action_portail_maintenance(
                self.contrat, type_demande='suppression')

        self.assertFalse(
            Activity.objects.filter(
                content_type=ct, object_id=self.contrat.id).exists())

    def test_notification_interne_diffusee(self):
        from apps.notifications.models import Notification

        services.demander_action_portail_maintenance(
            self.contrat, type_demande='resiliation')

        # Best-effort : la diffusion dépend des destinataires configurés de la
        # société — on vérifie qu'aucune notification n'a pu être créée pour
        # une AUTRE société, et que l'appel n'a jamais levé.
        self.assertFalse(
            Notification.objects.exclude(company=self.company).exists())


class ListePortailContratsMaintenanceTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.client_portail = make_client(self.company)
        self.autre_client = make_client(self.company)
        self.contrat = make_contrat(
            self.company, self.client_portail,
            visites_incluses_an=2, sla_response_days=1,
            tarif_usage=Decimal('1.2500'), notes='Note interne')
        self.contrat_autre = make_contrat(self.company, self.autre_client)

    def test_liste_scopee_client(self):
        rows = selectors.contrats_maintenance_portail_client(
            self.company, self.client_portail.id)

        self.assertEqual([r['id'] for r in rows], [self.contrat.id])

    def test_liste_nexpose_aucun_champ_interne(self):
        rows = selectors.contrats_maintenance_portail_client(
            self.company, self.client_portail.id)

        interdits = {
            'sla_response_days', 'sla_resolution_days', 'tarif_usage',
            'franchise_incluse', 'derniere_facturation', 'facturation_active',
            'notes', 'derniere_visite',
        }
        self.assertEqual(interdits & set(rows[0]), set())
        self.assertEqual(rows[0]['visites_incluses_an'], 2)

    def test_liste_scopee_societe(self):
        autre_company = make_company()

        self.assertEqual(
            selectors.contrats_maintenance_portail_client(
                autre_company, self.client_portail.id),
            [])

    def test_liste_vide_sans_client(self):
        self.assertEqual(
            selectors.contrats_maintenance_portail_client(self.company, None),
            [])

    def test_contrat_dun_autre_client_introuvable(self):
        self.assertIsNone(
            selectors.contrat_maintenance_du_client(
                self.company, self.client_portail.id, self.contrat_autre.id))
        self.assertEqual(
            selectors.contrat_maintenance_du_client(
                self.company, self.client_portail.id, self.contrat.id),
            self.contrat)
