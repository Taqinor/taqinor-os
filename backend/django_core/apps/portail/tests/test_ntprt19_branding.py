"""Tests NTPRT19 — Branding white-label des portails (login public + emails).

Critère d'acceptation : deux sociétés portant des ``TenantTheme`` différents
voient un portail visuellement distinct SANS toucher au code. Le pivot est le
domaine white-label — d'où les deux familles de tests :

* résolution par ``Host`` UNIQUEMENT (jamais un paramètre d'URL, qui ferait de
  l'endpoint public un énumérateur de tenants), et charge utile limitée à la
  MARQUE (ni id société, ni domaine, ni identité légale) ;
* repli CHAMP PAR CHAMP sur ``CompanyProfile`` quand le thème est partiel, et
  repli NEUTRE (200, marque vide) quand rien ne correspond — jamais 404, jamais
  d'erreur : une page de login ne casse pas pour un logo.

Run :
    python manage.py test apps.portail.tests.test_ntprt19_branding -v2
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.portail.branding import company_pour_hote, marque_portail
from authentication.models import Company
from core.models import TenantTheme

URL = '/api/django/public/portail/theme/'


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par appelant."""
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


# Les domaines white-label de test doivent être joignables : en PROD c'est
# `DJANGO_ALLOWED_HOSTS` (et le reverse-proxy) qui doivent porter le domaine
# du tenant — sans quoi Django répond 400 avant même d'atteindre la vue.
_HOTES = [
    'portail-a.example', 'portail-b.example', 'repli.example',
    'inconnu.example', 'autre.example', 'testserver',
]


@override_settings(ALLOWED_HOSTS=_HOTES)
class ResolutionParDomaineTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ntprt19-co-a', 'Société A')
        self.co_b = make_company('ntprt19-co-b', 'Société B')
        TenantTheme.objects.create(
            company=self.co_a, domaine='portail-a.example',
            nom_affichage='Alpha Énergie', couleur_primaire='#111111',
            couleur_secondaire='#222222', logo_url='https://cdn/a.png')
        TenantTheme.objects.create(
            company=self.co_b, domaine='portail-b.example',
            nom_affichage='Beta Solaire', couleur_primaire='#333333')
        self.api = APIClient()

    def test_deux_domaines_deux_marques_distinctes(self):
        a = self.api.get(URL, HTTP_HOST='portail-a.example')
        b = self.api.get(URL, HTTP_HOST='portail-b.example')

        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        self.assertEqual(a.data['nom_affichage'], 'Alpha Énergie')
        self.assertEqual(b.data['nom_affichage'], 'Beta Solaire')
        self.assertNotEqual(a.data['couleur_primaire'],
                            b.data['couleur_primaire'])

    def test_le_port_est_ignore(self):
        res = self.api.get(URL, HTTP_HOST='portail-a.example:8443')
        self.assertEqual(res.data['nom_affichage'], 'Alpha Énergie')

    def test_domaine_inconnu_renvoie_une_marque_vide_pas_une_erreur(self):
        res = self.api.get(URL, HTTP_HOST='inconnu.example')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['nom_affichage'], '')
        self.assertEqual(res.data['logo_url'], '')

    def test_aucun_parametre_ne_permet_de_choisir_une_societe(self):
        """Pas d'énumération de tenants : le paramètre est simplement ignoré."""
        res = self.api.get(
            URL + f'?company={self.co_a.id}', HTTP_HOST='inconnu.example')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['nom_affichage'], '')

    def test_la_charge_utile_ne_porte_que_la_marque(self):
        res = self.api.get(URL, HTTP_HOST='portail-a.example')
        self.assertEqual(
            set(res.data.keys()),
            {'nom_affichage', 'logo_url', 'couleur_primaire',
             'couleur_secondaire'})
        # Le jeu de clés EXACT ci-dessus est l'assertion forte : ni `domaine`
        # (qui révélerait le mapping tenant↔domaine), ni identifiant société,
        # ni identité légale (ICE/RC/patente/CNSS/RIB) ne sortent d'ici.
        for interdit in ('domaine', 'company_id', 'identifiant_fiscal',
                         'patente', 'cnss', 'rib'):
            self.assertNotIn(interdit, res.data)

    def test_endpoint_accessible_sans_authentification(self):
        res = APIClient().get(URL, HTTP_HOST='portail-a.example')
        self.assertEqual(res.status_code, 200)

    def test_un_theme_sans_domaine_n_est_jamais_resolu(self):
        """Sinon TOUTES les sociétés sans domaine seraient candidates."""
        co_c = make_company('ntprt19-co-c', 'Société C')
        TenantTheme.objects.create(
            company=co_c, domaine='', nom_affichage='Gamma')
        self.assertIsNone(company_pour_hote(''))
        self.assertIsNone(company_pour_hote(None))
        res = self.api.get(URL, HTTP_HOST='autre.example')
        self.assertEqual(res.data['nom_affichage'], '')


@override_settings(ALLOWED_HOSTS=_HOTES)
class RepliMarqueTests(TestCase):
    def test_repli_champ_par_champ_sur_le_profil_societe(self):
        """Un thème PARTIEL ne doit pas effacer le nom de la société."""
        from apps.parametres.models import CompanyProfile

        company = make_company('ntprt19-repli', 'Raison Sociale SARL')
        CompanyProfile.objects.update_or_create(
            company=company,
            defaults={'nom': 'Profil SARL', 'couleur_principale': '#abcdef'})
        # Thème présent mais SANS nom ni couleur : seul le logo est posé.
        TenantTheme.objects.create(
            company=company, domaine='repli.example',
            logo_url='https://cdn/repli.png')

        marque = marque_portail(company)
        self.assertEqual(marque['logo_url'], 'https://cdn/repli.png')
        self.assertEqual(marque['nom_affichage'], 'Profil SARL')
        self.assertEqual(marque['couleur_primaire'], '#abcdef')

    def test_sans_theme_ni_profil_marque_vide_jamais_d_exception(self):
        company = make_company('ntprt19-nu', 'Société Nue')
        marque = marque_portail(company)
        self.assertEqual(set(marque.keys()),
                         {'nom_affichage', 'logo_url', 'couleur_primaire',
                          'couleur_secondaire'})
        self.assertEqual(marque['logo_url'], '')

    def test_company_none_est_inerte(self):
        marque = marque_portail(None)
        self.assertEqual(marque['nom_affichage'], '')
        self.assertEqual(marque['couleur_primaire'], '')
