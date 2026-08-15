"""WIR176 — les deep-links de notification ATTERRISSENT sur une route déclarée.

~17 notifications pointaient vers des chemins qui n'existent PAS côté front
(`/leads/<pk>`, `/factures/<pk>`, `/sav/tickets/<pk>`, `/gestion-projet/...`,
`/automation/approvals/<pk>`, `/installations/<pk>`, `/admin/impersonation/
<pk>`…) : un clic depuis la cloche tombait en 404. Calqué sur
``tests_qx12_devis_links`` : chaque événement assert SON lien.

Les cibles sont les routes RÉELLEMENT déclarées par les module.config du
frontend, avec le motif de requête RÉELLEMENT lu par l'écran :
``/sav?id=`` (TicketsPage), ``/crm/leads?lead=`` (LeadsPage — motif préservé
pour ``_lead_id_from_link``), ``/ventes/factures?facture=`` (FactureList),
``/projets/<id>`` (ProjetDetailPage), ``/chantiers?id=`` (InstallationsPage),
``/approbations?source=`` (ApprobationsPage) et ``/admin/impersonation``.
"""
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.notifications.models import EventType, Notification
from apps.notifications.sweeps import _lead_id_from_link

User = get_user_model()

# Routes déclarées côté front consommées par ces liens (préfixes autorisés).
# Toute évolution de cette table doit rester alignée avec les
# `features/*/module.config.jsx` correspondants.
ROUTES_DECLAREES = (
    '/crm/leads',
    '/ventes/factures',
    '/ventes/bons-commande',
    '/ventes/devis',
    '/sav',
    '/sav/contrats',
    '/equipements',
    '/projets/',
    '/chantiers',
    '/chantiers/demandes-achat',
    '/approbations',
    '/comptabilite/approbations-config',
    '/admin/impersonation',
    '/stock',
    '/contrats/',
    '/activites',
)


class Wir176LeadLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='wir176-co', nom='WIR176 Co')
        self.owner = User.objects.create_user(
            username='wir176_owner', password='x', company=self.company)

    def test_lead_assigned_link_lands_and_stays_parsable(self):
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', owner=self.owner)
        notif = Notification.objects.filter(
            recipient=self.owner,
            event_type=EventType.LEAD_ASSIGNED).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.link, f'/crm/leads?lead={lead.pk}')
        # Le motif `lead=` est CELUI que lit l'escalade des leads chauds
        # (`_lead_id_from_link`) : le changement de route ne le casse pas.
        self.assertEqual(_lead_id_from_link(notif.link), lead.pk)
        self.assertNotIn(f'/leads/{lead.pk}', notif.link)


class Wir176SourceLinkTests(TestCase):
    """Garde statique : plus AUCUN `link=` de ces modules ne sort de la table
    de routes déclarées. Un futur lien inventé casse ce test."""

    FICHIERS = (
        Path(__file__).resolve().parent / 'signals.py',
        Path(__file__).resolve().parent / 'sweeps.py',
        Path(__file__).resolve().parents[1] / 'adminops'
        / 'impersonation_service.py',
    )
    # Littéraux de lien : `link=f'/...'`, `link='/...'`, `lien = f'/...'`.
    MOTIF = re.compile(r"(?:link|lien)\s*=\s*f?'(/[^']*)'")

    def test_tous_les_liens_pointent_une_route_declaree(self):
        vus = 0
        for fichier in self.FICHIERS:
            texte = fichier.read_text(encoding='utf-8')
            for lien in self.MOTIF.findall(texte):
                vus += 1
                chemin = lien.split('?')[0]
                self.assertTrue(
                    any(chemin == r or chemin.startswith(r)
                        for r in ROUTES_DECLAREES),
                    msg=(f'{fichier.name} : le lien de notification « {lien} »'
                         ' ne correspond à aucune route déclarée.'))
        # Garde-fou : le motif doit réellement avoir trouvé des liens.
        self.assertGreater(vus, 10)

    def test_aucun_lien_vers_les_anciennes_routes_fantomes(self):
        fantomes = (
            "'/leads/", "'/factures/", "'/bons-commande/", "'/sav/tickets/",
            "'/gestion-projet/", "'/automation/approvals/",
            "'/compta/approbations/", "'/installations/",
            "'/sav/equipements/", "'/sav/maintenances/", "'/ged/documents/",
            "'/admin/impersonation/{",
        )
        for fichier in self.FICHIERS:
            texte = fichier.read_text(encoding='utf-8')
            for fantome in fantomes:
                for prefixe in ('link=f', 'link = f', 'lien=f', 'lien = f'):
                    self.assertNotIn(
                        f'{prefixe}{fantome}', texte,
                        msg=f'{fichier.name} pointe encore vers {fantome}')
