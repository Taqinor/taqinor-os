"""QJR419 (QJR4-10) — la salle de vente publique cesse de remettre au visiteur
anonyme un chemin INTERNE qu'il ne peut pas ouvrir.

CE QUE LE ROUGE PROUVAIT. ``apps/crm/public_views.py`` posait dans la charge
utile d'un endpoint ``AllowAny`` (``public_salle_vente``) ::

    'proposal_path': f'/api/django/ventes/devis/{devis.pk}/proposal/'

Deux défauts d'un seul champ :

* le lien pointe un endpoint **AUTHENTIFIÉ** — inutilisable pour son
  destinataire, qui n'a ni session ni jeton d'API ;
* il **divulgue la clé primaire interne** du devis, qui n'a rien à faire dans
  une charge utile publique.

CORRECTIF : on sert **le lien public** (la page tokenisée du site, construite
par le builder unique ``ventes.utils.client_links`` — QX13, jamais une URL
forgée à la main), c'est-à-dire celui qui fonctionne réellement pour un
visiteur, ou **rien du tout**.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm.models import Client, SalleVente, SalleVenteItem
from apps.ventes.models import Devis, LigneDevis


class SalleVenteLienPublicTests(TestCase):

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='qjr419', defaults={'nom': 'QJR419'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR419')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj,
            reference='DEV-QJR419', statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, designation='Onduleur réseau 5 kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            remise=Decimal('0'))
        self.salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj,
            titre='Salle QJR419')
        self.item = SalleVenteItem.objects.create(
            salle=self.salle, type=SalleVenteItem.TypeItem.DEVIS,
            titre='Ma proposition', ordre=1, reference=str(self.devis.pk))
        self.anon = APIClient()

    def _payload(self):
        reponse = self.anon.get(
            '/api/django/crm/salle-vente/%s/' % self.salle.token)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_aucun_chemin_interne_ni_cle_primaire_dans_la_charge_utile(self):
        """ROUGE avant QJR419 : la charge utile portait
        ``/api/django/ventes/devis/<pk>/proposal/``."""
        item = self._payload()['items'][0]
        lien = item['proposal_path']
        self.assertNotIn('/api/django/', lien)
        self.assertNotIn('/ventes/devis/', lien)
        self.assertNotIn(
            '/api/django/ventes/devis/%s/proposal/' % self.devis.pk, lien)

    def test_le_lien_servi_est_celui_du_builder_unique(self):
        """QX13 — jamais une URL forgée à la main : c'est EXACTEMENT ce que
        ``client_links.url_proposition`` produit pour ce devis."""
        from apps.ventes.utils.client_links import url_proposition

        item = self._payload()['items'][0]
        self.assertEqual(item['proposal_path'], url_proposition(self.devis))
        self.assertIn('/proposition/', item['proposal_path'])

    def test_un_visiteur_anonyme_ouvre_reellement_la_proposition(self):
        """Second test du `Done` : le parcours n'est pas cassé — le jeton porté
        par le lien servi résout bien un ShareLink valide de CE devis."""
        from apps.ventes.models import ShareLink

        item = self._payload()['items'][0]
        jeton = item['proposal_path'].rstrip('/').rsplit('/', 1)[-1]
        link = ShareLink.objects.filter(token=jeton).first()
        self.assertIsNotNone(link, 'le lien servi ne porte aucun jeton valide')
        self.assertEqual(link.devis_id, self.devis.pk)
        self.assertTrue(link.is_valid)

    def test_le_reste_de_la_charge_utile_est_inchange(self):
        """Troisième test du `Done` : seul le lien a bougé."""
        from apps.ventes.quote_engine.builder import display_totals

        item = self._payload()['items'][0]
        self.assertEqual(item['id'], self.item.id)
        self.assertEqual(item['type'], SalleVenteItem.TypeItem.DEVIS)
        self.assertEqual(item['titre'], 'Ma proposition')
        self.assertEqual(item['ordre'], 1)
        self.assertEqual(item['reference'], self.devis.reference)
        self.assertEqual(item['statut'], self.devis.statut)
        self.assertEqual(item['total_ttc'],
                         str(display_totals(self.devis)['total']))

    def test_un_item_non_devis_ne_porte_aucun_lien(self):
        """Un item qui n'est pas un devis n'a jamais porté de lien : inchangé."""
        SalleVenteItem.objects.all().delete()
        SalleVenteItem.objects.create(
            salle=self.salle, type=SalleVenteItem.TypeItem.DOCUMENT,
            titre='Fiche technique', ordre=1, reference='doc-1')
        item = self._payload()['items'][0]
        self.assertNotIn('proposal_path', item)

    def test_un_devis_d_une_autre_societe_ne_fuit_rien(self):
        """Multi-tenant : ni référence, ni total, ni lien."""
        autre = Company.objects.create(nom='Autre QJR419', slug='qjr419-autre')
        # `Devis.client` est NOT NULL : le devis de l'autre société porte SON
        # propre client (le cloisonnement testé n'en dépend pas).
        client_autre = Client.objects.create(
            company=autre, nom='Client Autre QJR419')
        devis_autre = Devis.objects.create(
            company=autre, client=client_autre, reference='DEV-QJR419-X',
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        SalleVenteItem.objects.all().delete()
        SalleVenteItem.objects.create(
            salle=self.salle, type=SalleVenteItem.TypeItem.DEVIS,
            titre='Devis d\'ailleurs', ordre=1,
            reference=str(devis_autre.pk))
        item = self._payload()['items'][0]
        self.assertIsNone(item['reference'])
        self.assertNotIn('proposal_path', item)
        self.assertNotIn('total_ttc', item)
