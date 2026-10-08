"""ADEV59 (C-ADEV-042) — l'effacement DSR ventes efface la copie du toit.

Rejoue VB r4d : après ``erase_ventes``, le devis né d'un calepinage
géoréférencé portait encore ``roof_layout['pin'] = {'lat': 33.5731,
'lng': -7.5898}``. Désormais : plus d'épingle ni de coordonnée absolue dans
``roof_layout``, plus de coordonnées dans ``etude_params.toiture``,
``roof_image`` détachée (objet supprimé s'il n'est plus référencé) — la
géométrie relative (panneaux, comptes) reste pour la cohérence des totaux.
Test-du-test : retirer le scrub de ``roof_layout`` ⇒ test_pin_efface échoue.

Mesure prod (lecture seule, 08/10/2026) : 350 devis, 56 portent ``pin``,
57 des coordonnées dans ``roof_layout``, 41 une ``roof_image``, 0 des
coordonnées dans ``etude_params.toiture``.
"""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.dsr_provider import erase_ventes
from apps.ventes.models import Devis

User = get_user_model()

LAT, LNG = 33.5731, -7.5898
SOMMETS = [[LNG, LAT], [LNG + 0.0001, LAT], [LNG + 0.0001, LAT + 0.0001],
           [LNG, LAT + 0.0001]]


def _layout():
    return {
        'version': 2,
        'pin': {'lat': LAT, 'lng': LNG},
        'outline': [[lat, lng] for lng, lat in SOMMETS],
        'zones': [{'id': 'Z1', 'vertices': [list(p) for p in SOMMETS],
                   'result': {'count': 8, 'kwc': 4.4, 'areaM2': 110.0}}],
        'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7000},
        'repereAcquitte': {'lat': LAT, 'lng': LNG},
    }


def _contient_position(valeur):
    texte = json.dumps(valeur)
    cles = ('pin', 'lat', 'lng', 'repereAcquitte')
    return any(f'"{k}"' in texte for k in cles)


class DsrCopieToitDevisTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADEV59 Co')
        self.user = User.objects.create_user(
            username='adev59_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Sujet', prenom='ADEV59',
            email='sujet.adev59@example.com', telephone='+212600005959')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-202610-5901',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user,
            roof_layout=_layout(),
            roof_image=f'roofs/{self.company.pk}/DEV-202610-5901.png',
            etude_params={'puissance_kwc': 4.4, 'toiture': {
                'nb_panneaux': 8, 'kwc': 4.4,
                'pans': [{'label': 'P1', 'nb_panneaux': 8,
                          'centerLat': LAT, 'centerLng': LNG}],
                'gps': {'lat': LAT, 'lng': LNG}}})

    def _effacer(self):
        with mock.patch('apps.ventes.services.supprimer_fichier_toiture') as sup:
            erase_ventes(self.company, 'sujet.adev59@example.com')
        self.devis.refresh_from_db()
        return sup

    def test_pin_efface(self):
        self._effacer()
        layout = self.devis.roof_layout
        self.assertNotIn('pin', layout)
        self.assertNotIn('repereAcquitte', layout)
        self.assertFalse(_contient_position(layout))
        # Aucune coordonnée absolue ne survit : les sommets sont en mètres
        # locaux (le carré fait ~10 m de côté), jamais 33.57 / -7.58.
        for x, y in layout['zones'][0]['vertices']:
            self.assertLess(abs(x), 50)
            self.assertLess(abs(y), 50)
        texte = json.dumps(layout)
        self.assertNotIn('33.57', texte)
        self.assertNotIn('-7.58', texte)

    def test_toiture_coordonnees_effacees(self):
        sup = self._effacer()
        toiture = self.devis.etude_params['toiture']
        self.assertFalse(_contient_position(toiture))
        self.assertNotIn('centerLat', json.dumps(toiture))
        self.assertNotIn('gps', toiture)
        # roof_image détachée ; objet supprimé (plus aucun devis ne le porte).
        self.assertFalse(self.devis.roof_image)
        sup.assert_called_once_with(
            f'roofs/{self.company.pk}/DEV-202610-5901.png')

    def test_geometrie_relative_conservee(self):
        self._effacer()
        layout = self.devis.roof_layout
        self.assertEqual(layout['result'], _layout()['result'])
        self.assertEqual(layout['zones'][0]['result'],
                         _layout()['zones'][0]['result'])
        self.assertEqual(len(layout['zones'][0]['vertices']), 4)
        toiture = self.devis.etude_params['toiture']
        self.assertEqual(toiture['nb_panneaux'], 8)
        self.assertEqual(toiture['pans'][0]['nb_panneaux'], 8)
        self.assertEqual(self.devis.etude_params['puissance_kwc'], 4.4)
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_image_partagee_conservee(self):
        cle = self.devis.roof_image
        autre_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='Client',
            email='autre.adev59@example.com', telephone='+212600005960')
        Devis.objects.create(
            company=self.company, reference='DEV-202610-5902',
            client=autre_client, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user, roof_image=cle)
        sup = self._effacer()
        self.assertFalse(self.devis.roof_image)
        sup.assert_not_called()
