# -*- coding: utf-8 -*-
"""STKCAT9 — le devis AUTOMATIQUE écoute enfin la structure du LEAD.

``POST /ventes/devis/auto/`` compose sans commercial dans la boucle : c'est le
chemin où personne ne rattrape un écart. Il ignorait TOUT du choix de structure
du lead et composait donc systématiquement de l'ACIER — y compris pour un lead
qui avait explicitement demandé de l'aluminium, et sans aucun moyen de désigner
une pergola (``structure_pref`` ne sait dire que « acier » ou « aluminium »).

Ce que ces tests verrouillent :

  * un lead ``structure_pref='aluminium'`` reçoit un devis ALUMINIUM ;
  * un lead portant ``structure_produit`` reçoit CE produit-là, à la ligne
    près — pergola comprise, alors qu'aucun mot-clé de son nom ne la désigne ;
  * le produit ÉPINGLÉ l'emporte sur la préférence acier/alu (les deux ne se
    combinent jamais) ;
  * un lead qui ne dit rien produit EXACTEMENT le devis d'hier (acier).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Categorie, Produit
from apps.ventes.domain.creation import _structure_demandee
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

AUTO_URL = '/api/django/ventes/devis/auto/'

CATALOGUE = (
    ('Panneau Canadien Solar 710W', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', '17000'),
    ('Structures acier', '500'),
    ('Structures aluminium', '850'),
    ('Socles', '80'),
    ('Transport', '1000'),
)


class STKCAT9Base(TestCase):
    slug = 'stkcat9-co'

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})[0]
        self.user = User.objects.create_user(
            username='stkcat9_user', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        for nom, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=1000)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='STKCAT9 Structures spéciales',
            ordre=15, type_equipement=Categorie.TypeEquipement.STRUCTURE)
        self.pergola = Produit.objects.create(
            company=self.company, nom='Pergola acier 4x3',
            categorie=self.categorie, prix_vente=Decimal('18000'),
            prix_achat=Decimal('1'), quantite_stock=5)

    def lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Structure', prenom='Lead',
            email='stkcat9@example.com',
            taille_souhaitee_kwc=Decimal('5'), **extra)

    def devis_auto(self, lead):
        reponse = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return Devis.objects.get(pk=reponse.data['id'])

    @staticmethod
    def designations_structure(devis):
        """L'ENSEMBLE des désignations de STRUCTURE réellement écrites.

        Un ENSEMBLE, pas une liste : un devis « Les deux » peut dédoubler la
        ligne par variante (L-2OPT) — ce que ces tests tiennent, c'est QUEL
        matériau est vendu, jamais combien de lignes le portent.
        """
        from apps.ventes.domain.composition import _classe_kit_de_ligne
        return {ligne.designation for ligne in devis.lignes.all()
                if _classe_kit_de_ligne(ligne) == 'structure'}


class LeDevisAutoSuitLeLead(STKCAT9Base):
    def test_un_lead_aluminium_ne_recoit_plus_un_devis_acier(self):
        devis = self.devis_auto(self.lead(structure_pref='aluminium'))
        self.assertEqual(self.designations_structure(devis),
                         {'Structures aluminium'})

    def test_un_lead_acier_reste_en_acier(self):
        devis = self.devis_auto(self.lead(structure_pref='acier'))
        self.assertEqual(self.designations_structure(devis),
                         {'Structures acier'})

    def test_un_lead_muet_compose_comme_hier(self):
        devis = self.devis_auto(self.lead())
        self.assertEqual(self.designations_structure(devis),
                         {'Structures acier'})

    def test_un_lead_a_pergola_recoit_SA_pergola(self):
        devis = self.devis_auto(self.lead(structure_produit=self.pergola))
        lignes = [li for li in devis.lignes.all()
                  if li.produit_id == self.pergola.id]
        self.assertTrue(lignes, self.designations_structure(devis))
        self.assertEqual({li.designation for li in lignes},
                         {'Pergola acier 4x3'})
        self.assertEqual(self.designations_structure(devis),
                         {'Pergola acier 4x3'})

    def test_le_produit_epingle_gagne_sur_la_preference(self):
        """Les deux ne se combinent JAMAIS : un produit arrêté est souverain."""
        devis = self.devis_auto(
            self.lead(structure_pref='aluminium',
                      structure_produit=self.pergola))
        self.assertEqual(self.designations_structure(devis),
                         {'Pergola acier 4x3'})


class LaResolutionDeLaStructureDemandee(TestCase):
    """La fonction pure de résolution, cas par cas — aucune base requise."""

    class _Lead:
        def __init__(self, produit_id=None, pref=None):
            self.structure_produit_id = produit_id
            self.structure_pref = pref

    def test_l_appelant_est_souverain(self):
        lead = self._Lead(produit_id=7, pref='aluminium')
        self.assertEqual(_structure_demandee(lead, 99), (99, 'acier'))
        self.assertEqual(_structure_demandee(lead, None, 'alu'),
                         (None, 'alu'))

    def test_le_produit_du_lead_passe_devant_sa_preference(self):
        lead = self._Lead(produit_id=7, pref='aluminium')
        self.assertEqual(_structure_demandee(lead), (7, 'acier'))

    def test_la_preference_est_mappee_par_mot_cle(self):
        self.assertEqual(
            _structure_demandee(self._Lead(pref='aluminium')), (None, 'alu'))
        self.assertEqual(
            _structure_demandee(self._Lead(pref='acier')), (None, 'acier'))

    def test_un_lead_muet_ou_absent_rend_le_defaut_historique(self):
        self.assertEqual(_structure_demandee(self._Lead()), (None, 'acier'))
        self.assertEqual(_structure_demandee(None), (None, 'acier'))
