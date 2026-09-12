"""
NTP2P45 (volet installations) — Notifications in-app sur les étapes
d'approbation achats.

``EtapeApprobationAchat`` est instanciée en bloc via ``bulk_create`` (aucun
signal ``post_save`` ne se déclenche) : l'étape 1 est déjà couverte par la
notification SOUMISE existante (VX99). Ce fichier couvre le trou réel —
jusqu'ici silencieux — que ``services.approuver_etape_achat`` comble :
l'approbation d'une étape notifie IMMÉDIATEMENT les approbateurs de l'étape
SUIVANTE devenue active, sans attendre le prochain cycle Celery beat.

Run :
    python manage.py test \
        apps.installations.test_ntp2p45_notif_etape_suivante -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations import services
from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)
from apps.notifications.models import EventType, Notification

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p45-co-{n}', defaults={'nom': f'NTP2P45 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p45-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_demande(company, user, *, montant):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-NTP2P45-{next(_seq):04d}',
        objet='Réquisition NTP2P45', created_by=user)
    DemandeAchatLigne.objects.create(
        demande=da, designation='Article', quantite=1, prix_estime=montant)
    da.statut = DemandeAchat.Statut.SOUMISE
    da.save(update_fields=['statut'])
    return da


class NotifierEtapeSuivanteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        # Un admin pour recevoir la notification (resolve_recipients replie
        # sur admin/responsable actifs sans NotificationRoutingRule).
        self.admin = make_user(self.company, role='admin')
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Deux niveaux',
            montant_min=1000, nombre_approbateurs=2, actif=True)
        self.da = make_demande(self.company, self.demandeur, montant=50000)
        self.etapes = services.lancer_workflow_approbation_achat(self.da)
        self.assertEqual(len(self.etapes), 2)

    def test_approuver_premiere_etape_notifie_la_suivante(self):
        Notification.objects.filter(company=self.company).delete()
        premiere = self.etapes[0]
        services.approuver_etape_achat(
            premiere, approbateur=self.admin, commentaire='')

        notifs = Notification.objects.filter(
            company=self.company, event_type=EventType.APPROVAL_REQUESTED)
        self.assertGreaterEqual(notifs.count(), 1)
        self.assertTrue(
            any('Étape 2' in n.title for n in notifs))

    def test_approuver_derniere_etape_n_appelle_pas_le_notifieur_de_suite(self):
        premiere = self.etapes[0]
        services.approuver_etape_achat(
            premiere, approbateur=self.admin, commentaire='')
        deuxieme = services.prochaine_etape_approbation_achat(self.da)
        Notification.objects.filter(company=self.company).delete()

        services.approuver_etape_achat(
            deuxieme, approbateur=self.admin, commentaire='')

        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.APPROUVEE)
        # Plus aucune étape en attente : le helper ne trouve rien à notifier.
        self.assertIsNone(
            services.prochaine_etape_approbation_achat(self.da))

    def test_une_seule_etape_ne_declenche_jamais_ce_notifieur(self):
        company = make_company()
        demandeur = make_user(company)
        admin = make_user(company, role='admin')
        RegleApprobationAchat.objects.create(
            company=company, libelle='Un niveau',
            montant_min=1000, nombre_approbateurs=1, actif=True)
        da = make_demande(company, demandeur, montant=50000)
        etapes = services.lancer_workflow_approbation_achat(da)
        self.assertEqual(len(etapes), 1)
        Notification.objects.filter(company=company).delete()

        services.approuver_etape_achat(
            etapes[0], approbateur=admin, commentaire='')

        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
        self.assertEqual(
            EtapeApprobationAchat.objects.filter(demande=da).count(), 1)
