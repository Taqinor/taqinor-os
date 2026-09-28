"""ERR-QAH-VISITES-COUVERTURE-ENUM-SANS-AFFORDANCE (qa-explorer 28/09/2026).

Répro observée : « Type de couverture » et « État de la couverture » sont des
champs texte libres (aucune liste, aucun placeholder) sur l'onglet « Toiture »
du relevé, mais n'acceptent que des codes internes — un technicien qui tape
« Tuile » / « Bon état » recevait un 400 et ne découvrait les valeurs permises
qu'après coup. Règle fondateur « normaliser plutôt que refuser quand
l'intention est claire » : ``apps.visites.services.valeur_mesure`` normalise
désormais la saisie CHOIX (casse/accents/« état »…) avant de refuser, et ne
refuse plus qu'une valeur VRAIMENT inconnue — en la nommant toujours.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.visites import services
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VisitesCouvertureEnumTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QAH2 Solaire', slug='qah2-couverture')
        self.role = Role.objects.create(
            company=self.company, nom='terrain',
            permissions=['crm_voir', 'visites_voir', 'visites_creer',
                         'visites_modifier'])
        self.commercial = User.objects.create_user(
            username='qah2-commercial', password='x', company=self.company,
            role_legacy='normal', role=self.role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Sami',
            telephone='+212600000099', ville='Bouskoura')
        self.api = auth(self.commercial)
        resp = self.api.post(
            '/api/django/visites/visites/',
            {'lead': self.lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.visite_id = resp.data['id']

    def patch_mesures(self, categorie, valeurs):
        return self.api.patch(
            f'/api/django/visites/visites/{self.visite_id}/mesures/',
            {'categorie': categorie, 'valeurs': valeurs}, format='json')

    # ── OBSERVÉ avant correction : 400 sur une saisie humaine limpide ───────
    def test_type_de_couverture_tuile_normalise_et_accepte(self):
        resp = self.patch_mesures('toiture', {'type_couverture': 'Tuile'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['mesures']['type_couverture'], 'tuile')

    def test_etat_de_la_couverture_bon_etat_normalise_et_accepte(self):
        resp = self.patch_mesures('toiture', {'etat_couverture': 'Bon état'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mesures']['etat_couverture'], 'bon')

    def test_les_deux_champs_ensemble_valeurs_accentuees_avec_espaces(self):
        resp = self.patch_mesures('toiture', {
            'type_couverture': 'Tôle', 'etat_couverture': 'État moyen',
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mesures']['type_couverture'], 'tole')
        self.assertEqual(resp.data['mesures']['etat_couverture'], 'moyen')

    def test_bac_acier_en_deux_mots_normalise(self):
        resp = self.patch_mesures('toiture', {'type_couverture': 'bac acier'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mesures']['type_couverture'], 'bac_acier')

    # ── une valeur VRAIMENT inconnue reste refusée, en nommant le champ ─────
    def test_valeur_inconnue_reste_refusee_en_nommant_le_champ(self):
        resp = self.patch_mesures('toiture', {'type_couverture': 'Ardoise'})
        self.assertEqual(resp.status_code, 400, resp.data)
        message = resp.data['erreurs']['type_couverture']
        self.assertIn('Type de couverture', message)
        self.assertIn('Ardoise', message)
        self.assertIn('tuile', message)


class NormaliserChoixUnitTests(TestCase):
    """Le helper pur (aucune base requise) — les cas exacts de l'incident."""

    def test_reconnait_les_libelles_observes_par_le_qa_explorer(self):
        choix_couverture = [
            'tuile', 'tole', 'bac_acier', 'beton', 'fibrociment', 'autre']
        choix_etat = ['bon', 'moyen', 'mauvais']
        self.assertEqual(
            services.normaliser_choix('Tuile', choix_couverture), 'tuile')
        self.assertEqual(
            services.normaliser_choix('Bon état', choix_etat), 'bon')
        self.assertEqual(
            services.normaliser_choix('Tôle', choix_couverture), 'tole')
        self.assertEqual(
            services.normaliser_choix('Béton', choix_couverture), 'beton')
        self.assertEqual(
            services.normaliser_choix('bac acier', choix_couverture),
            'bac_acier')

    def test_une_valeur_sans_correspondance_renvoie_none(self):
        self.assertIsNone(
            services.normaliser_choix('Ardoise', ['tuile', 'tole']))
        self.assertIsNone(services.normaliser_choix('', ['tuile']))
