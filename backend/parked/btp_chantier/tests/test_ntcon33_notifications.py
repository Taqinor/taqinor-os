"""NTCON33 — notifications ciblées sur les événements BTP clés.

Ce que le test PROUVE :
  * chaque événement génère la notification au BON destinataire — réserve
    bloquante → responsable désigné, RFI → destinataire, visa soumis →
    revuseurs routés, avenant décidé → équipe projet ;
  * le routage passe par ``NotificationRoutingRule`` (le registre existant) et
    retombe sur les managers quand aucune règle n'est configurée — jamais une
    liste de destinataires calculée dans ``btp_chantier`` ;
  * les ``NotificationPreference`` de l'utilisateur sont respectées (le
    canal in-app coupé ⇒ aucune notification in-app) ;
  * aucun canal ad hoc : toutes les notifications sont des
    ``notifications.Notification``.
"""
from django.test import TestCase

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    AvenantChantier, ReserveChantier, VisaDocument,
)
from apps.notifications.models import (
    EventType, Notification, NotificationPreference, NotificationRoutingRule,
)

from .helpers import make_chantier, make_company, make_user


def _notifs(user, event_type=None):
    qs = Notification.objects.filter(recipient=user)
    if event_type:
        qs = qs.filter(event_type=event_type)
    return qs


class NotificationsBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.auteur = make_user(self.co, role='responsable',
                                username='ntcon33-auteur')
        # Manager « par défaut » : destinataire du repli de resolve_recipients.
        self.manager = make_user(self.co, role='admin',
                                 username='ntcon33-manager')
        self.conducteur = make_user(self.co, role='normal',
                                    username='ntcon33-conducteur')

    # ── réserve bloquante ──────────────────────────────────────────────────
    def test_reserve_bloquante_notifie_le_responsable_designe(self):
        reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='électricité',
            localisation_plan={}, description='Tableau non conforme',
            gravite=ReserveChantier.Gravite.BLOQUANTE,
            responsable_leve=self.conducteur, created_by=self.auteur)
        services.enregistrer_creation_reserve(reserve, created_by=self.auteur)
        self.assertEqual(
            _notifs(self.conducteur, EventType.APPROVAL_REQUESTED).count(), 1)

    def test_reserve_bloquante_sans_responsable_route_vers_l_equipe(self):
        reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='CVC',
            localisation_plan={}, description='Gaine bloquée',
            gravite=ReserveChantier.Gravite.BLOQUANTE, created_by=self.auteur)
        services.enregistrer_creation_reserve(reserve, created_by=self.auteur)
        # Repli historique de resolve_recipients : les managers actifs.
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_REQUESTED).count(), 1)

    def test_reserve_non_bloquante_ne_notifie_personne(self):
        reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='peinture',
            localisation_plan={}, description='Retouche',
            gravite=ReserveChantier.Gravite.MINEURE,
            responsable_leve=self.conducteur, created_by=self.auteur)
        services.enregistrer_creation_reserve(reserve, created_by=self.auteur)
        self.assertEqual(_notifs(self.conducteur).count(), 0)
        self.assertEqual(_notifs(self.manager).count(), 0)

    # ── RFI ────────────────────────────────────────────────────────────────
    def test_rfi_notifie_le_destinataire_interne(self):
        services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.auteur,
            question='Section de câble ?', destinataire_user=self.conducteur)
        self.assertEqual(
            _notifs(self.conducteur, EventType.APPROVAL_REQUESTED).count(), 1)

    def test_rfi_destinataire_externe_route_vers_l_equipe(self):
        """Un RFI posé au BE externe ne doit pas dormir jusqu'au sweep."""
        services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.auteur,
            question='Section de câble ?', destinataire_texte='BE Structure')
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_REQUESTED).count(), 1)

    def test_l_auteur_n_est_pas_notifie_de_son_propre_geste(self):
        services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.manager,
            question='?', destinataire_texte='BE')
        self.assertEqual(_notifs(self.manager).count(), 0)

    # ── visa ───────────────────────────────────────────────────────────────
    def test_visa_soumis_notifie_les_revuseurs_routes(self):
        services.soumettre_visa(
            company=self.co, chantier=self.chantier, document_ged_id=7,
            soumis_par=self.auteur,
            type_visa=VisaDocument.TypeVisa.PLAN_EXECUTION)
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_REQUESTED).count(), 1)

    def test_regle_de_routage_redirige_le_visa(self):
        """Le registre NotificationRoutingRule PRIME sur le repli managers."""
        NotificationRoutingRule.objects.create(
            company=self.co, event_type=EventType.APPROVAL_REQUESTED,
            target_user=self.conducteur, enabled=True)
        services.soumettre_visa(
            company=self.co, chantier=self.chantier, document_ged_id=8,
            soumis_par=self.auteur,
            type_visa=VisaDocument.TypeVisa.NOTE_CALCUL)
        self.assertEqual(
            _notifs(self.conducteur, EventType.APPROVAL_REQUESTED).count(), 1)
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_REQUESTED).count(), 0)

    def test_preference_utilisateur_respectee(self):
        """Canal in-app coupé ⇒ aucune notification in-app pour cet événement."""
        NotificationPreference.objects.update_or_create(
            user=self.manager, event_type=EventType.APPROVAL_REQUESTED,
            defaults={'company': self.co, 'in_app': False, 'email': False,
                      'whatsapp': False, 'push': False})
        services.soumettre_visa(
            company=self.co, chantier=self.chantier, document_ged_id=9,
            soumis_par=self.auteur,
            type_visa=VisaDocument.TypeVisa.FICHE_TECHNIQUE)
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_REQUESTED).count(), 0)

    # ── avenant ────────────────────────────────────────────────────────────
    def test_avenant_approuve_notifie_l_equipe_projet(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier, reference='AV-1',
            description='Reprise VRD', montant_ht=1000,
            statut=AvenantChantier.Statut.SOUMIS_CLIENT,
            cree_par=self.auteur, impact_budget=True)
        services.approuver_avenant(avenant, user=self.auteur)
        self.assertEqual(
            _notifs(self.manager, EventType.APPROVAL_DECIDED).count(), 1)

    def test_avenant_refuse_notifie_l_equipe_avec_le_motif(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier, reference='AV-2',
            description='Reprise VRD', montant_ht=1000,
            statut=AvenantChantier.Statut.SOUMIS_CLIENT,
            cree_par=self.auteur, impact_budget=True)
        services.refuser_avenant(
            avenant, user=self.auteur, motif='hors enveloppe')
        notif = _notifs(self.manager, EventType.APPROVAL_DECIDED).first()
        self.assertIsNotNone(notif)
        self.assertIn('hors enveloppe', notif.body)

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_aucune_notification_ne_traverse_la_frontiere_societe(self):
        autre = make_company()
        voisin = make_user(autre, role='admin', username='ntcon33-voisin')
        services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.auteur,
            question='?', destinataire_texte='BE')
        self.assertEqual(_notifs(voisin).count(), 0)
