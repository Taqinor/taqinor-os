"""CAL23 — le calcul lourd en TÂCHE DE FOND (kind `calepinage`).

Ce qui est prouvé ici :

* au-delà du budget synchrone, ``moteur/calculer`` rend 202 avec un ``job_id``
  RÉEL (un ``BackgroundJob`` de kind ``calepinage``), pas une simple consigne ;
* le résultat se relit par le MÊME identifiant sur
  ``moteur/resultat/<job_id>/`` ;
* DEUX exécutions de la tâche sur le même job n'écrivent qu'UN seul résultat
  (idempotence : même entrée ⇒ même empreinte ⇒ même clé) ;
* une soumission MULTIPLE passe par le MÊME kind, et chaque élément réussit ou
  échoue SÉPARÉMENT et NOMMÉMENT ;
* un job d'une AUTRE société est introuvable (404), jamais « interdit ».

Le MOTEUR est simulé : ce fichier prouve la file, pas la géométrie.

Run :
    python manage.py test apps.calepinage.tests.test_moteur_async -v2
"""
from unittest import mock

from django.test import SimpleTestCase

from core.models import BackgroundJob

from .test_api_liste import BaseApiCalepinage
from .test_api_moteur import DOCUMENT, URL, CoutFactice

RESULTAT = {'schema_version': 1, 'repere': 'SITE-ESSAI', 'total_modules': 12,
            'kwc': 8.64, 'hash_entree': 'a' * 64, 'version_moteur': 'essai'}


def url_resultat(job_id):
    return f'/api/django/calepinage/moteur/resultat/{job_id}/'


