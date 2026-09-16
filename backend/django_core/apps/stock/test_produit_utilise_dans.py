"""STKCAT25 — onglet « Utilisé dans » de la fiche produit (devis/leads/chantiers).

Ce que ce module AFFIRME, et pourquoi :

* **Le contrat committé est la source de vérité** (PACT10). Le test CHARGE
  ``apps/stock/contract_samples/produit_utilise_dans.json`` et compare la vraie
  réponse à son ``exemple`` : mêmes clés exactement, mêmes natures, mêmes
  formes de ligne. L'écran importe LE MÊME fichier comme charge utile de test
  (``ProduitDetail.test.jsx``) — les deux moitiés ne peuvent plus se mentir
  chacune de son côté, c'est tout l'objet de l'incident du 03/08/2026.
* **La visibilité des devis est celle de /ventes/devis, pas une copie
  allégée.** Deux utilisateurs de la MÊME société : l'un à portée « équipe »
  sans superviseur (il ne voit que ses propres devis), l'autre sans marqueur
  de portée. Le premier ne doit pas voir, par la fiche produit du Stock, le
  devis que la liste /ventes/devis lui masque — la même donnée par une autre
  porte serait exactement le trou.
* **Le cross-tenant reste fermé** : le produit d'une autre société est un 404,
  et rien d'une autre société n'entre dans les listes.
* **Aucun prix d'achat, aucune marge** ne sort par cet endpoint.

Run:
    python manage.py test apps.stock.test_produit_utilise_dans -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.roles.models import Role
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'produit_utilise_dans.json')

_PERMS = ['stock_voir', 'crm_voir', 'ventes_voir']


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _nature(valeur):
    """Nature JSON d'une valeur — le vocabulaire du contrat (clé -> nature)."""
    if isinstance(valeur, bool):
        return 'booleen'
    if isinstance(valeur, dict):
        return 'objet'
    if isinstance(valeur, (list, tuple)):
        return 'liste'
    if isinstance(valeur, (int, float, Decimal)):
        return 'nombre'
    if isinstance(valeur, str):
        return 'texte'
    return 'inconnu'


class UtiliseDansBase(TestCase):
    def setUp(self):
        self.company = _company('stkcat25-co')
        # Rôle SANS marqueur de portée -> voit tout (comportement historique).
        self.large = _user(self.company, 'stkcat25-large', permissions=_PERMS)
        # Rôle RESTREINT à l'équipe : sans superviseur, sa portée se limite à
        # lui-même (``core.scoping.peer_user_ids``).
        self.restreint = _user(
            self.company, 'stkcat25-restreint',
            permissions=_PERMS + ['records_scope_equipe'])

        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau STKCAT25', sku='PAN-STKCAT25',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=10)
        self.autre_produit = Produit.objects.create(
            company=self.company, nom='Onduleur STKCAT25', sku='OND-STKCAT25',
            prix_vente=Decimal('9000'), prix_achat=Decimal('6000'),
            quantite_stock=3)

        self.client_crm = Client.objects.create(
            company=self.company, nom='Ferme Doukkala', prenom='',
            email='stkcat25@example.com', telephone='+212600000025')

    # ── fabriques ────────────────────────────────────────────────────────
    def _devis(self, reference, created_by, produit=None, lead=None,
               statut=None):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_crm,
            lead=lead, created_by=created_by,
            statut=statut or Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        cible = produit or self.produit
        LigneDevis.objects.create(
            devis=devis, produit=cible, designation=cible.nom,
            quantite=Decimal('2'), prix_unitaire=cible.prix_vente)
        return devis

    def _chantier(self, reference, devis, produit=None, **kwargs):
        chantier = Installation.objects.create(
            company=self.company, reference=reference,
            client=self.client_crm, devis=devis, **kwargs)
        StockReservation.objects.create(
            company=self.company, installation=chantier,
            produit=produit or self.produit, quantite=2)
        return chantier

    def _get(self, user, produit=None):
        produit = produit or self.produit
        return _api(user).get(
            f'/api/django/stock/produits/{produit.pk}/utilise-dans/')


