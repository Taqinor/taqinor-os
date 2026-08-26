"""WIR176 — ~17 liens de notification cassés (404) atterrissent enfin.

Chaque site producteur de ``link=`` dans ``signals.py``/``sweeps.py``/
``apps.adminops.impersonation_service`` pointait vers une route INEXISTANTE
côté front (ex. ``/sav/tickets/<pk>``, ``/leads/<pk>``, ``/factures/<pk>``,
``/gestion-projet/projets/<pk>``, ``/automation/approvals/<pk>``,
``/compta/approbations/<pk>``, ``/installations/…``, ``/ged/documents/<pk>``,
``/admin/impersonation/<pk>``). Ce module vérifie, par catégorie (calqué sur
``tests_qx12_devis_links.py``), que le ``link`` posé correspond désormais à
une route RÉELLE :
  - ``/sav?id=<pk>``            — TicketsPage (SAV_TICKET_OPENED/RESOLU,
    SAV_EQUIPEMENT_REMPLACE, SAV_TICKET_BREACHING, SAV_ACTIVITE_DUE) ;
  - ``/crm/leads?lead=<pk>``    — LeadsPage (LEAD_ASSIGNED), format préservé
    pour ``sweeps._lead_id_from_link`` ;
  - ``/ventes/factures?facture=<pk>`` — FactureList (FACTURE_PAYEE,
    FACTURE_OVERDUE) ;
  - ``/ventes/bons-commande``   — BonCommandeList (BON_COMMANDE_CREE, pas de
    deep-link par id : jamais un paramètre fabriqué) ;
  - ``/projets/<pk>``           — route directe `/projets/:id` (PROJET_STATUT_
    CHANGE) ;
  - ``/approbations?source=…``  — boîte unique XKB1, filtrée par la source
    réelle de l'agrégateur (automation/installations/ged) ;
  - ``/comptabilite/approbations-config`` — écran DÉDIÉ de
    ``compta.DemandeApprobationConfig`` (PAS une source de l'agrégateur XKB1) ;
  - ``/equipements`` / ``/sav/contrats`` / ``/chantiers/demandes-achat`` —
    écrans de liste réels (WARRANTY_EXPIRING/MAINTENANCE_DUE/DA_SOUMISE_STALE,
    pas de deep-link vérifié côté page : jamais un paramètre fabriqué) ;
  - ``/chantiers?id=<pk>``      — InstallationsPage (CHANTIER_DUE) ;
  - ``/admin/impersonation``    — ImpersonationConsentement (pas de
    deep-link par id).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import EventType, Notification

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _make_company(name):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal', **kwargs):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy, **kwargs)


# ── LEAD_ASSIGNED ─────────────────────────────────────────────────────────

class LeadAssignedLinkTests(TestCase):
    def test_link_lands_on_crm_leads_and_stays_parsable(self):
        from apps.crm.models import Lead
        from .sweeps import _lead_id_from_link

        company = _make_company('Wir176LeadCo')
        owner = _make_user(company, 'wir176-lead-owner')
        lead = Lead.objects.create(company=company, nom='Bennani', owner=owner)

        notif = Notification.objects.get(
            recipient=owner, event_type=EventType.LEAD_ASSIGNED)
        self.assertEqual(notif.link, f'/crm/leads?lead={lead.pk}')
        self.assertNotIn('/leads/' + str(lead.pk), notif.link)
        # Préservé : le format reste extractible par le sweep d'escalade
        # QX31be (`_lead_id_from_link`).
        self.assertEqual(_lead_id_from_link(notif.link), lead.pk)


# ── SAV_TICKET_OPENED / _RESOLU / _EQUIPEMENT_REMPLACE (signals.py) ────────

class SavSignalLinkTests(TestCase):
    def setUp(self):
        self.company = _make_company('Wir176SavCo')
        self.admin = _make_user(self.company, 'wir176-sav-admin', role_legacy='admin')
        self.client_obj = None

    def _client(self):
        from apps.crm.models import Client
        if self.client_obj is None:
            self.client_obj = Client.objects.create(
                company=self.company, nom='ClientWir176Sav')
        return self.client_obj

    def test_ticket_opened_link_lands_on_sav_with_id(self):
        from apps.sav.models import Ticket
        ticket = Ticket.objects.create(
            company=self.company, client=self._client(),
            reference='SAV-WIR176-1', technicien_responsable=self.admin)
        notif = Notification.objects.get(
            recipient=self.admin, event_type=EventType.SAV_TICKET_OPENED)
        self.assertEqual(notif.link, f'/sav?id={ticket.pk}')
        self.assertNotIn('/sav/tickets/', notif.link)

    def test_ticket_resolu_link_lands_on_sav_with_id(self):
        from apps.installations.models import Installation
        from apps.sav.models import Ticket
        from apps.sav.services import emettre_ticket_resolu

        inst = Installation.objects.create(
            company=self.company, reference='CHT-WIR176-1',
            client=self._client())
        ticket = Ticket.objects.create(
            company=self.company, client=self._client(), installation=inst,
            reference='SAV-WIR176-2', statut=Ticket.Statut.EN_COURS,
            technicien_responsable=self.admin, created_by=self.admin)
        Notification.objects.all().delete()

        # `emettre_ticket_resolu` n'émet QUE sur le franchissement RÉEL vers
        # RESOLU (garde sur `ticket.statut` courant) — poser le nouveau
        # statut avant l'appel, comme le fait le vrai appelant (views.py).
        ticket.statut = Ticket.Statut.RESOLU
        ticket.save(update_fields=['statut'])
        emettre_ticket_resolu(
            ticket, company=self.company, user=self.admin,
            ancien_statut=Ticket.Statut.EN_COURS)

        notif = Notification.objects.get(
            recipient=self.admin, event_type=EventType.SAV_TICKET_RESOLU)
        self.assertEqual(notif.link, f'/sav?id={ticket.pk}')
        self.assertNotIn('/sav/tickets/', notif.link)

    def test_equipement_remplace_link_lands_on_sav_with_ticket_id(self):
        from apps.installations.models import Installation
        from apps.sav.models import Equipement, Ticket
        from apps.sav.services import retirer_piece
        from apps.stock.models import Produit

        inst = Installation.objects.create(
            company=self.company, reference='CHT-WIR176-2',
            client=self._client())
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur WIR176', sku='OND-WIR176',
            prix_achat=1000, prix_vente=2000, quantite_stock=Decimal('2'))
        ticket = Ticket.objects.create(
            company=self.company, client=self._client(), installation=inst,
            reference='SAV-WIR176-3', created_by=self.admin)
        Equipement.objects.create(
            company=self.company, produit=onduleur, installation=inst,
            numero_serie='SN-WIR176-1', created_by=self.admin)
        Notification.objects.all().delete()

        retirer_piece(
            company=self.company, ticket=ticket, produit=onduleur,
            quantite=Decimal('1'), numero_serie='SN-WIR176-1',
            destination='retour_fournisseur', user=self.admin)

        notif = Notification.objects.get(
            event_type=EventType.SAV_EQUIPEMENT_REMPLACE)
        self.assertEqual(notif.link, f'/sav?id={ticket.pk}')
        self.assertNotIn('/sav/tickets/', notif.link)


# ── FACTURE_PAYEE / BON_COMMANDE_CREE ──────────────────────────────────────

class FacturePayeeBonCommandeLinkTests(TestCase):
    def setUp(self):
        self.company = _make_company('Wir176FacBcCo')
        self.vendeur = _make_user(self.company, 'wir176-vendeur')
        self.magasinier = _make_user(
            self.company, 'wir176-magasinier', role_legacy='responsable')

    def test_facture_payee_link_lands_on_ventes_factures(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from core.events import facture_payee

        cl = Client.objects.create(company=self.company, nom='ClientFacWir176')
        facture = Facture.objects.create(
            company=self.company, reference='FAC-WIR176-1', client=cl,
            statut=Facture.Statut.EMISE, created_by=self.vendeur)

        facture_payee.send(
            sender=Facture, instance=facture, company=self.company)

        notif = Notification.objects.get(
            recipient=self.vendeur, event_type=EventType.FACTURE_PAYEE)
        self.assertEqual(notif.link, f'/ventes/factures?facture={facture.pk}')
        self.assertNotIn(f'/factures/{facture.pk}', notif.link)

    def test_bon_commande_cree_link_lands_on_ventes_bons_commande(self):
        from apps.crm.models import Client
        from apps.ventes.models import BonCommande
        from core.events import bon_commande_cree

        cl = Client.objects.create(company=self.company, nom='ClientBcWir176')
        bc = BonCommande.objects.create(
            company=self.company, reference='BC-WIR176-1', client=cl)

        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=self.company)

        notif = Notification.objects.get(
            recipient=self.magasinier, event_type=EventType.BON_COMMANDE_CREE)
        self.assertEqual(notif.link, '/ventes/bons-commande')
        self.assertNotIn('/bons-commande/', notif.link)


# ── PROJET_STATUT_CHANGE ────────────────────────────────────────────────────

class ProjetStatutChangeLinkTests(TestCase):
    def test_link_lands_on_projets_detail_route(self):
        from apps.gestion_projet.models import Projet
        from core.events import projet_status_change

        company = _make_company('Wir176ProjetCo')
        resp = _make_user(company, 'wir176-proj-resp', role_legacy='responsable')
        projet = Projet.objects.create(
            company=company, code='PRJ-WIR176-1', nom='Projet WIR176',
            responsable=resp)

        projet_status_change.send(
            sender=None, projet=projet, company=company, user=resp,
            ancien_statut=Projet.Statut.PLANIFIE,
            nouveau_statut=Projet.Statut.EN_COURS)

        notif = Notification.objects.get(
            recipient=resp, event_type=EventType.PROJET_STATUT_CHANGE)
        self.assertEqual(notif.link, f'/projets/{projet.pk}')
        self.assertNotIn('/gestion-projet/', notif.link)


# ── Approbations : automation / installations / ged → boîte unique XKB1 ────

class ApprobationsSourceLinkTests(TestCase):
    def test_automation_approval_link_uses_approbations_source(self):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        company = _make_company('Wir176AutoCo')
        approver = _make_user(company, 'wir176-auto-approver', role_legacy='admin')
        requester = _make_user(company, 'wir176-auto-requester')
        rule = AutomationRule.objects.create(
            company=company, nom='Règle WIR176',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        AutomationApproval.objects.create(
            company=company, rule=rule, description='Action WIR176',
            requested_by=requester)

        notif = Notification.objects.get(
            recipient=approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notif.link, '/approbations?source=automation')
        self.assertNotIn('/automation/', notif.link)

    def test_installations_demande_achat_link_uses_approbations_source(self):
        from apps.installations.models import DemandeAchat
        company = _make_company('Wir176DaCo')
        approver = _make_user(company, 'wir176-da-approver', role_legacy='admin')
        requester = _make_user(company, 'wir176-da-requester')
        da = DemandeAchat.objects.create(
            company=company, reference='DA-WIR176-1', objet='Onduleurs',
            created_by=requester)
        Notification.objects.all().delete()

        da.statut = DemandeAchat.Statut.SOUMISE
        da.save()

        notif = Notification.objects.get(
            recipient=approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notif.link, '/approbations?source=installations')
        self.assertNotIn('/installations/demandes-achat/', notif.link)

    def test_ged_demande_approbation_link_uses_approbations_source(self):
        from apps.ged import services as ged_services
        from apps.ged.models import Cabinet, Document, Folder

        company = _make_company('Wir176GedCo')
        approver = _make_user(company, 'wir176-ged-approver', role_legacy='admin')
        requester = _make_user(company, 'wir176-ged-requester')
        cabinet = Cabinet.objects.create(company=company, nom='Admin')
        folder = Folder.objects.create(
            company=company, cabinet=cabinet, nom='Dossier WIR176')
        doc = Document.objects.create(
            company=company, folder=folder, nom='Contrat WIR176')

        ged_services.request_review(doc, user=requester)

        notif = Notification.objects.get(
            recipient=approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notif.link, '/approbations?source=ged')
        self.assertNotIn('/ged/documents/', notif.link)


# ── compta.DemandeApprobationConfig — écran DÉDIÉ (PAS l'agrégateur XKB1) ──

class ComptaApprobationConfigLinkTests(TestCase):
    def test_link_lands_on_dedicated_compta_screen(self):
        from apps.compta.models import DemandeApprobationConfig

        company = _make_company('Wir176ComptaCo')
        approver = _make_user(company, 'wir176-compta-approver', role_legacy='admin')
        requester = _make_user(company, 'wir176-compta-requester')

        DemandeApprobationConfig.objects.create(
            company=company, devis_reference='DV-WIR176-1',
            motif='kWc/onduleur incohérents', demandeur=requester)

        notif = Notification.objects.get(
            recipient=approver, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notif.link, '/comptabilite/approbations-config')
        self.assertNotIn('/compta/approbations/', notif.link)


# ── Impersonation ────────────────────────────────────────────────────────

class ImpersonationLinkTests(TestCase):
    def test_link_lands_on_admin_impersonation(self):
        from apps.adminops import impersonation_service

        tenant = _make_company('Wir176ImpCo')
        admin = _make_user(tenant, 'wir176-imp-admin', role_legacy='admin')
        cible = _make_user(tenant, 'wir176-imp-cible')
        support = User.objects.create_user(
            username='wir176-imp-support', password='pw',
            is_taqinor_support=True)

        demande = impersonation_service.demander_impersonation(
            utilisateur_cible=cible, initiee_par=support,
            motif='Diagnostic WIR176')

        notif = Notification.objects.get(
            recipient=admin, event_type=EventType.IMPERSONATION_REQUESTED)
        self.assertEqual(notif.link, '/admin/impersonation')
        self.assertNotIn(f'/admin/impersonation/{demande.pk}', notif.link)


# ── Sweeps (sweeps.py) — WARRANTY_EXPIRING / MAINTENANCE_DUE / SAV_TICKET_
#    BREACHING / CHANTIER_DUE / FACTURE_OVERDUE / DA_SOUMISE_STALE /
#    SAV_ACTIVITE_DUE ─────────────────────────────────────────────────────

class SweepLinkTests(TestCase):
    def setUp(self):
        self.company = _make_company('Wir176SweepCo')
        self.manager = _make_user(
            self.company, 'wir176-sweep-mgr', role_legacy='admin')

    def test_warranty_expiring_link_lands_on_equipements_list(self):
        from apps.crm.models import Client
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        from .sweeps import _sweep_warranty_expiring

        cl = Client.objects.create(company=self.company, nom='ClientWarranty')
        chantier = Installation.objects.create(
            company=self.company, client=cl, reference='CH-WIR176-WARR',
            statut=Installation.Statut.CLOTURE)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur Warranty', prix_vente=0)
        Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie=date.today() + timedelta(days=30))

        _sweep_warranty_expiring(self.company)
        notif = Notification.objects.get(event_type=EventType.WARRANTY_EXPIRING)
        self.assertEqual(notif.link, '/equipements')
        self.assertNotIn('/sav/equipements/', notif.link)

    def test_maintenance_due_link_lands_on_sav_contrats(self):
        from apps.crm.models import Client
        from apps.sav.models import ContratMaintenance
        from .sweeps import _sweep_maintenance_due

        cl = Client.objects.create(company=self.company, nom='ClientMaint')
        ContratMaintenance.objects.create(
            company=self.company, client=cl,
            date_debut=date.today() - timedelta(days=400), actif=True,
            periodicite='annuel')

        _sweep_maintenance_due(self.company)
        notif = Notification.objects.get(event_type=EventType.MAINTENANCE_DUE)
        self.assertEqual(notif.link, '/sav/contrats')
        self.assertNotIn('/sav/maintenances/', notif.link)

    def test_sav_breaching_link_lands_on_sav_with_id(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket
        from .sweeps import _sweep_sav_breaching

        cl = Client.objects.create(company=self.company, nom='ClientBreach')
        ticket = Ticket.objects.create(
            company=self.company, client=cl, reference='T-WIR176-BREACH',
            statut=Ticket.Statut.NOUVEAU,
            date_ouverture=date.today() - timedelta(days=10))

        _sweep_sav_breaching(self.company)
        notif = Notification.objects.get(
            event_type=EventType.SAV_TICKET_BREACHING)
        self.assertEqual(notif.link, f'/sav?id={ticket.pk}')
        self.assertNotIn('/sav/tickets/', notif.link)

    def test_chantier_due_link_lands_on_chantiers_with_id(self):
        from apps.crm.models import Client
        from apps.installations.models import Installation
        from .sweeps import _sweep_chantier_due

        cl = Client.objects.create(company=self.company, nom='ClientChantierDue')
        chantier = Installation.objects.create(
            company=self.company, client=cl, reference='CH-WIR176-DUE',
            statut=Installation.Statut.SIGNE,
            date_pose_prevue=date.today() + timedelta(days=5))

        _sweep_chantier_due(self.company)
        notif = Notification.objects.get(event_type=EventType.CHANTIER_DUE)
        self.assertEqual(notif.link, f'/chantiers?id={chantier.pk}')
        self.assertNotIn('/installations/', notif.link)

    def test_facture_overdue_link_lands_on_ventes_factures(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from .sweeps import _sweep_facture_overdue

        cl = Client.objects.create(company=self.company, nom='ClientOverdue')
        facture = Facture.objects.create(
            company=self.company, client=cl, reference='FA-WIR176-OV',
            statut=Facture.Statut.EMISE,
            date_echeance=date.today() - timedelta(days=10),
            created_by=self.manager)

        _sweep_facture_overdue(self.company)
        notif = Notification.objects.get(event_type=EventType.FACTURE_OVERDUE)
        self.assertEqual(notif.link, f'/ventes/factures?facture={facture.pk}')
        self.assertNotIn(f'/ventes/factures/{facture.pk}', notif.link)

    def test_da_soumise_stale_link_lands_on_chantiers_demandes_achat(self):
        from apps.installations.models import DemandeAchat
        from .sweeps import _sweep_da_soumise_stale

        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{MONTH}-9001',
            objet='câbles WIR176', statut=DemandeAchat.Statut.SOUMISE,
            created_by=self.manager)
        vieux = timezone.now() - timedelta(days=5)
        DemandeAchat.objects.filter(pk=da.pk).update(date_modification=vieux)

        _sweep_da_soumise_stale(self.company)
        notif = Notification.objects.get(event_type=EventType.DA_SOUMISE_STALE)
        self.assertEqual(notif.link, f'/chantiers/demandes-achat?demande={da.pk}')
        self.assertNotIn('/installations/demandes-achat', notif.link)

    def test_sav_activite_due_link_lands_on_sav_with_id(self):
        from apps.crm.models import Client
        from apps.sav.models import Ticket, TicketActiviteAFaire
        from .sweeps import _sweep_sav_activite_due

        cl = Client.objects.create(company=self.company, nom='ClientTAFWir176')
        ticket = Ticket.objects.create(
            company=self.company, client=cl, reference='T-WIR176-TAF',
            statut=Ticket.Statut.NOUVEAU, date_ouverture=date.today())
        TicketActiviteAFaire.objects.create(
            company=self.company, ticket=ticket, type='appel',
            titre='Rappeler le client WIR176',
            echeance=date.today() - timedelta(days=1), fait=False)

        _sweep_sav_activite_due(self.company)
        notif = Notification.objects.get(event_type=EventType.SAV_ACTIVITE_DUE)
        self.assertEqual(notif.link, f'/sav?id={ticket.pk}')
        self.assertNotIn('/sav/tickets/', notif.link)
