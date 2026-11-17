"""Modèles de l'app `taches` (reference/donnees.md §2) : contraintes, managers, `__str__` neutre.

Deux familles : `StructureModelesTests` (sans base : lit les `Meta`) et `ContraintesEnBaseTests`
(base de test de la CI : prouve que Postgres refuse ce que la référence interdit).
"""
import datetime

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

NOM_MAX = 30


def _modeles():
    return list(apps.get_app_config('taches').get_models())


class StructureModelesTests(SimpleTestCase):
    def test_unicites_commencent_par_company(self):
        for modele in _modeles():
            for contrainte in modele._meta.constraints:
                if isinstance(contrainte, models.UniqueConstraint):
                    with self.subTest(contrainte=contrainte.name):
                        self.assertEqual(contrainte.fields[0], 'company')

    def test_unicites_des_modeles_a_suppression_douce_excluent_les_supprimes(self):
        for nom in ('Projet', 'Tache'):
            modele = apps.get_model('taches', nom)
            for contrainte in modele._meta.constraints:
                if isinstance(contrainte, models.UniqueConstraint):
                    with self.subTest(contrainte=contrainte.name):
                        self.assertIn(('is_deleted', False), contrainte.condition.children)

    def test_noms_prefixes_et_courts(self):
        for modele in _modeles():
            for objet in [*modele._meta.constraints, *modele._meta.indexes]:
                with self.subTest(nom=objet.name):
                    self.assertTrue(objet.name.startswith('taches_'))
                    self.assertLessEqual(len(objet.name), NOM_MAX)

    def test_cascade_vers_un_utilisateur_nomme_proprietaire(self):
        utilisateur = get_user_model()
        for modele in _modeles():
            for champ in modele._meta.get_fields():
                if getattr(champ, 'related_model', None) is utilisateur and champ.concrete \
                        and champ.remote_field.on_delete is models.CASCADE:
                    with self.subTest(champ=f'{modele.__name__}.{champ.name}'):
                        self.assertEqual(champ.name, 'proprietaire')

    def test_str_neutre(self):
        Projet = apps.get_model('taches', 'Projet')
        Tache = apps.get_model('taches', 'Tache')
        self.assertEqual(str(Projet(pk=7, nom='Secret')), 'projet #7')
        self.assertEqual(str(Tache(pk=3, titre='Appeler le notaire')), 'tâche #3')


