"""AGR300 — garde serveur : aucune « Économie / an » ni « Rentabilisé en »
RÉSIDENTIELS ne sort sur la proposition d'un devis AGRICOLE.

Avant : ``builder`` appelle ``calculate_savings_roi`` pour TOUT mode, et
``proposal_data`` / ``_data_pour_taille_detail`` ne vidaient ces clés que si
``is_residential(...)`` — faux en agricole. Un devis de pompage servait donc
des économies calculées comme si le champ PV remplaçait de l'électricité ONEE,
alors que son PDF n'en imprime aucune.

La charge utile est vérifiée en RÉEL (client Django, ``build_quote_data``
jamais mocké) ; un devis résidentiel garde ses chiffres (non-régression).
"""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import (
    BLOCS_ECONOMIES_RESIDENTIELLES, CLES_ECONOMIES_RESIDENTIELLES,
    _data_pour_taille_detail, _vider_economies_residentielles,
)

User = get_user_model()

LIGNES_POMPAGE = [
    ('Pompe immergée OSP 30/8 10 CV', '1', '18000'),
    ('Variateur VEICHI 7,5 kW', '1', '9000'),
    ('Panneau mono 550W', '20', '1100'),
    ('Structures acier', '20', '375'),
]
ETUDE_POMPAGE = {
    'pompe_cv': '10', 'pompe_kw': 7.5, 'type_pompe': 'immergee',
    'alim': 'tri', 'hmt_m': '60', 'debit_hmt_m3h': 30,
    'heures_pompage': 7, 'm3_jour': 210, 'champ_kwc': 10.65,
}
LIGNES_RESIDENTIEL = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '10', '1400'),
]
ETUDE_RESIDENTIEL = {
    'scenario': 'Sans batterie',
    'factures_mensuelles_reelles': [900] * 12,
    'distributeur': 'onee', 'ville': 'casablanca',
}


class Agr300FonctionPureTests(SimpleTestCase):

    def test_agricole_toutes_les_cles_a_none_et_blocs_retires(self):
        data = {'mode_installation': 'Agricole ',
                'economies_mensuelles': {'x': 1},
                'economies_periodes': {'y': 2}}
        for cle in CLES_ECONOMIES_RESIDENTIELLES:
            data[cle] = 123
        _vider_economies_residentielles(data)
        for cle in CLES_ECONOMIES_RESIDENTIELLES:
            with self.subTest(cle=cle):
                self.assertIsNone(data[cle])
        for bloc in BLOCS_ECONOMIES_RESIDENTIELLES:
            self.assertNotIn(bloc, data)

    def test_residentiel_intact(self):
        data = {'mode_installation': 'residentiel', 'eco_s_ann': 9000,
                'roi_s': 4.2}
        _vider_economies_residentielles(data)
        self.assertEqual(data['eco_s_ann'], 9000)
        self.assertEqual(data['roi_s'], 4.2)


class Agr300PropositionReelleTests(TestCase):

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='agr300-co', defaults={'nom': 'AGR300 Co'})
        self.user = User.objects.create_user(
            username='agr300', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Fellah', prenom='Ali',
            email='agr300@example.com', telephone='+212600000300')

    def _devis(self, ref, mode, lignes, etude):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            mode_installation=mode, etude_params=dict(etude))
        for i, (desig, qty, pu) in enumerate(lignes):
            p = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{ref[-6:]}-{i}',
                prix_vente=Decimal(pu), prix_achat=Decimal('7777'),
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=p, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), ordre=i)
        return devis

    def _lien(self, devis):
        return ShareLink.objects.create(company=self.company, devis=devis,
                                        token=str(uuid.uuid4()))

    def _payload(self, lien):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def test_devis_agricole_aucune_economie_residentielle_publique(self):
        devis = self._devis('DEV-AGR300-AGRI', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        p = self._payload(self._lien(devis))
        quote = p['quote']
        for cle in CLES_ECONOMIES_RESIDENTIELLES:
            with self.subTest(cle=cle):
                self.assertIsNone(quote.get(cle))
        for bloc in BLOCS_ECONOMIES_RESIDENTIELLES:
            with self.subTest(bloc=bloc):
                self.assertNotIn(bloc, p)
                self.assertNotIn(bloc, quote)
        blob = json.dumps(p)
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('7777', blob)

    def test_preparation_jumelle_taille_detail_meme_garde(self):
        devis = self._devis('DEV-AGR300-TWIN', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        data, _resid = _data_pour_taille_detail(devis, self._lien(devis))
        for cle in CLES_ECONOMIES_RESIDENTIELLES:
            with self.subTest(cle=cle):
                self.assertIsNone(data.get(cle))
        for bloc in BLOCS_ECONOMIES_RESIDENTIELLES:
            self.assertNotIn(bloc, data)

    def test_le_calcul_interne_du_builder_reste_intact(self):
        """On cesse de REPUBLIER ; ``build_quote_data`` ne change pas."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-AGR300-BLD', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIn('eco_s_ann', data)
        self.assertIn('roi_s', data)

    def test_devis_residentiel_garde_ses_chiffres(self):
        devis = self._devis('DEV-AGR300-RES', 'residentiel',
                            LIGNES_RESIDENTIEL, ETUDE_RESIDENTIEL)
        quote = self._payload(self._lien(devis))['quote']
        self.assertIsNotNone(quote.get('eco_s_ann'))
        self.assertIsNotNone(quote.get('roi_s'))
