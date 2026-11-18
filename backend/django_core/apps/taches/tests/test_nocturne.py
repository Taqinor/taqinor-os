"""TCH37 — Nuit orchestrée : `nocturne.executer(company_id, jour)`.

Base requise (`TestCase` : chaque étape tourne dans sa transaction) : joué par la CI. Les étapes sont
livrées vides (remplies par TCH58, TCH70, TCH75) : les tests d'ordre et de panne remplacent une étape
par une fonction de test ; le rejeu passe par les VRAIES étapes.
"""
import datetime
from unittest import mock

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.notifications.models import Notification
from apps.records.models import Activity
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

    def test_un_compte_en_echec_n_arrete_pas_les_autres(self):
        """Revue F2 #2 : l'exception d'UN compte (clôture de la veille, rythme) est isolée dans son
        savepoint ; les autres comptes de la société sont traités, le journal ne porte que l'id."""
        from apps.taches.models.journee import PlanJour
        u2 = fabriques.compte(self.a, nom='u2')
        for compte in (self.u1, u2):
            fabriques.reglages(compte)
        vrai_clore, vraie_nuit, vus = journee._clore_pour, rythme._nuit_du_compte, []

        def clore(user, hier):
            if user.pk == self.u1.pk:
                raise RuntimeError('panne')
            return vrai_clore(user, hier)

        def nuit(reglages, jour):
            if reglages.proprietaire_id == self.u1.pk:
                raise RuntimeError('panne')
            vus.append(reglages.proprietaire_id)
            return vraie_nuit(reglages, jour)
        with mock.patch.object(journee, '_clore_pour', side_effect=clore), \
                mock.patch.object(rythme, '_nuit_du_compte', side_effect=nuit), \
                self.assertLogs('apps.taches.services', level='ERROR') as journal:
            rendu = nocturne.executer(self.a.pk, JOUR)
        self.assertTrue(rendu['clore_jour_precedent'] and rendu['etapes_nocturnes'])
        hier = JOUR - datetime.timedelta(days=1)
        self.assertTrue(PlanJour.objects.filter(proprietaire=u2, jour=hier).exists())
        self.assertFalse(PlanJour.objects.filter(proprietaire=self.u1, jour=hier).exists())
        self.assertEqual(vus, [u2.pk])
        self.assertEqual(len(journal.output), 2)
        self.assertTrue(all(f'compte {self.u1.pk} (RuntimeError)' in ligne for ligne in journal.output))

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
    """TCH99 — `taches.nocturne` (sweeps.py) : sociétés actives, module actif ; le coupe-circuit ne coupe
    que l'ENVOI (`societes_a_balayer`, `taches.balayer`), jamais la nuit (décision de la fusion 2)."""

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

    def test_une_nuit_par_societe_du_module_au_jour_local(self):
        with mock.patch('apps.taches.sweeps.timezone.localdate', return_value=JOUR), \
                mock.patch.object(nocturne, 'executer') as executer:
            rendu = sweeps.nocturne_quotidienne()
        appels = [c.args for c in executer.call_args_list]
        self.assertIn((self.a.pk, JOUR), appels)
        self.assertIn((self.b.pk, JOUR), appels)  # coupe-circuit : la nuit tourne quand même
        self.assertFalse({self.c.pk, self.d.pk} & {company_id for company_id, _jour in appels})
        self.assertEqual(rendu, {'societes': len(appels), 'jour': JOUR.isoformat()})

    def test_coupe_circuit_la_cloture_d_hier_tourne_quand_meme(self):
        from apps.taches.models.journee import PlanJour
        compte = fabriques.compte(self.b, nom='u1')
        fabriques.reglages(compte)
        with mock.patch('apps.taches.sweeps.timezone.localdate', return_value=JOUR):
            sweeps.nocturne_quotidienne()
        hier = PlanJour.objects.get(company=self.b, proprietaire=compte, jour=JOUR - datetime.timedelta(days=1))
        self.assertNotEqual(hier.statut_jour, '')
        self.assertFalse(PlanJour.objects.filter(company__in=[self.c, self.d]).exists())

    def test_planifiee_a_3_h_sur_la_file_scheduled(self):
        from django.conf import settings

        from erp_agentique.celery import app
        entree = app.conf.beat_schedule['taches-nocturne']
        self.assertEqual(entree['task'], 'taches.nocturne')
        self.assertEqual((entree['schedule'].hour, entree['schedule'].minute), ({3}, {0}))
        self.assertEqual(entree['options'], {'expires': 3600})
        self.assertEqual(settings.CELERY_TASK_ROUTES['taches.nocturne'], {'queue': 'scheduled'})


