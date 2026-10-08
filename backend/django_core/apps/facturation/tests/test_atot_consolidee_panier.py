"""ATOT3 (C-ATOT-002) — la facture consolidée recopie, devis par devis,
EXACTEMENT le panier de `copier_devis_sur_facture` (option effective, lignes
comptées seulement, taux par ligne, remise et palier du devis) : son TTC
égale Σ TTC des devis au centime, et une ligne de section ne fait plus 500.

Rejoue la sonde V1 TFAC-2 : aujourd'hui 300 000 au lieu de 270 000 (remise
perdue), l'option non activée comptée, la ligne sans taux au taux de tête de
la facture (20 %) au lieu de celui du devis, et `TypeError` → 500 sur une
section. Endpoint réel, aucun mock ; l'oracle est `option_totaux` (réel).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_consolidee_panier"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class ConsolideePanierTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT3 Co', slug=f'atot3-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Panier', prenom='ATOT3',
            email=f'atot3-{_nxt()}@example.invalid')
        self.user = User.objects.create_user(
            username=f'atot3_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, lignes, *, taux='20.00', remise='0', **extra):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT3-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal(taux), remise_globale=Decimal(remise), **extra)
        for li in lignes:
            LigneDevis.objects.create(devis=devis, **li)
        return Devis.objects.get(pk=devis.pk)

    @staticmethod
    def _ligne(pu, taux='20.00', **extra):
        return {'designation': extra.pop('designation', 'Centrale'),
                'quantite': Decimal('1'), 'prix_unitaire': Decimal(pu),
                'remise': Decimal('0'),
                'taux_tva': None if taux is None else Decimal(taux), **extra}

    def _consolider(self, *devis):
        return self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [d.id for d in devis]}, format='json')

    def _attendu(self, *devis):
        from apps.ventes.utils.options import option_totaux
        return sum((Decimal(str(option_totaux(d)['ttc'])) for d in devis),
                   Decimal('0'))

    def _facture(self, resp):
        from apps.ventes.models import Facture
        self.assertEqual(resp.status_code, 201, resp.data)
        return Facture.objects.get(pk=resp.data['id'])

    def test_remise_par_devis(self):
        d1 = self._devis([self._ligne('125000')], remise='10')
        d2 = self._devis([self._ligne('125000')], remise='10')
        self.assertEqual(self._attendu(d1, d2), Decimal('270000.00'))
        facture = self._facture(self._consolider(d1, d2))
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('270000.00'))
        # Persistance : relu par l'API.
        resp = self.api.get(f'/api/django/ventes/factures/{facture.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(str(resp.data['total_ttc'])),
                         Decimal('270000.00'))

    def test_remises_differentes_refusees(self):
        from apps.ventes.models import Facture
        d1 = self._devis([self._ligne('125000')], remise='10')
        d2 = self._devis([self._ligne('125000')], remise='5')
        resp = self._consolider(d1, d2)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(d1.reference, str(resp.data))
        self.assertIn(d2.reference, str(resp.data))
        self.assertFalse(Facture.objects.filter(
            company=self.company).exists())

    def test_optionnelle_exclue(self):
        d1 = self._devis([self._ligne('125000')])
        d2 = self._devis([self._ligne('125000'),
                          self._ligne('10000', optionnelle=True,
                                      designation='Option non activée')])
        self.assertEqual(self._attendu(d1, d2), Decimal('300000.00'))
        facture = self._facture(self._consolider(d1, d2))
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('300000.00'))
        self.assertFalse(facture.lignes.filter(
            designation__contains='Option non activée').exists())

    def test_taux_ligne_null(self):
        d1 = self._devis([self._ligne('125000', taux='10.00')], taux='10.00')
        d2 = self._devis([self._ligne('125000', taux=None)], taux='10.00')
        self.assertEqual(self._attendu(d1, d2), Decimal('275000.00'))
        facture = self._facture(self._consolider(d1, d2))
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('275000.00'))

    def test_section_ignoree(self):
        d1 = self._devis([self._ligne('125000')])
        d2 = self._devis([
            {'designation': 'Section matériel', 'type_ligne': 'section',
             'quantite': None, 'prix_unitaire': None},
            self._ligne('125000')])
        facture = self._facture(self._consolider(d1, d2))
        self.assertEqual(Decimal(str(facture.total_ttc)), self._attendu(d1, d2))
        self.assertFalse(facture.lignes.filter(
            designation__contains='Section matériel').exists())

    def test_deux_options_option_effective(self):
        from apps.ventes.models import Devis
        d1 = self._devis([self._ligne('20000', designation='Pose')])
        d2 = self._devis(
            [self._ligne('11700', designation='Onduleur réseau'),
             self._ligne('24000', designation='Onduleur hybride'),
             self._ligne('15400', designation='Panneau mono 550W'),
             self._ligne('14000', designation='Batterie 5 kWh')],
            etude_params={'scenario': 'Les deux (Sans + Avec)'},
            option_acceptee=Devis.OptionAcceptee.SANS_BATTERIE)
        facture = self._facture(self._consolider(d1, d2))
        self.assertEqual(Decimal(str(facture.total_ttc)), self._attendu(d1, d2))
        designations = list(facture.lignes.values_list('designation',
                                                       flat=True))
        self.assertFalse(any('Batterie' in d for d in designations))
        self.assertFalse(any('hybride' in d for d in designations))
