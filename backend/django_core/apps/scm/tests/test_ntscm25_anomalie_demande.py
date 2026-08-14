"""NTSCM25 — Détection d'anomalie de demande (pic/creux inattendu).

Critère d'acceptation : une consommation multipliée par 4 sur un mois isolé
déclenche un flag, une variation normale de ±20% n'en déclenche aucun."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.services import detecter_anomalies_demande
from apps.stock.models import MouvementStock, Produit
from core.models import AnomalyFlag

from .helpers import auth, make_company, make_user


class DetecterAnomaliesDemandeTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-anomalie', 'Supply Anomalie')
        self.admin = make_user(self.company, 'scm-anomalie-admin', 'admin')

    def _seed(self, produit, valeurs):
        """``valeurs[-1]`` = mois le plus RÉCENT (dernier mois écoulé)."""
        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        for offset, valeur in enumerate(reversed(valeurs)):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=valeur, quantite_avant=100000,
                quantite_apres=100000 - valeur)
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

    def test_pic_isole_x4_declenche_un_flag(self):
        produit = Produit.objects.create(
            company=self.company, nom='Câble solaire', prix_vente=15,
            quantite_stock=1000)
        valeurs = [100] * 11 + [400]  # dernier mois = pic x4
        self._seed(produit, valeurs)

        flags = detecter_anomalies_demande(self.company)
        self.assertTrue(any(
            f.subject_type == 'scm.demande'
            and f.metric == f'consommation_mensuelle:{produit.id}'
            for f in flags))
        self.assertTrue(
            AnomalyFlag.objects.filter(
                company=self.company, subject_type='scm.demande',
                metric=f'consommation_mensuelle:{produit.id}',
                category=AnomalyFlag.CATEGORY_STOCK).exists())

    def test_variation_normale_ne_declenche_rien(self):
        produit = Produit.objects.create(
            company=self.company, nom='Connecteur', prix_vente=8,
            quantite_stock=1000)
        # Série volatile (spread réaliste) ; dernier mois dans le même ordre
        # de grandeur que le reste -> aucun z-score n'atteint le seuil.
        valeurs = [80, 130, 90, 120, 85, 125, 95, 115, 80, 130, 90, 120]
        self._seed(produit, valeurs)

        flags = detecter_anomalies_demande(self.company)
        self.assertFalse(any(
            f.metric == f'consommation_mensuelle:{produit.id}' for f in flags))

    def test_appel_repete_ne_duplique_pas_le_flag(self):
        produit = Produit.objects.create(
            company=self.company, nom='Fusible DC', prix_vente=12,
            quantite_stock=1000)
        valeurs = [100] * 11 + [400]
        self._seed(produit, valeurs)

        detecter_anomalies_demande(self.company)
        detecter_anomalies_demande(self.company)

        self.assertEqual(
            AnomalyFlag.objects.filter(
                company=self.company, subject_type='scm.demande',
                metric=f'consommation_mensuelle:{produit.id}').count(),
            1)

    def test_endpoint_detecter_puis_lister(self):
        produit = Produit.objects.create(
            company=self.company, nom='Disjoncteur DC', prix_vente=20,
            quantite_stock=1000)
        valeurs = [100] * 11 + [400]
        self._seed(produit, valeurs)

        resp_detecter = auth(self.admin).post(
            '/api/django/scm/anomalies-demande/detecter/', {}, format='json')
        self.assertEqual(resp_detecter.status_code, 200, resp_detecter.data)
        self.assertGreaterEqual(resp_detecter.data['nb_flags'], 1)

        resp_liste = auth(self.admin).get('/api/django/scm/anomalies-demande/')
        self.assertEqual(resp_liste.status_code, 200, resp_liste.data)
        self.assertTrue(any(
            row['produit_id'] == str(produit.id) for row in resp_liste.data))
