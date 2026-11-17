"""TCH37 — Nuit orchestrée : `nocturne.executer(company_id, jour)`.

Base requise (`TestCase` : chaque étape tourne dans sa transaction) : joué par la CI. Les étapes sont
livrées vides (remplies par TCH58, TCH70, TCH75) : les tests d'ordre et de panne remplacent une étape
par une fonction de test ; le rejeu passe par les VRAIES étapes.
"""
import datetime
from unittest import mock

from django.test import TestCase

from apps.taches import nocturne
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.taches import Tache
from apps.taches.services import erp, journee, purge, rythme
from apps.taches.services.gestes import enregistrer_geste
from apps.taches.tests import fabriques

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
