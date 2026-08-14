"""NTWMS7 — quais et créneaux transporteur.

Critère d'acceptation testé : deux rendez-vous ne peuvent PAS se chevaucher sur
le même quai — refus SERVEUR (dans `save()`, pas seulement `clean()`, sinon un
`objects.create()` passerait à travers) — et le planning jour/semaine les
expose par quai.

Run :
    python manage.py test apps.stock.test_ntwms7_quais -v 2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Quai, RendezVousTransporteur
from apps.stock.selectors import planning_quais

User = get_user_model()

# Dates/heures FIXES (jamais `now()` : une suite qui bascule à minuit devient
# flaky). Le lundi 2026-05-11 sert d'ancre de semaine.
LUNDI = datetime.date(2026, 5, 11)
MERCREDI = datetime.date(2026, 5, 13)


def h(date, heure, minute=0):
    """Datetime AWARE (jamais naïf : le projet est en USE_TZ)."""
    return timezone.make_aware(
        datetime.datetime(date.year, date.month, date.day, heure, minute),
        timezone.get_default_timezone())


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms7Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms7-co', 'NTWMS7 Co')
        self.autre = make_company('ntwms7-autre', 'NTWMS7 Autre')
        self.admin = User.objects.create_user(
            username='ntwms7_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Entrepôt NTWMS7', is_principal=True)
        self.quai_a = Quai.objects.create(
            company=self.company, nom='Quai A', emplacement=self.emplacement,
            type_quai=Quai.TypeQuai.RECEPTION)
        self.quai_b = Quai.objects.create(
            company=self.company, nom='Quai B', emplacement=self.emplacement,
            type_quai=Quai.TypeQuai.EXPEDITION)
        self.api = auth(self.admin)

    def _rdv(self, quai, debut_h, fin_h, date=LUNDI, **kwargs):
        return RendezVousTransporteur.objects.create(
            company=self.company, quai=quai,
            date_heure_debut=h(date, debut_h), date_heure_fin=h(date, fin_h),
            **kwargs)


class TestNonChevauchement(Ntwms7Base):
    def test_deux_creneaux_disjoints_acceptes(self):
        self._rdv(self.quai_a, 8, 9)
        self._rdv(self.quai_a, 9, 10)
        self.assertEqual(
            RendezVousTransporteur.objects.filter(quai=self.quai_a).count(), 2)

    def test_chevauchement_refuse_meme_par_objects_create(self):
        """La garde vit dans `save()` : un `objects.create()` direct (import en
        masse, script, admin) est refusé exactement comme l'API."""
        self._rdv(self.quai_a, 8, 10)
        with self.assertRaises(ValueError):
            self._rdv(self.quai_a, 9, 11)
        self.assertEqual(
            RendezVousTransporteur.objects.filter(quai=self.quai_a).count(), 1)

    def test_creneau_englobant_refuse(self):
        self._rdv(self.quai_a, 9, 10)
        with self.assertRaises(ValueError):
            self._rdv(self.quai_a, 8, 12)

    def test_meme_creneau_sur_un_autre_quai_accepte(self):
        self._rdv(self.quai_a, 8, 10)
        self._rdv(self.quai_b, 8, 10)
        self.assertEqual(RendezVousTransporteur.objects.count(), 2)

    def test_creneau_annule_libere_la_place(self):
        rdv = self._rdv(self.quai_a, 8, 10)
        rdv.statut = RendezVousTransporteur.Statut.ANNULE
        rdv.save(update_fields=['statut'])
        self._rdv(self.quai_a, 8, 10)
        self.assertEqual(
            RendezVousTransporteur.objects.filter(
                quai=self.quai_a,
                statut=RendezVousTransporteur.Statut.PLANIFIE).count(), 1)

    def test_fin_avant_debut_refusee(self):
        with self.assertRaises(ValueError):
            self._rdv(self.quai_a, 11, 9)

    def test_deplacement_sur_un_creneau_libre_accepte(self):
        self._rdv(self.quai_a, 8, 9)
        rdv = self._rdv(self.quai_a, 14, 15)
        rdv.date_heure_debut = h(LUNDI, 16)
        rdv.date_heure_fin = h(LUNDI, 17)
        rdv.save()
        rdv.refresh_from_db()
        self.assertEqual(rdv.date_heure_debut, h(LUNDI, 16))


class TestPlanningQuais(Ntwms7Base):
    def test_vue_jour(self):
        self._rdv(self.quai_a, 8, 9)
        self._rdv(self.quai_b, 10, 11)
        self._rdv(self.quai_a, 8, 9, date=MERCREDI)
        donnees = planning_quais(
            self.company, date_str=LUNDI.isoformat(), vue='jour')
        self.assertEqual(donnees['vue'], 'jour')
        par_quai = {q['quai_nom']: q for q in donnees['quais']}
        self.assertEqual(len(par_quai['Quai A']['rendez_vous']), 1)
        self.assertEqual(len(par_quai['Quai B']['rendez_vous']), 1)

    def test_vue_semaine_couvre_lundi_a_dimanche(self):
        self._rdv(self.quai_a, 8, 9)
        self._rdv(self.quai_a, 8, 9, date=MERCREDI)
        donnees = planning_quais(
            self.company, date_str=MERCREDI.isoformat(), vue='semaine')
        self.assertEqual(donnees['date_debut'], LUNDI)
        self.assertEqual(donnees['date_fin'],
                         LUNDI + datetime.timedelta(days=6))
        self.assertEqual(len(donnees['quais'][0]['rendez_vous']), 2)

    def test_date_obligatoire(self):
        with self.assertRaises(ValueError):
            planning_quais(self.company, date_str=None)

    def test_vue_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            planning_quais(
                self.company, date_str=LUNDI.isoformat(), vue='mois')

    def test_planning_ne_voit_pas_une_autre_societe(self):
        self._rdv(self.quai_a, 8, 9)
        donnees = planning_quais(self.autre, date_str=LUNDI.isoformat())
        self.assertEqual(donnees['quais'], [])


class TestEndpointsQuais(Ntwms7Base):
    def test_api_refuse_le_chevauchement_en_400(self):
        self._rdv(self.quai_a, 8, 10)
        resp = self.api.post(
            '/api/django/stock/rendez-vous-transporteur/', {
                'quai': self.quai_a.id,
                'date_heure_debut': h(LUNDI, 9).isoformat(),
                'date_heure_fin': h(LUNDI, 11).isoformat(),
            }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_api_accepte_un_creneau_libre(self):
        resp = self.api.post(
            '/api/django/stock/rendez-vous-transporteur/', {
                'quai': self.quai_a.id,
                'date_heure_debut': h(LUNDI, 9).isoformat(),
                'date_heure_fin': h(LUNDI, 11).isoformat(),
            }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['statut'], 'planifie')

    def test_endpoint_planning(self):
        self._rdv(self.quai_a, 8, 9)
        resp = self.api.get(
            f'/api/django/stock/quais/planning/?date={LUNDI.isoformat()}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['quais']), 2)

    def test_quai_d_une_autre_societe_refuse(self):
        emplacement_autre = EmplacementStock.objects.create(
            company=self.autre, nom='Entrepôt autre NTWMS7')
        quai_autre = Quai.objects.create(
            company=self.autre, nom='Quai X',
            emplacement=emplacement_autre)
        resp = self.api.post(
            '/api/django/stock/rendez-vous-transporteur/', {
                'quai': quai_autre.id,
                'date_heure_debut': h(LUNDI, 9).isoformat(),
                'date_heure_fin': h(LUNDI, 11).isoformat(),
            }, format='json')
        self.assertEqual(resp.status_code, 400)