class TacheDeFondTest(BaseApiCalepinage):
    def _lancer(self):
        """Force la bascule asynchrone et renvoie la réponse 202."""
        with mock.patch('apps.calepinage.moteur_service.cout_calepinage',
                        return_value=CoutFactice(synchrone=False)), \
                mock.patch('core.jobs.current_app.send_task'), \
                mock.patch('apps.calepinage.tasks.calculer_calepinage.delay'):
            return self.api.post(URL, DOCUMENT, format='json')

    def test_202_porte_un_job_reel(self):
        reponse = self._lancer()
        self.assertEqual(reponse.status_code, 202, reponse.data)
        job = BackgroundJob.objects.get(pk=reponse.data['job_id'])
        self.assertEqual(job.kind, 'calepinage')
        self.assertEqual(job.company_id, self.company.pk)
        self.assertEqual(job.user_id, self.user.pk)
        self.assertIsNone(reponse.data['resultat'])
        self.assertIn('cout_estime', reponse.data)

    def test_le_resultat_se_relit_par_le_meme_identifiant(self):
        from apps.calepinage.tasks import calculer_calepinage

        job_id = self._lancer().data['job_id']
        with mock.patch('apps.calepinage.moteur_service.calepinage_json',
                        return_value=dict(RESULTAT)):
            calculer_calepinage(job_id=job_id, entree=DOCUMENT)
        reponse = self.api.get(url_resultat(job_id))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], BackgroundJob.STATUT_DONE)
        self.assertEqual(reponse.data['resultat']['total_modules'], 12)

    def test_deux_executions_n_ecrivent_qu_un_resultat(self):
        from apps.calepinage.tasks import calculer_calepinage, cle_resultat

        job_id = self._lancer().data['job_id']
        with mock.patch('apps.calepinage.moteur_service.calepinage_json',
                        return_value=dict(RESULTAT)):
            calculer_calepinage(job_id=job_id, entree=DOCUMENT)
            calculer_calepinage(job_id=job_id, entree=DOCUMENT)
        from core import cache as cache_tenant

        cle = cle_resultat(RESULTAT['hash_entree'],
                           RESULTAT['version_moteur'])
        self.assertIsNotNone(cache_tenant.get(self.company.pk, cle))
        self.assertEqual(
            BackgroundJob.objects.filter(kind='calepinage').count(), 1)
        elements = self.api.get(url_resultat(job_id)).data['elements']
        self.assertEqual(len(elements), 1)

    def test_soumission_multiple_meme_kind_issues_separees(self):
        from apps.calepinage.moteur_service import (
            erreurs_moteur_calepinage,
        )
        from apps.calepinage.tasks import calculer_calepinage

        entree_invalide, _ = erreurs_moteur_calepinage()
        job = BackgroundJob.objects.create(
            company=self.company, user=self.user, kind='calepinage')
        bon = dict(DOCUMENT, repere='PAN-A')
        mauvais = dict(DOCUMENT, repere='PAN-B')

        def calcul(document, **kwargs):
            if document.get('repere') == 'PAN-B':
                raise entree_invalide('Surface absente.')
            return dict(RESULTAT)

        with mock.patch('apps.calepinage.moteur_service.calepinage_json',
                        side_effect=calcul):
            calculer_calepinage(job_id=job.pk, entrees=[bon, mauvais])
        reponse = self.api.get(url_resultat(job.pk))
        elements = {e['repere']: e for e in reponse.data['elements']}
        self.assertEqual(elements['PAN-A']['statut'], 'done')
        self.assertEqual(elements['PAN-B']['statut'], 'failed')
        self.assertIn('Surface absente.', elements['PAN-B']['motif'])
        self.assertEqual(
            BackgroundJob.objects.filter(kind='calepinage').count(), 1)

    def test_cache_vide_echec_au_troisieme_passage(self):
        # ACAL1963 — le compte des livraisons est porté par une ligne durable :
        # le cache société vidé entre chaque livraison ne le remet pas à 1.
        # Mutant : revenir au cache seul ⇒ quatre calculs, jamais l'échec.
        from django.core.cache import cache

        from apps.calepinage import tasks
        from apps.calepinage.models import Calepinage

        class _Tue(BaseException):
            pass

        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Tué 1963',
            roof_layout={})
        job = BackgroundJob.objects.create(
            company=self.company, user=self.user, kind='calepinage')
        issues = []
        with mock.patch('apps.calepinage.services.simulation.simuler_calepinage',
                        side_effect=_Tue) as calcul:
            for _ in range(4):
                cache.clear()
                try:
                    issues.append(tasks.simuler_calepinage(
                        job_id=job.pk, company_id=self.company.pk,
                        calepinage_id=calepinage.pk)['statut'])
                except _Tue:
                    issues.append('tue')
        self.assertEqual(issues[:3], ['tue', 'tue', 'failed'])
        self.assertEqual(calcul.call_count, 2)
        job.refresh_from_db()
        self.assertEqual(job.statut, BackgroundJob.STATUT_FAILED)

    def test_compteurs_de_livraison_anciens_supprimes_numerotation_intacte(self):
        # Revue lot 6 (ACAL1963) — la table reste bornée : un compteur de
        # livraison sans livraison depuis 48 h est supprimé à la livraison
        # suivante ; une séquence d'un autre usage n'est jamais touchée.
        import datetime

        from django.utils import timezone

        from core.models import SequenceCounter

        from apps.calepinage import tasks

        vieux = SequenceCounter.objects.create(
            company=self.company, cle=tasks.PREFIXE_COMPTEUR_LIVRAISONS + '1:1', dernier=2)
        autre = SequenceCounter.objects.create(company=self.company, cle='job', dernier=7)
        SequenceCounter.objects.filter(pk__in=[vieux.pk, autre.pk]).update(
            updated_at=timezone.now() - datetime.timedelta(hours=72))
        job = BackgroundJob.objects.create(
            company=self.company, user=self.user, kind='calepinage')
        self.assertEqual(tasks._livraison_de_trop(job), '')
        self.assertFalse(SequenceCounter.objects.filter(pk=vieux.pk).exists())
        self.assertTrue(SequenceCounter.objects.filter(pk=autre.pk).exists())

    def test_job_d_une_autre_societe_introuvable(self):
        job = BackgroundJob.objects.create(
            company=self.autre, user=self.user_autre, kind='calepinage')
        reponse = self.api.get(url_resultat(job.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        job = BackgroundJob.objects.create(
            company=self.company, user=self.user, kind='calepinage')
        reponse = self.api_sans.get(url_resultat(job.pk))
        self.assertEqual(reponse.status_code, 403)


class LivraisonSansBaseTest(SimpleTestCase):
    """Revue lot 6 (ACAL1963) — une erreur de base pendant le compte des
    livraisons est un échec DIT, jamais une exception qui laisse le job « en
    cours » à 5 % ; le compte au-delà de la borne dit l'interruption."""

    def _job(self):
        from types import SimpleNamespace

        return SimpleNamespace(pk=7, company=object(), company_id=3, created_at=None)

    def test_erreur_de_base_echec_dit(self):
        from django.db import DatabaseError

        from apps.calepinage import tasks

        with mock.patch('core.models.SequenceCounter.next',
                        side_effect=DatabaseError('hors ligne')):
            self.assertEqual(tasks._livraison_de_trop(self._job()),
                             tasks.MOTIF_COMPTE_INDISPONIBLE)

    def test_purge_en_echec_la_livraison_reste_acceptee(self):
        # Revue lot 6 — la purge a son propre try : son erreur est journalisée
        # et ne change jamais le verdict du compte (déjà incrémenté).
        from django.db import DatabaseError

        from apps.calepinage import tasks

        with mock.patch('core.models.SequenceCounter.next', side_effect=[1, 3]), \
                mock.patch('core.models.SequenceCounter.objects') as objets:
            objets.filter.return_value.delete.side_effect = DatabaseError('interblocage')
            self.assertEqual(tasks._livraison_de_trop(self._job()), '')
            self.assertEqual(tasks._livraison_de_trop(self._job()), tasks.MOTIF_INTERROMPU)

    def test_au_dela_de_la_borne_interrompu_sinon_rien(self):
        from apps.calepinage import tasks

        with mock.patch('core.models.SequenceCounter.next', side_effect=[1, 3]), \
                mock.patch('core.models.SequenceCounter.objects') as objets:
            self.assertEqual(tasks._livraison_de_trop(self._job()), '')
            self.assertEqual(tasks._livraison_de_trop(self._job()), tasks.MOTIF_INTERROMPU)
        filtre = objets.filter.call_args.kwargs
        self.assertEqual(filtre['cle__startswith'], tasks.PREFIXE_COMPTEUR_LIVRAISONS)
        self.assertEqual(filtre['company_id'], 3)
