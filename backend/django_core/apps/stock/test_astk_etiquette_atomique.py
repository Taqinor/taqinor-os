"""ASTK52 (C-ASTK-010) — étiquette d'expédition et sortie de stock sont
atomiques : jamais une expédition étiquetée sans son mouvement EXP-n.

Sonde WMS-9 d'origine : le décrément levait au 1er appel APRÈS la pose de
l'étiquette ; le 2e appel sortait tôt (« déjà étiquetée ») → 0 mouvement
EXP-n, stock 10 alors que la marchandise était partie.

Seule simulation admise : la PANNE d'infrastructure injectée sur le
décrément (1er appel) et le dépôt MinIO de l'étiquette. Le connecteur NoOp
et le décrément du 2e appel sont réels.

Run :
    python manage.py test apps.stock.test_astk_etiquette_atomique -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock import services_wms
from apps.stock.models import MouvementStock, Produit
from apps.stock.models_wms import ExpeditionTransporteur
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_expedition_transporteur,
    creer_unite_logistique, generer_etiquette_expedition,
    reference_sortie_expedition, sceller_unite_logistique,
)

User = get_user_model()

STOCKER = 'apps.stock.services_wms._stocker_etiquette'


def make_company(slug='astk52-co', nom='ASTK52 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EtiquetteAtomiqueTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = User.objects.create_user(
            username='astk52_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur ASTK52', sku='ASTK52-1',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=10)
        colis = creer_unite_logistique(company=self.co)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=colis, produit=self.produit, quantite=2)
        sceller_unite_logistique(unite=colis, user=self.user)
        colis.refresh_from_db()
        self.expedition = creer_expedition_transporteur(
            company=self.co, unite=colis)

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock

    def _mouvements(self):
        return MouvementStock.objects.filter(
            company=self.co,
            reference=reference_sortie_expedition(self.expedition)).count()

    def test_panne_du_decrement_puis_reprise(self):
        reel = services_wms.decrementer_stock_expedition
        with mock.patch(STOCKER, return_value='stock/x/etiquettes/t.pdf'), \
                mock.patch.object(
                    services_wms, 'decrementer_stock_expedition',
                    side_effect=RuntimeError('panne base')):
            with self.assertRaises(RuntimeError):
                generer_etiquette_expedition(
                    expedition=self.expedition, user=self.user)

        # Après la panne : soit l'étiquetage est annulé (rollback)...
        relue = ExpeditionTransporteur.objects.get(pk=self.expedition.pk)
        self.assertNotEqual(relue.statut,
                            ExpeditionTransporteur.Statut.ETIQUETTE)
        self.assertEqual(relue.numero_suivi, '')
        self.assertEqual(self._mouvements(), 0)
        self.assertEqual(self._stock(), 10)

        # ... et le 2e appel (même objet en mémoire) pose bien la sortie.
        self.assertIs(services_wms.decrementer_stock_expedition, reel)
        with mock.patch(STOCKER, return_value='stock/x/etiquettes/t.pdf'):
            generer_etiquette_expedition(
                expedition=self.expedition, user=self.user)
        relue = ExpeditionTransporteur.objects.get(pk=self.expedition.pk)
        self.assertEqual(relue.statut, ExpeditionTransporteur.Statut.ETIQUETTE)
        self.assertTrue(relue.numero_suivi)
        self.assertEqual(self._stock(), 8)
        self.assertEqual(self._mouvements(), 1)

    def test_expedition_deja_etiquetee_sans_sortie_rejoue_le_decrement(self):
        """État hérité (étiquette posée, décrément perdu) : le rappel rejoue
        le décrément, une seule fois."""
        ExpeditionTransporteur.objects.filter(pk=self.expedition.pk).update(
            numero_suivi='INT-HERITE', etiquette_pdf_key='stock/x/e.pdf',
            statut=ExpeditionTransporteur.Statut.ETIQUETTE)
        self.expedition.refresh_from_db()
        generer_etiquette_expedition(
            expedition=self.expedition, user=self.user)
        generer_etiquette_expedition(
            expedition=self.expedition, user=self.user)
        self.assertEqual(self._stock(), 8)
        self.assertEqual(self._mouvements(), 1)
        relue = ExpeditionTransporteur.objects.get(pk=self.expedition.pk)
        # Cohérence relue : étiquette ⇔ mouvement EXP-n.
        self.assertEqual(relue.numero_suivi, 'INT-HERITE')
