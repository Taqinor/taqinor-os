"""AUD718 — justificatif de congé et CV de candidature : MinIO, pas le disque.

DÉFAUT (rouge avant ce correctif) : `DemandeConge.justificatif` et
`Candidature.cv_fichier` étaient des `FileField` Django BRUTS. Aucun
`STORAGES`/`DEFAULT_FILE_STORAGE` n'est configuré dans les settings, aucune
route `/media/` n'existe (ni `erp_agentique/urls.py`, ni `nginx.conf`) : le
téléversement réussissait — le fichier s'écrivait sur le disque du conteneur —
mais l'URL renvoyée par l'API ne menait à AUCUNE route servie. Le RH ne pouvait
donc JAMAIS relire un certificat médical ni un CV.

Ce module épingle la bascule vers `records.Attachment` (MinIO), même pipeline
que `rh.BulletinPaie` :

* le dépôt multipart (mêmes clés `justificatif` / `cv_fichier`) crée une
  `Attachment` scopée société et NE touche plus le `FileField` legacy ;
* l'API renvoie `justificatif_url` / `cv_url` vers
  `/api/django/records/attachments/<id>/download/` — une route qui EXISTE et
  qui sert réellement le contenu (preuve : GET 200 + octets) ;
* le contrôle XRH3 (justificatif obligatoire au-delà du seuil) reconnaît la
  pièce jointe MinIO ;
* la purge de rétention CNDP (XRH24) efface AUSSI l'objet MinIO — sinon un CV
  « anonymisé » resterait téléchargeable par son URL.
"""
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.records.models import Attachment
from apps.rh import services
from apps.rh.models import (
    Candidature,
    DemandeConge,
    DossierEmploye,
    OuverturePoste,
    TypeAbsence,
)

User = get_user_model()

DEMANDES = '/api/django/rh/demandes-conge/'
CANDIDATURES = '/api/django/rh/candidatures/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def fake_store(file, *, company=None, audio=False):
    """Reproduit `store_attachment` sans MinIO — en gardant le préfixe SCA42."""
    cid = getattr(company, 'id', company)
    prefixe = f'{cid}/' if cid else ''
    return ({'file_key': f'attachments/{prefixe}aud718.pdf',
             'filename': getattr(file, 'name', 'piece.pdf'),
             'size': 1024, 'mime': 'application/pdf'}, None)


def fichier(nom='piece.pdf'):
    f = BytesIO(b'%PDF-1.4 aud718')
    f.name = nom
    return f


class JustificatifCongeMinioTests(TestCase):
    def setUp(self):
        self.co = make_company('aud718-conge', 'A')
        self.rh = make_user(self.co, 'aud718-conge-rh')
        self.type_maladie = TypeAbsence.objects.create(
            company=self.co, code='MAL', libelle='Maladie',
            decompte_jours_ouvres=False, deduit_solde=True,
            jours_max_sans_justificatif=3)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='J1', nom='Tazi', prenom='Reda')

    def _deposer(self):
        with mock.patch('apps.rh.views.store_attachment',
                        side_effect=fake_store):
            return auth(self.rh).post(DEMANDES, {
                'employe': self.emp.id,
                'type_absence': self.type_maladie.id,
                'date_debut': '2026-08-10', 'date_fin': '2026-08-14',
                'justificatif': fichier('certificat.pdf'),
            }, format='multipart')

    def test_depot_cree_une_piece_jointe_scopee_societe(self):
        resp = self._deposer()
        self.assertEqual(resp.status_code, 201, resp.data)
        demande = DemandeConge.objects.get(pk=resp.data['id'])
        self.assertIsNotNone(demande.justificatif_attachment_id)
        attachment = demande.justificatif_attachment
        self.assertEqual(attachment.company, self.co)
        # SCA42 — la clé porte le préfixe société.
        self.assertIn(f'attachments/{self.co.id}/', attachment.file_key)
        # Le FileField legacy n'est PLUS jamais écrit.
        self.assertFalse(demande.justificatif)

    def test_url_renvoyee_est_une_route_qui_sert_vraiment_le_fichier(self):
        """Le cœur du défaut : l'ancienne URL ne résolvait vers AUCUNE route."""
        resp = self._deposer()
        url = resp.data['justificatif_url']
        self.assertIsNotNone(url)
        self.assertIn('/records/attachments/', url)
        with mock.patch('apps.records.views.fetch_attachment',
                        return_value=(b'%PDF-1.4 aud718', None)):
            telecharge = auth(self.rh).get(url)
        self.assertEqual(telecharge.status_code, 200)
        self.assertEqual(telecharge.content, b'%PDF-1.4 aud718')

    def test_sans_justificatif_aucune_url(self):
        resp = auth(self.rh).post(DEMANDES, {
            'employe': self.emp.id, 'type_absence': self.type_maladie.id,
            'date_debut': '2026-08-10', 'date_fin': '2026-08-11',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['justificatif_url'])

    def test_xrh3_reconnait_la_piece_jointe_minio(self):
        """Le seuil « justificatif obligatoire » ne doit pas régresser."""
        resp = self._deposer()
        demande = DemandeConge.objects.get(pk=resp.data['id'])
        self.assertGreater(demande.jours, Decimal('3'))
        # Ne lève pas : la pièce jointe MinIO COMPTE comme justificatif.
        services.valider_demande(demande, decide_par=self.rh)
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)

    def test_xrh3_refuse_toujours_une_demande_sans_aucun_justificatif(self):
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.type_maladie,
            date_debut='2026-08-10', date_fin='2026-08-14',
            jours=Decimal('5'))
        with self.assertRaises(ValueError):
            services.valider_demande(demande, decide_par=self.rh)

    def test_format_refuse_ne_laisse_aucune_demande_orpheline(self):
        """Le fichier est téléversé AVANT la ligne : 400 et rien en base."""
        with mock.patch('apps.rh.views.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            resp = auth(self.rh).post(DEMANDES, {
                'employe': self.emp.id,
                'type_absence': self.type_maladie.id,
                'date_debut': '2026-08-10', 'date_fin': '2026-08-14',
                'justificatif': fichier('virus.exe'),
            }, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('justificatif', resp.data)
        self.assertFalse(DemandeConge.objects.exists())


