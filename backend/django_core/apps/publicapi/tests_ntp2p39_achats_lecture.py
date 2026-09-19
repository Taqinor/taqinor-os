"""NTP2P39 — exposition LECTURE SEULE des objets Procure-to-Pay par clé d'API.

Critère d'acceptation : « une clé API scoped `lecture_achats` peut lister les
demandes d'achat de sa société sans exposer les prix d'achat internes. » Les
deux moitiés sont vérifiées, et la seconde l'est sur le RENDU sérialisé complet
(pas sur une liste de champs déclarés) — un prix qui fuiterait par une clé
imbriquée serait attrapé.
"""
import json
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.installations.models_demande_achat import (
    DemandeAchat, DemandeAchatLigne,
)
from apps.installations.models_rfq import RFQ, RFQConsultation, RFQOffre
from apps.stock.models import Fournisseur, Produit

from .constants import ALL_SCOPES, SCOPE_READ_ACHATS, SCOPE_READ_LEADS
from .models import ApiKey

URL_DEMANDES = '/api/public/v1/achats/demandes-achat/'
URL_RFQ = '/api/public/v1/achats/rfq/'

# Secrets distinctifs à 5 chiffres : s'ils apparaissent dans le rendu, c'est
# une fuite, et le message d'échec les montre sans ambiguïté.
PRIX_ACHAT_UNITAIRE = Decimal('81234.00')
MONTANT_OFFRE_RETENUE = Decimal('97531.00')


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntp2p39ScopeTests(TestCase):
    def test_le_scope_est_declare_au_catalogue(self):
        """Sans cette déclaration, `ApiKey.issue` filtrerait le scope
        silencieusement et la clé n'ouvrirait rien (garde NTAPI42)."""
        self.assertIn(SCOPE_READ_ACHATS, ALL_SCOPES)
        self.assertEqual(SCOPE_READ_ACHATS, 'lecture_achats')


class Ntp2p39DemandeAchatTests(TestCase):
    def setUp(self):
        self.co = _company('ntp2p39', 'NTP2P39')
        self.autre = _company('ntp2p39-autre', 'NTP2P39 autre')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 550 Wc', sku='PV-550',
            prix_vente=Decimal('1250.00'),
            prix_achat=PRIX_ACHAT_UNITAIRE)
        self.demande = DemandeAchat.objects.create(
            company=self.co, reference='DA-202609-0001',
            objet='12 panneaux pour le chantier Bouskoura',
            statut=DemandeAchat.Statut.SOUMISE,
            priorite=DemandeAchat.Priorite.HAUTE)
        DemandeAchatLigne.objects.create(
            demande=self.demande, produit=self.produit,
            designation='Panneau 550 Wc', quantite=Decimal('12'),
            prix_estime=PRIX_ACHAT_UNITAIRE)
        _key, self.raw = ApiKey.issue(
            company=self.co, label='achats', scopes=[SCOPE_READ_ACHATS])
        _ro, self.raw_autre_scope = ApiKey.issue(
            company=self.co, label='leads', scopes=[SCOPE_READ_LEADS])

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_une_cle_lecture_achats_liste_ses_demandes(self):
        resp = _key_client(self.raw).get(URL_DEMANDES)
        self.assertEqual(resp.status_code, 200, resp.content)
        resultats = resp.data['results']
        self.assertEqual(len(resultats), 1)
        ligne = resultats[0]
        self.assertEqual(ligne['reference'], 'DA-202609-0001')
        self.assertEqual(ligne['statut'], DemandeAchat.Statut.SOUMISE)
        self.assertEqual(ligne['priorite'], DemandeAchat.Priorite.HAUTE)
        self.assertIn('montant_estime', ligne)

    def test_aucun_prix_dachat_interne_dans_le_rendu(self):
        """Scanné sur le RENDU sérialisé complet : une fuite par une clé
        imbriquée (`lignes`, `fournisseur_suggere`…) serait attrapée ici."""
        resp = _key_client(self.raw).get(URL_DEMANDES)
        rendu = json.dumps(resp.data, default=str)
        # Le prix unitaire ESTIMÉ (un prix d'achat) ne sort jamais…
        self.assertNotIn('81234', rendu)
        # …et les lignes qui le portent ne sont pas exposées du tout.
        self.assertNotIn('lignes', rendu)
        self.assertNotIn('prix_estime', rendu)
        self.assertNotIn('prix_achat', rendu)
        self.assertNotIn('fournisseur_suggere', rendu)

    def test_le_montant_estime_est_lagregat_demande_par_le_plan(self):
        """12 × 81 234 = 974 808. L'agrégat sort ; ni la quantité ni le nombre
        de lignes ne sortent, donc aucun prix unitaire n'est reconstituable."""
        resp = _key_client(self.raw).get(URL_DEMANDES)
        ligne = resp.data['results'][0]
        self.assertEqual(Decimal(str(ligne['montant_estime'])),
                         Decimal('974808.00'))
        self.assertNotIn('quantite', ligne)

    def test_une_autre_societe_est_invisible(self):
        DemandeAchat.objects.create(
            company=self.autre, reference='DA-AUTRE-0001',
            objet="Pas à moi", statut=DemandeAchat.Statut.SOUMISE)
        resp = _key_client(self.raw).get(URL_DEMANDES)
        references = [lig['reference'] for lig in resp.data['results']]
        self.assertEqual(references, ['DA-202609-0001'])

    def test_une_cle_dun_autre_scope_est_refusee(self):
        resp = _key_client(self.raw_autre_scope).get(URL_DEMANDES)
        self.assertEqual(resp.status_code, 403)

    def test_sans_cle_cest_un_401(self):
        self.assertEqual(APIClient().get(URL_DEMANDES).status_code, 401)

    def test_lecture_seule_stricte(self):
        api = _key_client(self.raw)
        self.assertEqual(
            api.post(URL_DEMANDES, {'objet': 'x'}, format='json').status_code,
            405)
        self.assertEqual(
            api.delete(f'{URL_DEMANDES}{self.demande.pk}/').status_code, 405)

    def test_filtre_en_liste_blanche(self):
        api = _key_client(self.raw)
        self.assertEqual(
            len(api.get(URL_DEMANDES, {'statut': 'soumise'}).data['results']), 1)
        self.assertEqual(
            len(api.get(URL_DEMANDES, {'statut': 'approuvee'}).data['results']), 0)
        # Un filtre hors liste blanche est un 400 explicite, jamais un 500.
        self.assertEqual(
            api.get(URL_DEMANDES, {'montant_estime': '1'}).status_code, 400)

    def test_detail_cross_tenant_est_un_404(self):
        etrangere = DemandeAchat.objects.create(
            company=self.autre, reference='DA-AUTRE-0002', objet='x',
            statut=DemandeAchat.Statut.SOUMISE)
        resp = _key_client(self.raw).get(f'{URL_DEMANDES}{etrangere.pk}/')
        self.assertEqual(resp.status_code, 404)


