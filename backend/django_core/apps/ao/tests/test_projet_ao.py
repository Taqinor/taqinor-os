"""AOF12 — le PROJET d'appel d'offres au complet (champs additifs).

Ce que la fiche AO doit savoir dire : qui est le maître d'ouvrage (≠ l'acheteur
qui publie), sous quelle raison sociale le dossier est déposé (le dépôt peut se
faire sous une autre entité, cas réel), où est le site, par quel mode de
passation, sous quelle référence de CPS, à quelles dates (ouverture des plis,
validité 75 j, délai d'exécution), en combien d'exemplaires, pour quel
engagement global en modules et pour quels montants d'offre HT/TTC.

**Invariant de confidentialité (le plus important de ce test) :** AUCUN champ
de coût, de marge ou de bénéfice n'existe sur ``AppelOffre``. L'économie de
l'AO vit dans des tables SÉPARÉES derrière ``ao_rentabilite_voir`` ; déposer un
coût de revient ici l'exposerait à quiconque peut lire un AO. Le test
d'introspection ci-dessous échoue si un tel champ apparaît un jour.

Run :
    python manage.py test apps.ao.tests.test_projet_ao -v2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/appels-offres/'

#: Fragments de nom qui trahissent une donnée d'ÉCONOMIE (coût/marge/achat).
#: ``montant_offre_*``/``montant_estime``/``caution_*`` sont des montants
#: d'OFFRE, remis au maître d'ouvrage : ils ne sont pas concernés.
FRAGMENTS_INTERDITS = (
    'cout', 'coût', 'marge', 'benefice', 'bénéfice', 'prix_achat',
    'prix_revient', 'revient', 'rentabilite', 'rentabilité', 'achat',
)

CHAMPS_ATTENDUS = (
    'maitre_ouvrage', 'soumissionnaire', 'groupement', 'groupement_membres',
    'site_adresse', 'site_gps_lat', 'site_gps_lng', 'mode_passation',
    'reference_cps', 'date_ouverture_plis', 'validite_offre_jours',
    'delai_execution_jours', 'nombre_exemplaires', 'engagement_modules',
    'montant_offre_ht', 'montant_offre_ttc',
)


class TestChampsProjet(SimpleTestCase):
    def test_tous_les_champs_du_projet_existent(self):
        noms = {f.name for f in AppelOffre._meta.get_fields()}
        for champ in CHAMPS_ATTENDUS:
            self.assertIn(champ, noms, champ)

    def test_defauts_metier(self):
        self.assertEqual(
            AppelOffre._meta.get_field('validite_offre_jours').default, 75)
        self.assertEqual(
            AppelOffre._meta.get_field('nombre_exemplaires').default, 2)

    def test_maitre_ouvrage_et_acheteur_sont_deux_champs(self):
        noms = {f.name for f in AppelOffre._meta.get_fields()}
        self.assertIn('acheteur', noms)
        self.assertIn('maitre_ouvrage', noms)

    def test_aucun_champ_de_cout_ni_de_marge_sur_le_modele(self):
        """Introspection : l'économie ne doit JAMAIS atterrir sur ce modèle.

        On inspecte les champs LOCAUX (colonnes réelles de la table), pas les
        accesseurs inverses : une table d'économie SÉPARÉE a le droit de
        pointer vers l'AO — c'est même l'architecture voulue.
        """
        fautifs = []
        for champ in list(AppelOffre._meta.local_fields) + list(
                AppelOffre._meta.local_many_to_many):
            nom = champ.name.lower()
            for fragment in FRAGMENTS_INTERDITS:
                if fragment in nom:
                    fautifs.append(champ.name)
                    break
        self.assertEqual(
            fautifs, [],
            "L'économie d'un AO (coût de revient, marge, bénéfice) vit dans "
            "des tables SÉPARÉES gardées par ao_rentabilite_voir — jamais sur "
            f"AppelOffre. Champs fautifs : {fautifs}")

    def test_le_serializer_n_expose_aucun_cout(self):
        from apps.ao.serializers import AppelOffreSerializer
        for nom in AppelOffreSerializer().get_fields():
            for fragment in FRAGMENTS_INTERDITS:
                self.assertNotIn(fragment, nom.lower(), nom)


class TestValiditeDerivee(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF12 Co', slug='aof12-co')

    def _ao(self, **kwargs):
        return AppelOffre.objects.create(
            company=self.company, reference=kwargs.pop('reference', 'AO-12-1'),
            objet='Projet', **kwargs)

    def test_fin_de_validite_court_depuis_l_ouverture_des_plis(self):
        ao = self._ao(date_ouverture_plis=datetime.date(2026, 3, 10))
        self.assertEqual(
            ao.date_fin_validite_offre, datetime.date(2026, 5, 24))

    def test_repli_sur_la_date_limite(self):
        ao = self._ao(reference='AO-12-2',
                      date_limite=datetime.date(2026, 3, 10))
        self.assertEqual(
            ao.date_fin_validite_offre, datetime.date(2026, 5, 24))

    def test_aucune_date_inventee_sans_base(self):
        self.assertIsNone(self._ao(reference='AO-12-3').date_fin_validite_offre)


class TestApiProjet(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF12 API', slug='aof12-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof12_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_creation_avec_le_projet_complet(self):
        r = self.api.post(URL, {
            'objet': 'Centrale PV sur toitures — lot 2',
            'acheteur': 'Direction régionale',
            'maitre_ouvrage': 'Établissement scolaire',
            'soumissionnaire': 'Entité déposante SARL',
            'groupement': True,
            'groupement_membres': 'Entité A\nEntité B',
            'site_adresse': 'Route de Marrakech, Benguerir',
            'site_gps_lat': '32.236000',
            'site_gps_lng': '-7.951000',
            'mode_passation': 'appel_ouvert',
            'reference_cps': 'CPS-2026-77',
            'date_ouverture_plis': '2026-03-10',
            'delai_execution_jours': 120,
            'engagement_modules': 618,
            'montant_offre_ht': '4200000.00',
            'montant_offre_ttc': '5040000.00',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['maitre_ouvrage'], 'Établissement scolaire')
        self.assertEqual(r.data['nombre_exemplaires'], 2)
        self.assertEqual(r.data['validite_offre_jours'], 75)
        self.assertEqual(r.data['date_fin_validite_offre'], '2026-05-24')
        self.assertEqual(r.data['mode_passation_display'],
                         "Appel d'offres ouvert")

    def test_filtre_par_mode_de_passation(self):
        AppelOffre.objects.create(
            company=self.company, reference='AO-12-A', objet='Ouvert',
            mode_passation=AppelOffre.ModePassation.APPEL_OUVERT)
        AppelOffre.objects.create(
            company=self.company, reference='AO-12-B', objet='Concours',
            mode_passation=AppelOffre.ModePassation.CONCOURS)
        r = self.api.get(URL, {'mode_passation': 'concours'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual([x['reference'] for x in lignes], ['AO-12-B'])

    def test_filtre_par_statut(self):
        AppelOffre.objects.create(
            company=self.company, reference='AO-12-C', objet='Identifié')
        AppelOffre.objects.create(
            company=self.company, reference='AO-12-D', objet='Déposé',
            statut=AppelOffre.Statut.DEPOSE)
        r = self.api.get(URL, {'statut': 'depose'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual([x['reference'] for x in lignes], ['AO-12-D'])

    def test_gps_hors_bornes_refuse(self):
        r = self.api.post(URL, {
            'objet': 'Hors bornes', 'site_gps_lat': '120.000000',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('site_gps_lat', r.data)
