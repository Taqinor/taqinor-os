"""CIQ219 — Réviser V2, dupliquer, variante, variante-gamme, renouveler : un
devis C&I recopie ses entrées (tarif déclaré, saisies d'économie, jalons,
retenue, pénalités, caution, payeur tiers) — jamais sa référence de commande
sur une duplication. Sans mock des chemins de copie (seul le réseau PVGIS
l'est, patron CIQ210).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq219_copies_ci"
"""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

TARIF = {'source': 'facture', 'prix_kwh_ht': 1.35,
         'note': 'saisi, illustratif'}
SAISIES = {'tva_recuperable': 'oui', 'taux_actualisation_pct': 6}
JALONS = [
    {'pct_or_montant': 40, 'jalon': 'commande'},
    {'pct_or_montant': 50, 'jalon': 'mise_en_service',
     'delai_reglement_jours': 30},
    {'pct_or_montant': 10, 'jalon': 'reception_definitive',
     'payeur': 'tiers'},
]
RETENUE = {'taux_pct': 5.0, 'liberation': 'reception_definitive'}
PENALITES = {'taux_pct_par_semaine': 0.5, 'plafond_pct': 5}
CAUTION = {'nature': 'caution bancaire', 'montant_ou_pct': '5 %',
           'plafond': '10 %'}
CONDITIONS = ('retenue_garantie', 'penalites_retard_livraison', 'caution')


class CopiesDevisCITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        cls.co = Company.objects.get_or_create(
            slug='ciq219-co', defaults={'nom': 'CIQ219 Co'})[0]
        cls.client_obj = Client.objects.create(
            company=cls.co, nom='Supermarché Atlas', email='ciq219@ex.com')
        cls.financeur = Client.objects.create(
            company=cls.co, nom='Banque Verte', email='fin219@ex.com')
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1300'),
            prix_achat=Decimal('1'))
        cls.ond = Produit.objects.create(
            company=cls.co, nom='Onduleur réseau 50kW Triphasé',
            prix_vente=Decimal('40000'), prix_achat=Decimal('1'),
            role_devis='onduleur_reseau')

    def setUp(self):
        from apps.ventes.domain import etude_ci
        from apps.ventes.tests.test_ciq118_etude_ci_preview import (
            _production_casablanca)
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq219_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.source = self._source()

    def _source(self):
        devis = Devis.objects.create(
            company=self.co, reference='DEV-202610-2190',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='commercial',
            etude_params={'tarif_declare': json.loads(json.dumps(TARIF)),
                          'saisies_economie_ci': json.loads(
                              json.dumps(SAISIES))},
            echeancier=json.loads(json.dumps(JALONS)),
            tiers_payeur=self.financeur,
            retenue_garantie=dict(RETENUE),
            penalites_retard_livraison=dict(PENALITES),
            caution=dict(CAUTION),
            reference_commande_client='BC-2026-0457')
        for ordre, (produit, qte, prix) in enumerate((
                (self.panneau, 70, '1300'), (self.ond, 1, '40000'))):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), taux_tva=Decimal('20'), ordre=ordre)
        return devis

    def _post(self, chemin, corps=None, statut_source=None):
        if statut_source:
            Devis.objects.filter(pk=self.source.pk).update(
                statut=statut_source)
        rep = self.api.post('/api/django/ventes/devis/%s/%s/'
                            % (self.source.pk, chemin), corps or {},
                            format='json')
        self.assertEqual(rep.status_code, 201, rep.content[:500])
        return rep.json()

    def _copies(self):
        """(chemin, copie, référence de commande attendue)."""
        yield 'dupliquer', self._post('dupliquer')['id'], ''
        variantes = self._post('dupliquer-variante', {'scales': [1.0]})
        yield 'variante', variantes[0]['id'], ''
        yield 'gamme', self._post('dupliquer-variante-gamme',
                                  {'nom': 'Premium'})['gamme']['id'], ''
        yield 'renouveler', self._post('renouveler',
                                       statut_source='expire')['id'], ''
        yield 'reviser', self._post('reviser')['id'], 'BC-2026-0457'

    def test_les_cinq_chemins(self):
        for chemin, copie_id, reference in self._copies():
            with self.subTest(chemin=chemin):
                copie = Devis.objects.get(pk=copie_id)
                self.assertEqual(copie.statut, 'brouillon')
                self.assertEqual(copie.tiers_payeur_id, self.financeur.pk)
                self.assertEqual(copie.retenue_garantie, RETENUE)
                self.assertEqual(copie.penalites_retard_livraison, PENALITES)
                self.assertEqual(copie.caution, CAUTION)
                self.assertEqual(copie.reference_commande_client, reference)
                self.assertEqual(copie.etude_params['tarif_declare'], TARIF)
                self.assertEqual(copie.etude_params['saisies_economie_ci'],
                                 SAISIES)
                self.assertNotIn('etude_ci', copie.etude_params or {})
                self.assertEqual(
                    [t.get('jalon') for t in copie.echeancier],
                    ['commande', 'mise_en_service', 'reception_definitive'])

    def test_modifier_la_copie_ne_modifie_pas_la_source(self):
        from apps.ventes.domain.creation_clone import dupliquer_devis
        copie = dupliquer_devis(self.source, user=self.user)
        copie.etude_params['tarif_declare']['prix_kwh_ht'] = 9.99
        copie.retenue_garantie['taux_pct'] = 7.0
        copie.save(update_fields=['etude_params', 'retenue_garantie'])
        self.assertEqual(self.source.etude_params['tarif_declare'], TARIF)
        self.assertEqual(self.source.retenue_garantie, RETENUE)
        self.source.refresh_from_db()
        self.assertEqual(self.source.etude_params['tarif_declare'], TARIF)
        self.assertEqual(self.source.retenue_garantie, RETENUE)

    def test_aucun_statut_source_touche_par_la_duplication(self):
        statut = self.source.statut
        self._post('dupliquer')
        self.source.refresh_from_db()
        self.assertEqual(self.source.statut, statut)
        self.assertEqual(self.source.reference_commande_client,
                         'BC-2026-0457')
