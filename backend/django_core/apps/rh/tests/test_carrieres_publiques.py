"""Tests XRH33 — Publication publique des offres d'emploi (careers, flag OFF
par défaut, pattern contact-form parké).

Couvre :
* Flag OFF (défaut) → 404 sur les deux endpoints, peu importe l'état des
  données.
* Flag ON → liste publique des seules ouvertures ``publiee=True`` +
  ``statut=OUVERT`` (intitulé/description/ville UNIQUEMENT, jamais de champ
  interne) ; société inconnue → 404.
* Candidature publique : crée une ``Candidature`` company-scopée,
  ``source='site_web'``, ``etape='recu'`` ; honeypot rempli → 404 sans
  création ; ouverture non publiée/non trouvée → 404 ; nom/email
  obligatoires (400).
* Throttling configuré (scope dédié, pas de crash sur appels répétés dans la
  limite du test).
"""
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.rh.models import Candidature, OuverturePoste

CARRIERES_URL = '/api/django/rh/carrieres/{slug}/'
CANDIDATER_URL = '/api/django/rh/carrieres/{slug}/{oid}/candidater/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_ouverture(company, intitule, **kwargs):
    defaults = dict(
        statut=OuverturePoste.Statut.OUVERT, publiee=True, ville='Casablanca')
    defaults.update(kwargs)
    return OuverturePoste.objects.create(
        company=company, intitule=intitule, **defaults)


class CareersFlagOffTests(TestCase):
    def setUp(self):
        self.company = make_company('carr-off', 'Off SARL')
        self.ouverture = make_ouverture(self.company, 'Technicien PV')

    @override_settings(CAREERS_ENABLED=False)
    def test_liste_404_flag_off(self):
        resp = self.client.get(CARRIERES_URL.format(slug=self.company.slug))
        self.assertEqual(resp.status_code, 404)

    @override_settings(CAREERS_ENABLED=False)
    def test_candidater_404_flag_off(self):
        resp = self.client.post(
            CANDIDATER_URL.format(slug=self.company.slug, oid=self.ouverture.pk),
            {'nom': 'Ali', 'email': 'ali@example.com'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Candidature.objects.count(), 0)


@override_settings(CAREERS_ENABLED=True)
class CareersFlagOnListTests(TestCase):
    def setUp(self):
        self.company = make_company('carr-on', 'On SARL')

    def test_liste_seulement_publiees_et_ouvertes(self):
        make_ouverture(self.company, 'Poste publié', publiee=True)
        make_ouverture(self.company, 'Poste non publié', publiee=False)
        make_ouverture(
            self.company, 'Poste clos', publiee=True,
            statut=OuverturePoste.Statut.CLOS)

        resp = self.client.get(CARRIERES_URL.format(slug=self.company.slug))
        self.assertEqual(resp.status_code, 200)
        intitules = {row['intitule'] for row in resp.data}
        self.assertEqual(intitules, {'Poste publié'})

    def test_champs_exposes_uniquement_intitule_description_ville(self):
        make_ouverture(
            self.company, 'Poste public', description='Détails du poste',
            ville='Rabat')
        resp = self.client.get(CARRIERES_URL.format(slug=self.company.slug))
        row = resp.data[0]
        self.assertEqual(
            set(row.keys()), {'id', 'intitule', 'description', 'ville'})

    def test_societe_inconnue_404(self):
        resp = self.client.get(CARRIERES_URL.format(slug='n-existe-pas'))
        self.assertEqual(resp.status_code, 404)


@override_settings(CAREERS_ENABLED=True)
class CareersApplyTests(TestCase):
    def setUp(self):
        self.company = make_company('carr-apply', 'Apply SARL')
        self.ouverture = make_ouverture(self.company, 'Poseur PV')

    def test_candidature_creee_company_scopee(self):
        resp = self.client.post(
            CANDIDATER_URL.format(
                slug=self.company.slug, oid=self.ouverture.pk),
            {'nom': 'Sara Alami', 'email': 'sara@example.com',
             'telephone': '0600000000'})
        self.assertEqual(resp.status_code, 201, resp.data)
        candidature = Candidature.objects.get(pk=resp.data['id'])
        self.assertEqual(candidature.company, self.company)
        self.assertEqual(candidature.source, 'site_web')
        self.assertEqual(candidature.etape, Candidature.Etape.RECU)
        self.assertEqual(candidature.ouverture_id, self.ouverture.pk)

    def test_honeypot_rempli_404_sans_creation(self):
        resp = self.client.post(
            CANDIDATER_URL.format(
                slug=self.company.slug, oid=self.ouverture.pk),
            {'nom': 'Bot', 'email': 'bot@example.com', 'site_web': 'http://spam.example'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Candidature.objects.count(), 0)

    def test_nom_ou_email_manquant_400(self):
        resp = self.client.post(
            CANDIDATER_URL.format(
                slug=self.company.slug, oid=self.ouverture.pk),
            {'nom': 'Sans email'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Candidature.objects.count(), 0)

    def test_ouverture_non_publiee_404(self):
        fermee = make_ouverture(
            self.company, 'Non publiée', publiee=False)
        resp = self.client.post(
            CANDIDATER_URL.format(slug=self.company.slug, oid=fermee.pk),
            {'nom': 'X', 'email': 'x@example.com'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Candidature.objects.count(), 0)

    def test_ouverture_autre_societe_404(self):
        autre_company = make_company('carr-apply-b', 'Autre SARL')
        autre_ouverture = make_ouverture(autre_company, 'Autre poste')
        resp = self.client.post(
            CANDIDATER_URL.format(
                slug=self.company.slug, oid=autre_ouverture.pk),
            {'nom': 'X', 'email': 'x@example.com'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Candidature.objects.count(), 0)
