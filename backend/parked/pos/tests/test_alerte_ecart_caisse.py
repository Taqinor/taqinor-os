"""NTRET32 — Alerte fondateur/gérant sur écart de caisse anormal.

Couvre : un écart au-dessus du seuil configuré notifie les managers une
fois, un écart sous le seuil reste silencieux, seuil vide/0 (défaut) =
comportement actuel inchangé (aucune notification), l'écart TPE déclenche
aussi l'alerte, un utilisateur 'normal' (non manager) n'est jamais notifié.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.notifications.models import EventType, Notification
from apps.parametres.models_pos import ParametresPos
from apps.pos import services

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class AlerteEcartCaisseTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret32', 'NTRET32 Co')
        self.manager = make_user(self.co, 'manager-ntret32', role='responsable')
        self.caissier = make_user(self.co, 'caissier-ntret32', role='normal')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        self.caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))

    def _ouvrir(self):
        return services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.caissier, fond_ouverture=Decimal('0'), user=self.caissier)

    def test_seuil_desactive_par_defaut_aucune_alerte(self):
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('500'), user=self.caissier)
        self.assertEqual(
            Notification.objects.filter(
                company=self.co, event_type=EventType.CAISSE_ECART_ANORMAL).count(),
            0)

    def test_ecart_sous_le_seuil_reste_silencieux(self):
        params = ParametresPos.get(self.co)
        params.seuil_alerte_ecart_caisse = Decimal('50')
        params.save(update_fields=['seuil_alerte_ecart_caisse'])
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('20'), user=self.caissier)
        self.assertEqual(
            Notification.objects.filter(
                company=self.co, event_type=EventType.CAISSE_ECART_ANORMAL).count(),
            0)

    def test_ecart_especes_au_dessus_du_seuil_notifie_le_manager(self):
        params = ParametresPos.get(self.co)
        params.seuil_alerte_ecart_caisse = Decimal('50')
        params.save(update_fields=['seuil_alerte_ecart_caisse'])
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('500'), user=self.caissier)

        notifs = Notification.objects.filter(
            company=self.co, event_type=EventType.CAISSE_ECART_ANORMAL)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().recipient_id, self.manager.id)
        self.assertIn(str(session.pk), notifs.first().title)

    def test_caissier_normal_jamais_notifie(self):
        params = ParametresPos.get(self.co)
        params.seuil_alerte_ecart_caisse = Decimal('50')
        params.save(update_fields=['seuil_alerte_ecart_caisse'])
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('500'), user=self.caissier)
        self.assertFalse(
            Notification.objects.filter(
                company=self.co, event_type=EventType.CAISSE_ECART_ANORMAL,
                recipient=self.caissier).exists())

    def test_ecart_tpe_au_dessus_du_seuil_notifie_aussi(self):
        params = ParametresPos.get(self.co)
        params.seuil_alerte_ecart_caisse = Decimal('10')
        params.save(update_fields=['seuil_alerte_ecart_caisse'])
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('0'),
            montant_tpe_compte=Decimal('100'), user=self.caissier)
        self.assertEqual(
            Notification.objects.filter(
                company=self.co, event_type=EventType.CAISSE_ECART_ANORMAL).count(),
            1)

    def test_isolation_multi_tenant(self):
        co_b = make_company('ntret32-b', 'NTRET32 B')
        make_user(co_b, 'manager-ntret32-b', role='responsable')
        params_b = ParametresPos.get(co_b)
        params_b.seuil_alerte_ecart_caisse = Decimal('50')
        params_b.save(update_fields=['seuil_alerte_ecart_caisse'])

        # Seuil configuré uniquement pour co_b : la clôture de self.co (sans
        # seuil) ne notifie jamais personne dans co_b.
        session = self._ouvrir()
        services.cloturer_session(
            session=session, montant_compte=Decimal('500'), user=self.caissier)
        self.assertEqual(
            Notification.objects.filter(
                company=co_b, event_type=EventType.CAISSE_ECART_ANORMAL).count(),
            0)
