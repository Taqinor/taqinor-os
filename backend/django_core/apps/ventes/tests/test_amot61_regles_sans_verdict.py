"""AMOT61 (C-AMOT-037) — la passe nocturne de cohérence signale toute règle
restée sans verdict : ``rule_errors > 0`` ⇒ digest aux administrateurs
(« N règles sans verdict », décompte par règle) puis tâche en ÉCHEC visible,
APRÈS persistance du rapport ; une nuit sans erreur reste silencieuse.

``run_audit`` réel, constructeur de document injecté qui lève (comme la
sonde VB) ; ``notify`` réel observé.

Test-du-test : remettre « ``if report.new`` » comme seule condition de
notification ⇒ ``test_regles_sans_verdict_notifiees_puis_echec`` échoue.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ventes.coherence import moteur
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


def _constructeur_qui_leve(*args, **kwargs):
    raise RuntimeError('constructeur indisponible')


class ReglesSansVerdictTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AMOT61', slug='amot61-co')
        self.admin = User.objects.create_user(
            username='amot61_admin', password='x', role_legacy='admin',
            company=self.company)
        from apps.crm.models import Client
        client = Client.objects.create(company=self.company, nom='Client 61')
        Devis.objects.create(company=self.company, reference='DEV-AMOT61-1',
                             client=client, taux_tva=Decimal('20'))

    def _rapport_en_erreur(self):
        return moteur.run_audit(company=self.company, persist=True,
                                constructeur=_constructeur_qui_leve)

    def test_regles_sans_verdict_notifiees_puis_echec(self):
        from apps.ventes.tasks import audit_coherence_nuit
        rapport = self._rapport_en_erreur()
        self.assertTrue(rapport.rule_errors)
        with mock.patch('apps.ventes.coherence.moteur.run_audit',
                        return_value=rapport), \
                mock.patch('apps.notifications.services.notify',
                           return_value=object()) as notify:
            with self.assertRaises(RuntimeError) as ctx:
                audit_coherence_nuit()
        self.assertIn('sans verdict', str(ctx.exception))
        titres = [c.args[2] for c in notify.call_args_list]
        self.assertTrue(any('sans verdict' in t for t in titres), titres)

    def test_nuit_sans_erreur_silencieuse(self):
        from apps.ventes.tasks import audit_coherence_nuit
        vide = moteur.AuditReport()
        with mock.patch('apps.ventes.coherence.moteur.run_audit',
                        return_value=vide), \
                mock.patch('apps.notifications.services.notify') as notify:
            resume = audit_coherence_nuit()
        notify.assert_not_called()
        self.assertEqual(resume['rule_errors'], 0)
