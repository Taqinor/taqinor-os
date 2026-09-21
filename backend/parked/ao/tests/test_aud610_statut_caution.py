"""AUD610 — le statut d'une caution de soumission n'est plus un champ libre.

Une caution de soumission porte de l'argent RÉELLEMENT engagé : « appelée »
signifie que la banque a DÉJÀ débité le montant. Tant que ``statut`` était
PATCHable, la machine d'états n'était qu'un affichage — un retour
``appelée → constituée`` effaçait la trace d'un débit réel, sans transition,
sans journal, sans que rien ne le dise.

Run :
    python manage.py test apps.ao.tests.test_aud610_statut_caution -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, CautionSoumission
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.records.models import Activity
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ao/cautions-soumission/'


class BaseCaution(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD610 Co',
                                              slug='aud610-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-610-1', objet='Caution')
        self.caution = CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            montant=Decimal('50000.00'), banque='Attijariwafa')
        role = Role.objects.create(company=self.company, nom='AUD610 gestion',
                                   permissions=[AO_VOIR, AO_GERER])
        self.user = User.objects.create_user(
            username='aud610', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, suffixe=''):
        return f'{BASE}{self.caution.pk}/{suffixe}'


class TestStatutNonPatchable(BaseCaution):
    def test_un_patch_de_statut_ne_change_rien(self):
        reponse = self.api.patch(
            self._url(), {'statut': CautionSoumission.Statut.APPELEE},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.caution.refresh_from_db()
        self.assertEqual(self.caution.statut,
                         CautionSoumission.Statut.CONSTITUEE)

    def test_le_champ_est_declare_lecture_seule(self):
        from apps.ao.serializers import CautionSoumissionSerializer

        champ = CautionSoumissionSerializer().fields['statut']
        self.assertTrue(champ.read_only)

    def test_le_retour_en_arriere_hors_graphe_est_refuse(self):
        """APPELÉE → CONSTITUÉE effacerait la trace d'un débit bancaire réel."""
        services.changer_statut_caution(
            self.caution, CautionSoumission.Statut.APPELEE, user=self.user)
        reponse = self.api.post(
            self._url('changer-statut/'),
            {'statut': CautionSoumission.Statut.CONSTITUEE}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.caution.refresh_from_db()
        self.assertEqual(self.caution.statut,
                         CautionSoumission.Statut.APPELEE)


class TestActionDediee(BaseCaution):
    def test_une_transition_du_graphe_passe(self):
        reponse = self.api.post(
            self._url('changer-statut/'),
            {'statut': CautionSoumission.Statut.APPELEE,
             'motif': 'Appel de la garantie par le maître d\'ouvrage'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.caution.refresh_from_db()
        self.assertEqual(self.caution.statut,
                         CautionSoumission.Statut.APPELEE)

    def test_la_transition_est_journalisee_au_chatter(self):
        self.api.post(
            self._url('changer-statut/'),
            {'statut': CautionSoumission.Statut.RESTITUEE}, format='json')
        activites = Activity.objects.filter(field='statut')
        self.assertEqual(activites.count(), 1, list(activites))
        self.assertEqual(activites.first().new_value, 'Restituée')

    def test_un_statut_inconnu_est_refuse(self):
        reponse = self.api.post(
            self._url('changer-statut/'), {'statut': 'emise'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_la_caution_d_une_autre_societe_est_invisible(self):
        voisine = Company.objects.create(nom='AUD610 Voisine',
                                         slug='aud610-voisine')
        ao_voisin = AppelOffre.objects.create(
            company=voisine, reference='AO-610-V', objet='Voisin')
        caution_voisine = CautionSoumission.objects.create(
            company=voisine, appel_offre=ao_voisin,
            montant=Decimal('10000.00'))
        reponse = self.api.post(
            f'{BASE}{caution_voisine.pk}/changer-statut/',
            {'statut': CautionSoumission.Statut.APPELEE}, format='json')
        self.assertEqual(reponse.status_code, 404)


class TestGrapheDeclaratif(BaseCaution):
    def test_les_deux_issues_sont_terminales(self):
        for terminal in (CautionSoumission.Statut.RESTITUEE,
                         CautionSoumission.Statut.APPELEE):
            with self.subTest(statut=terminal):
                self.assertEqual(
                    CautionSoumission.TRANSITIONS[terminal], ())

    def test_le_service_refuse_un_saut_hors_graphe(self):
        services.changer_statut_caution(
            self.caution, CautionSoumission.Statut.RESTITUEE, user=self.user)
        with self.assertRaises(ValidationError):
            services.changer_statut_caution(
                self.caution, CautionSoumission.Statut.APPELEE,
                user=self.user)

    def test_reposer_le_meme_statut_est_sans_effet(self):
        avant = Activity.objects.count()
        services.changer_statut_caution(
            self.caution, CautionSoumission.Statut.CONSTITUEE,
            user=self.user)
        self.assertEqual(Activity.objects.count(), avant)
