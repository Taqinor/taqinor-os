"""QJ2 — Tests des notifications vendeur speed-to-lead.

Trois événements couverts :
  (a) arrivée d'un nouveau lead via le webhook site web → notify owner ;
  (b) première ouverture du lien public de proposition → notify owner ;
  (c) acceptation e-signature → notification in-app + wa.me au créateur du devis.

Chaque test vérifie :
  - La notification in-app est créée (via notifications.services.notify).
  - Le corps contient un lien wa.me quand le numéro est présent.
  - La société est correctement scopée (multi-tenant).
  - Un owner absent est un no-op (pas d'exception).
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from django.contrib.auth import get_user_model

from apps.crm.models import Lead
from apps.crm.leads_notifications import notify_new_lead, notify_devis_opened
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType

User = get_user_model()


def _make_company(slug='co'):
    return Company.objects.create(nom=slug, slug=slug)


def _make_user(company, username='vendeur', role='responsable'):
    return User.objects.create_user(
        username=username, password='x',
        company=company, role_legacy=role)


def _make_lead(company, owner=None, telephone='0612345678', nom='Client Test'):
    return Lead.objects.create(
        company=company,
        nom=nom,
        telephone=telephone,
        owner=owner,
    )


# ── (a) notify_new_lead ───────────────────────────────────────────────────────

class NotifyNewLeadTests(TestCase):
    def setUp(self):
        self.company = _make_company('co-a')
        self.owner = _make_user(self.company, 'owner_a')

    def test_notification_created_for_owner(self):
        """Un nouveau lead déclenche une notification in-app pour le owner."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead)
        notifs = Notification.objects.filter(
            recipient=self.owner, event_type='lead_new')
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.LEAD_NEW)
        self.assertIn('Client Test', n.title)

    def test_body_contains_wa_url_when_phone_present(self):
        """Le corps de la notification contient un lien wa.me quand le numéro
        est présent (speed-to-lead : répondre en un tap)."""
        lead = _make_lead(self.company, owner=self.owner, telephone='0612345678')
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertIn('wa.me', n.body)

    def test_sous_seuil_mentionne_dans_le_titre_et_le_corps(self):
        """18/08/2026 — le site transmet les leads sous le seuil de facture :
        ils sont notifiés comme les autres (jamais silencieux) mais le
        commercial le VOIT avant de décrocher."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead, sous_seuil=True)
        n = Notification.objects.filter(
            recipient=self.owner, event_type='lead_new').get()
        self.assertIn('(sous le seuil)', n.title)
        self.assertIn('sous le seuil', n.body)

    def test_defaut_sans_mention_de_seuil(self):
        """Le défaut (tous les autres appelants : création manuelle, imports)
        reste strictement inchangé."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead)
        n = Notification.objects.filter(
            recipient=self.owner, event_type='lead_new').get()
        self.assertNotIn('seuil', n.title)
        self.assertNotIn('seuil', n.body)

    def test_no_notification_without_owner(self):
        """Un lead sans owner ne lève pas d'exception et ne crée rien."""
        lead = _make_lead(self.company, owner=None)
        notify_new_lead(lead)  # must not raise
        self.assertEqual(Notification.objects.count(), 0)

    def test_company_scoped(self):
        """La notification est scopée à la société du lead (multi-tenant)."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.company, self.company)

    def test_no_phone_no_wa_url(self):
        """Sans numéro de téléphone, il n'y a pas de lien wa.me dans le corps."""
        lead = _make_lead(self.company, owner=self.owner, telephone='')
        notify_new_lead(lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertNotIn('wa.me', n.body)

    def test_notify_failure_never_propagates(self):
        """Une erreur dans notify() ne doit jamais remonter à l'appelant."""
        lead = _make_lead(self.company, owner=self.owner)
        with mock.patch('apps.notifications.services.notify',
                        side_effect=RuntimeError('boom')):
            try:
                notify_new_lead(lead)
            except Exception as exc:
                self.fail(f'notify_new_lead a levé une exception : {exc}')


# ── (b) notify_devis_opened ───────────────────────────────────────────────────

class NotifyDevisOpenedTests(TestCase):
    def setUp(self):
        self.company = _make_company('co-b')
        self.owner = _make_user(self.company, 'owner_b')

    def test_notification_created_on_first_open(self):
        """La première ouverture du devis déclenche une notification in-app."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_devis_opened('DEV-001', lead)
        notifs = Notification.objects.filter(
            recipient=self.owner, event_type='devis_opened')
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.DEVIS_OPENED)
        self.assertIn('DEV-001', n.title)

    def test_body_contains_wa_url(self):
        """Le corps contient un lien wa.me vers le prospect."""
        lead = _make_lead(self.company, owner=self.owner, telephone='0655555555')
        notify_devis_opened('DEV-002', lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(n)
        self.assertIn('wa.me', n.body)

    def test_no_owner_is_noop(self):
        """Sans owner le call est silent."""
        lead = _make_lead(self.company, owner=None)
        notify_devis_opened('DEV-003', lead)
        self.assertEqual(Notification.objects.count(), 0)

    def test_company_scoped(self):
        """La notification est scopée à la société du lead."""
        lead = _make_lead(self.company, owner=self.owner)
        notify_devis_opened('DEV-004', lead)
        n = Notification.objects.filter(recipient=self.owner).first()
        self.assertEqual(n.company, self.company)

    def test_lead_oppose_aucun_lien_wa(self):
        """AMSG8 — nouveau lead, devis ouvert, demande de contact WhatsApp d'un
        lead « ne plus contacter » : notifications créées, AUCUN wa.me ; témoin
        inchangé ; APUB39 (11/11) : un rappel demandé ne lève plus l'opposition — toujours aucun wa.me."""
        from apps.crm.cadence_signaux import notify_client_contact_request
        oppose = _make_lead(self.company, owner=self.owner, nom='Oppose')
        Lead.objects.filter(pk=oppose.pk).update(ne_plus_contacter=True)
        oppose.refresh_from_db()
        notify_new_lead(oppose)
        notify_devis_opened('DEV-AMSG8-1', oppose)
        notify_client_contact_request('DEV-AMSG8-1', oppose, canal='whatsapp')
        corps = list(Notification.objects.filter(recipient=self.owner).values_list('body', flat=True))
        self.assertGreaterEqual(len(corps), 3)
        self.assertFalse([c for c in corps if 'wa.me' in (c or '')], corps)

        temoin = _make_lead(self.company, owner=self.owner, nom='Temoin', telephone='0655555556')
        Notification.objects.all().delete()
        notify_devis_opened('DEV-AMSG8-2', temoin)
        self.assertIn('wa.me', Notification.objects.get(recipient=self.owner).body)

        Notification.objects.all().delete()
        notify_client_contact_request('DEV-AMSG8-1', oppose, canal='rappel')
        demande = Notification.objects.get(recipient=self.owner, event_type='client_contact_request')
        self.assertNotIn('wa.me', demande.body)

    def test_parrainage_lead_oppose_sans_lien_wa(self):
        """AMSG8 — la notification de parrainage d'un devis accepté d'un lead
        opposé garde le lien « mon installation » mais perd « Envoyer en WhatsApp »."""
        from django.utils import timezone

        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Devis
        from core.events import devis_accepted
        CompanyProfile.objects.update_or_create(company=self.company, defaults={'referral_enabled': True})
        lead = _make_lead(self.company, owner=self.owner, nom='Oppose')
        Lead.objects.filter(pk=lead.pk).update(ne_plus_contacter=True)
        client = Client.objects.create(company=self.company, nom='Oppose', email='amsg8@example.invalid')
        devis = Devis.objects.create(
            company=self.company, reference=f"DEV-{timezone.now():%Y%m}-AMSG801", client=client,
            lead=Lead.objects.get(pk=lead.pk), statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            devis_accepted.send(sender=None, devis=devis, user=None, ancien_statut='envoye')
        parrainage = [n for n in Notification.objects.all() if 'Lien de parrainage prêt' in n.title]
        self.assertEqual(len(parrainage), 1)
        self.assertNotIn('wa.me', parrainage[0].body)
        self.assertNotIn('Envoyer en WhatsApp', parrainage[0].body)


# ── (c) acceptance — _notify_seller_accepted + wa.me ─────────────────────────

class ChaineAcceptationTests(TestCase):
    """CADV112 — la passe quotidienne ``traiter_chaine_acceptation``."""

    INSTANT = datetime.datetime(2026, 11, 23, 8, 45, tzinfo=datetime.timezone.utc)

    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        self.company = _make_company('co-j14')
        self.owner = _make_user(self.company, 'meryem_j14')
        self.direction = get_user_model().objects.create_user(
            username='reda_j14', password='x', company=self.company,
            role_legacy='admin')
        self.lead = Lead.objects.create(
            company=self.company, nom='Karim Tazi', owner=self.owner,
            stage='SIGNED', telephone='+212661778800')
        client = Client.objects.create(company=self.company, nom='Karim Tazi')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-J14-0001', client=client,
            lead=self.lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), date_acceptation=datetime.date(2026, 11, 9))

    def _passage(self, paye=False):
        from apps.crm.cadence_filet import traiter_chaine_acceptation
        with mock.patch('apps.ventes.selectors.acompte_paye_pour_devis',
                        return_value=paye), mock.patch(
                'apps.notifications.services.notify_many') as envoi:
            bilan = traiter_chaine_acceptation(self.INSTANT)
        return bilan, envoi

    def test_devis_accepte_sans_acompte_escalade_a_j14_une_seule_fois(self):
        """Mutant : retirer le marqueur ⇒ le second passage renvoie une 2ᵉ
        notification et échoue."""
        from apps.notifications.types_evenements import EventType

        bilan, envoi = self._passage()
        self.assertEqual(bilan['escalades'], 1)
        envoi.assert_called_once()
        destinataires, evenement = envoi.call_args.args
        self.assertIn(self.direction, destinataires)
        self.assertEqual(evenement, EventType.DEVIS_ACCEPTED)
        self.assertEqual(envoi.call_args.kwargs['title'],
                         'Acompte non reçu à J+14 — Karim Tazi')
        self.assertEqual(self.lead.activites.filter(
            body__startswith='Acompte non reçu à J+14').count(), 1)

        bilan, envoi = self._passage()
        self.assertEqual(bilan['escalades'], 0)
        envoi.assert_not_called()

    def test_acompte_paye_aucune_escalade_et_chaine_annulee(self):
        from apps.crm.cadence_filet import poser_chaine_apres_acceptation
        from apps.crm.models import RelanceEtape

        with mock.patch('apps.ventes.selectors.acompte_paye_pour_devis',
                        return_value=False):
            poser_chaine_apres_acceptation(self.devis, self.owner)
        self.assertEqual(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).count(), 2)

        bilan, envoi = self._passage(paye=True)
        self.assertEqual(bilan, {'escalades': 0, 'annulees': 2})
        envoi.assert_not_called()
        self.assertEqual(set(self.lead.relance_etapes.values_list('statut', 'note')),
                         {(RelanceEtape.Statut.ANNULEE, 'acompte reçu')})

    def test_avant_j14_et_vieille_vente_ne_partent_pas(self):
        from apps.ventes.models import Devis

        for jour in (datetime.date(2026, 11, 10), datetime.date(2026, 6, 1)):
            with self.subTest(acceptation=jour):
                Devis.objects.filter(pk=self.devis.pk).update(date_acceptation=jour)
                bilan, _envoi = self._passage()
                self.assertEqual(bilan['escalades'], 0)

    def test_une_autre_societe_n_est_pas_prevenue(self):
        bilan, envoi = self._passage()
        self.assertEqual(bilan['escalades'], 1)
        destinataires = envoi.call_args.args[0]
        self.assertTrue(all(u.company_id == self.company.pk for u in destinataires))


