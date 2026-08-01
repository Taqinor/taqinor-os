"""AOF137 — ``PieceAdministrative`` : une attestation est une donnée DATÉE.

Ce qui est prouvé ici :

* **une attestation fiscale de plus d'un an À LA DATE D'OUVERTURE fait échouer
  un contrôle BLOQUANT, en citant sa date** — même si elle est encore valable
  « aujourd'hui » ;
* la MÊME pièce se rattache à deux appels d'offres sans dupliquer un octet ;
* aucun nouveau ``FileField`` : le fichier vit dans ``records.Attachment`` ou
  ``ged.Document`` ;
* le rappel J-N liste les pièces à renouveler.

Run :
    python manage.py test apps.ao.tests.test_pieces_administratives -v2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, PieceAdministrative
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/pieces-administratives/'

OUVERTURE = date(2026, 9, 15)


class TestAucunFileField(SimpleTestCase):
    def test_le_fichier_passe_par_records_ou_ged(self):
        champs = {f.name: f.__class__.__name__
                  for f in PieceAdministrative._meta.get_fields()}
        self.assertNotIn('FileField', champs.values())
        self.assertIn('attachment', champs)
        self.assertIn('ged_document', champs)

    def test_les_durees_reglementaires_sont_declarees(self):
        self.assertEqual(
            PieceAdministrative.DUREES_PAR_DEFAUT[
                PieceAdministrative.TypePiece.ATTESTATION_FISCALE], 365)
        self.assertEqual(
            PieceAdministrative.DUREES_PAR_DEFAUT[
                PieceAdministrative.TypePiece.ATTESTATION_CNSS], 90)


class BaseAdministratif(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF137 Co',
                                              slug='aof137-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-137-1', objet='Administratif',
            date_ouverture_plis=OUVERTURE)
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def _piece(self, type_piece, date_emission, **kwargs):
        base = {'libelle': 'Pièce', 'emetteur': 'Organisme'}
        base.update(kwargs)
        return PieceAdministrative.objects.create(
            company=self.company, type_piece=type_piece,
            date_emission=date_emission, **base)


class TestPeremptionALaDateDeRemise(BaseAdministratif):
    def test_la_duree_reglementaire_est_posee_automatiquement(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            date(2026, 1, 10))
        self.assertEqual(piece.duree_validite_jours, 365)
        self.assertEqual(piece.date_expiration, date(2027, 1, 10))

    def test_une_fiscale_de_plus_d_un_an_a_l_ouverture_est_bloquante(self):
        """Le cœur d'AOF137 : la date de l'OUVERTURE, pas celle du jour."""
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            date(2025, 6, 1), libelle='Attestation fiscale 2025')
        services.rattacher_piece_administrative(piece, self.dossier)
        controles = services.controler_pieces_administratives(self.dossier)
        bloquants = [c for c in controles
                     if c['severite'] == services.SEVERITE_BLOQUANT]
        self.assertEqual(len(bloquants), 1)
        message = bloquants[0]['message']
        self.assertIn('2025-06-01', message)
        self.assertIn('2026-06-01', message)
        self.assertIn('2026-09-15', message)
        self.assertEqual(bloquants[0]['code'], 'AO_PIECE_ADMIN_EXPIREE')

    def test_la_meme_piece_est_valable_aujourd_hui_mais_pas_a_l_ouverture(self):
        """Contrôler « à aujourd'hui » donnerait un dossier faussement vert."""
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_CNSS,
            OUVERTURE - timedelta(days=100))
        self.assertFalse(
            piece.est_expiree_a(OUVERTURE - timedelta(days=95)))
        self.assertTrue(piece.est_expiree_a(OUVERTURE))

    def test_une_piece_valide_ne_bloque_pas(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            OUVERTURE - timedelta(days=30))
        services.rattacher_piece_administrative(piece, self.dossier)
        controles = services.controler_pieces_administratives(self.dossier)
        self.assertEqual(
            [c for c in controles
             if c['severite'] == services.SEVERITE_BLOQUANT], [])

    def test_une_piece_bientot_expiree_est_un_avertissement(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_CNSS,
            OUVERTURE - timedelta(days=70), rappel_jours=30)
        services.rattacher_piece_administrative(piece, self.dossier)
        controles = services.controler_pieces_administratives(self.dossier)
        self.assertEqual(controles[0]['severite'],
                         services.SEVERITE_AVERTISSEMENT)
        self.assertEqual(controles[0]['code'],
                         'AO_PIECE_ADMIN_BIENTOT_EXPIREE')

    def test_une_piece_sans_peremption_ne_bloque_jamais(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.RIB, date(2020, 1, 1))
        self.assertIsNone(piece.date_expiration)
        services.rattacher_piece_administrative(piece, self.dossier)
        self.assertEqual(
            services.controler_pieces_administratives(self.dossier), [])

    def test_sans_date_de_remise_le_controle_avertit_au_lieu_de_deviner(self):
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-137-SANSDATE',
            objet='Sans date')
        dossier = services.creer_dossier_ao(self.company, ao)
        controles = services.controler_pieces_administratives(dossier)
        self.assertEqual(controles[0]['code'], 'AO_DATE_REFERENCE_ABSENTE')
        self.assertEqual(controles[0]['severite'],
                         services.SEVERITE_AVERTISSEMENT)

    def test_la_porte_de_depot_relaie_le_motif(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            date(2025, 6, 1), libelle='Attestation fiscale 2025')
        services.rattacher_piece_administrative(piece, self.dossier)
        raisons = ' '.join(self.dossier.raisons_de_non_depot())
        self.assertIn('EXPIRÉE à la date de remise des plis', raisons)


