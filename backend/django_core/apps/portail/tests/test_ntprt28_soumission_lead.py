"""Tests NTPRT28 — deal registration du portail PARTENAIRE authentifié.

Le critère d'acceptation de la tâche est l'ANTI-DOUBLON : une re-soumission du
même prospect par le même partenaire à moins de 30 jours doit être SIGNALÉE
avant création — « jamais de doublon silencieux ». On vérifie aussi que le
partenaire est résolu du COMPTE (jamais du corps) et qu'il ne voit que SES
soumissions.

Run :
    python manage.py test apps.portail.tests.test_ntprt28_soumission_lead -v2
"""
import datetime
import itertools

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Partenaire, SoumissionLeadPartenaire
from apps.roles.models import (
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    PORTAIL_PARTENAIRE_PERMISSIONS,
    ROLE_PORTAIL_FOURNISSEUR,
    ROLE_PORTAIL_PARTENAIRE,
    Role,
)
from authentication.models import Company, CustomUser

URL = '/api/django/portail/mes-soumissions/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_PARTENAIRE: (
        ROLE_PORTAIL_PARTENAIRE, 'portail_partenaire_id',
        PORTAIL_PARTENAIRE_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_partenaire(company, nom='Partenaire', statut_onboarding='agree'):
    n = next(_seq)
    # `token_acces` est UNIQUE et sans défaut : la production le pose côté
    # serveur, une fixture qui l'omet violerait la contrainte au 2ᵉ appel.
    # `statut_onboarding='agree'` : un partenaire qui dépose une affaire est,
    # par construction, un partenaire AGRÉÉ (la garde d'agrément elle-même est
    # couverte par les tests NTPRT32).
    return Partenaire.objects.create(
        company=company, nom=f'{nom}-{n}', token_acces=f'tok-ntprt28-{n}',
        statut_onboarding=statut_onboarding)


PROSPECT = {
    'nom_prospect': 'Villa Ain Diab',
    'email_prospect': 'Contact@Villa-AinDiab.ma',
    'telephone_prospect': '0600000000',
    'ville': 'Casablanca',
    'note': 'Toiture 120 m2, facture ONEE 1 800 MAD/mois.',
}


class SoumissionPartenaireTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt28-co', 'NTPRT28 Société')
        self.p_a = make_partenaire(self.company, 'Alpha')
        self.p_b = make_partenaire(self.company, 'Beta')
        self.user_a = make_portal_user(
            self.company, 'ntprt28-p-a',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_soumission_nominale(self):
        res = self.api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['nom_prospect'], 'Villa Ain Diab')
        self.assertEqual(res.data['statut'], 'soumis')
        self.assertFalse(res.data['converti'])

        soumission = SoumissionLeadPartenaire.objects.get(pk=res.data['id'])
        # Société ET partenaire viennent du compte, jamais du corps.
        self.assertEqual(soumission.company_id, self.company.id)
        self.assertEqual(soumission.partenaire_id, self.p_a.id)

    def test_partenaire_du_corps_est_ignore(self):
        """Un `partenaire` envoyé par le client ne déplace jamais la ligne."""
        res = self.api.post(
            URL, {**PROSPECT, 'partenaire': self.p_b.id,
                  'company': 999}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        soumission = SoumissionLeadPartenaire.objects.get(pk=res.data['id'])
        self.assertEqual(soumission.partenaire_id, self.p_a.id)
        self.assertEqual(soumission.company_id, self.company.id)

    def test_doublon_moins_de_30_jours_est_signale_sans_creer(self):
        """Critère d'acceptation NTPRT28."""
        self.assertEqual(
            self.api.post(URL, PROSPECT, format='json').status_code, 201)

        res = self.api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 409, res.data)
        self.assertIn('Déjà soumis', res.data['email_prospect'])
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            company=self.company, partenaire=self.p_a).count(), 1)

    def test_doublon_insensible_a_la_casse_de_l_email(self):
        self.api.post(URL, PROSPECT, format='json')
        res = self.api.post(
            URL, {**PROSPECT, 'email_prospect': 'contact@villa-aindiab.ma'},
            format='json')
        self.assertEqual(res.status_code, 409, res.data)

    def test_au_dela_de_30_jours_une_nouvelle_soumission_passe(self):
        premiere = SoumissionLeadPartenaire.objects.create(
            company=self.company, partenaire=self.p_a,
            nom_prospect='Villa Ain Diab',
            email_prospect='contact@villa-aindiab.ma',
            statut=SoumissionLeadPartenaire.Statut.SOUMIS)
        # `date_soumission` est auto_now_add : on la recule par UPDATE.
        vieux = timezone.now() - datetime.timedelta(days=45)
        SoumissionLeadPartenaire.objects.filter(pk=premiere.pk).update(
            date_soumission=vieux)

        res = self.api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            company=self.company, partenaire=self.p_a).count(), 2)

    def test_le_meme_prospect_chez_un_AUTRE_partenaire_n_est_pas_un_doublon(
            self):
        SoumissionLeadPartenaire.objects.create(
            company=self.company, partenaire=self.p_b,
            nom_prospect='Villa Ain Diab',
            email_prospect='contact@villa-aindiab.ma',
            statut=SoumissionLeadPartenaire.Statut.SOUMIS)
        res = self.api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_nom_manquant_nomme_le_champ_fautif(self):
        res = self.api.post(
            URL, {**PROSPECT, 'nom_prospect': '  '}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('nom_prospect', res.data)

    def test_sans_email_ni_telephone_nomme_le_champ_fautif(self):
        res = self.api.post(
            URL, {'nom_prospect': 'Anonyme'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('email_prospect', res.data)

    def test_sans_email_mais_avec_telephone_ce_n_est_pas_un_doublon(self):
        """Deux prospects sans email ne doivent JAMAIS s'annuler l'un
        l'autre."""
        base = {'nom_prospect': 'Prospect A', 'telephone_prospect': '0611111111'}
        self.assertEqual(
            self.api.post(URL, base, format='json').status_code, 201)
        autre = {'nom_prospect': 'Prospect B',
                 'telephone_prospect': '0622222222'}
        self.assertEqual(
            self.api.post(URL, autre, format='json').status_code, 201)

    def test_le_partenaire_ne_voit_que_SES_soumissions(self):
        self.api.post(URL, PROSPECT, format='json')
        SoumissionLeadPartenaire.objects.create(
            company=self.company, partenaire=self.p_b,
            nom_prospect='Prospect de Beta',
            statut=SoumissionLeadPartenaire.Statut.SOUMIS)

        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        noms = [r['nom_prospect'] for r in res.data['results']]
        self.assertIn('Villa Ain Diab', noms)
        self.assertNotIn('Prospect de Beta', noms)

    def test_detail_d_une_soumission_d_autrui_est_404(self):
        autre = SoumissionLeadPartenaire.objects.create(
            company=self.company, partenaire=self.p_b,
            nom_prospect='Prospect de Beta',
            statut=SoumissionLeadPartenaire.Statut.SOUMIS)
        self.assertEqual(self.api.get(f'{URL}{autre.id}/').status_code, 404)

    def test_un_compte_fournisseur_est_refuse(self):
        f = make_portal_user(
            self.company, 'ntprt28-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        api = APIClient()
        api.force_authenticate(user=f)
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(
            api.post(URL, PROSPECT, format='json').status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_partenaire_d_une_autre_societe_ne_soumet_rien(self):
        autre = make_company('ntprt28-co-b', 'NTPRT28 Société B')
        etranger = make_portal_user(
            autre, 'ntprt28-p-etranger',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            partenaire=self.p_a).count(), 0)
