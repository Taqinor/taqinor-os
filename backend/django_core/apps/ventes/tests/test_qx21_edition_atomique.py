"""QJR544 (Groupe QJR5, contrat QJR504) — enregistrer une édition = UNE
transaction serveur via ``replace-lines`` : en-tête (``entete``) + lignes +
choix d'écran (``etude_params``), neutre pour le statut ; trace et instantané
dans la même transaction (UNE ligne de chatter par clic sur un envoyé).

Le corps envoyé reprend la FORME de l'exemple committé
``contract_samples/devis_replace_lines_entete.json`` (PACT10).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'devis_replace_lines_entete.json')


class TestEditionAtomique(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.company = Company.objects.create(
            nom='QJR544 Co', slug='qjr544-co')
        cls.user = User.objects.create_user(
            username='qjr544_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR544',
            email='qjr544@example.com', telephone='+212600005440')
        cls.panneau = Produit.objects.create(
            company=cls.company, nom='Panneau Canadien Solar 710W',
            sku='QJR544-PV', prix_vente=Decimal('1450'), quantite_stock=100)
        cls.onduleur = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau Huawei 5kW Monophasé',
            sku='QJR544-OND', prix_vente=Decimal('9000'), quantite_stock=10)

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, num, statut, company=None, client=None):
        devis = Devis.objects.create(
            company=company or self.company,
            reference=f'DEV-{MONTH}-{5440 + num * 10}',
            client=client or self.client_obj, statut=statut,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'), note='avant')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('8'), prix_unitaire=Decimal('1450'),
            remise=Decimal('0'))
        return devis

    def _lignes(self):
        return [
            {'produit': self.panneau.id, 'designation': self.panneau.nom,
             'quantite': '10', 'prix_unitaire': '1450.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 0},
            {'produit': self.onduleur.id, 'designation': self.onduleur.nom,
             'quantite': '1', 'prix_unitaire': '9000.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 1},
        ]

    def _post(self, devis, corps):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/', corps,
            format='json')

    def test_contrat_porte_entete_et_etude(self):
        corps = self.contrat['corps']
        self.assertIn('entete', corps)
        self.assertIn('etude_params', corps)
        self.assertNotIn('statut', corps['entete'])

    def test_ligne_invalide_rien_ne_change(self):
        devis = self._devis(1, Devis.Statut.BROUILLON)
        lignes = self._lignes()
        lignes[1]['produit'] = 999999  # produit inconnu → échec des lignes
        r = self._post(devis, {
            'lignes': lignes,
            'entete': {'remise_globale': '7', 'taux_tva': '10'}})
        self.assertEqual(r.status_code, 400, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.remise_globale, Decimal('0'))
        self.assertEqual(devis.taux_tva, Decimal('20'))
        self.assertEqual(devis.lignes.count(), 1)

    def test_entete_et_lignes_appliques_ensemble(self):
        devis = self._devis(2, Devis.Statut.BROUILLON)
        r = self._post(devis, {
            'lignes': self._lignes(),
            'entete': {'remise_globale': '5', 'note': 'après',
                       'date_validite': self.contrat['corps']['entete'][
                           'date_validite']},
            'etude_params': {'scenario': 'Sans batterie'}})
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.remise_globale, Decimal('5'))
        self.assertEqual(devis.note, 'après')
        self.assertEqual(devis.lignes.count(), 2)
        self.assertEqual(devis.etude_params.get('scenario'), 'Sans batterie')

    def test_statut_brouillon_sur_envoye_ignore(self):
        devis = self._devis(3, Devis.Statut.ENVOYE)
        r = self._post(devis, {
            'lignes': self._lignes(),
            'entete': {'statut': 'brouillon', 'note': 'corrigée'}})
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.note, 'corrigée')

    def test_accepte_409(self):
        devis = self._devis(4, Devis.Statut.ACCEPTE)
        r = self._post(devis, {'lignes': self._lignes(),
                               'entete': {'note': 'x'}})
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('revision_possible', r.json())
        devis.refresh_from_db()
        self.assertEqual(devis.note, 'avant')

    def test_autre_societe_404(self):
        autre = Company.objects.create(nom='QJR544 Autre', slug='qjr544-autre')
        client_autre = Client.objects.create(
            company=autre, nom='Autre', email='autre544@example.com')
        devis = self._devis(5, Devis.Statut.BROUILLON, company=autre,
                            client=client_autre)
        r = self._post(devis, {'lignes': self._lignes(),
                               'entete': {'note': 'x'}})
        self.assertEqual(r.status_code, 404, r.content)

    def test_envoye_corrige_une_seule_activite(self):
        devis = self._devis(6, Devis.Statut.ENVOYE)
        avant = DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi').count()
        r = self._post(devis, {
            'lignes': self._lignes(),
            'entete': {'note': 'corrigée', 'remise_globale': '2'},
            'etude_params': {'scenario': 'Sans batterie'}})
        self.assertEqual(r.status_code, 200, r.content)
        apres = DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi').count()
        self.assertEqual(apres - avant, 1)
