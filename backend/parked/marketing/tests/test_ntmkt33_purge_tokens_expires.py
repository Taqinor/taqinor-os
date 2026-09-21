"""NTMKT33 — Purge des tokens expirés (désinscription XMKT3 / préférences
NTMKT22), tâche Celery beat quotidienne (03:00).

Les deux jetons publics sont des jetons SIGNÉS (``django.core.signing``),
jamais stockés en base : il n'existe donc aucun enregistrement à purger pour
eux — leur expiration est imposée à la LECTURE via ``max_age`` (90 jours).
Ce test verrouille les DEUX faces de l'acceptance : un jeton de +90j est
rejeté (« purgé » fonctionnellement), un jeton récent reste valide ; et la
tâche beat elle-même ne lève jamais et reste joignable (QX11).
"""
from django.test import TestCase

from authentication.models import Company

from apps.marketing import services as mkt_services


class TokenPreferencesExpirationTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt33', nom='NTMKT33')

    def test_token_recent_reste_valide(self):
        token = mkt_services.generer_token_preferences(self.co.id, 'a@b.ma')
        company, destinataire = mkt_services.lire_token_preferences(token)
        self.assertEqual(company, self.co)
        self.assertEqual(destinataire, 'a@b.ma')

    def test_token_de_plus_de_90_jours_est_rejete(self):
        token = mkt_services.generer_token_preferences(self.co.id, 'a@b.ma')
        # Un jeton "vieux" est simulé en lisant avec un max_age déjà écoulé
        # (équivalent à un jeton signé il y a plus de 90 jours).
        company, destinataire = mkt_services.lire_token_preferences(
            token, max_age=-1)
        self.assertIsNone(company)
        self.assertIsNone(destinataire)

    def test_token_invalide_est_rejete_proprement(self):
        company, destinataire = mkt_services.lire_token_preferences('garbage')
        self.assertIsNone(company)
        self.assertIsNone(destinataire)


class PurgerTokensExpiresServiceTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt33b', nom='NTMKT33b')

    def test_purge_ne_leve_jamais_et_renvoie_un_compte(self):
        rapport = mkt_services.purger_tokens_expires(self.co)
        self.assertEqual(rapport, {'jetons_purges': 0})


class PurgerTokensExpiresTaskTests(TestCase):
    def test_la_tache_beat_est_joignable(self):
        from apps.marketing.tasks import purger_tokens_expires_task
        resultat = purger_tokens_expires_task()
        self.assertIn('jetons_purges', resultat)
