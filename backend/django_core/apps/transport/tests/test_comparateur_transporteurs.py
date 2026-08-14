"""NTLOG7 — comparateur de coûts d'affrètement : liste les
`installations.Transporteur` actifs, triés par prix (tarif_base) croissant.

Fixture cross-app : les modèles `installations` sont importés directement ICI
(fichier de TEST, pas du code de `apps.transport`) pour construire des
transporteurs réels — le sélecteur lui-même (`apps.transport.selectors.
comparer_transporteurs`) ne les lit qu'en LECTURE via
`django.apps.apps.get_model` (jamais un import statique)."""
from django.test import TestCase

from apps.installations.models import Transporteur
from apps.transport.models import OrdreTransport

from ._helpers import auth, make_company, make_user

ORDRES_BASE = '/api/django/transport/ordres-transport/'


class ComparateurTransporteursTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-cmp-a', 'A')
        self.co_b = make_company('transport-cmp-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-cmp-a')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a,
            mode_transport=OrdreTransport.ModeTransport.AFFRETEMENT)
        self.cher = Transporteur.objects.create(
            company=self.co_a, nom='Cher SARL', tarif_base='800.00',
            active=True)
        self.pas_cher = Transporteur.objects.create(
            company=self.co_a, nom='Pas cher SARL', tarif_base='300.00',
            active=True)
        self.inactif = Transporteur.objects.create(
            company=self.co_a, nom='Fermé SARL', tarif_base='100.00',
            active=False)
        # Bruit d'une autre société — ne doit jamais apparaître.
        Transporteur.objects.create(
            company=self.co_b, nom='Autre société', tarif_base='50.00',
            active=True)

    def test_liste_triee_par_prix_croissant(self):
        resp = auth(self.user_a).get(
            f'{ORDRES_BASE}{self.ordre.id}/comparer-transporteurs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = [row['nom'] for row in resp.data]
        self.assertEqual(noms, ['Pas cher SARL', 'Cher SARL'])

    def test_transporteur_inactif_exclu(self):
        resp = auth(self.user_a).get(
            f'{ORDRES_BASE}{self.ordre.id}/comparer-transporteurs/')
        noms = [row['nom'] for row in resp.data]
        self.assertNotIn('Fermé SARL', noms)

    def test_transporteur_autre_societe_exclu(self):
        resp = auth(self.user_a).get(
            f'{ORDRES_BASE}{self.ordre.id}/comparer-transporteurs/')
        noms = [row['nom'] for row in resp.data]
        self.assertNotIn('Autre société', noms)

    def test_selecteur_appelable_directement(self):
        from apps.transport import selectors

        rows = selectors.comparer_transporteurs(
            self.ordre.id, company=self.co_a)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['prix_applicable'], self.pas_cher.tarif_base)
