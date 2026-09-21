"""NTSCM45 — Notifications ciblées sur écart de prévision important.

Critère d'acceptation : un produit à MAPE 55% déclenche exactement une
notification par Acheteur concerné, pas de doublon si la tâche est relancée
le même mois."""
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import EventType, Notification
from apps.records.models import Follower
from apps.scm.models import PrevisionDemande
from apps.scm.tasks import notifier_ecarts_prevision_importants
from apps.stock.models import MouvementStock, Produit

from .helpers import make_company, make_user


class NotifierEcartsPrevisionImportantsTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-notif-ecart', 'Supply Notif Écart')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 8kW', prix_vente=9000,
            quantite_stock=50)
        self.admin = make_user(self.company, 'scm-notif-ecart-admin', 'admin')

    def _periode_mois_dernier(self):
        today = timezone.localdate()
        idx = today.year * 12 + (today.month - 1) - 1
        y, m0 = divmod(idx, 12)
        return y, m0 + 1

    def _seed_ecart_important(self):
        # Réel très supérieur à la prévision -> MAPE > 40% garanti.
        y, m = self._periode_mois_dernier()
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=f'{y:04d}-{m:02d}', quantite_prevue=10)
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=100, quantite_avant=1000, quantite_apres=900)
        mvt.date = timezone.make_aware(timezone.datetime(y, m, 15))
        mvt.save(update_fields=['date'])

    def test_produit_a_mape_important_notifie_les_destinataires_resolus(self):
        self._seed_ecart_important()
        resultat = notifier_ecarts_prevision_importants()
        ligne = next(r for r in resultat if r['company_id'] == self.company.id)
        self.assertEqual(ligne['nb_notifications'], 1)

        notifs = Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.SCM_ECART_PREVISION_IMPORTANT)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(str(self.produit.id), notifs.first().link)

    def test_relance_le_meme_mois_ne_duplique_pas(self):
        self._seed_ecart_important()
        notifier_ecarts_prevision_importants()
        notifier_ecarts_prevision_importants()

        notifs = Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.SCM_ECART_PREVISION_IMPORTANT)
        self.assertEqual(notifs.count(), 1)

    def test_aucun_ecart_important_aucune_notification(self):
        y, m = self._periode_mois_dernier()
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=f'{y:04d}-{m:02d}', quantite_prevue=100)
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=100, quantite_avant=1000, quantite_apres=900)
        mvt.date = timezone.make_aware(timezone.datetime(y, m, 15))
        mvt.save(update_fields=['date'])

        notifier_ecarts_prevision_importants()
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.SCM_ECART_PREVISION_IMPORTANT).exists())

    def test_follower_explicite_du_produit_prime_sur_les_destinataires_resolus(self):
        self._seed_ecart_important()
        from django.contrib.contenttypes.models import ContentType
        suiveur = make_user(self.company, 'scm-notif-ecart-suiveur', 'normal')
        Follower.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Produit),
            object_id=self.produit.id, user=suiveur)

        notifier_ecarts_prevision_importants()

        self.assertTrue(
            Notification.objects.filter(
                recipient=suiveur,
                event_type=EventType.SCM_ECART_PREVISION_IMPORTANT).exists())
        # Le followers explicite REMPLACE (jamais n'ajoute à) le repli
        # managers — self.admin n'est pas suivi explicitement.
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.admin,
                event_type=EventType.SCM_ECART_PREVISION_IMPORTANT).exists())
