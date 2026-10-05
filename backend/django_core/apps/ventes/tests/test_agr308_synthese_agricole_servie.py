"""AGR308 — ``proposal_data`` sert ``synthese_agricole`` : la MÊME fonction
que le PDF, prouvée par un test de parité (patron
``test_pvcov_synthese_servie.py``).

La charge utile est lue en RÉEL (client Django, ``build_quote_data`` jamais
mocké). Seul le bloc d'économie AGR3 est fourni par un ``patch`` du sélecteur
(il relit l'étude de pompage serveur et PVGIS — hors sujet ici) : sa valeur
est l'``exemple`` du contrat partagé ``economie_pompage.json``.
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
from apps.ventes.quote_engine.builder import build_quote_data

User = get_user_model()

_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'

LIGNES_POMPAGE = [
    ('Pompe immergée OSP 30/8 10 CV', '1', '18000'),
    ('Variateur VEICHI 7,5 kW', '1', '9000'),
    ('Panneau mono 550W', '20', '1100'),
    ('Structures acier', '20', '375'),
]
LIGNES_RESIDENTIEL = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '10', '1400'),
]
ETUDE_POMPAGE = {
    'pompe_cv': '10', 'pompe_kw': 7.5, 'type_pompe': 'immergee',
    'alim': 'tri', 'hmt_m': '60', 'debit_hmt_m3h': 30,
    'heures_pompage': 7, 'm3_jour': 210, 'champ_kwc': 10.65,
    'saisies_economie_pompage': {
        'energie_actuelle': {
            'valeur': 'butane',
            'provenance': {'origine': 'saisie', 'detail': None,
                           'date': '2026-09-12'}}},
}


def _bloc_agr3_public():
    bloc = json.loads((_CONTRATS / 'economie_pompage.json').read_text(
        encoding='utf-8'))['exemple']
    bloc.pop('vue_interne', None)
    return bloc


def _parcours_cles(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _parcours_cles(v)
    elif isinstance(o, list):
        for v in o:
            yield from _parcours_cles(v)


_PATCH_ECO = 'apps.ventes.selectors.economie_pompage_publique_pour_devis'


class Agr308SyntheseAgricoleServieTests(TestCase):

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='agr308-co', defaults={'nom': 'AGR308 Co'})
        self.user = User.objects.create_user(
            username='agr308', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Fellah', prenom='Ali',
            email='agr308@example.com', telephone='+212600000308')

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

    def _payload(self, devis, sections=None):
        lien = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()),
            **({'sections': sections} if sections is not None else {}))
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def test_parite_cle_par_cle_avec_le_calcul_du_pdf(self):
        devis = self._devis('DEV-AGR308-A', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        with mock.patch(_PATCH_ECO, return_value=_bloc_agr3_public()):
            payload = self._payload(devis)
            attendu = synthese_agricole(
                build_quote_data(devis, {'pdf_mode': 'full'}))
        servie = payload['synthese_agricole']
        # Le passage JSON de la réponse : on compare sur la même forme.
        attendu = json.loads(json.dumps(attendu))
        self.assertEqual(set(servie), set(attendu))
        for cle in attendu:
            with self.subTest(cle=cle):
                self.assertEqual(servie[cle], attendu[cle])
        self.assertIn('economies', servie)
        self.assertIn('schema_svg', servie)

    def test_cle_absente_pour_un_residentiel(self):
        devis = self._devis('DEV-AGR308-R', 'residentiel', LIGNES_RESIDENTIEL,
                            {'scenario': 'Sans batterie'})
        payload = self._payload(devis)
        self.assertNotIn('synthese_agricole', payload)

    def test_aucun_prix_achat_ni_cle_interne(self):
        devis = self._devis('DEV-AGR308-P', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        bloc = _bloc_agr3_public()
        bloc['vue_interne'] = {'van_mad': 1.0}
        with mock.patch(_PATCH_ECO, return_value=bloc):
            payload = self._payload(devis)
        cles = set(_parcours_cles(payload['synthese_agricole']))
        self.assertNotIn('prix_achat', cles)
        self.assertNotIn('vue_interne', cles)
        # Le bloc AGR3 brut ne ressort jamais par ``quote`` (clé préfixée).
        self.assertNotIn('_economie_pompage', payload['quote'])
        self.assertNotIn('economie_pompage', payload['quote'])

    def test_case_economies_decochee_retire_l_argent(self):
        devis = self._devis('DEV-AGR308-S', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        with mock.patch(_PATCH_ECO, return_value=_bloc_agr3_public()):
            payload = self._payload(devis, sections={'economies': False})
        servie = payload['synthese_agricole']
        self.assertNotIn('economies', servie)
        self.assertIn('eau', servie)

    def test_forme_conforme_au_fragment_exemple_agricole(self):
        contrat = json.loads((_CONTRATS / 'proposal_data.json').read_text(
            encoding='utf-8'))['exemple_agricole']['synthese_agricole']
        devis = self._devis('DEV-AGR308-F', 'agricole', LIGNES_POMPAGE,
                            ETUDE_POMPAGE)
        with mock.patch(_PATCH_ECO, return_value=_bloc_agr3_public()):
            servie = self._payload(devis)['synthese_agricole']
        self.assertEqual(sorted(set(servie) - set(contrat)), [],
                         "clé de synthese_agricole non déclarée au contrat")
        for cle in servie:
            if servie[cle] is None or contrat[cle] is None:
                continue
            with self.subTest(cle=cle):
                self.assertEqual(type(servie[cle]).__name__ in ('int', 'float'),
                                 type(contrat[cle]).__name__ in ('int', 'float'))
                if not isinstance(servie[cle], (int, float)):
                    self.assertIs(type(servie[cle]), type(contrat[cle]))