class TestReutilisationSansDuplication(BaseAdministratif):
    def test_une_piece_sert_deux_appels_d_offres(self):
        autre_ao = AppelOffre.objects.create(
            company=self.company, reference='AO-137-2', objet='Second',
            date_ouverture_plis=OUVERTURE)
        autre_dossier = services.creer_dossier_ao(self.company, autre_ao)
        piece = self._piece(
            PieceAdministrative.TypePiece.REGISTRE_COMMERCE,
            date(2026, 1, 1))
        services.rattacher_piece_administrative(piece, self.dossier)
        services.rattacher_piece_administrative(piece, autre_dossier)
        self.assertEqual(piece.dossiers.count(), 2)
        self.assertEqual(
            PieceAdministrative.objects.filter(company=self.company).count(),
            1)

    def test_un_rattachement_cross_societe_est_refuse(self):
        autre = Company.objects.create(nom='AOF137 X', slug='aof137-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-137-X', objet='X')
        dossier_autre = services.creer_dossier_ao(autre, ao)
        piece = self._piece(
            PieceAdministrative.TypePiece.RIB, date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            services.rattacher_piece_administrative(piece, dossier_autre)

    def test_rattacher_deux_fois_ne_duplique_pas(self):
        piece = self._piece(
            PieceAdministrative.TypePiece.POUVOIRS, date(2026, 1, 1))
        services.rattacher_piece_administrative(piece, self.dossier)
        services.rattacher_piece_administrative(piece, self.dossier)
        self.assertEqual(piece.dossiers.count(), 1)


class TestRappelJmoinsN(BaseAdministratif):
    def test_le_rappel_liste_les_pieces_dans_leur_fenetre(self):
        aujourdhui = date(2026, 8, 1)
        self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_CNSS,
            aujourdhui - timedelta(days=70), rappel_jours=30,
            libelle='CNSS bientôt expirée')
        self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            aujourdhui - timedelta(days=10), rappel_jours=30,
            libelle='Fiscale fraîche')
        a_renouveler = services.pieces_administratives_a_renouveler(
            self.company, a_la_date=aujourdhui)
        self.assertEqual([p.libelle for p in a_renouveler],
                         ['CNSS bientôt expirée'])

    def test_une_piece_inactive_est_ignoree(self):
        aujourdhui = date(2026, 8, 1)
        self._piece(
            PieceAdministrative.TypePiece.ATTESTATION_CNSS,
            aujourdhui - timedelta(days=70), actif=False)
        self.assertEqual(
            services.pieces_administratives_a_renouveler(
                self.company, a_la_date=aujourdhui), [])


class TestApiAdministratif(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF137 API',
                                              slug='aof137-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof137_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-137-API', objet='API',
            date_ouverture_plis=OUVERTURE)
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def test_creation_et_rattachement(self):
        r = self.api.post(URL, {
            'type_piece': 'attestation_fiscale',
            'libelle': 'Attestation fiscale 2026',
            'date_emission': '2026-01-10'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['date_expiration'], '2027-01-10')
        piece_id = r.data['id']
        r = self.api.post(f'{URL}{piece_id}/rattacher/',
                          {'dossier': self.dossier.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['dossiers'], [self.dossier.id])

    def test_le_controle_administratif_est_expose(self):
        piece = PieceAdministrative.objects.create(
            company=self.company,
            type_piece=PieceAdministrative.TypePiece.ATTESTATION_FISCALE,
            libelle='Fiscale périmée', date_emission=date(2025, 6, 1))
        services.rattacher_piece_administrative(piece, self.dossier)
        r = self.api.get(
            f'/api/django/ao/dossiers-ao/{self.dossier.id}/'
            'controle-administratif/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['bloquant'])
        self.assertIn('2026-09-15', r.data['controles'][0]['message'])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF137 Y', slug='aof137-y')
        PieceAdministrative.objects.create(
            company=autre, type_piece=PieceAdministrative.TypePiece.RIB,
            libelle='Interdit', date_emission=date(2026, 1, 1))
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])