def _lignes_taches(**filtre_proprietaire):
    """Nombre de lignes de CHAQUE modèle de l'app `taches` (corbeille comprise) → `{modèle: n}`. Avec
    `proprietaire__in=[…]`, seuls les modèles qui portent un `proprietaire` sont comptés, filtrés dessus."""
    comptes = {}
    for modele in apps.get_app_config('taches').get_models():
        lignes = modele._base_manager.all()
        if filtre_proprietaire:
            if 'proprietaire' not in {champ.name for champ in modele._meta.get_fields()}:
                continue
            lignes = lignes.filter(**filtre_proprietaire)
        comptes[modele.__name__] = lignes.count()
    return comptes


class NuitSansEffetPourUnCompteInactifTests(TestCase):
    """F2 — la nuit ne parcourt que les comptes qui ont des données Tâches (`ReglagesRythme`) : un compte
    qui n'a jamais ouvert le module n'a aucune ligne créée, et le coût ne dépend pas de la taille de la
    société."""

    def test_les_comptes_sans_donnees_n_ont_aucune_ligne(self):
        societe = fabriques.societe('nuit1')
        actif = fabriques.compte(societe, nom='actif')
        inactifs = [fabriques.compte(societe, nom='vide1'), fabriques.compte(societe, nom='vide2')]
        fabriques.reglages(actif)
        fabriques.tache(actif, jour_prevu=JOUR)
        notifications = Notification.objects.count()
        activites = Activity.objects.count()
        nocturne.executer(societe.pk, JOUR)
        self.assertEqual(sum(_lignes_taches(proprietaire__in=inactifs).values()), 0)
        self.assertEqual(Notification.objects.count(), notifications)
        self.assertEqual(Activity.objects.count(), activites)

    def _requetes(self, slug, comptes):
        societe = fabriques.societe(slug)
        for numero in range(comptes):
            fabriques.compte(societe, nom=f'u{numero}')
        avant = _lignes_taches()
        notifications = Notification.objects.count()
        activites = Activity.objects.count()
        with CaptureQueriesContext(connection) as requetes:
            nocturne.executer(societe.pk, JOUR)
        self.assertEqual(_lignes_taches(), avant)
        self.assertEqual(sum(avant.values()), 0)
        self.assertEqual(Notification.objects.count(), notifications)
        self.assertEqual(Activity.objects.count(), activites)
        return len(requetes)

    def test_societe_sans_donnee_n_ecrit_rien_et_coute_la_meme_chose_quelle_que_soit_sa_taille(self):
        petite = self._requetes('nuit2', 3)
        grande = self._requetes('nuit3', 30)
        self.assertEqual(petite, grande)

    def test_comptes_jamais_utilises_ou_sans_reglages_ne_creent_aucune_ligne_dans_aucune_table(self):
        """Garde avant activation : ni compte vierge, ni compte qui n'a que des tâches (pas de
        `ReglagesRythme`) ne fait écrire la nuit : aucune table de l'app, aucune notification."""
        societe = fabriques.societe('nuit4')
        fabriques.compte(societe, nom='vierge')
        seulement_taches = fabriques.compte(societe, nom='taches')
        fabriques.tache(seulement_taches, jour_prevu=JOUR - datetime.timedelta(days=1))
        fabriques.tache(seulement_taches, jour_prevu=JOUR)
        avant = _lignes_taches()
        notifications = Notification.objects.count()
        activites = Activity.objects.count()
        nocturne.executer(societe.pk, JOUR)
        nocturne.executer(societe.pk, JOUR)
        self.assertEqual(_lignes_taches(), avant)
        self.assertEqual(Notification.objects.count(), notifications)
        self.assertEqual(Activity.objects.count(), activites)
