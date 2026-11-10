"""Tests NTOBS34 — marqueur d'alerte d'expiration sur le trust center (schéma).

Ce que le champ doit garantir : défaut FAUX (donc la première alerte partira),
et une entrée déjà alertée reste marquée — c'est tout ce sur quoi le balayage
périodique s'appuie pour ne jamais réémettre deux fois la même alerte.

La CHARGE UTILE publique du trust center ne doit PAS exposer ce marqueur :
c'est un détail d'exploitation interne, pas une information de confiance.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from core.trust_center import TrustCenterEntry, TrustCenterEntrySerializer


class AlerteExpirationTests(TestCase):

    def _entree(self, titre='ISO 27001'):
        return TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre=titre)

    def test_defaut_faux(self):
        entree = self._entree()
        self.assertFalse(entree.alerte_expiration_envoyee)

    def test_marqueur_persiste(self):
        entree = self._entree('ISO 9001')
        entree.alerte_expiration_envoyee = True
        entree.save(update_fields=['alerte_expiration_envoyee', 'updated_at'])

        entree.refresh_from_db()
        self.assertTrue(entree.alerte_expiration_envoyee)

    def test_marqueur_absent_de_la_charge_publique(self):
        entree = self._entree('Hébergement Maroc')
        donnees = TrustCenterEntrySerializer(entree).data
        self.assertNotIn('alerte_expiration_envoyee', donnees)

    def test_marquee_seulement_si_notifiee(self):
        """ASOC29 — sans superutilisateur actif, aucune notification : l'entrée
        reste non alertée et la tâche rend 0 ; avec un actif : 1, marquée."""
        from django.apps import apps as django_apps

        from core.tasks import verifier_fraicheur_trust_center_task
        # Contrat core-foundation : aucun import statique d'une app dans core/tests.
        Notification = django_apps.get_model('notifications', 'Notification')

        cache.clear()
        entree = TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION, titre='ISO',
            dernier_audit_le=datetime.date.today() - datetime.timedelta(days=400))
        racine = get_user_model().objects.create_superuser(
            username='asoc29-root', password='x', is_active=False)
        self.assertEqual(verifier_fraicheur_trust_center_task(), {'notifies': 0})
        entree.refresh_from_db()
        self.assertFalse(entree.alerte_expiration_envoyee)
        racine.is_active = True
        racine.save(update_fields=['is_active'])
        self.assertEqual(verifier_fraicheur_trust_center_task(), {'notifies': 1})
        entree.refresh_from_db()
        self.assertTrue(entree.alerte_expiration_envoyee)
        self.assertEqual(Notification.objects.filter(
            recipient=racine, event_type='trust_center_audit_expire').count(), 1)
