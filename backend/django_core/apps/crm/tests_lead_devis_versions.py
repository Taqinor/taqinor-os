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
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_devis_ligne.json').read_text(encoding='utf-8'))


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

    def test_vnt69_lignes_servies_par_lead_devis_payload_cles_inchangees(self):
        """VNT69 — ``get_devis`` délègue à ``lead_devis_payload`` : la ligne
        servie par l'API est exactement celle du module, mêmes clés."""
        from apps.crm.lead_devis_payload import lignes_devis_du_lead
        v1 = self._devis('DEV-QJR535-C1')
        ligne = self._lignes()[v1.id]
        directe = lignes_devis_du_lead(Lead.objects.get(pk=self.lead.pk),
                                       {'include_vente': True})
        self.assertEqual(set(directe[0]), set(ligne))
        self.assertEqual(set(ligne) >= {
            'id', 'reference', 'statut', 'total_ttc', 'date_creation',
            'option_acceptee', 'chantier', 'share_link', 'lecture',
            'version', 'superseded_by', 'corrige_le', 'is_active'}, True)

    # ── VNT70 — `solde` et `vente` au DÉTAIL du lead ──────────────────────
    def _facture(self, devis, n):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-VNT70-{devis.pk}-{n}',
            devis=devis, client=self.client_obj,
            statut=Facture.Statut.EMISE, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            created_by=self.user)

    def _chaine_acceptee(self):
        v2 = self._devis('DEV-VNT70-2', version=2)
        v1 = self._devis('DEV-VNT70-1', version=1, is_active=False,
                         superseded_by=v2)
        Devis.objects.filter(pk=v2.pk).update(version_parent=v1)
        Devis.objects.filter(pk__in=[v1.pk, v2.pk]).update(statut='accepte')
        return v1, v2

    def _detail_mesure(self):
        with CaptureQueriesContext(connection) as ctx:
            lignes = self._lignes()
        return lignes, len(ctx.captured_queries)

    def test_vnt70_ligne_acceptee_cles_et_types_du_contrat(self):
        """Une ligne ACCEPTÉE servie au détail a les clés ET les types de
        ``exemple_accepte`` (``solde`` en texte, ``vente`` du contrat
        ``vente_etat.json``) ; une ligne envoyée porte ``solde``/``vente``
        null."""
        _v1, v2 = self._chaine_acceptee()
        envoye = self._devis('DEV-VNT70-E')
        self._facture(v2, 1)
        lignes = self._lignes()
        attendu = CONTRAT['exemple_accepte']['devis'][0]
        ligne = lignes[v2.id]
        self.assertEqual(set(ligne), set(attendu))
        for cle, valeur in attendu.items():
            if valeur is not None:
                self.assertIsInstance(ligne[cle], type(valeur), cle)
        self.assertEqual(set(ligne['solde']), set(attendu['solde']))
        self.assertTrue(all(isinstance(v, str)
                            for v in ligne['solde'].values()))
        self.assertEqual(set(ligne['vente']), set(attendu['vente']))
        self.assertEqual(ligne['vente']['emis_ttc'], '1200.00')
        self.assertIsNone(lignes[envoye.id]['solde'])
        self.assertIsNone(lignes[envoye.id]['vente'])

    def test_get_devis_sert_le_solde(self):
        """ATOT39 — devis accepté à facture COMPLÈTE émise : la ligne du
        détail du lead porte ``solde.porte_facturation == 'aucune'`` et
        ``facturation_terminee`` vrai (texte, contrat ``devis_solde.json``) :
        l'onglet Devis masque « Facturer »."""
        devis = self._devis('DEV-ATOT39-10')
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        self._facture(devis, 1)
        solde = self._lignes()[devis.id]['solde']
        self.assertEqual(solde['porte_facturation'], 'aucune')
        self.assertEqual(solde['facturation_terminee'], 'True')
        self.assertEqual(solde['tranches_facturees'], '0')

    def test_vnt70_liste_des_leads_sans_solde_ni_vente(self):
        self._chaine_acceptee()
        r = self.api.get('/api/django/crm/leads/', {'page_size': 100})
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        leads = data.get('results', data) if isinstance(data, dict) else data
        lignes = [x for lead in leads for x in lead.get('devis') or []]
        self.assertTrue(all('vente' not in x and 'solde' not in x
                            for x in lignes))

    def test_vnt70_cout_constant_en_nombre_de_factures(self):
        """Chaîne acceptée V1 → V2 : 1 puis 3 factures ⇒ même nombre de
        requêtes (``etat_vente_map`` lit la vente en lot)."""
        v1, v2 = self._chaine_acceptee()
        self._facture(v1, 1)
        _lignes, une = self._detail_mesure()
        self._facture(v2, 2)
        self._facture(v2, 3)
        lignes, trois = self._detail_mesure()
        self.assertEqual(len(lignes[v2.id]['vente']['factures']), 3)
        self.assertEqual(une, trois)
        # Plafond DÉRIVÉ (détail 15 sans devis + lignes devis + lot de la
        # vente) — la mesure CI fait foi.
        self.assertLessEqual(trois, 80)
