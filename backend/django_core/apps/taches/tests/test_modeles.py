"""Modèles de l'app `taches` (reference/donnees.md §2) : contraintes, managers, `__str__` neutre.

Deux familles : `StructureModelesTests` (sans base : lit les `Meta`) et `ContraintesEnBaseTests`
(base de test de la CI : prouve que Postgres refuse ce que la référence interdit).
"""
import datetime
import hashlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from apps.taches.tests import fabriques
from core.feature_flags import module_actif

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

    def test_vingt_et_un_modeles(self):
        self.assertEqual(len(_modeles()), 21)

    def test_defauts_json_appelables(self):
        for modele in _modeles():
            for champ in modele._meta.concrete_fields:
                if isinstance(champ, models.JSONField) and champ.has_default():
                    with self.subTest(champ=f'{modele.__name__}.{champ.name}'):
                        self.assertTrue(callable(champ.default))

    def test_familles_suggestions_par_defaut(self):
        ReglagesRythme = apps.get_model('taches', 'ReglagesRythme')
        un, deux = ReglagesRythme(), ReglagesRythme()
        self.assertEqual(un.familles_suggestions, ['devis_accepte', 'chantier_receptionne', 'chantier_annule'])
        un.familles_suggestions.append('visite_validee')
        self.assertEqual(len(deux.familles_suggestions), 3)

    def test_onze_cles_de_preference(self):
        Preference = apps.get_model('taches', 'Preference')
        self.assertEqual(len(Preference._meta.get_field('cle').choices), 11)

    def test_types_d_incitation_push_et_ecran(self):
        IncitationCoach = apps.get_model('taches', 'IncitationCoach')
        valeurs = [v for v, _ in IncitationCoach._meta.get_field('type').choices]
        self.assertEqual(len(valeurs), 11)
        self.assertIn('plan_matin', valeurs)
        self.assertIn('revelation', valeurs)

    def test_hote_seul_montre_de_l_agenda(self):
        from apps.taches.models.agenda import hote_de
        self.assertEqual(hote_de('https://Outlook.Office365.com/owa/calendar/x/reachcalendar.ics'),
                         'outlook.office365.com')
        self.assertEqual(hote_de('pas une adresse'), '')


