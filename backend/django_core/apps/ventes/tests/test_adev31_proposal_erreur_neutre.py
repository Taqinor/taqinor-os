"""ADEV31 (C-ADEV-043) — un échec de rendu de ``/proposal`` ne sert plus le
texte brut de l'exception (hôte MinIO, bucket, chemin serveur) : message
neutre, exception journalisée avec sa pile.

L'échec est injecté en doublant la SEULE fonction de rendu (doublure déclarée,
comme la sonde VB r5) ; la vue est réelle.

Test-du-test : remettre ``f'… : {exc}'`` ⇒ le test échoue.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

SECRET = 'minio:9000 bucket=erp-pdf secret-path /app/x.py'


class ProposalErreurNeutreTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='adev31-co', nom='ADEV31')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company),
            [('Onduleur hybride', '1', '12000')], reference='DEV-ADEV31-1')

    def test_aucun_texte_d_exception_servi(self):
        api = APIClient()
        api.force_authenticate(self.user)
        with mock.patch(
                'apps.ventes.quote_engine.generate_premium_devis_pdf',
                side_effect=RuntimeError(SECRET)), \
                self.assertLogs('apps.ventes.views.devis_pdf',
                                level='ERROR') as journal:
            resp = api.get(
                '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(
            resp.json(),
            {'detail': 'Génération de la proposition momentanément '
                       'indisponible.'})
        corps = resp.content.decode()
        for fragment in ('minio', 'bucket', 'erp-pdf', '/app/x.py'):
            self.assertNotIn(fragment, corps)
        # La pile est journalisée côté serveur.
        self.assertTrue(any(SECRET in ligne for ligne in journal.output))

    def test_regle_dure_sans_onduleur_409_neutre(self):
        # ENF11 — la RÈGLE DURE du moteur (aucune option sans onduleur) est
        # un refus tenant au contenu du devis : 409 au message neutre, pas
        # le 500 « momentanément indisponible » ; jamais le texte brut.
        api = APIClient()
        api.force_authenticate(self.user)
        refus = ValueError(
            "Devis DEV-ADEV31-1 : aucune option ne contient d'onduleur — "
            "génération du PDF à options refusée (règle de sécurité).")
        with mock.patch(
                'apps.ventes.quote_engine.generate_premium_devis_pdf',
                side_effect=refus):
            resp = api.get(
                '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertIn('onduleur', resp.json()['detail'])
        self.assertNotIn('DEV-ADEV31-1', resp.content.decode())

    def test_refus_ci_premium_409_nomme(self):
        # ADEV88 (C-ACI-012) — le refus nommé du rendu C&I (AMOT79) devient
        # un 409 « Devis commercial incomplet : <motif> », journalisé en
        # warning ; jamais le 500 neutre, jamais le texte brut (réf. devis).
        from apps.ventes.quote_engine.builder import FRAGMENT_REFUS_CI
        api = APIClient()
        api.force_authenticate(self.user)
        refus = ValueError(
            f'{FRAGMENT_REFUS_CI} — devis DEV-ADEV31-1 : nomenclature trop '
            'longue ; aucun repli legacy pour un devis commercial / '
            'industriel')
        with self.assertLogs('apps.ventes.views.devis_pdf', level='WARNING'):
            with mock.patch(
                    'apps.ventes.quote_engine.generate_premium_devis_pdf',
                    side_effect=refus):
                resp = api.get(
                    '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 409, resp.content)
        detail = resp.json()['detail']
        self.assertTrue(detail.startswith('Devis commercial incomplet'), detail)
        self.assertIn('nomenclature trop longue', detail)
        self.assertNotIn('legacy', detail)
        self.assertNotIn('DEV-ADEV31-1', detail)

    def test_autre_erreur_reste_500_neutre_meme_avec_mot_ci(self):
        # ADEV88 — une RuntimeError (même au texte proche) n'est PAS un refus
        # C&I : le 500 neutre est inchangé.
        api = APIClient()
        api.force_authenticate(self.user)
        with mock.patch(
                'apps.ventes.quote_engine.generate_premium_devis_pdf',
                side_effect=RuntimeError('Rendu premium C&I refusé — x')):
            resp = api.get(
                '/api/django/ventes/devis/%s/proposal/' % self.devis.pk)
        self.assertEqual(resp.status_code, 500)
