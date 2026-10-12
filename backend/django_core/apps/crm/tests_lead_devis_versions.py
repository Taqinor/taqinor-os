"""
QJR535 (Groupe QJR5) — la ligne devis de la fiche lead porte sa version et le
devis qui la remplace : le cockpit signale « Remplacé par … » au lieu de
laisser une V1 obsolète vivante et renvoyable.

Contrat partagé : ``apps/crm/contract_samples/lead_devis_ligne.json`` (QJR500,
clés ``is_active`` / ``version`` / ``superseded_by`` — ``is_active`` est servi
par QJR516). Aucun import de ``ventes.models`` côté crm : ``version`` et
``superseded_by`` sont des attributs de l'instance déjà chargée.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_lead_devis_versions"
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, Facture
from authentication.models import Company

User = get_user_model()

# VNT69 — clés EXACTES d'une ligne ``Lead.devis[]`` (avant == après la sortie
# de ``get_devis`` hors de serializers.py).
CLES_LIGNE_DEVIS = {
    'id', 'reference', 'statut', 'total_ttc', 'date_creation',
    'option_acceptee', 'chantier', 'share_link', 'lecture', 'modifiable',
    'raison_non_modifiable', 'revision_possible', 'is_active', 'version',
    'superseded_by', 'corrige_le',
}


# VNT70 — le DÉTAIL du lead sert en plus ``solde`` et ``vente`` (la LISTE
# garde les 16 clés ci-dessus : budget de requêtes 15 intact).
CLES_LIGNE_DEVIS_DETAIL = CLES_LIGNE_DEVIS | {'solde', 'vente'}

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_devis_ligne.json').read_text(encoding='utf-8'))


def _types(valeur):
    """Forme (clés + types) d'une valeur JSON, récursive ; ``factures`` et
    ``prochaines_echeances`` comparent la forme de leur 1er élément."""
    if isinstance(valeur, dict):
        return {k: _types(v) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [_types(valeur[0])] if valeur else []
    return type(valeur).__name__


class TestLeadDevisVersions(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR535 Co', slug='qjr535-co')
        self.user = User.objects.create_user(
            username='qjr535_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR535',
            email='qjr535@example.com', telephone='+212600000535')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR535',
            email='qjr535-lead@example.com', telephone='0612345535')

    def _devis(self, reference, **extra):
        return Devis.objects.create(
            company=self.company, reference=reference, lead=self.lead,
            client=self.client_obj, statut='envoye', taux_tva=20,
            remise_globale=0, created_by=self.user, **extra)

    def _lignes(self):
        r = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return {row['id']: row for row in r.json()['devis']}

    def test_v1_remplacee_expose_is_active_false_version_et_superseded_by(self):
        v2 = self._devis('DEV-QJR535-2', version=2)
        v1 = self._devis('DEV-QJR535-1', version=1, is_active=False,
                         superseded_by=v2)
        lignes = self._lignes()
        self.assertFalse(lignes[v1.id]['is_active'])
        self.assertEqual(lignes[v1.id]['version'], 1)
        self.assertEqual(lignes[v1.id]['superseded_by'], v2.id)

    def test_version_courante_superseded_by_null(self):
        v2 = self._devis('DEV-QJR535-B2', version=2)
        self._devis('DEV-QJR535-B1', version=1, is_active=False,
                    superseded_by=v2)
        ligne = self._lignes()[v2.id]
        self.assertTrue(ligne['is_active'])
        self.assertEqual(ligne['version'], 2)
        self.assertIsNone(ligne['superseded_by'])

    # VNT69 — ``get_devis`` sorti de serializers.py vers ``lead_devis_payload`` :
    # aucune clé ne change, la ligne servie == la sortie directe du module.
    def test_ligne_servie_porte_exactement_les_cles_epinglees(self):
        d = self._devis('DEV-VNT69-1', version=1)
        self.assertEqual(set(self._lignes()[d.id]), CLES_LIGNE_DEVIS_DETAIL)

    # ── VNT70 : ``solde`` et ``vente`` sur le DÉTAIL seulement ──────────────

    def _accepte_avec_factures(self, reference, nb_factures):
        d = self._devis(reference, version=1)
        d.statut = 'accepte'
        d.save(update_fields=['statut'])
        for i in range(nb_factures):
            Facture.objects.create(
                company=self.company, reference=f'FAC-{reference}-{i}',
                devis=d, client=self.client_obj,
                statut=Facture.Statut.EMISE, montant_ht=Decimal('100'),
                montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
                created_by=self.user)
        return d

    def test_detail_devis_accepte_forme_et_types_du_contrat(self):
        d = self._accepte_avec_factures('DEV-VNT70-A', 1)
        ligne = self._lignes()[d.id]
        attendu = CONTRAT['exemple_accepte']['devis'][0]
        self.assertEqual(set(ligne), set(attendu))
        self.assertEqual(_types(ligne['solde']), _types(attendu['solde']))
        self.assertEqual(set(ligne['vente']), set(attendu['vente']))
        # Types de chaque clé de ``vente`` (``factures`` : liste des deux
        # côtés, son contenu dépend du jeu d'essai).
        self.assertEqual(
            {k: type(v).__name__ for k, v in ligne['vente'].items()
             if k != 'revision_en_cours'},
            {k: type(v).__name__ for k, v in attendu['vente'].items()
             if k != 'revision_en_cours'})
        self.assertEqual(_types(ligne['vente']['peut']),
                         _types(attendu['vente']['peut']))

    def test_detail_devis_non_accepte_solde_et_vente_null(self):
        d = self._devis('DEV-VNT70-E', version=1)
        ligne = self._lignes()[d.id]
        self.assertIsNone(ligne['solde'])
        self.assertIsNone(ligne['vente'])
        self.assertEqual(set(ligne), set(CONTRAT['exemple']['devis'][0]))

    def test_liste_ne_sert_ni_solde_ni_vente(self):
        d = self._accepte_avec_factures('DEV-VNT70-L', 1)
        r = self.api.get('/api/django/crm/leads/')
        self.assertEqual(r.status_code, 200, r.content)
        corps = r.json()
        lignes = (corps['results'] if isinstance(corps, dict) else corps)
        devis = [x for lead in lignes if lead['id'] == self.lead.id
                 for x in lead['devis']]
        self.assertEqual({x['id'] for x in devis}, {d.id})
        for ligne in devis:
            self.assertEqual(set(ligne), CLES_LIGNE_DEVIS)

    def test_cout_constant_en_nombre_de_factures(self):
        d = self._accepte_avec_factures('DEV-VNT70-C', 1)
        url = f'/api/django/crm/leads/{self.lead.id}/'
        self.api.get(url)  # amorce les singletons de société
        with CaptureQueriesContext(connection) as a:
            self.assertEqual(self.api.get(url).status_code, 200)
        for i in range(1, 4):
            Facture.objects.create(
                company=self.company, reference=f'FAC-VNT70-C-{i}',
                devis=d, client=self.client_obj,
                statut=Facture.Statut.EMISE, montant_ht=Decimal('100'),
                montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
                created_by=self.user)
        with CaptureQueriesContext(connection) as b:
            r = self.api.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(a.captured_queries), len(b.captured_queries))
        self.assertEqual(len(r.json()['devis'][0]['vente']['factures']), 4)

    def test_module_payload_rend_les_memes_lignes_que_l_api(self):
        from apps.crm.lead_devis_payload import lignes_devis_du_lead
        v2 = self._devis('DEV-VNT69-B2', version=2)
        self._devis('DEV-VNT69-B1', version=1, is_active=False,
                    superseded_by=v2)
        servies = self.api.get(
            f'/api/django/crm/leads/{self.lead.id}/').json()['devis']
        # VNT70 — le détail sert ``solde`` / ``vente`` : le module, lui, les
        # rend sous le drapeau ``include_vente`` (posé par ``retrieve``).
        contexte = {'include_vente': True,
                    'request': SimpleNamespace(user=self.user)}
        directes = lignes_devis_du_lead(
            Lead.objects.prefetch_related('devis').get(pk=self.lead.pk),
            contexte)
        self.assertEqual(servies, directes)
