"""CIQ652 — un besoin de continuité déclaré à la visite pose UNE note interne
« orienter vers une étude de secours » sur le lead : sans dimensionnement, sans
prix, jamais un message client. La visite est validée par le vrai service (le
sélecteur du relevé n'est jamais mocké).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm import services
from apps.crm.models import Lead, LeadActivity
from apps.visites import services as visites_services
from apps.visites.models import VisiteTerrain

User = get_user_model()


class NoteBesoinSecours(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ652 Co', slug='ciq652-co')
        self.bureau = User.objects.create_user(
            username='ciq652_bureau', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Clinique',
            type_installation='commercial')

    def _visite(self, besoin, non_releve=False):
        commerce = {'categorie': 'sante',
                    'horaires_constates': '24h/24',
                    'besoin_continuite_service': besoin}
        if non_releve:
            commerce['_non_releves'] = {
                'besoin_continuite_service': 'a_faire_par_electricien'}
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='ci',
            statut=VisiteTerrain.Statut.TERMINEE,
            mesures={'comptage': {'type_compteur': 'triphasé',
                                  'niveau_tension_constate': 'bt'},
                     'site_commerce': commerce})

    def _notes(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body=services.NOTE_BESOIN_SECOURS)

    def test_besoin_declare_pose_une_note_du_valideur(self):
        visites_services.valider_visite(self._visite(True), self.bureau)
        notes = self._notes()
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.get().user, self.bureau)

    def test_la_note_ne_dimensionne_ni_ne_chiffre(self):
        self.assertIn('orienter vers une étude de secours',
                      services.NOTE_BESOIN_SECOURS)
        for interdit in ('kWh', 'kWc', 'kVA', 'MAD', 'DH', 'autonomie de',
                         'heures'):
            self.assertNotIn(interdit, services.NOTE_BESOIN_SECOURS)

    def test_revalider_garde_une_seule_note(self):
        visite = self._visite(True)
        visites_services.valider_visite(visite, self.bureau)
        visites_services.valider_visite(visite, self.bureau)
        self.assertEqual(self._notes().count(), 1)

    def test_pas_de_besoin_pas_de_note(self):
        visites_services.valider_visite(self._visite(False), self.bureau)
        self.assertEqual(self._notes().count(), 0)

    def test_besoin_non_renseigne_ou_non_releve_pas_de_note(self):
        visites_services.valider_visite(self._visite(None), self.bureau)
        self.assertEqual(self._notes().count(), 0)
        visites_services.valider_visite(
            self._visite(True, non_releve=True), self.bureau)
        self.assertEqual(self._notes().count(), 0)

    def test_visite_residentielle_ne_pose_rien(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='toiture',
            statut=VisiteTerrain.Statut.TERMINEE,
            mesures={'toiture': {'longueur_m': 12, 'largeur_m': 8}})
        visites_services.valider_visite(visite, self.bureau)
        self.assertEqual(self._notes().count(), 0)

    def test_aucun_message_client_n_est_envoye(self):
        visites_services.valider_visite(self._visite(True), self.bureau)
        client = {LeadActivity.Kind.EMAIL, LeadActivity.Kind.WHATSAPP}
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, kind__in=client).exists())
