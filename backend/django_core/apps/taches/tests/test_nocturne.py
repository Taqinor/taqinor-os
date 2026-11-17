"""TCH37 — Nuit orchestrée : `nocturne.executer(company_id, jour)`.

Base requise (`TestCase` : chaque étape tourne dans sa transaction) : joué par la CI. Les étapes sont
livrées vides (remplies par TCH58, TCH70, TCH75) : les tests d'ordre et de panne remplacent une étape
par une fonction de test ; le rejeu passe par les VRAIES étapes.
"""
import datetime
from unittest import mock

from django.test import TestCase

from apps.taches import nocturne, sweeps
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.presence import ReglagesSociete
from apps.taches.models.taches import Tache
from apps.taches.services import erp, journee, purge, rythme
from apps.taches.services.gestes import enregistrer_geste
from apps.taches.tests import fabriques
from authentication.models import Company
from core.models import ModuleToggle

JOUR = datetime.date(2026, 11, 18)
ORDRE = ['clore_jour_precedent', 'etapes_nocturnes', 'reverifier_liens', 'purger']


class NocturneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.a, nom='u1')

    def _remplacer(self, remplacements):
        """Remplace des étapes par des fonctions de test (nom → fonction)."""
        modules = {'clore_jour_precedent': journee, 'etapes_nocturnes': rythme,
                   'reverifier_liens': erp, 'purger': purge}
        for nom, fonction in remplacements.items():
            patcher = mock.patch.object(modules[nom], nom, side_effect=fonction)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ordre_des_etapes_et_arguments(self):
        appels = []
        self._remplacer({nom: (lambda n: lambda c, j: appels.append((n, c, j)))(nom) for nom in ORDRE})
        rendu = nocturne.executer(self.a.pk, JOUR)
        self.assertEqual(appels, [(nom, self.a.pk, JOUR) for nom in ORDRE])
        self.assertEqual(list(rendu.items()), [(nom, True) for nom in ORDRE])

    def test_une_etape_qui_leve_n_arrete_pas_les_suivantes(self):
        appels = []

        def en_panne(company_id, jour):
            raise RuntimeError('panne')
        remplacements = {nom: (lambda n: lambda c, j: appels.append(n))(nom) for nom in ORDRE}
        remplacements['etapes_nocturnes'] = en_panne
        self._remplacer(remplacements)
        with self.assertLogs('apps.taches.nocturne', level='ERROR'):
            rendu = nocturne.executer(self.a.pk, JOUR)
        self.assertEqual(appels, ['clore_jour_precedent', 'reverifier_liens', 'purger'])
        self.assertEqual(rendu, {'clore_jour_precedent': True, 'etapes_nocturnes': False,
                                 'reverifier_liens': True, 'purger': True})

    def test_l_ecriture_d_une_etape_en_panne_est_defaite_seule(self):
        def ecrit_puis_leve(company_id, jour):
            enregistrer_geste(self.u1, 'rythme', 'défait', [])
            raise RuntimeError('panne')

        def ecrit(company_id, jour):
            enregistrer_geste(self.u1, 'rythme', 'gardé', [])
        self._remplacer({'clore_jour_precedent': ecrit_puis_leve, 'purger': ecrit})
        with self.assertLogs('apps.taches.nocturne', level='ERROR'):
            nocturne.executer(self.a.pk, JOUR)
        self.assertEqual(list(GesteAnnulable.objects.values_list('message', flat=True)), ['gardé'])

    def test_rejeu_idempotent_avec_les_vraies_etapes(self):
        tache = fabriques.tache(self.u1, jour_prevu=JOUR)
        premier = nocturne.executer(self.a.pk, JOUR)
        etat = list(Tache.objects.values_list('pk', 'lock_version', 'jour_prevu', 'reports'))
        second = nocturne.executer(self.a.pk, JOUR)
        self.assertEqual(premier, second)
        self.assertEqual(premier, {nom: True for nom in ORDRE})
        self.assertEqual(list(Tache.objects.values_list('pk', 'lock_version', 'jour_prevu', 'reports')), etat)
        self.assertEqual(etat, [(tache.pk, 0, JOUR, 0)])


class TachePlanifieeNocturneTests(TestCase):
    """TCH99 — `taches.nocturne` (sweeps.py) : sociétés actives, module actif, coupe-circuit respecté."""

    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b, cls.c, cls.d = (fabriques.societe(slug) for slug in ('a', 'b', 'c', 'd'))
        ReglagesSociete.objects.create(company=cls.b, balayage_actif=False)
        ModuleToggle.objects.create(company=cls.c, module='taches', actif=False)
        Company.objects.filter(pk=cls.d.pk).update(actif=False)

    def test_seules_les_societes_balayables(self):
        ids = sweeps.societes_a_balayer()
        self.assertIn(self.a.pk, ids)
        for exclue in (self.b, self.c, self.d):
            with self.subTest(societe=exclue.slug):
                self.assertNotIn(exclue.pk, ids)

    def test_une_nuit_par_societe_balayable_au_jour_local(self):
        with mock.patch('apps.taches.sweeps.timezone.localdate', return_value=JOUR), \
                mock.patch.object(nocturne, 'executer') as executer:
            rendu = sweeps.nocturne_quotidienne()
        appels = [c.args for c in executer.call_args_list]
        self.assertIn((self.a.pk, JOUR), appels)
        self.assertFalse({self.b.pk, self.c.pk, self.d.pk} & {company_id for company_id, _jour in appels})
        self.assertEqual(rendu, {'societes': len(appels), 'jour': JOUR.isoformat()})

    def test_planifiee_a_3_h_sur_la_file_scheduled(self):
        from django.conf import settings

        from erp_agentique.celery import app
        entree = app.conf.beat_schedule['taches-nocturne']
        self.assertEqual(entree['task'], 'taches.nocturne')
        self.assertEqual((entree['schedule'].hour, entree['schedule'].minute), ({3}, {0}))
        self.assertEqual(entree['options'], {'expires': 3600})
        self.assertEqual(settings.CELERY_TASK_ROUTES['taches.nocturne'], {'queue': 'scheduled'})
