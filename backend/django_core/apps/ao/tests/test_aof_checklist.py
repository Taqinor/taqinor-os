"""AOF136 — checklist partenaire : un OBJET SUIVI, pas un document mort.

Ce qui est prouvé ici :

* les SEPT blocs réels existent en base, avec leurs points ;
* **le dépôt est BLOQUÉ tant qu'une case obligatoire est ouverte** ;
* l'état est consultable et éditable par l'API ;
* chaque ligne TRACE son responsable, posé côté serveur ;
* l'initialisation est idempotente et n'écrase jamais un point déjà pointé.

Run :
    python manage.py test apps.ao.tests.test_aof_checklist -v2
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, DossierAO, LigneChecklistPartenaire, PieceDossierAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/checklist-partenaire/'
URL_DOSSIER = '/api/django/ao/dossiers-ao/'


class TestLesSeptBlocs(SimpleTestCase):
    def test_les_sept_blocs_de_la_checklist_reelle(self):
        blocs = {b for b, _, _ in services.CHECKLIST_PARTENAIRE}
        self.assertEqual(blocs, {
            'cps', 'acte_engagement', 'bordereau', 'lettre_soumission',
            'memoire', 'administratif', 'verifications'})

    def test_les_points_sensibles_sont_nommes(self):
        libelles = ' | '.join(
            libelle for _, _, libelle in services.CHECKLIST_PARTENAIRE)
        for attendu in ('lu et accepté', 'CHAQUE page',
                        'NE MODIFIER AUCUN PRIX NI AUCUNE QUANTITÉ',
                        'clause de réserve', "moins d'un an",
                        'moins de trois mois', 'modèle J',
                        'décennale étanchéité', 'Caution provisoire',
                        'PAR ÉCRIT', 'visite des lieux',
                        'Plis séparés ou pli unique'):
            self.assertIn(attendu, libelles, attendu)

    def test_les_codes_sont_uniques(self):
        codes = [code for _, code, _ in services.CHECKLIST_PARTENAIRE]
        self.assertEqual(len(codes), len(set(codes)))


class BaseChecklist(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF136 Co',
                                              slug='aof136-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-136-1', objet='Checklist')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)
        self.user = User.objects.create_user(
            username='aof136_user', password='x', company=self.company)


class TestSeedIdempotent(BaseChecklist):
    def test_l_initialisation_cree_tous_les_points(self):
        crees, existants = services.seeder_checklist_partenaire(self.dossier)
        self.assertEqual(crees, len(services.CHECKLIST_PARTENAIRE))
        self.assertEqual(existants, 0)
        self.assertEqual(self.dossier.lignes_checklist.count(),
                         len(services.CHECKLIST_PARTENAIRE))

    def test_rejouer_ne_duplique_rien(self):
        services.seeder_checklist_partenaire(self.dossier)
        crees, existants = services.seeder_checklist_partenaire(self.dossier)
        self.assertEqual(crees, 0)
        self.assertEqual(existants, len(services.CHECKLIST_PARTENAIRE))

    def test_rejouer_n_efface_pas_un_point_deja_pointe(self):
        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.get(code='CPS_PARAPHE')
        services.pointer_checklist(
            ligne, responsable=self.user, commentaire='Paraphé le 12/07',
            user=self.user)
        services.seeder_checklist_partenaire(self.dossier)
        ligne.refresh_from_db()
        self.assertTrue(ligne.faite)
        self.assertEqual(ligne.commentaire, 'Paraphé le 12/07')


class TestPorteDeDepot(BaseChecklist):
    def _amener_au_controle(self):
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.EN_CONSTITUTION)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.CONTROLE)

    def _piece_presente(self):
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='00',
            libelle='Checklist', presente=True)

    def test_une_case_obligatoire_ouverte_bloque_le_depot(self):
        self._piece_presente()
        services.seeder_checklist_partenaire(self.dossier)
        self._amener_au_controle()
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        message = ' '.join(ctx.exception.message_dict['statut'])
        self.assertIn('checklist partenaire', message)
        self.assertIn('CPS', message)

    def test_tout_pointe_ouvre_la_porte(self):
        self._piece_presente()
        services.seeder_checklist_partenaire(self.dossier)
        for ligne in self.dossier.lignes_checklist.all():
            services.pointer_checklist(ligne, user=self.user)
        self._amener_au_controle()
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierAO.Statut.PRET_A_DEPOSER)

    def test_un_point_facultatif_ouvert_ne_bloque_pas(self):
        self._piece_presente()
        LigneChecklistPartenaire.objects.create(
            company=self.company, dossier=self.dossier,
            bloc=LigneChecklistPartenaire.Bloc.VERIFICATIONS,
            code='OPTION', libelle='Point facultatif', obligatoire=False)
        self._amener_au_controle()
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierAO.Statut.PRET_A_DEPOSER)

    def test_un_dossier_sans_checklist_n_est_pas_bloque_par_elle(self):
        self._piece_presente()
        self._amener_au_controle()
        self.assertEqual(self.dossier.raisons_de_non_depot(), [])

    def test_depointer_referme_la_porte(self):
        services.seeder_checklist_partenaire(self.dossier)
        for ligne in self.dossier.lignes_checklist.all():
            services.pointer_checklist(ligne, user=self.user)
        ligne = self.dossier.lignes_checklist.get(code='ADM_CNSS')
        services.pointer_checklist(ligne, faite=False, user=self.user)
        self.assertTrue(self.dossier.raisons_de_non_depot())


class TestResponsableTrace(BaseChecklist):
    def test_le_responsable_est_pose_a_defaut_par_l_auteur(self):
        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.get(code='ADM_RIB')
        services.pointer_checklist(ligne, user=self.user)
        ligne.refresh_from_db()
        self.assertEqual(ligne.responsable_id, self.user.id)
        self.assertIsNotNone(ligne.date_faite)

    def test_un_responsable_explicite_prime(self):
        autre = User.objects.create_user(
            username='aof136_autre', password='x', company=self.company)
        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.get(code='ADM_RC')
        services.pointer_checklist(
            ligne, responsable=autre, user=self.user)
        ligne.refresh_from_db()
        self.assertEqual(ligne.responsable_id, autre.id)

    def test_depointer_efface_la_date(self):
        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.get(code='ADM_RC')
        services.pointer_checklist(ligne, user=self.user)
        services.pointer_checklist(ligne, faite=False, user=self.user)
        ligne.refresh_from_db()
        self.assertIsNone(ligne.date_faite)

    def test_le_pointage_ecrit_au_chatter_generique(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.first()
        services.pointer_checklist(ligne, user=self.user)
        ct = ContentType.objects.get_for_model(DossierAO)
        self.assertTrue(Activity.objects.filter(
            content_type=ct, object_id=self.dossier.pk,
            field='checklist').exists())


class TestApiChecklist(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF136 API',
                                              slug='aof136-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof136_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-136-API', objet='API')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def test_initialiser_puis_lister(self):
        r = self.api.post(
            f'{URL_DOSSIER}{self.dossier.id}/initialiser-checklist/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['crees'],
                         len(services.CHECKLIST_PARTENAIRE))
        r = self.api.get(URL, {'dossier': self.dossier.id, 'bloc': 'cps'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 3)

    def test_pointer_par_l_api_trace_l_utilisateur(self):
        services.seeder_checklist_partenaire(self.dossier)
        ligne = self.dossier.lignes_checklist.get(code='ACTE_RIB')
        r = self.api.post(f'{URL}{ligne.id}/pointer/',
                          {'commentaire': 'RIB vérifié'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['faite'])
        self.assertEqual(r.data['responsable'], self.user.id)
        self.assertEqual(r.data['commentaire'], 'RIB vérifié')

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF136 X', slug='aof136-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-136-X', objet='X')
        dossier = services.creer_dossier_ao(autre, ao)
        services.seeder_checklist_partenaire(dossier)
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])
