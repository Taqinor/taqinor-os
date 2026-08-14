"""NTWMS8 — kiosque d'enregistrement de quai (check-in chauffeur).

Critère d'acceptation testé : un chauffeur saisit son code de rendez-vous et
voit son quai assigné SANS jamais se connecter à l'ERP. On vérifie aussi que la
réponse ne fuit RIEN d'autre, que l'horodatage est posé par le SERVEUR, et
qu'un code inconnu ne distingue pas société-fausse de code-faux.

Run :
    python manage.py test apps.stock.test_ntwms8_quai_checkin -v 2
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.stock.models import EmplacementStock, Quai, RendezVousTransporteur
from apps.stock.services import enregistrer_arrivee_chauffeur

LUNDI = datetime.date(2026, 5, 11)

# Champs autorisés dans la réponse publique — la liste EXACTE. Tout ajout
# involontaire (client, transporteur, id interne) fait rougir ce test.
CHAMPS_PUBLICS = {
    'quai', 'type_quai', 'heure_rendez_vous', 'horodatage_arrivee', 'message',
}


def h(heure):
    return timezone.make_aware(
        datetime.datetime(LUNDI.year, LUNDI.month, LUNDI.day, heure, 0),
        timezone.get_default_timezone())


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Ntwms8Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms8-co', 'NTWMS8 Co')
        self.autre = make_company('ntwms8-autre', 'NTWMS8 Autre')
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Entrepôt NTWMS8', is_principal=True)
        self.quai = Quai.objects.create(
            company=self.company, nom='Quai 3', emplacement=self.emplacement,
            type_quai=Quai.TypeQuai.RECEPTION)
        self.rdv = RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai,
            date_heure_debut=h(9), date_heure_fin=h(10),
            chauffeur_nom='Ahmed B.', immatriculation='12345-A-6')
        # Client SANS aucune authentification : c'est tout l'intérêt du kiosque.
        self.public = APIClient()


class TestCodeCheckin(Ntwms8Base):
    def test_code_genere_automatiquement(self):
        self.assertEqual(len(self.rdv.code_checkin), 8)
        self.assertTrue(self.rdv.code_checkin.isalnum())

    def test_codes_distincts_entre_rendez_vous(self):
        autre_rdv = RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai,
            date_heure_debut=h(11), date_heure_fin=h(12))
        self.assertNotEqual(self.rdv.code_checkin, autre_rdv.code_checkin)

    def test_code_sans_caracteres_ambigus(self):
        for _ in range(20):
            code = RendezVousTransporteur.generer_code_checkin()
            self.assertFalse(set(code) & set('OI01'))


class TestEnregistrementArrivee(Ntwms8Base):
    def test_arrivee_enregistree(self):
        resultat = enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat['quai'], 'Quai 3')
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, RendezVousTransporteur.Statut.ARRIVE)
        self.assertIsNotNone(self.rdv.date_arrivee)

    def test_reponse_ne_fuit_rien_d_autre(self):
        resultat = enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin)
        self.assertEqual(set(resultat.keys()), CHAMPS_PUBLICS)

    def test_idempotent_l_heure_d_origine_n_est_pas_ecrasee(self):
        premier = enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin)
        second = enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin)
        self.assertEqual(premier['horodatage_arrivee'],
                         second['horodatage_arrivee'])

    def test_code_insensible_a_la_casse(self):
        resultat = enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin.lower())
        self.assertIsNotNone(resultat)

    def test_code_inconnu(self):
        self.assertIsNone(enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code='ZZZZZZZZ'))

    def test_societe_inconnue(self):
        self.assertIsNone(enregistrer_arrivee_chauffeur(
            societe_slug='societe-fantome', code=self.rdv.code_checkin))

    def test_code_d_une_autre_societe_refuse(self):
        """Le code seul ne suffit jamais : il est lu DANS la société annoncée."""
        self.assertIsNone(enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-autre', code=self.rdv.code_checkin))

    def test_rendez_vous_annule_non_enregistrable(self):
        self.rdv.statut = RendezVousTransporteur.Statut.ANNULE
        self.rdv.save(update_fields=['statut'])
        self.assertIsNone(enregistrer_arrivee_chauffeur(
            societe_slug='ntwms8-co', code=self.rdv.code_checkin))

    def test_parametres_vides(self):
        self.assertIsNone(enregistrer_arrivee_chauffeur(
            societe_slug='', code=''))


class TestEndpointPublic(Ntwms8Base):
    URL = '/api/django/stock/public/quai-checkin/'

    def test_checkin_sans_aucune_authentification(self):
        resp = self.public.post(self.URL, {
            'societe': 'ntwms8-co', 'code': self.rdv.code_checkin,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['quai'], 'Quai 3')
        self.assertEqual(set(resp.data.keys()), CHAMPS_PUBLICS)

    def test_reponse_noindex(self):
        resp = self.public.post(self.URL, {
            'societe': 'ntwms8-co', 'code': self.rdv.code_checkin,
        }, format='json')
        self.assertIn('noindex', resp['X-Robots-Tag'])

    def test_code_inconnu_404_sans_indice(self):
        resp = self.public.post(self.URL, {
            'societe': 'ntwms8-co', 'code': 'AAAAAAAA',
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('societe', str(resp.data).lower())

    def test_mount_public_partage(self):
        """Le même endpoint est aussi servi sous le mount public historique."""
        resp = self.public.post(
            '/api/django/public/stock/quai-checkin/', {
                'societe': 'ntwms8-co', 'code': self.rdv.code_checkin,
            }, format='json')
        self.assertEqual(resp.status_code, 200)
