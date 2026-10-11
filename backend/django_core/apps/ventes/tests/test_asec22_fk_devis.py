"""ASEC22 (C-ASEC-005 site b + C-ASEC-008 volet devis) — FK inscriptibles du
devis bornées à la société de l'utilisateur.

Deux sociétés A et B. Un utilisateur de A ne peut :
  * créer / modifier une ligne de devis avec le ``produit`` ou le ``lot`` de B ;
  * créer une règle de liste de prix avec le ``produit`` de B ;
  * imposer ``updated_by`` (posé par le serveur à ``request.user``) ;
  * écrire ``roof_image`` par le corps du devis (seule porte : la génération
    du calepinage, clé ``roofs/<company_id>/<ref>.png``).

Chaque refus est un 400 sur le champ nommé, sans écriture ; un id inexistant
donne le même 400 (jamais un 500) ; les ids de A passent comme avant.

ENF17 — la ligne (``devis``), le devis (``client``/``lead``/``entite``/
``remise_approuvee_par``), les listes de prix (``liste``) et les fils
chatter/e-mails (lecture seule) suivent la même borne : l'id de B reçoit la
réponse d'un id absent (« objet inexistant »).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, LigneDevis, ListePrix, LotDevis, RegleListePrix,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
LIGNES = '/api/django/ventes/devis-lignes/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FkDevisSocieteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.co_a = Company.objects.create(slug='asec22-a', nom='A')
        cls.co_b = Company.objects.create(slug='asec22-b', nom='B')
        cls.user_a = User.objects.create_user(
            username='asec22_a', password='x', role_legacy='responsable',
            company=cls.co_a)
        cls.user_b = User.objects.create_user(
            username='asec22_b', password='x', role_legacy='responsable',
            company=cls.co_b)
        cls.client_a = Client.objects.create(
            company=cls.co_a, nom='Client', prenom='A',
            email='a@asec22.test', telephone='+212600000001',
            adresse='Casablanca')
        cls.client_b = Client.objects.create(
            company=cls.co_b, nom='Client', prenom='B',
            email='b@asec22.test', telephone='+212600000002',
            adresse='Rabat')
        cls.devis_a = Devis.objects.create(
            company=cls.co_a, reference=f'DEV-{MONTH}-8221',
            client=cls.client_a, statut=Devis.Statut.BROUILLON,
            roof_image=f'roofs/{cls.co_a.id}/DEV-{MONTH}-8221.png')
        cls.devis_b = Devis.objects.create(
            company=cls.co_b, reference=f'DEV-{MONTH}-8222',
            client=cls.client_b, statut=Devis.Statut.BROUILLON)
        cls.produit_a = Produit.objects.create(
            company=cls.co_a, nom='Panneau A', sku='ASEC22-A',
            prix_vente=Decimal('1000'), quantite_stock=10)
        cls.produit_b = Produit.objects.create(
            company=cls.co_b, nom='Panneau B', sku='ASEC22-B',
            prix_vente=Decimal('900'), quantite_stock=10)
        # PV15 — le catalogue GLOBAL (company NULL) reste quotable.
        cls.produit_global = Produit.objects.create(
            company=None, nom='Panneau global', sku='ASEC22-G',
            prix_vente=Decimal('800'), quantite_stock=10)
        cls.lot_a = LotDevis.objects.create(
            company=cls.co_a, devis=cls.devis_a, nom_lot='Villa 1')
        cls.lot_b = LotDevis.objects.create(
            company=cls.co_b, devis=cls.devis_b, nom_lot='Villa B')
        cls.liste_a = ListePrix.objects.create(company=cls.co_a, nom='Gros')

    def setUp(self):
        self.api = _auth(self.user_a)

    def _ligne(self, **extra):
        corps = {
            'devis': self.devis_a.id, 'produit': self.produit_a.id,
            'designation': 'Panneau', 'quantite': '1',
            'prix_unitaire': '1000', 'remise': '0',
        }
        corps.update(extra)
        return self.api.post(LIGNES, corps, format='json')

    # ── LigneDevis.produit ──────────────────────────────────────────────
    def test_ligne_produit_etranger_400(self):
        r = self._ligne(produit=self.produit_b.id)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)
        self.assertFalse(
            LigneDevis.objects.filter(produit=self.produit_b).exists())

        # PATCH d'une ligne existante : refusé, ligne inchangée.
        ligne = LigneDevis.objects.create(
            devis=self.devis_a, produit=self.produit_a, designation='P',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        r = self.api.patch(f'{LIGNES}{ligne.id}/',
                           {'produit': self.produit_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.produit_id, self.produit_a.id)

        # Id inexistant : même 400 nommé, jamais un 500.
        r = self._ligne(produit=999999999)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)

    # ── LigneDevis.lot ──────────────────────────────────────────────────
    def test_ligne_lot_etranger_400(self):
        r = self._ligne(lot=self.lot_b.id)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('lot', r.data)
        self.assertFalse(LigneDevis.objects.filter(lot=self.lot_b).exists())

        ligne = LigneDevis.objects.create(
            devis=self.devis_a, produit=self.produit_a, designation='P',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        r = self.api.patch(f'{LIGNES}{ligne.id}/',
                           {'lot': self.lot_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('lot', r.data)
        ligne.refresh_from_db()
        self.assertIsNone(ligne.lot_id)

        r = self._ligne(lot=999999999)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('lot', r.data)

    # ── RegleListePrix.produit ──────────────────────────────────────────
    def test_regle_liste_prix_produit_etranger_400(self):
        url = f'/api/django/ventes/listes-prix/{self.liste_a.id}/regles/'
        r = self.api.post(url, {
            'produit': self.produit_b.id,
            'type_regle': RegleListePrix.TypeRegle.REMISE_PCT,
            'valeur': '8', 'quantite_min': '1',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)
        self.assertFalse(RegleListePrix.objects.filter(
            produit=self.produit_b).exists())

        r = self.api.post(url, {
            'produit': 999999999,
            'type_regle': RegleListePrix.TypeRegle.REMISE_PCT,
            'valeur': '8', 'quantite_min': '1',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)

    # ── Devis.updated_by ────────────────────────────────────────────────
    def test_updated_by_force_serveur(self):
        r = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_a.id, 'taux_tva': '20',
            'updated_by': self.user_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        devis = Devis.objects.get(pk=r.data['id'])
        self.assertEqual(devis.updated_by_id, self.user_a.id)

        # PATCH : le corps ne choisit pas non plus l'auteur.
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/', {
            'note': 'x', 'updated_by': self.user_b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.updated_by_id, self.user_a.id)

    # ── Devis.roof_image ────────────────────────────────────────────────
    def test_roof_image_lecture_seule(self):
        avant = self.devis_a.roof_image
        cle_b = f'roofs/{self.co_b.id}/x.png'
        r = self.api.patch(f'/api/django/ventes/devis/{self.devis_a.id}/',
                           {'roof_image': cle_b}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.devis_a.refresh_from_db()
        self.assertEqual(self.devis_a.roof_image, avant)

        r = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_a.id, 'taux_tva': '20',
            'roof_image': cle_b,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn(Devis.objects.get(pk=r.data['id']).roof_image,
                      (None, ''))
        # Le champ reste LISIBLE (contrat inchangé).
        r = self.api.get(f'/api/django/ventes/devis/{self.devis_a.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('roof_image', r.data)

    # ── Les ids de A passent comme avant ────────────────────────────────
    def test_ids_societe_ok(self):
        r = self._ligne(lot=self.lot_a.id)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['produit'], self.produit_a.id)
        self.assertEqual(r.data['lot'], self.lot_a.id)

        r = self._ligne(produit=self.produit_global.id)
        self.assertEqual(r.status_code, 201, r.content)

        r = self.api.post(
            f'/api/django/ventes/listes-prix/{self.liste_a.id}/regles/', {
                'produit': self.produit_a.id,
                'type_regle': RegleListePrix.TypeRegle.REMISE_PCT,
                'valeur': '8', 'quantite_min': '1',
            }, format='json')
        self.assertEqual(r.status_code, 201, r.content)

    # ── ENF17 — FK restantes du devis bornées société ───────────────────
    def _assert_comme_absent(self, r, r_absent, champ, id_etranger):
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data[champ][0].code, 'does_not_exist', r.content)
        self.assertEqual(
            str(r.data[champ][0]).replace(str(id_etranger), '<ID>'),
            str(r_absent.data[champ][0]).replace('999999999', '<ID>'))

    def _assert_borne(self, cls, champ, propre, etranger):
        ctx = {'request': SimpleNamespace(user=self.user_a)}
        with self.subTest(serializer=cls.__name__, champ=champ):
            ser = cls(data={champ: etranger.pk}, partial=True, context=ctx)
            self.assertFalse(ser.is_valid())
            self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
            champ_lie = cls(context=ctx).fields[champ]
            self.assertEqual(champ_lie.to_internal_value(propre.pk), propre)

    def test_enf17_ligne_devis_etranger_comme_absent(self):
        r = self._ligne(devis=self.devis_b.id)
        r_absent = self._ligne(devis=999999999)
        self._assert_comme_absent(r, r_absent, 'devis', self.devis_b.id)
        self.assertFalse(
            LigneDevis.objects.filter(devis=self.devis_b).exists())

    def test_enf17_devis_client_lead_entite_etrangers_400(self):
        from apps.crm.models import Lead
        from apps.entites.models import Entite
        lead_b = Lead.objects.create(company=self.co_b, nom='Lead', prenom='B')
        entite_b = Entite.objects.create(
            company=self.co_b, nom='Entité B', code='ENF17-B')
        url = '/api/django/ventes/devis/'
        r = self.api.post(url, {'client': self.client_b.id, 'taux_tva': '20'},
                          format='json')
        r_absent = self.api.post(url, {'client': 999999999, 'taux_tva': '20'},
                                 format='json')
        self._assert_comme_absent(r, r_absent, 'client', self.client_b.id)
        for champ, etranger in (('client', self.client_b), ('lead', lead_b),
                                ('entite', entite_b)):
            with self.subTest(champ=champ):
                r = self.api.patch(f'{url}{self.devis_a.id}/',
                                   {champ: etranger.id}, format='json')
                r_absent = self.api.patch(f'{url}{self.devis_a.id}/',
                                          {champ: 999999999}, format='json')
                self._assert_comme_absent(r, r_absent, champ, etranger.id)
        self.devis_a.refresh_from_db()
        self.assertEqual(self.devis_a.client_id, self.client_a.id)
        self.assertIsNone(self.devis_a.lead_id)
        self.assertIsNone(self.devis_a.entite_id)

    def test_enf17_serialiseurs_devis_et_listes_bornes(self):
        from apps.crm.models import Lead
        from apps.entites.models import Entite
        from apps.ventes.serializers import (
            DevisSerializer, LignePrixListeSerializer,
            RegleListePrixSerializer,
        )
        lead_a = Lead.objects.create(company=self.co_a, nom='Lead', prenom='A')
        lead_b = Lead.objects.create(company=self.co_b, nom='Lead', prenom='B')
        entite_a = Entite.objects.create(
            company=self.co_a, nom='Entité A', code='ENF17-A')
        entite_b = Entite.objects.create(
            company=self.co_b, nom='Entité B', code='ENF17-B')
        liste_b = ListePrix.objects.create(company=self.co_b, nom='Gros B')
        for champ, propre, etranger in (
                ('client', self.client_a, self.client_b),
                ('lead', lead_a, lead_b), ('entite', entite_a, entite_b),
                ('remise_approuvee_par', self.user_a, self.user_b)):
            self._assert_borne(DevisSerializer, champ, propre, etranger)
        self._assert_borne(LignePrixListeSerializer, 'liste',
                           self.liste_a, liste_b)
        self._assert_borne(LignePrixListeSerializer, 'produit',
                           self.produit_a, self.produit_b)
        self._assert_borne(RegleListePrixSerializer, 'liste',
                           self.liste_a, liste_b)

    def test_enf17_fils_lecture_seule_jamais_ecrits(self):
        from apps.ventes.serializers import (
            DevisActivitySerializer, EmailLogSerializer,
        )
        ctx = {'request': SimpleNamespace(user=self.user_a)}
        for cls, champs in ((DevisActivitySerializer, ('devis',)),
                            (EmailLogSerializer, ('client', 'devis',
                                                  'facture'))):
            for champ in champs:
                with self.subTest(serializer=cls.__name__, champ=champ):
                    ser = cls(data={champ: self.devis_b.id}, partial=True,
                              context=ctx)
                    self.assertTrue(ser.is_valid(), ser.errors)
                    self.assertNotIn(champ, ser.validated_data)
                    self.assertIn(champ, cls.same_company_fields)