class ContratTests(UtiliseDansBase):
    """Le contrat COMMITTÉ est affirmé par le serveur, pas décrit à côté."""

    def setUp(self):
        super().setUp()
        self.document = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.exemple = self.document['exemple']
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Youssef',
            ville='Casablanca', owner=self.large)
        self.devis = self._devis(
            'DEV-STKCAT25-001', self.large, lead=self.lead)
        self._chantier('CH-STKCAT25-001', self.devis)

    def test_endpoint_du_contrat_est_bien_celui_servi(self):
        """Le chemin écrit dans le contrat est le chemin qui répond 200."""
        chemin = self.document['endpoint'].split(' ', 1)[1]
        reel = chemin.replace('<int:pk>', str(self.produit.pk))
        resp = _api(self.large).get(reel)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

    def test_reponse_a_exactement_les_cles_du_contrat(self):
        resp = self._get(self.large)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(
            set(resp.data), set(self.exemple),
            "La réponse et l'exemple committé ne portent pas les mêmes clés : "
            "l'un des deux a dérivé (PACT10).")

    def test_natures_identiques_a_celles_du_contrat(self):
        resp = self._get(self.large)
        for cle, attendue in sorted(self.exemple.items()):
            self.assertEqual(
                _nature(resp.data[cle]), _nature(attendue),
                f"La clé '{cle}' ne rend pas la même nature que l'exemple "
                f"committé.")

    def test_lignes_ont_la_forme_des_lignes_du_contrat(self):
        """Chaque liste rend des lignes aux clés/natures de l'exemple."""
        resp = self._get(self.large)
        for cle in ('devis', 'leads', 'chantiers'):
            modele = self.exemple[cle][0]
            lignes = resp.data[cle]
            self.assertTrue(
                lignes, f"Le scénario doit produire au moins une ligne "
                        f"'{cle}' pour que la forme soit vérifiable.")
            for ligne in lignes:
                self.assertEqual(
                    set(ligne), set(modele),
                    f"Une ligne '{cle}' ne porte pas les clés de l'exemple "
                    f"committé.")
                for champ, valeur in sorted(modele.items()):
                    self.assertEqual(
                        _nature(ligne[champ]), _nature(valeur),
                        f"'{cle}.{champ}' ne rend pas la nature de l'exemple.")

    def test_exemple_vide_est_un_etat_pas_une_autre_forme(self):
        """Un produit que rien n'utilise rend l'``exemple_vide`` du contrat."""
        resp = self._get(self.large, produit=self.autre_produit)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        attendu = self.document['exemple_vide']
        self.assertEqual(set(resp.data), set(attendu))
        self.assertEqual(resp.data['devis'], [])
        self.assertEqual(resp.data['leads'], [])
        self.assertEqual(resp.data['chantiers'], [])
        self.assertEqual(resp.data['limite'], attendu['limite'])


class ContenuTests(UtiliseDansBase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Youssef',
            ville='Casablanca', owner=self.large)
        self.devis = self._devis(
            'DEV-STKCAT25-010', self.large, lead=self.lead)
        self.chantier = self._chantier('CH-STKCAT25-010', self.devis)

    def test_le_devis_le_lead_et_le_chantier_du_produit_sont_listes(self):
        resp = self._get(self.large)
        self.assertEqual(
            [d['id'] for d in resp.data['devis']], [self.devis.pk])
        self.assertEqual(
            [lead['id'] for lead in resp.data['leads']], [self.lead.pk])
        self.assertEqual(
            [c['id'] for c in resp.data['chantiers']], [self.chantier.pk])

    def test_un_lead_lie_par_sa_structure_choisie_est_liste_sans_devis(self):
        # STKCAT9 + STKCAT25 bis : Lead.structure_produit est un lien direct.
        lead_structure = Lead.objects.create(
            company=self.company, nom='Benani', prenom='Sara',
            ville='Rabat', owner=self.large, structure_produit=self.produit)
        resp = self._get(self.large)
        self.assertIn(lead_structure.pk, [lead['id'] for lead in resp.data['leads']])
        self.assertIn(self.lead.pk, [lead['id'] for lead in resp.data['leads']])

    def test_un_autre_produit_ne_ramene_rien(self):
        resp = self._get(self.large, produit=self.autre_produit)
        self.assertEqual(resp.data['devis'], [])
        self.assertEqual(resp.data['leads'], [])
        self.assertEqual(resp.data['chantiers'], [])

    def test_un_devis_cite_une_seule_fois_meme_avec_deux_lignes(self):
        """Deux lignes du même produit : un devis, pas un doublon."""
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('3'),
            prix_unitaire=self.produit.prix_vente)
        resp = self._get(self.large)
        self.assertEqual([d['id'] for d in resp.data['devis']],
                         [self.devis.pk])

    def test_aucun_prix_d_achat_ni_marge_dans_la_charge_utile(self):
        """`Produit.prix_achat` ne sort JAMAIS par un endpoint de fiche."""
        resp = self._get(self.large)
        brut = json.dumps(resp.data, default=str)
        self.assertNotIn('prix_achat', brut)
        self.assertNotIn('marge', brut)
        # Les seules clés servies sont celles du contrat : aucune ne peut
        # porter un coût (vérifié clé à clé, pas par un grep de nombre qui
        # collisionnerait avec un id ou une date).
        for ligne in resp.data['devis']:
            self.assertEqual(
                set(ligne),
                {'id', 'reference', 'client_nom', 'statut', 'date',
                 'total_ttc'})

    def test_totaux_en_texte_decimal_jamais_un_flottant(self):
        resp = self._get(self.large)
        for ligne in resp.data['devis']:
            self.assertIsInstance(ligne['total_ttc'], str)


