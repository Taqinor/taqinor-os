"""CAD93 — deux leads du même foyer ne reçoivent plus deux cadences à l'aveugle.

Trou signalé par le critique de l'audit L3 du 21/09/2026 (§3) : le
rapprochement de doublons compare le téléphone, l'e-mail et le nom complet,
jamais l'ADRESSE. Deux membres d'un même ménage (ou deux numéros du même
client) passaient au travers et recevaient chacun onze touches.

Ce fichier verrouille les quatre choses qui font que cet indice aide au lieu
de nuire :

  * deux leads à la même adresse sont SIGNALÉS comme doublon probable ;
  * l'indice dit POURQUOI (``match_keys`` porte « adresse » / « gps ») ;
  * AUCUNE fusion n'est faite sans validation — la détection ne touche rien ;
  * l'indice vit dans l'ATELIER, pas dans la garde de démarrage de cadence :
    adresse et GPS sont vides à la création (c'est `valeur_j1` qui les
    demande à J1), et `find_duplicates_by_contact` reste inchangée.

Et les deux garde-fous qui évitent les faux foyers : une VILLE seule ne
rapproche personne, et un fragment d'adresse trop court non plus.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead
from apps.crm.selectors import doublons_foyer_probables
from apps.crm.services import (
    cles_foyer, cluster_match_keys, find_duplicate_clusters,
    find_duplicates_by_contact, normalize_adresse, normalize_gps)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Une vraie adresse de Bouskoura, écrite de deux façons par deux personnes.
ADRESSE_A = 'Résidence Al Firdaous, Immeuble 4, Appartement 12'
ADRESSE_B = 'immeuble 4 appartement 12 residence al firdaous'


class NormalisationTests(SimpleTestCase):
    """Les normaliseurs sont purs : aucune base, aucun réglage société."""

    def test_deux_ecritures_de_la_meme_adresse_donnent_la_meme_cle(self):
        self.assertEqual(normalize_adresse(ADRESSE_A, 'Bouskoura'),
                         normalize_adresse(ADRESSE_B, 'bouskoura'))

    def test_une_ville_seule_ne_fabrique_aucune_cle(self):
        """Sinon tous les leads de Casablanca seraient un seul foyer."""
        self.assertEqual(normalize_adresse('', 'Casablanca'), '')
        self.assertEqual(normalize_adresse(None, 'Casablanca'), '')
        self.assertEqual(normalize_adresse('   ', 'Casablanca'), '')

    def test_fragment_trop_court_ecarte(self):
        self.assertEqual(normalize_adresse('lot 4'), '')

    def test_gps_arrondi_au_meme_toit(self):
        """4 décimales ≈ 11 m : deux relevés du même toit, une seule case."""
        self.assertEqual(normalize_gps(33.412345, -7.612341),
                         normalize_gps(33.412348, -7.612348))

    def test_gps_incomplet_ou_illisible_rend_une_cle_vide(self):
        self.assertEqual(normalize_gps(33.4123, None), '')
        self.assertEqual(normalize_gps(None, -7.6123), '')
        self.assertEqual(normalize_gps('nord', -7.6123), '')

    def test_cles_foyer_tolere_un_objet_sans_coordonnees(self):
        class _Sans:
            adresse = ADRESSE_A
            ville = 'Bouskoura'
            gps_lat = None
            gps_lng = None

        cles = cles_foyer(_Sans())
        self.assertTrue(cles['adresse'])
        self.assertEqual(cles['gps'], '')


class DoublonFoyerTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad93', defaults={'nom': 'cad93'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad93-resp', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, nom, **extra):
        return Lead.objects.create(
            company=self.company, nom=nom, owner=self.acteur,
            stage=stages.NEW, **extra)

    def test_deux_leads_a_la_meme_adresse_sont_signales(self):
        """LE cas de l'audit : le père et le fils, deux numéros, un foyer."""
        pere = self._lead('Benali', prenom='Aziz', telephone='0600000001',
                          adresse=ADRESSE_A, ville='Bouskoura')
        fils = self._lead('Benali', prenom='Youssef', telephone='0600000002',
                          adresse=ADRESSE_B, ville='Bouskoura')

        clusters, _ = find_duplicate_clusters(self.company)
        ids = [{lead.pk for lead in groupe} for groupe in clusters]
        self.assertIn({pere.pk, fils.pk}, ids)

    def test_le_signal_dit_pourquoi(self):
        pere = self._lead('Benali', prenom='Aziz', telephone='0600000001',
                          adresse=ADRESSE_A, ville='Bouskoura')
        fils = self._lead('Alaoui', prenom='Youssef', telephone='0600000002',
                          adresse=ADRESSE_B, ville='Bouskoura')
        self.assertEqual(cluster_match_keys([pere, fils]), ['adresse'])

    def test_meme_point_de_toiture_signale(self):
        un = self._lead('Chraibi', telephone='0600000003',
                        gps_lat='33.412345', gps_lng='-7.612341')
        deux = self._lead('Sekkat', telephone='0600000004',
                          gps_lat='33.412348', gps_lng='-7.612348')
        self.assertEqual(cluster_match_keys([un, deux]), ['gps'])

    def test_deux_villes_identiques_sans_adresse_ne_rapprochent_rien(self):
        self._lead('Tazi', telephone='0600000005', ville='Casablanca')
        self._lead('Idrissi', telephone='0600000006', ville='Casablanca')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual(clusters, [])

    def test_aucune_fusion_sans_validation(self):
        """La détection est une LECTURE : rien n'est archivé ni fusionné."""
        pere = self._lead('Benali', prenom='Aziz', telephone='0600000001',
                          adresse=ADRESSE_A, ville='Bouskoura')
        fils = self._lead('Benali', prenom='Youssef', telephone='0600000002',
                          adresse=ADRESSE_B, ville='Bouskoura')
        find_duplicate_clusters(self.company)
        doublons_foyer_probables(self.company)

        pere.refresh_from_db()
        fils.refresh_from_db()
        self.assertFalse(pere.is_archived)
        self.assertFalse(fils.is_archived)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)

    def test_la_garde_de_demarrage_ne_voit_toujours_que_contact(self):
        """L'indice « même foyer » n'entre PAS dans la garde de cadence.

        Adresse et GPS sont vides à la création : les y mettre ne bloquerait
        rien au bon moment et ferait dérailler un démarrage des mois plus
        tard, quand `valeur_j1` a enfin rempli l'adresse."""
        self._lead('Benali', prenom='Aziz', telephone='0600000001',
                   adresse=ADRESSE_A, ville='Bouskoura')
        fils = self._lead('Benali', prenom='Youssef',
                          telephone='0600000002', adresse=ADRESSE_B,
                          ville='Bouskoura')
        self.assertEqual(
            find_duplicates_by_contact(
                self.company, phone=fils.telephone, email=fils.email,
                exclude_pk=fils.pk),
            [])

    def test_lecture_foyer_isole_les_clusters_de_lieu(self):
        """Un cluster qui partage AUSSI un téléphone n'est pas un « foyer »."""
        self._lead('Benali', prenom='Aziz', telephone='0600000001',
                   adresse=ADRESSE_A, ville='Bouskoura')
        self._lead('Benali', prenom='Youssef', telephone='0600000002',
                   adresse=ADRESSE_B, ville='Bouskoura')
        # Deux fiches de la MÊME personne : même téléphone, pas d'adresse.
        self._lead('Tazi', telephone='0600000009')
        self._lead('Tazi bis', telephone='0600000009')

        foyers = doublons_foyer_probables(self.company)
        self.assertEqual(len(foyers), 1, foyers)
        self.assertEqual(foyers[0]['indices'], ['adresse'])
        self.assertEqual(len(foyers[0]['membres']), 2)

    def test_isolation_entre_societes(self):
        autre, _ = Company.objects.get_or_create(
            slug='cad93-autre', defaults={'nom': 'cad93-autre'})
        CompanyProfile.objects.get_or_create(company=autre)
        Lead.objects.create(company=autre, nom='Voisin A',
                            telephone='0600000007', adresse=ADRESSE_A,
                            ville='Bouskoura', stage=stages.NEW)
        Lead.objects.create(company=autre, nom='Voisin B',
                            telephone='0600000008', adresse=ADRESSE_B,
                            ville='Bouskoura', stage=stages.NEW)
        self.assertEqual(doublons_foyer_probables(self.company), [])
        self.assertEqual(len(doublons_foyer_probables(autre)), 1)