class Ntp2p39RfqTests(TestCase):
    def setUp(self):
        self.co = _company('ntp2p39-rfq', 'NTP2P39 RFQ')
        self.retenu = Fournisseur.objects.create(
            company=self.co, nom='Fournisseur retenu')
        self.perdant = Fournisseur.objects.create(
            company=self.co, nom='Fournisseur perdant')
        self.rfq = RFQ.objects.create(
            company=self.co, reference='RFQ-202609-0001',
            objet='Panneaux 550 Wc', statut=RFQ.Statut.CLOTUREE)
        self.offre_retenue = RFQOffre.objects.create(
            company=self.co, rfq=self.rfq, fournisseur=self.retenu,
            montant_ht=MONTANT_OFFRE_RETENUE, delai_jours=14, retenue=True)
        RFQOffre.objects.create(
            company=self.co, rfq=self.rfq, fournisseur=self.perdant,
            montant_ht=Decimal('99999.00'), delai_jours=30, retenue=False)
        self.consultation = RFQConsultation.objects.create(
            company=self.co, rfq=self.rfq, fournisseur=self.retenu,
            offre=self.offre_retenue)
        RFQConsultation.objects.create(
            company=self.co, rfq=self.rfq, fournisseur=self.perdant)
        _key, self.raw = ApiKey.issue(
            company=self.co, label='achats', scopes=[SCOPE_READ_ACHATS])

    def test_les_fournisseurs_consultes_et_loffre_retenue_sont_exposes(self):
        resp = _key_client(self.raw).get(URL_RFQ)
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne = resp.data['results'][0]
        self.assertEqual(ligne['reference'], 'RFQ-202609-0001')
        self.assertEqual(ligne['statut'], RFQ.Statut.CLOTUREE)
        noms = sorted(c['nom'] for c in ligne['fournisseurs_consultes'])
        self.assertEqual(noms, ['Fournisseur perdant', 'Fournisseur retenu'])
        repondu = {c['nom']: c['a_repondu']
                   for c in ligne['fournisseurs_consultes']}
        self.assertTrue(repondu['Fournisseur retenu'])
        self.assertFalse(repondu['Fournisseur perdant'])
        retenue = ligne['offre_retenue']
        self.assertEqual(retenue['id'], self.offre_retenue.pk)
        self.assertEqual(retenue['nom'], 'Fournisseur retenu')
        self.assertEqual(retenue['delai_jours'], 14)

    def test_aucun_montant_doffre_dans_le_rendu(self):
        """`RFQOffre.montant_ht` est documenté « Montants INTERNES » : c'est ce
        qu'un fournisseur nous facturerait, donc un prix d'achat."""
        rendu = json.dumps(_key_client(self.raw).get(URL_RFQ).data, default=str)
        self.assertNotIn('97531', rendu)
        self.assertNotIn('99999', rendu)
        self.assertNotIn('montant_ht', rendu)

    def test_le_jeton_de_consultation_ne_sort_jamais(self):
        """Il ouvre la page de réponse fournisseur SANS LOGIN (XPUR21) : le
        publier laisserait n'importe quel porteur de clé répondre à la place
        d'un fournisseur."""
        rendu = json.dumps(_key_client(self.raw).get(URL_RFQ).data, default=str)
        self.assertNotIn('token', rendu)
        self.assertNotIn(self.consultation.token, rendu)

    def test_sans_adjudication_loffre_retenue_est_nulle(self):
        RFQOffre.objects.filter(rfq=self.rfq).update(retenue=False)
        ligne = _key_client(self.raw).get(URL_RFQ).data['results'][0]
        self.assertIsNone(ligne['offre_retenue'])

    def test_une_autre_societe_est_invisible(self):
        autre = _company('ntp2p39-rfq-autre', 'NTP2P39 RFQ autre')
        RFQ.objects.create(
            company=autre, reference='RFQ-AUTRE', objet='Pas à moi',
            statut=RFQ.Statut.ENVOYEE)
        references = [lig['reference']
                      for lig in _key_client(self.raw).get(URL_RFQ).data['results']]
        self.assertEqual(references, ['RFQ-202609-0001'])

    def test_lecture_seule_stricte(self):
        api = _key_client(self.raw)
        self.assertEqual(
            api.post(URL_RFQ, {'objet': 'x'}, format='json').status_code, 405)
        self.assertEqual(
            api.delete(f'{URL_RFQ}{self.rfq.pk}/').status_code, 405)