class NotifySellerAcceptedTests(TestCase):
    """Tests pour la notification vendeur à l'acceptation (QJ2 event c).

    La fonction interne ``_notify_seller_accepted`` est testée indirectement
    via ``apps.ventes.services`` pour rester dans les limites du cross-app
    boundary (pas d'import direct des modèles Ventes ici — on crée les objets
    via la DB pour éviter d'importer ventes.models dans les tests CRM).
    On utilise des mocks pour isoler la notification."""

    def setUp(self):
        self.company = _make_company('co-c')
        self.vendeur = _make_user(self.company, 'vendeur_c')

    def test_wa_url_built_from_lead_phone(self):
        """_build_acceptance_wa_url retourne un lien wa.me si le lead a un tel."""
        from apps.ventes.domain.cycle_vie import _build_acceptance_wa_url

        # Build minimal stub objects without hitting the DB.
        lead_stub = mock.Mock()
        lead_stub.whatsapp = None
        lead_stub.telephone = '0612345678'
        lead_stub.nom = 'Ali Benali'

        devis_stub = mock.Mock()
        devis_stub.lead = lead_stub
        devis_stub.client_id = None
        devis_stub.reference = 'DEV-TEST-01'

        url = _build_acceptance_wa_url(devis=devis_stub)
        self.assertIsNotNone(url)
        self.assertIn('wa.me', url)
        self.assertIn('212', url)  # normalized Moroccan number

    def test_wa_url_none_when_no_phone(self):
        """Sans numéro, _build_acceptance_wa_url renvoie None."""
        from apps.ventes.domain.cycle_vie import _build_acceptance_wa_url

        lead_stub = mock.Mock()
        lead_stub.whatsapp = ''
        lead_stub.telephone = ''
        lead_stub.nom = ''

        devis_stub = mock.Mock()
        devis_stub.lead = lead_stub
        devis_stub.client_id = None
        devis_stub.reference = 'DEV-X'

        url = _build_acceptance_wa_url(devis=devis_stub)
        self.assertIsNone(url)

    def test_notify_seller_accepted_creates_notification(self):
        """_notify_seller_accepted crée une notification in-app pour le vendeur."""
        from apps.ventes.domain.cycle_vie import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-99'
        devis_stub.pk = 1
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)

        notifs = Notification.objects.filter(recipient=self.vendeur)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.event_type, EventType.DEVIS_ACCEPTED)
        self.assertIn('DEV-99', n.title)

    def test_notify_seller_accepted_uses_correct_event_type(self):
        """La notification utilise le type 'devis_accepted' (EventType valide)."""
        from apps.ventes.domain.cycle_vie import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-EV'
        devis_stub.pk = 2
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)

        n = Notification.objects.filter(recipient=self.vendeur).first()
        self.assertIsNotNone(n)
        self.assertIn(n.event_type, EventType.values)

    def test_self_notify_skipped(self):
        """Le créateur du devis n'est pas notifié quand il est l'acteur."""
        from apps.ventes.domain.cycle_vie import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-SELF'
        devis_stub.pk = 3
        devis_stub.created_by = self.vendeur
        devis_stub.company = self.company
        devis_stub.client = None
        devis_stub.client_id = None
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=self.vendeur)

        self.assertEqual(Notification.objects.count(), 0)

    def test_no_created_by_is_noop(self):
        """Pas de créateur = aucune notification, aucune exception."""
        from apps.ventes.domain.cycle_vie import _notify_seller_accepted

        devis_stub = mock.Mock()
        devis_stub.reference = 'DEV-NONE'
        devis_stub.pk = 4
        devis_stub.created_by = None
        devis_stub.company = self.company
        devis_stub.lead = None

        _notify_seller_accepted(devis=devis_stub, user=None)
        self.assertEqual(Notification.objects.count(), 0)
