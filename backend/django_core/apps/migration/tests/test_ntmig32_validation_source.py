"""NTMIG32 — validation de la qualité de la SOURCE avant chargement."""
from django.test import TestCase

from apps.migration import services, validation
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company

CSV_CLIENTS = (
    'Nom,Email,Telephone,ICE\n'
    'Client A,a@exemple.ma,0612345678,001234567000012\n'
    'Client B,b-exemple,0612345679,123\n'
    'Client C,c@exemple.ma,0612345670,00123456700ZZZ2\n'
    'Client D,d@exemple.ma,0612345671,1234\n'
    'Client E,e@exemple.ma,0612345672,12\n'
    'Client F,f@exemple.ma,0612345673,42\n'
).encode('utf-8')


class ValidationSourceTests(TestCase):
    """5 ICE malformés signalés AVANT chargement, rien n'est écrit."""

    def setUp(self):
        self.company = make_company('ntmig32', 'NTMIG32')
        self.admin = make_admin(self.company, 'ntmig32-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Reprise Sage', source='sage')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_cinq_ice_malformes_signales_avant_chargement(self):
        rapport = services.valider_source(
            self.lot, CSV_CLIENTS, 'clients.csv')
        self.assertEqual(rapport['total_lignes'], 6)
        # Lignes 2 à 6 : 5 ICE malformés (la ligne 2 cumule un e-mail invalide).
        self.assertEqual(rapport['lignes_invalides'], 5)
        self.assertEqual(rapport['lignes_valides'], 1)
        self.assertEqual(rapport['lignes_invalides_numeros'], [2, 3, 4, 5, 6])
        self.assertTrue(rapport['peut_continuer_sans_invalides'])
        self.assertTrue(any(d['regle'] == 'ice' for d in rapport['details']))

    def test_validation_n_ecrit_rien(self):
        """Un contrôle de qualité ne déplace pas le lot dans le flux."""
        services.valider_source(self.lot, CSV_CLIENTS, 'clients.csv')
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.EN_ATTENTE)
        self.assertEqual(self.lot.source_lignes, 0)

    def test_fichier_sans_lignes_retire_exactement_les_lignes_citees(self):
        octets, nom = services.fichier_sans_lignes(
            CSV_CLIENTS, 'clients.csv', [2, 3, 4, 5, 6])
        self.assertTrue(nom.endswith('.csv'))
        texte = octets.decode('utf-8')
        self.assertIn('Client A', texte)
        for absent in ('Client B', 'Client C', 'Client D', 'Client E',
                       'Client F'):
            self.assertNotIn(absent, texte)

    def test_endpoint_valider_source(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/'
            'valider-source/',
            {'fichier': _fichier()}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['lignes_invalides'], 5)

    def test_endpoint_charger_sans_les_lignes_invalides(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/migration/lots-migration/{self.lot.pk}/charger/',
            {'fichier': _fichier(), 'ignorer_lignes_invalides': 'true'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        corps = resp.json()
        self.assertEqual(corps['lignes_ignorees'], [2, 3, 4, 5, 6])
        # Seule la ligne saine est passée au moteur d'import.
        self.assertEqual(corps['resultat']['total'], 1)

    def test_champ_vide_n_est_pas_une_erreur_de_format(self):
        self.assertIsNone(validation.valider_ice(''))
        self.assertIsNone(validation.valider_email(None))
        self.assertIsNone(validation.valider_montant('  '))

    def test_regles_locales_ne_devinent_pas_sur_la_valeur(self):
        """Un champ sans mot-clé connu n'est soumis à aucune règle."""
        self.assertEqual(validation.regles_locales('reference'), [])
        self.assertEqual(validation.regles_locales('nom'), [])


def _fichier():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        'clients.csv', CSV_CLIENTS, content_type='text/csv')
