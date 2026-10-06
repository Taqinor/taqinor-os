"""CIQ633 — numéros de série : saisie atomique sans erreur 500, import en
lot avec la chaîne, gate C&I sur les quantités de la nomenclature.
"""
from decimal import Decimal

from django.test import TestCase

from apps.installations.models import Installation
from apps.installations.services import (
    _gate_check_series, ensure_checklist_items, lire_lignes_series,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_user,
)
from apps.sav.models import Equipement
from apps.stock.models import Produit


class SeriesCITests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.api = auth(make_user(self.company))
        self.module = Produit.objects.create(
            company=self.company, nom='Module 550 W', sku='MOD-633',
            prix_vente=Decimal('1'), quantite_stock=0)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 50 kW', sku='OND-633',
            prix_vente=Decimal('1'), quantite_stock=0)
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ633-10',
            type_installation='industriel', bom=[
                {'produit_id': self.module.id, 'designation': 'Module 550 W',
                 'quantite': 60},
                {'produit_id': self.onduleur.id,
                 'designation': 'Onduleur 50 kW', 'quantite': 1},
            ])
        self.url = f'{BASE}/chantiers/{self.inst.id}/series-lot/'

    def test_doublon_dans_un_lot_de_trois_sans_500(self):
        Equipement.objects.create(company=self.company, produit=self.module,
                                  numero_serie='S-2')
        r = self.api.post(self.url, {'lignes': [
            {'produit': self.module.id, 'numero_serie': 'S-1',
             'chaine': 'C1'},
            {'produit': self.module.id, 'numero_serie': 'S-2'},
            {'produit': self.module.id, 'numero_serie': 'S-3'},
        ]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        statuts = [x['statut'] for x in r.data['resultats']]
        self.assertEqual(statuts, ['cree', 'doublon', 'cree'])
        self.assertEqual(self.inst.equipements.count(), 2)
        eq = Equipement.objects.get(numero_serie='S-1')
        self.assertIn('C1', eq.note)

    def test_checklist_doublon_pas_de_500_et_coherente(self):
        items = ensure_checklist_items(self.inst)
        cle = items[0].cle
        Equipement.objects.create(company=self.company, produit=self.module,
                                  numero_serie='D-1')
        r = self.api.post(
            f'{BASE}/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': cle, 'fait': True, 'equipements': [
                {'produit': self.module.id, 'numero_serie': 'D-1'},
                {'produit': self.module.id, 'numero_serie': 'D-2'}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['equipements_crees'], 1)
        self.assertEqual([x['statut'] for x in r.data['resultats_series']],
                         ['doublon', 'cree'])

    def test_produit_d_une_autre_societe_refuse(self):
        autre = make_company()
        produit = Produit.objects.create(
            company=autre, nom='Module autre', sku='MOD-633-X',
            prix_vente=Decimal('1'), quantite_stock=0)
        r = self.api.post(self.url, {'lignes': [
            {'produit': produit.id, 'numero_serie': 'X-1'}]}, format='json')
        self.assertEqual(r.data['resultats'][0]['statut'], 'autre_societe')
        self.assertFalse(Equipement.objects.filter(numero_serie='X-1')
                         .exists())

    def test_gate_ci_59_series_sur_60(self):
        for i in range(59):
            Equipement.objects.create(
                company=self.company, produit=self.module,
                installation=self.inst, numero_serie=f'M-{i}')
        Equipement.objects.create(
            company=self.company, produit=self.onduleur,
            installation=self.inst, numero_serie='O-1')
        raison = _gate_check_series(self.inst)
        self.assertIn('1 série de module manquante', raison)

    def test_non_releve_avec_motif_leve_la_garde(self):
        Equipement.objects.create(
            company=self.company, produit=self.onduleur,
            installation=self.inst, numero_serie='O-1')
        r = self.api.post(self.url, {'non_releves': [
            {'produit': self.module.id,
             'motif': 'Étiquettes illisibles'}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertIsNone(_gate_check_series(self.inst))

    def test_collage_avec_chaine(self):
        lignes = lire_lignes_series('A1;Chaîne 1\nA2;Chaîne 2\n\n',
                                    produit_defaut=7)
        self.assertEqual(lignes, [
            {'produit': 7, 'numero_serie': 'A1', 'chaine': 'Chaîne 1'},
            {'produit': 7, 'numero_serie': 'A2', 'chaine': 'Chaîne 2'}])

    def test_residentiel_gate_inchange(self):
        inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ633-20',
            type_installation='residentiel', bom=[
                {'produit_id': self.module.id, 'designation': 'Module',
                 'quantite': 10}])
        items = ensure_checklist_items(inst)
        attendu = (None if not any(it.capture_serie for it in items)
                   else _gate_check_series(inst))
        self.assertEqual(_gate_check_series(inst), attendu)
        Equipement.objects.create(company=self.company, produit=self.module,
                                  installation=inst, numero_serie='R-1')
        self.assertIsNone(_gate_check_series(inst))