class VisibiliteDevisTests(UtiliseDansBase):
    """La portée de /ventes/devis vaut AUSSI par la fiche produit du Stock."""

    def setUp(self):
        super().setUp()
        self.devis_du_restreint = self._devis(
            'DEV-STKCAT25-100', self.restreint)
        self.devis_de_l_autre = self._devis('DEV-STKCAT25-101', self.large)

    def _ids_ventes(self, user):
        resp = _api(user).get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        donnees = resp.data
        lignes = donnees['results'] if isinstance(donnees, dict) else donnees
        return {d['id'] for d in lignes}

    def test_role_restreint_ne_voit_que_ses_devis_par_le_stock(self):
        resp = self._get(self.restreint)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        ids = [d['id'] for d in resp.data['devis']]
        self.assertIn(self.devis_du_restreint.pk, ids)
        self.assertNotIn(
            self.devis_de_l_autre.pk, ids,
            "La fiche produit du Stock expose un devis que la liste "
            "/ventes/devis masque à ce rôle : la portée est contournée.")

    def test_meme_ensemble_que_la_liste_ventes(self):
        """L'onglet Stock et /ventes/devis répondent la MÊME portée."""
        for user in (self.restreint, self.large):
            ids_stock = {d['id'] for d in self._get(user).data['devis']}
            self.assertLessEqual(
                ids_stock, self._ids_ventes(user),
                'Un devis visible par le Stock est invisible dans /ventes : '
                'les deux portées ont divergé.')

    def test_role_large_voit_les_deux_devis(self):
        ids = [d['id'] for d in self._get(self.large).data['devis']]
        self.assertIn(self.devis_du_restreint.pk, ids)
        self.assertIn(self.devis_de_l_autre.pk, ids)


class CrossTenantTests(UtiliseDansBase):
    def setUp(self):
        super().setUp()
        self.autre_company = _company('stkcat25-autre-co')
        self.autre_user = _user(
            self.autre_company, 'stkcat25-autre-user', permissions=_PERMS)
        self._devis('DEV-STKCAT25-200', self.large)

    def test_produit_d_une_autre_societe_est_un_404(self):
        resp = self._get(self.autre_user)
        self.assertEqual(resp.status_code, 404)

    def test_aucun_document_de_l_autre_societe_ne_remonte(self):
        produit_voisin = Produit.objects.create(
            company=self.autre_company, nom='Panneau voisin',
            sku='PAN-STKCAT25-V', prix_vente=Decimal('2000'),
            prix_achat=Decimal('1000'), quantite_stock=1)
        resp = self._get(self.autre_user, produit=produit_voisin)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(resp.data['devis'], [])
        self.assertEqual(resp.data['leads'], [])
        self.assertEqual(resp.data['chantiers'], [])
