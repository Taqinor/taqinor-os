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
        with mock.patch('apps.ao.selectors.cout_calepinage',
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
        with mock.patch('apps.ao.selectors.calepinage_json',
                        return_value=dict(RESULTAT)):
            calculer_calepinage(job_id=job_id, entree=DOCUMENT)
        reponse = self.api.get(url_resultat(job_id))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], BackgroundJob.STATUT_DONE)
        self.assertEqual(reponse.data['resultat']['total_modules'], 12)

    def test_deux_executions_n_ecrivent_qu_un_resultat(self):
        from apps.calepinage.tasks import calculer_calepinage, cle_resultat

        job_id = self._lancer().data['job_id']
        with mock.patch('apps.ao.selectors.calepinage_json',
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
        from apps.ao.selectors import erreurs_moteur_calepinage
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

        with mock.patch('apps.ao.selectors.calepinage_json',
                        side_effect=calcul):
            calculer_calepinage(job_id=job.pk, entrees=[bon, mauvais])
        reponse = self.api.get(url_resultat(job.pk))
        elements = {e['repere']: e for e in reponse.data['elements']}
        self.assertEqual(elements['PAN-A']['statut'], 'done')
        self.assertEqual(elements['PAN-B']['statut'], 'failed')
        self.assertIn('Surface absente.', elements['PAN-B']['motif'])
        self.assertEqual(
            BackgroundJob.objects.filter(kind='calepinage').count(), 1)

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