class CvCandidatureMinioTests(TestCase):
    def setUp(self):
        self.co = make_company('aud718-cv', 'A')
        self.rh = make_user(self.co, 'aud718-cv-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien PV',
            statut=OuverturePoste.Statut.OUVERT)

    def _postuler(self):
        with mock.patch('apps.rh.views.store_attachment',
                        side_effect=fake_store):
            return auth(self.rh).post(CANDIDATURES, {
                'ouverture': self.ouverture.id, 'nom': 'Alami Sara',
                'email': 'sara@example.ma',
                'cv_fichier': fichier('cv-sara.pdf'),
            }, format='multipart')

    def test_cv_range_dans_minio_et_recuperable(self):
        resp = self._postuler()
        self.assertEqual(resp.status_code, 201, resp.data)
        candidature = Candidature.objects.get(pk=resp.data['id'])
        self.assertIsNotNone(candidature.cv_attachment_id)
        self.assertFalse(candidature.cv_fichier)
        self.assertIn(f'attachments/{self.co.id}/',
                      candidature.cv_attachment.file_key)
        url = resp.data['cv_url']
        self.assertIn('/records/attachments/', url)
        with mock.patch('apps.records.views.fetch_attachment',
                        return_value=(b'%PDF-1.4 cv', None)):
            telecharge = auth(self.rh).get(url)
        self.assertEqual(telecharge.status_code, 200)

    def test_remplacer_le_cv_ne_laisse_pas_d_orphelin(self):
        candidature = Candidature.objects.get(pk=self._postuler().data['id'])
        premier_id = candidature.cv_attachment_id
        with mock.patch('apps.rh.views.store_attachment',
                        side_effect=fake_store), \
                mock.patch('apps.rh.views.delete_attachment') as suppr:
            resp = auth(self.rh).patch(
                f'{CANDIDATURES}{candidature.id}/',
                {'cv_fichier': fichier('cv-v2.pdf')}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        candidature.refresh_from_db()
        self.assertNotEqual(candidature.cv_attachment_id, premier_id)
        self.assertFalse(Attachment.objects.filter(pk=premier_id).exists())
        suppr.assert_called_once()

    def test_anonymisation_cndp_efface_aussi_l_objet_minio(self):
        candidature = Candidature.objects.get(pk=self._postuler().data['id'])
        attachment_id = candidature.cv_attachment_id
        with mock.patch('apps.records.storage.delete_attachment') as suppr:
            services.anonymiser_candidature(candidature)
        candidature.refresh_from_db()
        self.assertIsNone(candidature.cv_attachment_id)
        self.assertFalse(Attachment.objects.filter(pk=attachment_id).exists())
        suppr.assert_called_once()

    def test_fusion_absorbe_la_reference_minio(self):
        cible = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Alami S.',
            email='sara@example.ma')
        source = Candidature.objects.get(pk=self._postuler().data['id'])
        services.fusionner_candidatures(cible, source)
        cible.refresh_from_db()
        self.assertEqual(cible.cv_attachment_id, source.cv_attachment_id)
