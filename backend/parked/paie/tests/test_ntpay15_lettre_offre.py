"""Tests NTPAY15 — Lettre d'offre / proposition d'embauche (depuis NTPAY14).

Couvre : le contenu remis au candidat (poste, brut ET net, avantages, période
d'essai, mention légale), l'ABSENCE TOTALE de coût interne (charges
patronales, provisions, coût employeur chargé), le refus sans poste, et
l'endpoint (400/403).

Le rendu HTML est testé directement (aucune dépendance WeasyPrint) ; le PDF
lui-même passe par le même HTML.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.services import ensure_defaults, simuler_cout_embauche
from apps.roles.models import Role


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class LettreOffreHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay15')
        ensure_defaults(self.co)
        self.simulation = simuler_cout_embauche(
            self.co, brut=Decimal('12000'), le_jour=date(2026, 6, 1))

    def _html(self, **kwargs):
        params = dict(
            poste='Technicien photovoltaïque',
            candidat='Yasmine Bennani',
            avantages=['Assurance maladie complémentaire', 'Véhicule de service'],
            periode_essai='3 mois renouvelables une fois',
            date_prise_poste=date(2026, 7, 1),
            employeur=builders.employeur_context(self.co),
            today=date(2026, 6, 12))
        params.update(kwargs)
        return builders.render_lettre_offre_html(self.simulation, **params)

    def test_contenu_remis_au_candidat(self):
        html = self._html()
        self.assertIn('Proposition d’embauche', html)
        self.assertIn('Technicien photovoltaïque', html)
        self.assertIn('Yasmine Bennani', html)
        self.assertIn('Assurance maladie complémentaire', html)
        self.assertIn('3 mois renouvelables une fois', html)
        self.assertIn('Code du travail marocain', html)
        # Brut ET net proposés, tous deux affichés.
        self.assertIn(builders._fmt(self.simulation['brut']), html)
        self.assertIn(builders._fmt(self.simulation['net_a_payer']), html)
        self.assertIn('MAD', html)

    def test_aucun_cout_interne_n_atteint_le_candidat(self):
        html = self._html()
        interdits = [
            'charges patronales', 'coût employeur', 'cout employeur',
            'provision', 'patronale', 'chargé',
        ]
        minuscules = html.lower()
        for mot in interdits:
            self.assertNotIn(mot.lower(), minuscules, mot)
        # Et aucun des MONTANTS internes n'est imprimé.
        for montant in (self.simulation['charges_patronales'],
                        self.simulation['cout_total_employeur'],
                        self.simulation['provisions']['total']):
            self.assertNotIn(builders._fmt(montant), html)

    def test_champs_absents_ne_sont_pas_inventes(self):
        html = self._html(candidat='', avantages=[], periode_essai='',
                          date_prise_poste=None)
        self.assertNotIn('À l’attention de', html)
        self.assertNotIn('Avantages', html)
        self.assertNotIn('Période d’essai', html)
        self.assertNotIn('Date de prise de poste', html)
        # Le poste et la rémunération, eux, restent là.
        self.assertIn('Technicien photovoltaïque', html)

    def test_sans_poste_refuse(self):
        with self.assertRaises(ValueError):
            self._html(poste='')


class LettreOffreApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay15-api')
        ensure_defaults(self.co)
        self.url = '/api/django/paie/profils/lettre-offre/'
        self.api = self._client(
            ['paie_voir', 'paie_gerer', 'salaires_voir'], 'ntpay15-paye')

    def _client(self, permissions, username):
        role = Role.objects.create(
            company=self.co, nom=f'Role {username}', permissions=permissions)
        user = User.objects.create_user(
            username=username, password='x', company=self.co, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_sans_poste_est_400(self):
        rep = self.api.get(f'{self.url}?brut=12000')
        self.assertEqual(rep.status_code, 400)
        self.assertIn('poste', rep.data['detail'])

    def test_sans_brut_ni_net_cible_est_400(self):
        rep = self.api.get(f'{self.url}?poste=Technicien')
        self.assertEqual(rep.status_code, 400)

    def test_sans_salaires_voir_est_403(self):
        api = self._client(['paie_voir', 'paie_gerer'], 'ntpay15-sans')
        rep = api.get(f'{self.url}?poste=Technicien&brut=12000')
        self.assertEqual(rep.status_code, 403)
