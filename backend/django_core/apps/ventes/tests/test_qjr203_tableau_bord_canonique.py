"""QJR203 / décision fondateur DV2 — le tableau de bord ventes route par la
chaîne canonique, et son filtre de période s'applique AUSSI aux montants.

CE QUI ÉTAIT FAUX (``dashboard_view.py``, avant ce correctif). Les deux
montants « valeur pipeline » — le global et celui de ``par_commercial`` —
étaient une somme SQL de lignes
``quantite × prix_unitaire × (1 − remise/100)`` suivie d'une **TVA 20 % codée
en dur**. Cette expression :

  * ignorait ``Devis.remise_globale`` ;
  * ignorait ``ligne_compte_dans_totaux`` (optionnelles, sections, notes) ;
  * **additionnait LES DEUX OPTIONS** d'un devis à deux options ;
  * et ``par_commercial`` n'appliquait même pas ``periode`` — le sélecteur de
    période bougeait les compteurs, jamais les montants.

Le devis de référence est celui de ``test_qjr_solde_deux_options`` (mêmes
chiffres), plus une **remise globale de 10 %** :

    réseau 11 700 · hybride 24 000 · panneaux 14 × 1 100 · batterie 14 000 ·
    installation 4 000, TVA 20 %, remise globale 10 %

    → option AVEC (celle du total affiché, D9) = 57 400 HT brut
      → −5 740 de remise → 51 660 HT net → 10 332 TVA → **61 992,00 TTC**
    → l'ancien calcul du tableau de bord : (11 700 + 24 000 + 15 400 + 14 000
      + 4 000) × 1,20 = **82 920,00** — la somme des DEUX options, remise
      globale perdue, un montant qui n'existe dans aucun document.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr203_tableau_bord_canonique"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.test_utils import AssertQueryBudgetMixin
from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import display_totals
from apps.ventes.utils.options import option_totaux

User = get_user_model()
URL = '/api/django/ventes/dashboard/'
MONTH = timezone.now().strftime('%Y%m')

#: Le TTC de l'option mise en avant (AVEC), remise globale honorée.
TTC_AVEC_REMISE = Decimal('61992.00')
#: Ce que le tableau de bord affichait AVANT QJR203 : la somme des DEUX
#: options, remise globale ignorée, TVA 20 % en dur.
TTC_ANCIEN_CALCUL_FAUX = Decimal('82920.00')


class _Base(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            slug='qjr203-co', nom='QJR203 Co')
        self.caller = User.objects.create_user(
            username='qjr203_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='qjr203_comm', password='x', first_name='Sami',
            last_name='Bennani', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR203',
            email='qjr203@example.invalid', telephone='+212600000203')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.caller)}')
        self.compteur = 0

    # -- fixtures ---------------------------------------------------------
    def _lignes(self, devis, lignes, prefixe):
        for desig, qty, pu in lignes:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{prefixe}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))

    def _devis_deux_options(self, remise_globale='10'):
        """PV86 — un document à DEUX options DÉCLARE son alternative dans
        ``etude_params['scenario']`` (ce que le générateur persiste)."""
        self.compteur += 1
        prefixe = f'Q203D{self.compteur:02d}'
        devis = Devis.objects.create(
            company=self.company, created_by=self.commercial,
            reference=f'DEV-{MONTH}-{prefixe}', client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            remise_globale=Decimal(remise_globale),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        self._lignes(devis, [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ], prefixe)
        return devis

    def _devis_simple(self, prix='8000', statut=Devis.Statut.ENVOYE):
        self.compteur += 1
        prefixe = f'Q203S{self.compteur:02d}'
        devis = Devis.objects.create(
            company=self.company, created_by=self.commercial,
            reference=f'DEV-{MONTH}-{prefixe}', client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'))
        self._lignes(devis, [('Onduleur réseau', '1', prix)], prefixe)
        return devis

    @staticmethod
    def _vieillir(devis, jours=500):
        """``date_creation`` est ``auto_now_add`` : on la recule en base."""
        Devis.objects.filter(pk=devis.pk).update(
            date_creation=timezone.now() - timedelta(days=jours))

    # -- lecture ----------------------------------------------------------
    def _dashboard(self):
        return self.api.get(URL).data

    def _pipeline_global(self, data):
        return Decimal(data['devis']['valeur_pipeline'])

    def _pipeline_commercial(self, data, nom='Sami Bennani'):
        lignes = [row for row in data['par_commercial']
                  if row['commercial'] == nom]
        return lignes[0] if lignes else None


class PipelineSuitLaChaineCanonique(_Base):
    """Le montant du tableau de bord est CELUI de la liste, au centime."""

    def test_le_pipeline_egale_le_total_affiche_de_la_liste(self):
        """LE test de QJR203. Rouge avant le correctif : le tableau de bord
        rendait la somme des deux options × 1,20 (82 920), la liste 61 992."""
        devis = self._devis_deux_options()
        affiche = display_totals(devis)
        self.assertEqual(affiche['nb_options'], 2)
        ecart = abs(self._pipeline_global(self._dashboard())
                    - Decimal(str(affiche['total'])))
        self.assertLessEqual(ecart, Decimal('0.01'), (
            "le tableau de bord et la liste ne montrent pas le même prix pour "
            "le même devis"))

    def test_le_pipeline_nest_plus_la_somme_des_deux_options(self):
        """La régression épinglée nommément : l'ancien nombre est INTERDIT."""
        self._devis_deux_options()
        self.assertNotEqual(self._pipeline_global(self._dashboard()),
                            TTC_ANCIEN_CALCUL_FAUX)

    def test_la_remise_globale_est_honoree(self):
        self._devis_deux_options()
        self.assertEqual(self._pipeline_global(self._dashboard()),
                         TTC_AVEC_REMISE)

    def test_le_pipeline_egale_la_chaine_canonique(self):
        """Même porte que le solde, l'échéancier et le PDF."""
        devis = self._devis_deux_options()
        self.assertEqual(self._pipeline_global(self._dashboard()),
                         option_totaux(devis)['ttc'])

    def test_par_commercial_porte_LE_MEME_montant(self):
        """Les deux montants de l'écran sortaient de la MÊME expression fausse
        (`par_commercial` la réutilisait mot pour mot) : ils sortent
        désormais de la même chaîne canonique."""
        self._devis_deux_options()
        data = self._dashboard()
        ligne = self._pipeline_commercial(data)
        self.assertIsNotNone(ligne)
        self.assertEqual(Decimal(ligne['valeur_pipeline']),
                         self._pipeline_global(data))
        self.assertEqual(ligne['devis_actifs'], 1)

    def test_un_devis_sans_ligne_compte_pour_un_devis_actif(self):
        """Le comportement de `Count('id', distinct=True)` est préservé."""
        self.compteur += 1
        Devis.objects.create(
            company=self.company, created_by=self.commercial,
            reference=f'DEV-{MONTH}-Q203V{self.compteur:02d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        ligne = self._pipeline_commercial(self._dashboard())
        self.assertEqual(ligne['devis_actifs'], 1)
        self.assertEqual(Decimal(ligne['valeur_pipeline']), Decimal('0'))


class LaPeriodeSApplique(_Base):
    """DV2 — le sélecteur de période bougeait les compteurs, pas les montants."""

    def test_un_devis_hors_periode_ne_compte_dans_AUCUN_des_deux_montants(self):
        recent = self._devis_simple(prix='8000')
        vieux = self._devis_simple(prix='50000')
        self._vieillir(vieux)

        data = self._dashboard()
        attendu = option_totaux(recent)['ttc']
        self.assertEqual(self._pipeline_global(data), attendu)
        ligne = self._pipeline_commercial(data)
        self.assertEqual(Decimal(ligne['valeur_pipeline']), attendu)
        self.assertEqual(ligne['devis_actifs'], 1)

    def test_la_periode_explicite_borne_les_deux_montants(self):
        """?start=&end= sur une fenêtre qui n'attrape rien → zéro des deux
        côtés (avant : les compteurs tombaient à 0, les montants restaient)."""
        self._devis_simple(prix='8000')
        hier = (timezone.now() - timedelta(days=400)).date().isoformat()
        avant = (timezone.now() - timedelta(days=402)).date().isoformat()
        data = self.api.get(URL, {'start': avant, 'end': hier}).data
        self.assertEqual(self._pipeline_global(data), Decimal('0'))
        self.assertEqual(data['par_commercial'], [])


class BudgetDeRequetes(AssertQueryBudgetMixin, _Base):
    """SCA40 reste fermé : le tableau de bord n'a PAS de N+1."""

    def test_le_nombre_de_requetes_ne_grandit_pas_avec_le_pipeline(self):
        self._devis_simple()
        with self.assertMaxQueries(60) as petit:
            self.api.get(URL)
        compte_petit = len(petit.captured_queries)

        for _ in range(5):
            self._devis_simple()
        with self.assertMaxQueries(compte_petit) as grand:
            self.api.get(URL)
        compte_grand = len(grand.captured_queries)

        self.assertEqual(compte_grand, compte_petit, (
            f"{compte_petit} requête(s) pour 1 devis, {compte_grand} pour 6 : "
            "régression N+1 dans le pipeline du tableau de bord."))

    def test_le_nombre_de_requetes_ne_grandit_pas_avec_l_equipe(self):
        """La garantie d'origine de SCA40, reprise telle quelle."""
        for index in range(2):
            comm = User.objects.create_user(
                username=f'qjr203_c{index}', password='x',
                first_name=f'P{index}', last_name=f'N{index}',
                role_legacy='commercial', company=self.company)
            devis = self._devis_simple()
            Devis.objects.filter(pk=devis.pk).update(created_by=comm)
        with self.assertMaxQueries(60) as petit:
            self.api.get(URL)
        compte_petit = len(petit.captured_queries)

        for index in range(2, 6):
            comm = User.objects.create_user(
                username=f'qjr203_c{index}', password='x',
                first_name=f'P{index}', last_name=f'N{index}',
                role_legacy='commercial', company=self.company)
            devis = self._devis_simple()
            Devis.objects.filter(pk=devis.pk).update(created_by=comm)
        with self.assertMaxQueries(compte_petit) as grand:
            self.api.get(URL)

        self.assertEqual(len(grand.captured_queries), compte_petit, (
            "le nombre de requêtes grandit avec le nombre de commerciaux — "
            "c'est exactement le N+1 que SCA40 a fermé."))
