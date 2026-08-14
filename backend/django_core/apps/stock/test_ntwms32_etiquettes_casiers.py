"""NTWMS32 — étiquette de casier / planche imprimable.

Critère d'acceptation testé : la planche d'étiquettes de casier contient un
code scannable par le poste NTWMS5 pour CHAQUE casier de l'emplacement, prête
à coller en rayonnage.

Le rendu PDF (WeasyPrint) n'est pas exercé ici — la suite valide le CONTENU
via ``?sortie=html`` (même HTML que celui envoyé au moteur PDF), sans
dépendance système.

Run :
    python manage.py test apps.stock.test_ntwms32_etiquettes_casiers -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import labels
from apps.stock.models import EmplacementStock
from apps.stock.selectors import resoudre_code_scanne

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms32Base(TestCase):
    URL = '/api/django/stock/casiers/etiquettes-pdf/'

    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms32-co', 'NTWMS32 Co')
        self.autre = make_company('ntwms32-autre', 'NTWMS32 Autre')
        self.admin = User.objects.create_user(
            username='ntwms32_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS32', is_principal=True)
        self.vide = EmplacementStock.objects.create(
            company=self.company, nom='Annexe vide NTWMS32')
        self.casiers = [
            BinLocation.objects.create(
                company=self.company, emplacement=self.emplacement,
                code=code, zone=code[0], allee=code[2:4], casier=code[5:],
                ordre=ordre)
            for code, ordre in [('A-01-01', 10), ('A-01-02', 20),
                                ('B-03-05', 60)]
        ]
        self.api = auth(self.admin)


class TestPlancheEtiquettes(Ntwms32Base):
    def test_planche_contient_tous_les_casiers(self):
        reponse = self.api.get(
            self.URL, {'emplacement': self.emplacement.id, 'sortie': 'html'})

        self.assertEqual(reponse.status_code, 200)
        html = reponse.content.decode('utf-8')
        for casier in self.casiers:
            self.assertIn(casier.code, html)
        self.assertIn('Dépôt NTWMS32', html)
        self.assertIn('Zone A', html)

    def test_le_code_imprime_est_celui_que_le_scanner_resout(self):
        """Le jeton encodé doit être résolu par le poste NTWMS5."""
        token = labels.casier_token(self.casiers[0].code)
        resultat = resoudre_code_scanne(self.company, token)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat['type'], 'casier')
        self.assertEqual(resultat['id'], self.casiers[0].id)

    def test_casier_archive_exclu(self):
        self.casiers[0].archived = True
        self.casiers[0].save(update_fields=['archived'])
        html = self.api.get(
            self.URL,
            {'emplacement': self.emplacement.id, 'sortie': 'html'}
        ).content.decode('utf-8')
        self.assertNotIn('A-01-01', html)
        self.assertIn('A-01-02', html)

    def test_emplacement_manquant_400(self):
        self.assertEqual(
            self.api.get(self.URL, {'sortie': 'html'}).status_code, 400)

    def test_emplacement_sans_casier_404(self):
        reponse = self.api.get(
            self.URL, {'emplacement': self.vide.id, 'sortie': 'html'})
        self.assertEqual(reponse.status_code, 404)

    def test_symbologie_code128_acceptee(self):
        reponse = self.api.get(self.URL, {
            'emplacement': self.emplacement.id, 'sortie': 'html',
            'symbology': 'code128'})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('<svg', reponse.content.decode('utf-8'))

    def test_casiers_d_une_autre_societe_jamais_imprimes(self):
        intrus = User.objects.create_user(
            username='ntwms32_intrus', password='x', role_legacy='admin',
            company=self.autre)
        reponse = auth(intrus).get(
            self.URL, {'emplacement': self.emplacement.id, 'sortie': 'html'})
        self.assertEqual(reponse.status_code, 404)


class TestRenduHtmlPur(TestCase):
    """Le moteur d'étiquettes est pur : il se teste sans base de données."""

    def test_html_sans_casier_reste_valide(self):
        html = labels.render_etiquettes_casiers_html([])
        self.assertIn('<html>', html)

    def test_situation_omet_les_champs_vides(self):
        html = labels.render_etiquettes_casiers_html(
            [{'code': 'C-01-01', 'zone': '', 'allee': '', 'emplacement': ''}])
        self.assertIn('C-01-01', html)
        self.assertNotIn('Zone ', html)