class ContraintesEnBaseTests(TestCase):
    """Base requise : jouée par la CI."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.autre_societe = fabriques.societe('b')
        cls.compte = fabriques.compte(cls.societe, nom='u1')
        cls.autre = fabriques.compte(cls.autre_societe, nom='u2')

    def _projet(self, nom='Maison', compte=None):
        return fabriques.projet(compte or self.compte, nom=nom)

    def _tache(self, **champs):
        return fabriques.tache(self.compte, **champs)

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
        self._projet(nom='Maison', compte=self.autre)
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

    def test_un_plan_par_jour_et_une_cible_par_ligne(self):
        PlanJour = apps.get_model('taches', 'PlanJour')
        LignePlanJour = apps.get_model('taches', 'LignePlanJour')
        jour = datetime.date(2026, 11, 17)
        plan = PlanJour.objects.create(company=self.societe, proprietaire=self.compte, jour=jour)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanJour.objects.create(company=self.societe, proprietaire=self.compte, jour=jour)
        tache = self._tache()
        with self.assertRaises(IntegrityError), transaction.atomic():
            LignePlanJour.objects.create(
                company=self.societe, plan=plan, tache=tache, activite_id=4, prevue_au_plan=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LignePlanJour.objects.create(company=self.societe, plan=plan, prevue_au_plan=True)
        LignePlanJour.objects.create(company=self.societe, plan=plan, tache=tache, prevue_au_plan=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LignePlanJour.objects.create(company=self.societe, plan=plan, tache=tache, prevue_au_plan=False)

    def test_un_seul_reglage_de_rythme_et_de_preference_par_cle(self):
        ReglagesRythme = apps.get_model('taches', 'ReglagesRythme')
        Preference = apps.get_model('taches', 'Preference')
        reglages = ReglagesRythme.objects.create(company=self.societe, proprietaire=self.compte)
        reglages.refresh_from_db()
        self.assertEqual(reglages.mode, 'pousser')
        self.assertEqual(reglages.familles_suggestions, ['devis_accepte', 'chantier_receptionne', 'chantier_annule'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReglagesRythme.objects.create(company=self.societe, proprietaire=self.compte)
        Preference.objects.create(company=self.societe, proprietaire=self.compte, cle='heure_matin', valeur='08:30')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Preference.objects.create(company=self.societe, proprietaire=self.compte, cle='heure_matin', valeur='off')

    def test_un_jeton_actif_par_usage(self):
        JetonAcces = apps.get_model('taches', 'JetonAcces')
        commun = {'company': self.societe, 'proprietaire': self.compte, 'usage': 'flux', 'prefixe': 'tqf_ab12'}
        premier = JetonAcces.objects.create(jeton_hash='a' * 64, **commun)
        with self.assertRaises(IntegrityError), transaction.atomic():
            JetonAcces.objects.create(jeton_hash='b' * 64, **commun)
        premier.revoque_le = datetime.datetime(2026, 11, 17, tzinfo=datetime.timezone.utc)
        premier.save(update_fields=['revoque_le'])
        self.assertIsNotNone(JetonAcces.objects.create(jeton_hash='c' * 64, **commun).pk)

    def test_agenda_externe_unique_par_url_et_hote_calcule(self):
        AgendaExterne = apps.get_model('taches', 'AgendaExterne')
        url = 'https://agenda.example/a.ics'
        agenda = AgendaExterne.objects.create(company=self.societe, proprietaire=self.compte, url=url)
        self.assertEqual(agenda.hote, 'agenda.example')
        with self.assertRaises(IntegrityError), transaction.atomic():
            AgendaExterne.objects.create(company=self.societe, proprietaire=self.compte, url=url)
        agenda.url = 'https://calendar.example/b.ics'
        agenda.save(update_fields=['url'])
        agenda.refresh_from_db()
        self.assertEqual(agenda.hote, 'calendar.example')

    def test_un_coupe_circuit_par_societe(self):
        ReglagesSociete = apps.get_model('taches', 'ReglagesSociete')
        reglage = ReglagesSociete.objects.create(company=self.societe)
        self.assertTrue(reglage.balayage_actif)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReglagesSociete.objects.create(company=self.societe, balayage_actif=False)
        self.assertIsNotNone(ReglagesSociete.objects.create(company=self.autre_societe).pk)

    def test_suggestion_et_sollicitation_dedoublonnees(self):
        SuggestionTache = apps.get_model('taches', 'SuggestionTache')
        IncitationCoach = apps.get_model('taches', 'IncitationCoach')
        commun = {'company': self.societe, 'proprietaire': self.compte}
        SuggestionTache.objects.create(famille='devis_accepte', cle='devis_accepte:1', titre_propose='T', **commun)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SuggestionTache.objects.create(
                famille='devis_accepte', cle='devis_accepte:1', titre_propose='T', **commun)
        jour = datetime.date(2026, 11, 17)
        IncitationCoach.objects.create(jour=jour, type='plan_matin', canal='push', **commun)
        with self.assertRaises(IntegrityError), transaction.atomic():
            IncitationCoach.objects.create(jour=jour, type='plan_matin', canal='push', **commun)


class FabriquesPartageesTests(TestCase):
    """Les fabriques de `fabriques.py` rendent ce que leur contrat annonce (donnees.md §5)."""

    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')

    def test_deux_societes_distinctes_au_module_actif(self):
        self.assertNotEqual(self.a.pk, self.b.pk)
        self.assertTrue(module_actif(self.a, 'taches'))

    def test_comptes_et_droits(self):
        voit = fabriques.compte(self.a)
        aveugle = fabriques.compte(self.a, voir=False, nom='u2')
        admin = fabriques.compte(self.a, admin=True, nom='u3')
        meme_nom_ailleurs = fabriques.compte(self.b)
        self.assertTrue(voit.has_erp_permission('taches_voir'))
        self.assertFalse(voit.is_admin_role)
        self.assertFalse(aveugle.has_erp_permission('taches_voir'))
        self.assertIsNotNone(aveugle.role_id)
        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.has_erp_permission('taches_voir'))
        self.assertEqual(meme_nom_ailleurs.company_id, self.b.pk)
        self.assertTrue(voit.is_active)
        self.assertEqual(voit.portee, get_user_model().PORTEE_INTERNE)

    def test_projet_section_tache(self):
        compte = fabriques.compte(self.a)
        projet = fabriques.projet(compte)
        self.assertTrue(projet.nom.startswith('Projet '))
        self.assertEqual(projet.priorite, 0)
        self.assertEqual(fabriques.section(projet).company_id, self.a.pk)
        a_trier = fabriques.tache(compte)
        self.assertIsNone(a_trier.triee_le)
        premiere = fabriques.tache(compte, projet=projet)
        seconde = fabriques.tache(compte, projet=projet)
        self.assertIsNotNone(premiere.triee_le)
        self.assertEqual((premiere.rang_projet, seconde.rang_projet), (1024, 2048))
        self.assertEqual(a_trier.rang_projet, 1024)
        datee = fabriques.tache(compte, jour_prevu=datetime.date(2026, 11, 17))
        self.assertIsNotNone(datee.triee_le)

    def test_jeton_hache_et_prefixe(self):
        compte = fabriques.compte(self.a)
        objet, clair = fabriques.jeton(compte, 'capture')
        self.assertTrue(clair.startswith('tqc_'))
        self.assertEqual(objet.prefixe, clair[:8])
        self.assertEqual(objet.jeton_hash, hashlib.sha256(clair.encode('utf-8')).hexdigest())
        self.assertNotIn(clair, str(objet.__dict__))

    def test_reglages_plan_activite_agenda(self):
        compte = fabriques.compte(self.a)
        self.assertEqual(fabriques.reglages(compte, palier=5).palier, 5)
        jour = datetime.date(2026, 11, 17)
        self.assertEqual(fabriques.plan(compte, jour).jour, jour)
        activite = fabriques.activite(compte)
        self.assertEqual((activite.assigned_to_id, activite.done), (compte.pk, False))
        agenda = fabriques.agenda_externe(compte)
        self.assertEqual((agenda.url, agenda.hote), ('https://agenda.example/a.ics', 'agenda.example'))
