"""SOL14 — la grille « événement × canaux » suit les modules de la société.

Régler des canaux pour une notification qui ne partira jamais (module éteint,
hors plan, vertical parqué) n'a aucun sens et allongeait l'écran. Ce qui NE
DOIT PAS arriver : masquer un événement dont le module est incertain, ou
perdre un réglage déjà enregistré.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import (
    EventType, NotificationPreference,
)
from apps.notifications.module_map import (
    EVENT_TYPE_MODULE, event_types_masques,
)
from apps.notifications.services import merged_preferences
from authentication.models import Company
from core import modules as modules_infra
from core.models import ModuleToggle

User = get_user_model()


class TableEventTypeModuleTests(TestCase):
    def test_chaque_event_type_cite_existe(self):
        connus = set(EventType.values)
        morts = sorted(e for e in EVENT_TYPE_MODULE if e not in connus)
        self.assertEqual(morts, [], f'event types inexistants : {morts}')

    def test_chaque_module_cite_existe(self):
        manifests = modules_infra.collect_manifests()
        inconnus = sorted({
            m for m in EVENT_TYPE_MODULE.values() if m not in manifests})
        self.assertEqual(inconnus, [], f'modules inconnus : {inconnus}')

    def test_les_evenements_transverses_ne_sont_pas_mappes(self):
        """Jamais masquables : ils ne dépendent d'aucun module installable."""
        for event_type in ('digest', 'security_alert', 'approval_requested',
                           'annonce_published', 'snooze_reveil'):
            self.assertNotIn(event_type, EVENT_TYPE_MODULE, event_type)


class GrilleDesPreferencesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NOTIF SOL14', slug='sol14-n')
        cls.user = User.objects.create_user(
            username='sol14_notif', password='x', role_legacy='normal',
            company=cls.company)

    def test_sans_module_eteint_la_grille_est_complete(self):
        lignes = merged_preferences(self.user)
        self.assertEqual(len(lignes), len(EventType.choices))
        self.assertEqual(event_types_masques(self.company), frozenset())

    def test_un_module_eteint_retire_ses_evenements(self):
        ModuleToggle.objects.create(
            company=self.company, module='scm', actif=False)
        vus = {ligne['event_type'] for ligne in merged_preferences(self.user)}
        self.assertNotIn('scm_previsions_generees', vus)
        self.assertNotIn('scm_cycle_sop_ouvert', vus)
        self.assertNotIn('scm_ecart_prevision_important', vus)
        # Les événements des autres modules restent proposés.
        self.assertIn('devis_accepted', vus)
        self.assertIn('digest', vus)

    def test_un_evenement_non_mappe_n_est_jamais_masque(self):
        for cle in ('ventes', 'crm', 'stock', 'sav'):
            ModuleToggle.objects.create(
                company=self.company, module=cle, actif=False)
        vus = {ligne['event_type'] for ligne in merged_preferences(self.user)}
        # `devis_accepted` appartient de fait à `ventes`, mais il n'est PAS
        # dans la table : on ne devine pas par préfixe, donc on ne masque pas.
        self.assertIn('devis_accepted', vus)

    def test_un_reglage_deja_enregistre_reste_en_base(self):
        NotificationPreference.objects.create(
            user=self.user, company=self.company,
            event_type='scm_previsions_generees', in_app=False, email=True)
        ModuleToggle.objects.create(
            company=self.company, module='scm', actif=False)
        merged_preferences(self.user)
        pref = NotificationPreference.objects.get(
            user=self.user, event_type='scm_previsions_generees')
        self.assertTrue(pref.email)
        self.assertFalse(pref.in_app)

    def test_sans_societe_rien_n_est_masque(self):
        self.assertEqual(event_types_masques(None), frozenset())
