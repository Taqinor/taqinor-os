"""ADEV21 (C-ADEV-025) — la portée équipe (``core/scoping.scope_queryset``,
mêmes ``owner_fields`` que ``DevisViewSet``) s'applique à
``LigneDevisViewSet`` et aux aperçus ``etude-ci`` / ``etude-pompage``.

Un Commercial de portée ``team`` (rôle canonique réel, ``records_scope_equipe``,
sans superviseur commun avec l'auteur du brouillon) ne lit ni ne modifie
aucune ligne d'un devis hors de sa portée (404) ; ses propres lignes restent
lisibles et modifiables.

Test-du-test : retirer ``scope_queryset`` de ``LigneDevisViewSet.get_queryset``
⇒ ``test_patch_404_hors_portee`` échoue.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, RESPONSABLE_PERMISSIONS)
from apps.stock.models import Produit
from apps.ventes.domain import pompage
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

URL_LIGNES = '/api/django/ventes/devis-lignes/'
URL_POMPAGE = '/api/django/ventes/etude-pompage/preview/'


class PorteeLignesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ADEV21', slug='adev21-co')
        role_equipe = Role.objects.create(
            company=cls.company, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_equipe'],
            est_systeme=False)
        cls.commercial = User.objects.create_user(
            username='adev21_com', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.company)
        cls.auteur = User.objects.create_user(
            username='adev21_auteur', password='x',
            role_legacy='responsable', company=cls.company)
        client = Client.objects.create(
            company=cls.company, nom='Client ADEV21',
            email='adev21@example.com')
        cls.devis_autrui = Devis.objects.create(
            company=cls.company, reference='DV-ADEV21-A', client=client,
            created_by=cls.auteur)
        cls.ligne_autrui = LigneDevis.objects.create(
            devis=cls.devis_autrui, designation='Accessoires',
            quantite=1, prix_unitaire=Decimal('1272.73'))
        cls.devis_propre = Devis.objects.create(
            company=cls.company, reference='DV-ADEV21-P', client=client,
            created_by=cls.commercial)
        # Une ligne PRODUIT référence un produit (XSAL14,
        # ``LigneDevisSerializer.validate``) : sans lui, le PATCH de la ligne
        # propre répond 400 « Une ligne produit doit référencer un produit. »
        # avant même la portée testée ici.
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Câble solaire 6 mm²',
            sku='ADEV21-CAB', prix_vente=Decimal('100'))
        cls.ligne_propre = LigneDevis.objects.create(
            devis=cls.devis_propre, produit=cls.produit, designation='Câblage',
            quantite=1, prix_unitaire=Decimal('100'))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.commercial)

    @staticmethod
    def _ids(resp):
        corps = resp.data
        lignes = corps.get('results', corps) if isinstance(corps, dict) else corps
        return {ligne['id'] for ligne in lignes}

    def test_liste_vide_hors_portee(self):
        resp = self.api.get(URL_LIGNES)
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertNotIn(self.ligne_autrui.pk, ids)
        self.assertIn(self.ligne_propre.pk, ids)
        detail = self.api.get('%s%s/' % (URL_LIGNES, self.ligne_autrui.pk))
        self.assertEqual(detail.status_code, 404)

    def test_patch_404_hors_portee(self):
        resp = self.api.patch(
            '%s%s/' % (URL_LIGNES, self.ligne_autrui.pk),
            {'prix_unitaire': '1.00'}, format='json')
        self.assertEqual(resp.status_code, 404)
        # CLAUSE PERSISTANCE — relue en base : prix inchangé.
        self.ligne_autrui.refresh_from_db()
        self.assertEqual(self.ligne_autrui.prix_unitaire, Decimal('1272.73'))

    def test_apercus_404_hors_portee(self):
        for url in ('/api/django/ventes/etude-ci/preview/',
                    '/api/django/ventes/etude-pompage/preview/'):
            resp = self.api.post(url, {'devis': self.devis_autrui.pk},
                                 format='json')
            self.assertEqual(resp.status_code, 404, url)

    def test_propres_lignes_ok(self):
        url = '%s%s/' % (URL_LIGNES, self.ligne_propre.pk)
        self.assertEqual(self.api.get(url).status_code, 200)
        resp = self.api.patch(url, {'designation': 'Câblage DC'},
                              format='json')
        self.assertEqual(resp.status_code, 200)
        self.ligne_propre.refresh_from_db()
        self.assertEqual(self.ligne_propre.designation, 'Câblage DC')

    # -- AGM11 : le lead de l'apercu pompage est borne a la portee equipe --

    def _lead(self, owner):
        return Lead.objects.create(
            company=self.company, owner=owner, nom='Agri', prenom='Lead',
            telephone='+212600000021', besoin_eau_m3j=Decimal('90'),
            besoin_eau_source='client')

    def _entrees_apercu_pompage(self, lead):
        with mock.patch.object(pompage, 'profils_horaires_site',
                               return_value=None), \
                mock.patch.object(pompage, 'temperatures_du_site',
                                  return_value=None):
            resp = self.api.post(URL_POMPAGE, {'lead': lead.pk},
                                 format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()['entrees_resolues']

    def test_apercu_pompage_lead_hors_portee_ignore(self):
        # Le lead d'un autre proprietaire est ignore (comme un lead d'une
        # autre societe) : ses donnees (volume d'eau) ne sont pas lues.
        entrees = self._entrees_apercu_pompage(self._lead(self.auteur))
        self.assertNotIn('volume_m3_jour', entrees)

    def test_apercu_pompage_lead_propre_lu(self):
        entrees = self._entrees_apercu_pompage(self._lead(self.commercial))
        self.assertEqual(entrees['volume_m3_jour']['valeur'], 90)
        self.assertEqual(entrees['volume_m3_jour']['provenance']['origine'],
                         'lead')

    # -- ADVS24 : le lead du corps des portes de création, borné à la portée --

    def _corps_atomic(self, lead):
        return {'lead': lead.pk, 'taux_tva': '20.00', 'lignes': [{
            'produit': self.produit.pk, 'designation': 'Câblage',
            'quantite': '1', 'prix_unitaire': '100.00', 'taux_tva': '20'}]}

    def _portes_de_creation(self, lead):
        corps_composition = {'lead': lead.pk, 'nb_panneaux': 8,
                             'panel_watt': 550}
        return {
            'atomic': self.api.post('/api/django/ventes/devis/atomic/',
                                    self._corps_atomic(lead), format='json'),
            'auto': self.api.post('/api/django/ventes/devis/auto/',
                                  {'lead': lead.pk}, format='json'),
            'composition': self.api.post(
                '/api/django/ventes/devis/composition/', corps_composition,
                format='json'),
        }

    def test_lead_d_un_collegue_refuse_aux_trois_portes(self):
        lead = self._lead(self.auteur)
        reponses = self._portes_de_creation(lead)
        # atomic : le 404 d'un id d'une autre société (IdInconnu404Mixin), même
        # corps au pk près : le refus ne dit pas que le lead existe.
        self.assertEqual(reponses['atomic'].status_code, 404,
                         reponses['atomic'].content[:300])
        self.assertIn(str(lead.pk), str(reponses['atomic'].json()['lead']))
        for porte in ('auto', 'composition'):
            with self.subTest(porte=porte):
                self.assertEqual(reponses[porte].status_code, 404,
                                 reponses[porte].content[:300])
                self.assertEqual(reponses[porte].json()['detail'],
                                 'Lead inconnu.')
        # CLAUSE PERSISTANCE — relu en base : aucun devis créé sur ce lead.
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_auto_par_client_refuse_si_son_lead_est_hors_portee(self):
        client = Client.objects.create(
            company=self.company, nom='Client du collegue',
            email='adv24-collegue@example.com')
        lead = self._lead(self.auteur)
        lead.client = client
        lead.save(update_fields=['client'])
        resp = self.api.post('/api/django/ventes/devis/auto/',
                             {'client': client.pk}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content[:300])
        self.assertFalse(Devis.objects.filter(lead=lead).exists())

    def test_lead_d_une_autre_societe_refuse_comme_avant(self):
        autre = Company.objects.create(nom='ADEV21 B', slug='adev21-co-b')
        lead = Lead.objects.create(
            company=autre, nom='Etranger', prenom='Lead',
            telephone='+212600000022')
        reponses = self._portes_de_creation(lead)
        self.assertEqual(reponses['atomic'].status_code, 404)
        self.assertIn(str(lead.pk), str(reponses['atomic'].json()['lead']))
        self.assertEqual(reponses['auto'].status_code, 404)
        self.assertEqual(reponses['composition'].status_code, 404)

    def test_lead_propre_et_lead_de_l_equipe_atteignent_la_porte(self):
        # Le propriétaire et un responsable de sous-arbre passent la portée.
        role_sous_arbre = Role.objects.create(
            company=self.company, nom='Responsable equipe',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_sous_arbre'],
            est_systeme=False)
        responsable = User.objects.create_user(
            username='adev21_resp', password='x', role=role_sous_arbre,
            role_legacy='responsable', company=self.company)
        membre = User.objects.create_user(
            username='adev21_membre', password='x', role_legacy='responsable',
            company=self.company, supervisor=responsable)
        for acteur, proprietaire in ((self.commercial, self.commercial),
                                     (responsable, membre)):
            with self.subTest(acteur=acteur.username):
                self.api.force_authenticate(acteur)
                lead = self._lead(proprietaire)
                resp = self.api.post('/api/django/ventes/devis/atomic/',
                                     self._corps_atomic(lead), format='json')
                self.assertEqual(resp.status_code, 201, resp.content[:300])
                self.assertTrue(Devis.objects.filter(lead=lead).exists())

    def test_lead_en_portee_atteint_auto_et_composition(self):
        """ADVS24 — un lead en portée passe les portes ``/auto`` et
        ``/composition`` (jamais le 404 « Lead inconnu. »), pour un Commercial
        aux ``COMMERCIAL_PERMISSIONS`` canoniques en portée « soi ».

        ECART À SIGNALER (non changé ici) : ``/composition`` répond 200 et
        n'écrit rien (aucun devis), alors que ``/auto`` crée le devis.
        """
        role_soi = Role.objects.create(
            company=self.company, nom='Commercial soi',
            permissions=COMMERCIAL_PERMISSIONS + ['records_scope_soi'],
            est_systeme=False)
        soi = User.objects.create_user(
            username='adev24_soi', password='x', role=role_soi,
            role_legacy='commercial', company=self.company)
        for acteur in (self.commercial, soi):
            with self.subTest(acteur=acteur.username):
                self.api.force_authenticate(acteur)
                lead = self._lead(acteur)
                reponses = self._portes_de_creation(lead)
                for porte in ('auto', 'composition'):
                    self.assertNotEqual(
                        reponses[porte].status_code, 404,
                        (porte, reponses[porte].content[:300]))
                self.assertEqual(reponses['composition'].status_code, 200,
                                 reponses['composition'].content[:300])
                # composition ne persiste rien : seul /auto a pu créer.
                crees_avant = Devis.objects.filter(lead=lead).count()
                self.api.post('/api/django/ventes/devis/composition/',
                              {'lead': lead.pk, 'nb_panneaux': 8,
                               'panel_watt': 550}, format='json')
                self.assertEqual(
                    Devis.objects.filter(lead=lead).count(), crees_avant)
