"""CIQ300 — garde serveur : plus aucune économie résidentielle, BT ou JS sur
la proposition en ligne d'un devis commercial ou industriel.

Avant : ``proposal_data`` et ``_data_pour_taille_detail`` ne vidaient
``eco_s_ann/eco_a_ann/eco_a_cumul/roi_s/roi_a`` que pour le résidentiel (Z2) ;
un site MT dont le PDF masque les économies affichait en ligne « Vous
économisez sur 25 ans » au barème BT, et un commercial sans étude publiait le
modèle résidentiel à 60 % (C3-01, C3-VB-01). ``_mode_kpis`` servait un
``payback`` lu dans l'étude JS persistée (prix pondéré par la consommation,
pointe comprise — C3-02).

Après : la fonction unique d'AGR300 (``_vider_economies_residentielles``)
s'applique aussi à commercial / industriel, avec la liste ``quote_vide_en_ci``
du contrat partagé ``proposal_data.json`` (CIQ4) ; ``mode_kpis`` ne sert plus
ni ``economies_annuelles`` ni ``payback`` (CIQ306 les projettera depuis
``synthese_ci``). Le calcul interne du builder reste intact (règle #4).

La charge utile est vérifiée en RÉEL (client Django, ``build_quote_data``
jamais mocké).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ciq300_proposition_ci_sans_economie_residentielle -v 2
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.ventes.public_views import (
    BLOCS_ECONOMIES_RESIDENTIELLES, CLES_ECONOMIES_RESIDENTIELLES,
    CLES_ECONOMIES_RESIDENTIELLES_CI, _data_pour_taille_detail, _mode_kpis,
    _vider_economies_residentielles,
)

User = get_user_model()

_CONTRAT = Path(__file__).resolve().parents[1] / 'contract_samples' / \
    'proposal_data.json'

LIGNES_CI = [
    ('Onduleur réseau Huawei 50kW Triphasé', '1', '60000'),
    ('Panneau Canadien Solar 710W', '100', '1150'),
    ('Structures acier', '100', '400'),
    ('Installation', '1', '60000'),
]
#: Ce que l'écran persiste pour un C&I (``etudeMarcheBloc.js``) : un payback
#: JS, jamais ``economies_annuelles``.
ETUDE_ECRAN_BT = {'taux_autoconso': 74, 'taux_couverture': 52,
                  'payback': 3.6, 'conso_annuelle': 160000,
                  'tension_raccordement': 'BT'}
ETUDE_MT = {'tension_raccordement': 'MT', 'taux_autoconso': 70,
            'taux_couverture': 48, 'payback': 3.2}
LIGNES_RESIDENTIEL = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '10', '1400'),
]
ETUDE_RESIDENTIEL = {
    'scenario': 'Sans batterie',
    'factures_mensuelles_reelles': [900] * 12,
    'distributeur': 'onee', 'ville': 'casablanca',
}
#: Blocs publics du modèle résidentiel ABSENTS en C&I (contrat CIQ4,
#: ``absents_en_ci``) que cette garde retire.
BLOCS_ABSENTS_CI = ('economies_mensuelles', 'economies_periodes',
                    'profils_comparatifs', 'tranche_tarifaire')


class Ciq300FonctionPureTests(SimpleTestCase):

    def test_liste_egale_au_contrat_partage(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        self.assertEqual(set(CLES_ECONOMIES_RESIDENTIELLES_CI),
                         set(contrat['notes_ciq4']['quote_vide_en_ci']))
        self.assertEqual(set(CLES_ECONOMIES_RESIDENTIELLES_CI),
                         set(contrat['exemple_commercial']['quote']))
        # Les blocs retirés font partie des absents C&I du contrat.
        self.assertLessEqual(set(BLOCS_ABSENTS_CI),
                             set(contrat['notes_ciq4']['absents_en_ci']))

    def test_ci_toutes_les_cles_a_none_et_blocs_retires(self):
        for mode in ('commercial', ' Industriel '):
            with self.subTest(mode=mode):
                data = {'mode_installation': mode,
                        'economies_mensuelles': {'x': 1},
                        'economies_periodes': {'y': 2}}
                for cle in CLES_ECONOMIES_RESIDENTIELLES_CI:
                    data[cle] = 123
                _vider_economies_residentielles(data)
                for cle in CLES_ECONOMIES_RESIDENTIELLES_CI:
                    self.assertIsNone(data[cle], cle)
                for bloc in BLOCS_ECONOMIES_RESIDENTIELLES:
                    self.assertNotIn(bloc, data)

    def test_agricole_garde_sa_liste_agr300(self):
        data = {'mode_installation': 'agricole'}
        _vider_economies_residentielles(data)
        for cle in CLES_ECONOMIES_RESIDENTIELLES:
            self.assertIsNone(data[cle])
        self.assertNotIn('facture_sans_solaire', data)

    def test_residentiel_intact(self):
        data = {'mode_installation': 'residentiel', 'eco_s_ann': 9000,
                'roi_s': 4.2, 'facture_sans_solaire': 12000}
        _vider_economies_residentielles(data)
        self.assertEqual(data['eco_s_ann'], 9000)
        self.assertEqual(data['roi_s'], 4.2)
        self.assertEqual(data['facture_sans_solaire'], 12000)

    def test_mode_kpis_ci_ne_lit_plus_l_etude_js(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                k = _mode_kpis({'mode_installation': mode, 'etude': {
                    'taux_autoconso': 74, 'taux_couverture': 52,
                    'economies_annuelles': 98000, 'payback': 3.6}})
                self.assertIsNone(k['payback'])
                self.assertIsNone(k['economies_annuelles'])
                self.assertEqual(k['taux_autoconso'], 74)
                contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
                self.assertEqual(
                    set(k), set(contrat['exemple_commercial']['mode_kpis']))


class Ciq300PropositionReelleTests(TestCase):

    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='ciq300-co', defaults={'nom': 'CIQ300 Co'})
        self.user = User.objects.create_user(
            username='ciq300', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Atlas', prenom='Hotel',
            email='ciq300@example.com', telephone='+212600000300')

    def _devis(self, ref, mode, lignes, etude):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            mode_installation=mode,
            etude_params=dict(etude) if etude is not None else None)
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
        from apps.ventes.models import ShareLink
        return ShareLink.objects.create(company=self.company, devis=devis,
                                        token=str(uuid.uuid4()))

    def _payload(self, lien):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def _cas(self):
        return (
            ('DEV-CIQ300-COMBT', 'commercial', None),          # BT sans étude
            ('DEV-CIQ300-COMJS', 'commercial', ETUDE_ECRAN_BT),
            ('DEV-CIQ300-INDMT', 'industriel', ETUDE_MT),      # MT
        )

    def test_charge_utile_ci_sans_economie_residentielle(self):
        for ref, mode, etude in self._cas():
            with self.subTest(ref=ref):
                devis = self._devis(ref, mode, LIGNES_CI, etude)
                p = self._payload(self._lien(devis))
                quote = p['quote']
                for cle in CLES_ECONOMIES_RESIDENTIELLES_CI:
                    self.assertIsNone(quote.get(cle), cle)
                for bloc in BLOCS_ABSENTS_CI:
                    self.assertNotIn(bloc, p)
                    self.assertNotIn(bloc, quote)
                self.assertIsNone(p['mode_kpis']['payback'])
                self.assertIsNone(p['mode_kpis']['economies_annuelles'])
                blob = json.dumps(p)
                self.assertNotIn('prix_achat', blob)
                self.assertNotIn('7777', blob)

    def test_preparation_jumelle_taille_detail_meme_garde(self):
        for ref, mode, etude in self._cas():
            with self.subTest(ref=ref):
                devis = self._devis(ref + 'T', mode, LIGNES_CI, etude)
                data, _resid = _data_pour_taille_detail(devis,
                                                        self._lien(devis))
                for cle in CLES_ECONOMIES_RESIDENTIELLES_CI:
                    self.assertIsNone(data.get(cle), cle)
                for bloc in BLOCS_ECONOMIES_RESIDENTIELLES:
                    self.assertNotIn(bloc, data)

    def test_le_calcul_interne_du_builder_reste_intact(self):
        """On cesse de REPUBLIER ; ``build_quote_data`` ne change pas."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-CIQ300-BLD', 'commercial', LIGNES_CI, None)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertGreater(data['eco_s_ann'] or 0, 0)

    def test_devis_residentiel_garde_ses_chiffres(self):
        devis = self._devis('DEV-CIQ300-RES', 'residentiel',
                            LIGNES_RESIDENTIEL, ETUDE_RESIDENTIEL)
        quote = self._payload(self._lien(devis))['quote']
        self.assertIsNotNone(quote.get('eco_s_ann'))
        self.assertIsNotNone(quote.get('roi_s'))
