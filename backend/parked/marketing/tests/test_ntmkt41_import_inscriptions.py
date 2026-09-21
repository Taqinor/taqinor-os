"""NTMKT41 — Import CSV de contacts d'événement (inscriptions en masse hors
formulaire public).

Couvre : importer un CSV de 30 noms crée 30 InscriptionEvenement statut
« inscrit », les doublons (email déjà inscrit à CET événement) sont ignorés
proprement avec rapport, lignes sans nom signalées invalides, isolation
multi-société, authentification requise.
"""
import datetime
import io

from django.utils import timezone

from apps.marketing import services as mkt_services
from apps.marketing.models import EvenementMarketing, InscriptionEvenement

from testkit.base import TenantAPITestCase


def _date_debut():
    return timezone.now() + datetime.timedelta(days=10)


def _csv(lignes):
    contenu = 'nom,email,telephone\n' + '\n'.join(lignes)
    return contenu.encode('utf-8')


class ImporterInscriptionsServiceTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.evenement = EvenementMarketing.objects.create(
            company=self.company, nom='Salon Agricole',
            date_debut=_date_debut())

    def test_import_30_noms_cree_30_inscriptions(self):
        lignes = [f'Participant {i},p{i}@ex.ma,061234567{i % 10}'
                  for i in range(30)]
        rapport = mkt_services.importer_inscriptions_evenement(
            self.evenement, _csv(lignes), 'inscrits.csv')
        self.assertEqual(rapport['crees'], 30)
        self.assertEqual(rapport['doublons'], 0)
        self.assertEqual(InscriptionEvenement.objects.filter(
            evenement=self.evenement).count(), 30)
        premiere = InscriptionEvenement.objects.filter(
            evenement=self.evenement).order_by('id').first()
        self.assertEqual(premiere.statut, InscriptionEvenement.Statut.INSCRIT)

    def test_doublon_email_deja_inscrit_ignore_avec_rapport(self):
        InscriptionEvenement.objects.create(
            company=self.company, evenement=self.evenement, nom='Déjà là',
            email='deja@ex.ma')
        lignes = ['Nouveau,nouveau@ex.ma,0600000000',
                  'Ancien,deja@ex.ma,0600000001']
        rapport = mkt_services.importer_inscriptions_evenement(
            self.evenement, _csv(lignes), 'inscrits.csv')
        self.assertEqual(rapport['crees'], 1)
        self.assertEqual(rapport['doublons'], 1)
        self.assertEqual(InscriptionEvenement.objects.filter(
            evenement=self.evenement).count(), 2)

    def test_ligne_sans_nom_est_invalide_jamais_perdue_en_silence(self):
        lignes = ['Valide,valide@ex.ma,0600000000', ',sansnom@ex.ma,0600000001']
        rapport = mkt_services.importer_inscriptions_evenement(
            self.evenement, _csv(lignes), 'inscrits.csv')
        self.assertEqual(rapport['crees'], 1)
        self.assertEqual(rapport['lignes_invalides'], 1)
        self.assertEqual(rapport['total'], 2)

    def test_import_sans_email_reste_cree(self):
        rapport = mkt_services.importer_inscriptions_evenement(
            self.evenement, _csv(['Sans email,,0600000000']), 'inscrits.csv')
        self.assertEqual(rapport['crees'], 1)


class ImporterInscriptionsEndpointTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.evenement = EvenementMarketing.objects.create(
            company=self.company, nom='Salon Agricole',
            date_debut=_date_debut())

    def _upload(self, contenu, user=None):
        # `importer_inscriptions_evenement_view` exige explicitement
        # IsResponsableOrAdmin (apps/marketing/views.py) — un utilisateur
        # 'normal' (le défaut de TenantAPITestCase) reçoit 403 avant même
        # d'atteindre la vue.
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile(
            'inscrits.csv', contenu, content_type='text/csv')
        client = self.client_as(user=user) if user is not None \
            else self.client_as(role='responsable')
        return client.post(
            f'/api/django/marketing/evenements-marketing/{self.evenement.id}'
            '/importer-inscrits/',
            {'fichier': fichier}, format='multipart')

    def test_endpoint_exige_une_authentification(self):
        res = self.client.post(
            f'/api/django/marketing/evenements-marketing/{self.evenement.id}'
            '/importer-inscrits/')
        self.assertIn(res.status_code, (401, 403))

    def test_endpoint_importe_et_renvoie_le_rapport(self):
        res = self._upload(_csv(['A,a@ex.ma,0600000000', 'B,b@ex.ma,0600000001']))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['crees'], 2)
        self.assertEqual(InscriptionEvenement.objects.filter(
            evenement=self.evenement).count(), 2)

    def test_endpoint_sans_fichier_400(self):
        res = self.client_as(role='responsable').post(
            f'/api/django/marketing/evenements-marketing/{self.evenement.id}'
            '/importer-inscrits/', {}, format='multipart')
        self.assertEqual(res.status_code, 400)

    def test_evenement_d_une_autre_societe_404(self):
        autre = EvenementMarketing.objects.create(
            company=self.other_company, nom='Fuite',
            date_debut=_date_debut())
        res = self.client_as(role='responsable').post(
            f'/api/django/marketing/evenements-marketing/{autre.id}'
            '/importer-inscrits/',
            {'fichier': io.BytesIO(_csv(['A,a@ex.ma,']))}, format='multipart')
        self.assertEqual(res.status_code, 404)
