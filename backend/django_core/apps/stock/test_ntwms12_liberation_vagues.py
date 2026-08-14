"""NTWMS12 — règles de libération de vague (wave release strategy).

Critère d'acceptation testé : une vague en mode AUTO_HEURE passe
automatiquement de brouillon à lancée à l'heure configurée, SANS intervention
manuelle. Les tests injectent l'instant courant (`maintenant=`) : jamais
`now()`, sinon la suite bascule à minuit.

Run :
    python manage.py test apps.stock.test_ntwms12_liberation_vagues -v 2
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import AchatsParametres, Produit, VaguePicking
from apps.stock.services import (
    configurer_liberation_vague, creer_vague_depuis_besoins,
    liberer_vagues_planifiees,
)

User = get_user_model()

JOUR = datetime.date(2026, 5, 11)


def instant(heure, minute=0):
    """Datetime AWARE fixe (jamais `now()`)."""
    return timezone.make_aware(
        datetime.datetime(JOUR.year, JOUR.month, JOUR.day, heure, minute),
        timezone.get_default_timezone())


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms12Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms12-co', 'NTWMS12 Co')
        self.autre = make_company('ntwms12-autre', 'NTWMS12 Autre')
        self.admin = User.objects.create_user(
            username='ntwms12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS12',
            prix_achat=Decimal('90'), prix_vente=Decimal('140'),
            quantite_stock=100)
        self.api = auth(self.admin)

    def _vague(self, nb_lignes=1, company=None):
        company = company or self.company
        produit = self.produit
        if company is not self.company:
            produit = Produit.objects.create(
                company=company, nom='Autre', sku='AUT-NTWMS12',
                prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        besoins = [{'produit_id': produit.id, 'quantite': 1}
                   for _ in range(nb_lignes)]
        return creer_vague_depuis_besoins(
            company=company, user=self.admin, besoins=besoins)


class TestConfiguration(Ntwms12Base):
    def test_defaut_manuel(self):
        vague = self._vague()
        self.assertEqual(vague.mode_liberation,
                         VaguePicking.ModeLiberation.MANUEL)
        self.assertIsNone(vague.seuil_lignes)

    def test_configurer_auto_seuil(self):
        vague = self._vague()
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=3)
        vague.refresh_from_db()
        self.assertEqual(vague.mode_liberation, 'auto_seuil')
        self.assertEqual(vague.seuil_lignes, 3)

    def test_auto_seuil_sans_seuil_refuse(self):
        vague = self._vague()
        with self.assertRaises(ValueError):
            configurer_liberation_vague(vague=vague, mode='auto_seuil')

    def test_mode_inconnu_refuse(self):
        vague = self._vague()
        with self.assertRaises(ValueError):
            configurer_liberation_vague(vague=vague, mode='auto_lune')

    def test_vague_lancee_non_reconfigurable(self):
        vague = self._vague()
        vague.statut = VaguePicking.Statut.LANCEE
        vague.save(update_fields=['statut'])
        with self.assertRaises(ValueError):
            configurer_liberation_vague(vague=vague, mode='auto_heure')

    def test_endpoint_configurer(self):
        vague = self._vague()
        resp = self.api.post(
            f'/api/django/stock/vagues-picking/{vague.id}/'
            'configurer-liberation/',
            {'mode': 'auto_seuil', 'seuil_lignes': 2}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['mode_liberation'], 'auto_seuil')
        self.assertEqual(resp.data['seuil_lignes'], 2)

    def test_endpoint_mode_invalide_400(self):
        vague = self._vague()
        resp = self.api.post(
            f'/api/django/stock/vagues-picking/{vague.id}/'
            'configurer-liberation/', {'mode': 'auto_seuil'}, format='json')
        self.assertEqual(resp.status_code, 400)


class TestLiberationAutoHeure(Ntwms12Base):
    def setUp(self):
        super().setUp()
        parametres = AchatsParametres.for_company(self.company)
        parametres.heure_coupure_vagues = datetime.time(17, 0)
        parametres.save(update_fields=['heure_coupure_vagues'])

    def test_avant_l_heure_rien_ne_bouge(self):
        vague = self._vague()
        configurer_liberation_vague(vague=vague, mode='auto_heure')
        resultat = liberer_vagues_planifiees(maintenant=instant(16, 30))
        self.assertEqual(resultat['liberees'], [])
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.BROUILLON)

    def test_a_l_heure_la_vague_part_seule(self):
        vague = self._vague()
        configurer_liberation_vague(vague=vague, mode='auto_heure')
        resultat = liberer_vagues_planifiees(maintenant=instant(17, 0))
        self.assertEqual(resultat['liberees'], [vague.reference])
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.LANCEE)
        self.assertIsNotNone(vague.date_lancement)

    def test_idempotent(self):
        vague = self._vague()
        configurer_liberation_vague(vague=vague, mode='auto_heure')
        liberer_vagues_planifiees(maintenant=instant(18, 0))
        second = liberer_vagues_planifiees(maintenant=instant(19, 0))
        self.assertEqual(second['liberees'], [])

    def test_sans_heure_configuree_jamais_liberee(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.heure_coupure_vagues = None
        parametres.save(update_fields=['heure_coupure_vagues'])
        vague = self._vague()
        configurer_liberation_vague(vague=vague, mode='auto_heure')
        resultat = liberer_vagues_planifiees(maintenant=instant(23, 0))
        self.assertEqual(resultat['liberees'], [])

    def test_mode_manuel_jamais_touche(self):
        vague = self._vague()
        resultat = liberer_vagues_planifiees(maintenant=instant(23, 0))
        self.assertEqual(resultat['examinees'], 0)
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.BROUILLON)

    def test_filtrage_par_societe(self):
        vague = self._vague()
        configurer_liberation_vague(vague=vague, mode='auto_heure')
        resultat = liberer_vagues_planifiees(
            company=self.autre, maintenant=instant(23, 0))
        self.assertEqual(resultat['liberees'], [])
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.BROUILLON)


class TestLiberationAutoSeuil(Ntwms12Base):
    def test_sous_le_seuil_rien_ne_bouge(self):
        vague = self._vague(nb_lignes=2)
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=5)
        resultat = liberer_vagues_planifiees(maintenant=instant(10, 0))
        self.assertEqual(resultat['liberees'], [])

    def test_seuil_atteint_declenche(self):
        vague = self._vague(nb_lignes=3)
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=3)
        resultat = liberer_vagues_planifiees(maintenant=instant(10, 0))
        self.assertEqual(resultat['liberees'], [vague.reference])
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.LANCEE)


class TestCommandeManagement(Ntwms12Base):
    def test_commande_dry_run_n_ecrit_rien(self):
        vague = self._vague()
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=1)
        sortie = StringIO()
        call_command('liberer_vagues_planifiees', '--dry-run', stdout=sortie)
        self.assertIn('candidate', sortie.getvalue())
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.BROUILLON)

    def test_commande_libere(self):
        vague = self._vague(nb_lignes=2)
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=2)
        sortie = StringIO()
        call_command('liberer_vagues_planifiees', stdout=sortie)
        self.assertIn(vague.reference, sortie.getvalue())
        vague.refresh_from_db()
        self.assertEqual(vague.statut, VaguePicking.Statut.LANCEE)

    def test_commande_idempotente(self):
        vague = self._vague(nb_lignes=2)
        configurer_liberation_vague(
            vague=vague, mode='auto_seuil', seuil_lignes=2)
        call_command('liberer_vagues_planifiees', stdout=StringIO())
        sortie = StringIO()
        call_command('liberer_vagues_planifiees', stdout=sortie)
        self.assertIn('0 vague(s) libérée(s)', sortie.getvalue())
