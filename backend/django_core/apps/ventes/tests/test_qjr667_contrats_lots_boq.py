"""QJR667 (PACT10) — les réponses RÉELLES des actions `lots` (NTCPQ18) et
`ajouter-boq-electrique` (PV47) ont la forme de leurs échantillons partagés
`contract_samples/devis_lots.json` et `devis_boq_electrique.json`, que
l'écran de l'Édition complète importe dans ses tests.

Comparaison de FORME (clés, et nature de chaque valeur : nombre, texte,
booléen, liste, objet), sur le JSON réellement rendu — un montant servi en
texte au lieu d'un nombre rougit ici.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr667_contrats_lots_boq"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import LigneDevis, LotDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

ECHANTILLONS = Path(__file__).resolve().parents[1] / 'contract_samples'


def _echantillon(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


def _nature(valeur):
    if valeur is None:
        return 'null'
    if isinstance(valeur, bool):
        return 'bool'
    if isinstance(valeur, (int, float)):
        return 'nombre'
    if isinstance(valeur, str):
        return 'texte'
    if isinstance(valeur, list):
        return 'liste'
    return 'objet'


class _Forme:

    def assertMemeForme(self, reel, attendu, chemin='$'):
        if attendu is None or reel is None:
            return  # nullable des deux côtés (ex. hors_lot, produit d'une note)
        self.assertEqual(_nature(reel), _nature(attendu), chemin)
        if isinstance(attendu, dict):
            self.assertEqual(set(reel), set(attendu), chemin)
            for cle in attendu:
                self.assertMemeForme(reel[cle], attendu[cle], f'{chemin}.{cle}')
        elif isinstance(attendu, list) and attendu and reel:
            for i, item in enumerate(reel):
                self.assertMemeForme(item, attendu[0], f'{chemin}[{i}]')


class ContratLotsTests(_Forme, TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)
        self.url = f'/api/django/ventes/devis/{self.devis.id}/lots/'

    def _ligne(self, lot=None):
        return LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('2'),
            prix_unitaire=Decimal('1250.00'), lot=lot)

    def test_get_sans_lot(self):
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(json.loads(r.content),
                         _echantillon('devis_lots.json')['exemple_sans_lot'])

    def test_get_avec_lot_et_hors_lot(self):
        lot = LotDevis.objects.create(
            company=self.company, devis=self.devis, nom_lot='A',
            adresse_site='Casablanca', ordre=0)
        self._ligne(lot)
        self._ligne(None)
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertMemeForme(json.loads(r.content),
                             _echantillon('devis_lots.json')['exemple'])

    def test_post_rend_la_meme_forme(self):
        ligne = self._ligne(None)
        corps = dict(_echantillon('devis_lots.json')['requete_post']['corps'],
                     lignes=[ligne.id])
        r = self.api.post(self.url, corps, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertMemeForme(json.loads(r.content),
                             _echantillon('devis_lots.json')['exemple'])
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.lot_id)


class ContratBoqTests(_Forme, TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = DevisFactory(company=self.company)
        self.url = (f'/api/django/ventes/devis/{self.devis.id}'
                    '/ajouter-boq-electrique/')

    def test_sans_conception_400_detail(self):
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        attendu = _echantillon('devis_boq_electrique.json')['refus'][
            '400_sans_conception']
        self.assertEqual(json.loads(r.content), attendu)

    def test_reponse_a_la_forme_du_contrat(self):
        self.devis.electrical_design = {'bom': [
            {'designation': 'PDC1 — Parafoudre DC Type 2 (coffret de chaînes)',
             'quantite': 1, 'spec': 'In 20 kA'},
        ]}
        self.devis.save(update_fields=['electrical_design'])
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        reel = json.loads(r.content)
        attendu = _echantillon('devis_boq_electrique.json')['exemple']
        self.assertMemeForme(reel, attendu)
        self.assertEqual(reel['creees'], 1)
        self.assertTrue(reel['lignes'][0]['a_chiffrer'])