class ContraintesEnBaseTests(TestCase):
    """Base requise : jouée par la CI."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = Company.objects.create(nom='Tâches A', slug='taches-modeles-a')
        cls.autre_societe = Company.objects.create(nom='Tâches B', slug='taches-modeles-b')
        utilisateurs = get_user_model().objects
        cls.compte = utilisateurs.create_user(username='taches_modeles_u1', password='x', company=cls.societe)
        cls.autre = utilisateurs.create_user(username='taches_modeles_u2', password='x', company=cls.autre_societe)

    def _projet(self, nom='Maison', compte=None, societe=None):
        Projet = apps.get_model('taches', 'Projet')
        return Projet.objects.create(
            company=societe or self.societe, proprietaire=compte or self.compte, nom=nom, couleur='terre')

    def _tache(self, **champs):
        Tache = apps.get_model('taches', 'Tache')
        return Tache.objects.create(company=self.societe, proprietaire=self.compte, titre='T', **champs)

    def test_nom_cle_calcule_par_save(self):
        projet = self._projet(nom='  Rénovation-Maison ')
        self.assertEqual(projet.nom_cle, 'renovationmaison')
        projet.nom = 'Été'
        projet.save(update_fields=['nom'])
        projet.refresh_from_db()
        self.assertEqual(projet.nom_cle, 'ete')

    def test_projet_unique_par_nom_cle_tant_qu_il_est_vivant(self):
        premier = self._projet(nom='Maison')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._projet(nom='MAISON')
        premier.soft_delete(self.compte, record=False)
        self.assertEqual(self._projet(nom='maison').nom_cle, 'maison')

    def test_meme_nom_permis_dans_une_autre_societe(self):
        self._projet(nom='Maison')
        self._projet(nom='Maison', compte=self.autre, societe=self.autre_societe)
        Projet = apps.get_model('taches', 'Projet')
        self.assertEqual(Projet.objects.filter(nom_cle='maison').count(), 2)

    def test_bulk_create_et_update_du_nom_refuses(self):
        Projet = apps.get_model('taches', 'Projet')
        Section = apps.get_model('taches', 'Section')
        Etiquette = apps.get_model('taches', 'Etiquette')
        projet = self._projet()
        for gestionnaire, objet in (
                (Projet.objects, Projet(company=self.societe, proprietaire=self.compte, nom='X')),
                (Projet.all_objects, Projet(company=self.societe, proprietaire=self.compte, nom='Y')),
                (Section.objects, Section(company=self.societe, projet=projet, nom='Étape')),
                (Etiquette.objects, Etiquette(company=self.societe, proprietaire=self.compte, nom='client'))):
            with self.subTest(modele=objet._meta.model_name):
                with self.assertRaises(TypeError):
                    gestionnaire.bulk_create([objet])
                with self.assertRaises(TypeError):
                    gestionnaire.all().update(nom='Autre')
        self.assertEqual(Projet.objects.filter(pk=projet.pk).update(rang=2048), 1)

    def test_suppression_douce_masque_le_projet(self):
        Projet = apps.get_model('taches', 'Projet')
        projet = self._projet()
        projet.soft_delete(self.compte, record=False)
        self.assertFalse(Projet.objects.filter(pk=projet.pk).exists())
        self.assertTrue(Projet.all_objects.filter(pk=projet.pk).exists())

    def test_section_et_etiquette_uniques_par_cle(self):
        Section = apps.get_model('taches', 'Section')
        Etiquette = apps.get_model('taches', 'Etiquette')
        projet = self._projet()
        Section.objects.create(company=self.societe, projet=projet, nom='Devis')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Section.objects.create(company=self.societe, projet=projet, nom='devis')
        Etiquette.objects.create(company=self.societe, proprietaire=self.compte, nom='Urgent')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Etiquette.objects.create(company=self.societe, proprietaire=self.compte, nom='urgent')

    def test_heure_sans_jour_refusee(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._tache(heure_debut=datetime.time(9, 0))
        self.assertIsNotNone(self._tache(heure_debut=datetime.time(9, 0), jour_prevu=datetime.date(2026, 11, 17)).pk)

    def test_heure_d_echeance_sans_echeance_refusee(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._tache(echeance_heure=datetime.time(18, 0))
        self.assertIsNotNone(
            self._tache(echeance_heure=datetime.time(18, 0), echeance=datetime.date(2026, 11, 20)).pk)

    def test_client_id_unique_parmi_les_vivantes(self):
        premiere = self._tache(client_id='c-1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._tache(client_id='c-1')
        premiere.soft_delete(self.compte, record=False)
        self.assertIsNotNone(self._tache(client_id='c-1').pk)

    def test_occurrence_unique_par_regle(self):
        RegleRecurrence = apps.get_model('taches', 'RegleRecurrence')
        regle = RegleRecurrence.objects.create(
            company=self.societe, proprietaire=self.compte, frequence='quotidien',
            date_debut=datetime.date(2026, 11, 17))
        jour = datetime.date(2026, 11, 18)
        self._tache(recurrence=regle, occurrence_du=jour)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._tache(recurrence=regle, occurrence_du=jour)

    def test_verrou_optimiste_avance_a_chaque_save(self):
        tache = self._tache()
        self.assertEqual(tache.lock_version, 0)
        tache.titre = 'U'
        tache.save(update_fields=['titre'])
        tache.refresh_from_db()
        self.assertEqual(tache.lock_version, 1)

    def test_revue_un_seul_projet_de_la_semaine(self):
        RevueProjet = apps.get_model('taches', 'RevueProjet')
        lundi = datetime.date(2026, 11, 16)
        commun = {'company': self.societe, 'proprietaire': self.compte, 'semaine': lundi, 'focus': True}
        RevueProjet.objects.create(projet=self._projet(nom='A'), **commun)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RevueProjet.objects.create(projet=self._projet(nom='B'), **commun)
