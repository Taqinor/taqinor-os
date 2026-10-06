"""ADOC145 (C-ADOC-057) — l'anti-doublon partenaire couvre le TÉLÉPHONE.

Constat : ``crm.services.soumission_partenaire_deja_faite`` rendait ``None``
dès que l'email du prospect était vide — le même prospect soumis deux fois
par téléphone (sous deux formats) créait deux soumissions. Désormais, sans
email, la clé est le téléphone normalisé par ``crm.services.normalize_phone``
(la normalisation de la déduplication des leads, jamais une seconde).

Vrais POST sur ``/api/django/portail/mes-soumissions/``, aucun mock.

Run :
    python manage.py test apps.portail.tests.test_adoc_doublon_partenaire_telephone -v2
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import SoumissionLeadPartenaire
from authentication.models import CustomUser

from .test_ntprt28_soumission_lead import (
    URL, make_company, make_partenaire, make_portal_user,
)


class DoublonPartenaireTelephoneTests(TestCase):
    def setUp(self):
        self.company = make_company('adoc145-co', 'ADOC145 Société')
        self.partenaire = make_partenaire(self.company, 'Gamma')
        self.user = make_portal_user(
            self.company, 'adoc145-p',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.partenaire.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _soumissions(self):
        return SoumissionLeadPartenaire.objects.filter(
            company=self.company, partenaire=self.partenaire)

    def test_meme_telephone_normalise_409(self):
        premier = self.api.post(
            URL, {'nom_prospect': 'A', 'telephone_prospect': '0611111111'},
            format='json')
        self.assertEqual(premier.status_code, 201, premier.data)

        second = self.api.post(
            URL, {'nom_prospect': 'A',
                  'telephone_prospect': '+212 611111111'}, format='json')
        self.assertEqual(second.status_code, 409, second.data)
        self.assertIn('Déjà soumis', second.data['email_prospect'])
        self.assertEqual(second.data['soumission_existante'],
                         premier.data['id'])
        self.assertEqual(self._soumissions().count(), 1)

    def test_deux_telephones_differents_restent_deux_soumissions(self):
        for tel in ('0611111111', '0622222222'):
            res = self.api.post(
                URL, {'nom_prospect': 'A', 'telephone_prospect': tel},
                format='json')
            self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self._soumissions().count(), 2)

    def test_hors_fenetre_de_30_jours_n_est_pas_un_doublon(self):
        premier = self.api.post(
            URL, {'nom_prospect': 'A', 'telephone_prospect': '0611111111'},
            format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        SoumissionLeadPartenaire.objects.filter(pk=premier.data['id']).update(
            date_soumission=timezone.now() - datetime.timedelta(days=31))

        second = self.api.post(
            URL, {'nom_prospect': 'A', 'telephone_prospect': '00212611111111'},
            format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(self._soumissions().count(), 2)
