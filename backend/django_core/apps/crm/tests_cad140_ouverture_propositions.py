"""CAD140 (audit L3 du 21/09/2026, round 2) — le score d'engagement client
reprend le signal comportemental (ouverture de proposition) abandonné à la
création de `apps.crm.engagement` (NTCRM16).

Une lane précédente n'avait livré que le renommage du docstring en tête de
fichier, faute d'un sélecteur PAR CLIENT côté `apps.ventes` — ce sélecteur
(`apps.ventes.selectors.devis_ouverts_ratio_client`) existe désormais et ce
fichier verrouille sa réintégration :

  * un client dont TOUS les devis ont été ouverts (``ShareLink.view_count`` >
    0, compteur fiabilisé par CAD137) obtient le score plein du signal ;
  * un client dont AUCUN devis n'a été ouvert obtient 0 ;
  * un devis BROUILLON n'entre jamais dans le ratio (jamais montré au
    client, il n'a jamais pu être « ouvert ») ;
  * le poids du signal reste celui documenté en tête de `engagement.py`
    (20 pts, la part symétrique des 5 signaux — jamais un poids inventé) et
    le score total reste plafonné à 100.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.engagement import compute_engagement_score
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import devis_ouverts_ratio_client


class DevisOuvertsRatioClientTests(TestCase):
    """Le sélecteur ventes lui-même — CAD140."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD140 Selecteur Co')

    def _devis(self, ref, *, statut=Devis.Statut.ENVOYE, client=None):
        client = client or Client.objects.create(
            company=self.company, nom='Client', email=f'{ref}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=ref, client=client,
            statut=statut, taux_tva=Decimal('20'))

    def test_sans_client_id_ne_compte_rien(self):
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, None),
            {'total': 0, 'ouverts': 0})

    def test_client_sans_aucun_devis(self):
        client = Client.objects.create(company=self.company, nom='Vide')
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, client.id),
            {'total': 0, 'ouverts': 0})

    def test_devis_brouillon_exclu_du_ratio(self):
        client = Client.objects.create(company=self.company, nom='Brouillon')
        self._devis('DEV-CAD140-B1', statut=Devis.Statut.BROUILLON,
                    client=client)
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, client.id),
            {'total': 0, 'ouverts': 0})

    def test_devis_jamais_ouvert_compte_dans_le_total_pas_les_ouverts(self):
        client = Client.objects.create(company=self.company, nom='Jamais')
        devis = self._devis('DEV-CAD140-J1', client=client)
        ShareLink.objects.create(company=self.company, devis=devis)
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, client.id),
            {'total': 1, 'ouverts': 0})

    def test_devis_ouvert_compte_dans_les_deux(self):
        client = Client.objects.create(company=self.company, nom='Ouvert')
        devis = self._devis('DEV-CAD140-O1', client=client)
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=3)
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, client.id),
            {'total': 1, 'ouverts': 1})

    def test_ratio_mixte_sur_plusieurs_devis(self):
        client = Client.objects.create(company=self.company, nom='Mixte')
        ouvert = self._devis('DEV-CAD140-M1', client=client)
        jamais = self._devis('DEV-CAD140-M2', client=client)
        ShareLink.objects.create(
            company=self.company, devis=ouvert, view_count=1)
        ShareLink.objects.create(
            company=self.company, devis=jamais, view_count=0)
        self.assertEqual(
            devis_ouverts_ratio_client(self.company, client.id),
            {'total': 2, 'ouverts': 1})


class EngagementOuverturePropositionsScoreTests(TestCase):
    """Le signal reintégré dans `compute_engagement_score` — CAD140."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD140 Score Co')
        self.now = timezone.now()

    def test_client_avec_toutes_ses_propositions_ouvertes_score_plus_haut(self):
        """Deux clients IDENTIQUES sur les quatre autres signaux (aucun) :
        seule l'ouverture de la proposition les distingue — LE signal que
        CAD140 réintègre doit à lui seul creuser l'écart."""
        ouvreur = Client.objects.create(company=self.company, nom='Ouvreur')
        devis_ouvreur = Devis.objects.create(
            company=self.company, client=ouvreur, reference='DEV-CAD140-S1',
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        ShareLink.objects.create(
            company=self.company, devis=devis_ouvreur, view_count=2)

        silencieux = Client.objects.create(
            company=self.company, nom='Silencieux')
        devis_silencieux = Devis.objects.create(
            company=self.company, client=silencieux,
            reference='DEV-CAD140-S2', statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        ShareLink.objects.create(
            company=self.company, devis=devis_silencieux, view_count=0)

        score_ouvreur = compute_engagement_score(ouvreur, now=self.now)
        score_silencieux = compute_engagement_score(
            silencieux, now=self.now)
        self.assertGreater(score_ouvreur, score_silencieux)
        # Isolé (aucun autre signal actif) : exactement le poids du signal.
        self.assertEqual(score_ouvreur, 20)
        self.assertEqual(score_silencieux, 0)

    def test_score_reste_plafonne_a_100_avec_les_cinq_signaux_au_max(self):
        client = Client.objects.create(company=self.company, nom='Complet')
        devis = Devis.objects.create(
            company=self.company, client=client, reference='DEV-CAD140-S3',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=5)
        score = compute_engagement_score(client, now=self.now)
        self.assertLessEqual(score, 100)
