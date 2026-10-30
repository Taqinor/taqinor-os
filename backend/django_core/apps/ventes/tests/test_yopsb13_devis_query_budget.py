"""YOPSB13 / SCA43 / APRF5 — budget de requêtes sur GET /api/django/ventes/devis/.

Garde de RÉGRESSION N+1 : le nombre de requêtes ne doit PAS grandir avec le
nombre de devis listés (page de 10 puis de 25 devis).

Historique : SCA43 avait dé-skippé puis RE-SKIPPÉ ce module — chaque ligne de
liste faisait un passage moteur (``display_totals``) qui ré-interrogeait ses
lignes, PLUS un second ``build_quote_data`` complet pour la carte A/B des devis
à deux options (``get_comparaison_options``). APRF3 a ouvert le chemin
« totaux seuls » (lignes servies depuis le préchargement, aucune lecture
d'affiche / révision / ShareLink), APRF4 a complété le préchargement du
viewset, et APRF5 fait passer chaque ligne par UN SEUL passage moteur :
``DevisSerializer._display`` mémoïse le ``data`` et la carte A/B le relit (elle
RESTE servie en liste — ``DevisRow.jsx`` la lit). Le skip est retiré.

Page MIXTE : devis mono-option, devis à deux options, devis facturés, aucun
lien de partage (un GET de liste ne doit en écrire aucun — AMOT13).

Test-du-test : remettre ``@unittest.skip`` ⇒ APRF27 rougit ; retirer la
mémoïsation de ``data`` ⇒ la page à 25 fait un second ``build_quote_data``
par devis à deux options et ``test_query_count_does_not_grow_with_row_count``
échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
DEVIS_URL = '/api/django/ventes/devis/'
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}

MONO = [('Panneau mono 550W', '12', '1100'),
        ('Onduleur réseau 5kW', '1', '11700')]
DEUX = MONO + [('Onduleur hybride 5kW', '1', '15000'),
               ('Batterie 5 kWh', '1', '14000')]


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _ecritures(ctx):
    return [q['sql'] for q in ctx.captured_queries
            if q['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'))]


class DevisListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget Devis SARL')
        self.user = User.objects.create_user(
            username='budget_devis_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Budget',
            email='budget@example.com', telephone='+212600000002')
        # Les singletons de config société (profil, modèles de documents,
        # barème) sont créés à la PREMIÈRE lecture : posés ici pour mesurer ce
        # qu'une liste coûte À CHAQUE affichage, pas l'amorçage d'une société.
        from apps.parametres.models import CompanyProfile, TariffSettings
        from apps.parametres.models_documents import DocumentTemplates
        CompanyProfile.get(company=self.company)
        DocumentTemplates.get(company=self.company)
        TariffSettings.get(company=self.company)

    def _seed_devis(self, count, start=0, acceptes=False):
        """Page MIXTE : 1 sur 2 à deux options, 1 sur 3 facturé ;
        ``acceptes`` (VNT68) : 1 sur 4 ACCEPTÉ sans facture directe (la vente
        qui cherche ses factures de BC / consolidées)."""
        for i in range(start, start + count):
            deux = bool(i % 2)
            accepte = acceptes and i % 4 == 1
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-{i:04d}',
                client=self.client_obj, created_by=self.user,
                taux_tva=Decimal('20'),
                statut=(Devis.Statut.ACCEPTE if accepte
                        else Devis.Statut.BROUILLON),
                etude_params=dict(DEUX_OPTIONS) if deux else None)
            for j, (desig, qte, pu) in enumerate(DEUX if deux else MONO):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'{i}-{j}-{desig}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                    remise=Decimal('0'))
            if i % 3 == 0:
                Facture.objects.create(
                    company=self.company, reference=f'FAC-{MONTH}-{i:04d}',
                    devis=devis, client=self.client_obj,
                    statut=Facture.Statut.EMISE, montant_ht=Decimal('100'),
                    montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
                    created_by=self.user)

    def _devis_simple(self, reference, **champs):
        devis = Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, created_by=self.user,
            taux_tva=Decimal('20'), statut=Devis.Statut.ACCEPTE, **champs)
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'KIT-{reference}',
            prix_vente=Decimal('10000'), prix_achat=Decimal('1'),
            quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            remise=Decimal('0'))
        return devis

    def _facture(self, reference, **champs):
        return Facture.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), created_by=self.user, **champs)

    def _seed_ventes(self):
        """VNT68 — les quatre portes d'une vente, servies par la liste :
        chaîne de révision V1 → V2 (facture émise sur la V1), vente facturée
        par son BON DE COMMANDE, vente facturée par une CONSOLIDÉE."""
        from apps.ventes.models import BonCommande
        from apps.ventes.models_facturation import FactureSource
        v1 = self._devis_simple(f'DEV-{MONTH}-V681')
        v2 = self._devis_simple(f'DEV-{MONTH}-V682', version=2,
                                version_parent=v1)
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        self._facture(f'FAC-{MONTH}-V681', devis=v1)
        par_bc = self._devis_simple(f'DEV-{MONTH}-V683')
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-V683',
            devis=par_bc, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        self._facture(f'FAC-{MONTH}-V683', bon_commande=bc)
        conso = self._devis_simple(f'DEV-{MONTH}-V684')
        facture = self._facture(f'FAC-{MONTH}-V684')
        FactureSource.objects.create(company=self.company, facture=facture,
                                     devis=conso,
                                     sous_total_ht=Decimal('1000'))
        return v2, par_bc, conso

    def _get_liste(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(DEVIS_URL, {'page_size': 100})
        self.assertEqual(resp.status_code, 200)
        return resp, ctx

    @staticmethod
    def _lignes(resp):
        data = resp.data
        return data.get('results', data) if isinstance(data, dict) else data

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_devis(10)
        resp_10, ctx_10 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_10)), 10)

        self._seed_devis(15, start=10)  # total 25
        resp_25, ctx_25 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_25)), 25)

        self.assertEqual(
            len(ctx_10.captured_queries), len(ctx_25.captured_queries),
            'Le nombre de requêtes a grandi avec le nombre de devis (N+1) — '
            'vérifier le préchargement de DevisViewSet.queryset et le passage '
            'moteur UNIQUE de DevisSerializer._display.')
        # CLAUSE PERSISTANCE n/a — une lecture n'écrit rien (aucun ShareLink).
        self.assertEqual(_ecritures(ctx_25), [])

    def test_ventes_en_lot_requetes_constantes(self):
        """VNT68 — ``vente`` (et ``solde``) d'UNE page se lisent en lot :
        chaîne de révision, BC et consolidée comprises, la page de 25 coûte
        exactement ce que coûte la page de 10 (un accepté sur quatre)."""
        self._seed_ventes()
        self._seed_devis(10, acceptes=True)
        resp_10, ctx_10 = self._get_liste()
        self._seed_devis(15, start=10, acceptes=True)
        resp_25, ctx_25 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_25)),
                         len(self._lignes(resp_10)) + 15)
        self.assertEqual(
            len(ctx_10.captured_queries), len(ctx_25.captured_queries),
            'VNT68 — le nombre de requêtes a grandi avec le nombre de devis '
            '(vente / solde lus ligne par ligne au lieu du lot de la page).')
        # Plafond DÉRIVÉ du plan de requêtes (23 mesurées par APRF5 + ~21
        # requêtes fixes du lot, marge comprise — docs/query-budgets.yml).
        self.assertLessEqual(len(ctx_25.captured_queries), 60)
        self.assertEqual(_ecritures(ctx_25), [])

    def test_vente_liste_egale_detail_et_lecture_unitaire(self):
        """VNT68 — ``vente`` est servie en liste ET au détail, identique à
        ``etat_vente`` lu devis par devis ; ``solde`` reste celui de
        ``solde_devis`` (mêmes clés, toutes en texte)."""
        from apps.ventes.utils.echeancier import solde_devis
        from apps.ventes.vente_facturation import etat_vente
        v2, par_bc, conso = self._seed_ventes()
        self._seed_devis(4, acceptes=True)
        resp, _ctx = self._get_liste()
        lignes = {r['id']: r for r in self._lignes(resp)}
        for devis in Devis.objects.filter(company=self.company):
            ligne = lignes[devis.pk]
            attendu = etat_vente(Devis.objects.get(pk=devis.pk), self.user)
            self.assertEqual(ligne['vente'], attendu, devis.reference)
            self.assertEqual(ligne['solde'], {
                k: str(v) for k, v in solde_devis(
                    Devis.objects.get(pk=devis.pk)).items()})
            detail = self.api.get('%s%s/' % (DEVIS_URL, devis.pk))
            self.assertEqual(detail.data['vente'], ligne['vente'])
            self.assertEqual(detail.data['solde'], ligne['solde'])
        self.assertEqual(lignes[par_bc.pk]['vente']['emis_ttc'], '1200.00')
        self.assertEqual(lignes[conso.pk]['vente']['emis_ttc'], '1200.00')
        self.assertEqual(
            [v['id'] for v in lignes[v2.pk]['vente']['versions']],
            [v2.version_parent_id, v2.pk])

    def test_query_count_stays_within_fixed_budget(self):
        # Plafond absolu calé sur le coût O(1) mesuré par SCA43 (~32 requêtes
        # à 10 devis), marge de régression comprise. Le test de CROISSANCE
        # ci-dessus est la garde N+1 AUTORITAIRE.
        self._seed_devis(10)
        with self.assertMaxQueries(40):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)

    def _seed_agricoles(self, count, start=0):
        """ERR-PERF-DEVIS-LISTE-AGRICOLE-N1 — devis AGRICOLES avec lead et
        saisies d'économie de pompage (le chemin qui coûtait ≈ 11 requêtes
        par ligne : règle FDA, délai SAV, économie de pompage)."""
        import json
        from pathlib import Path
        from apps.crm.models import Lead
        saisies = json.loads(
            (Path(__file__).resolve().parent.parent / 'contract_samples'
             / 'economie_pompage.json').read_text(encoding='utf-8')
        )['saisies_economie_pompage']['exemple']
        for i in range(start, start + count):
            lead = Lead.objects.create(
                company=self.company, nom='Agri', prenom=f'Lead {i}',
                telephone=f'+2126110{i:05d}', ville='Taroudant')
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-A{i:03d}',
                client=self.client_obj, lead=lead, created_by=self.user,
                taux_tva=Decimal('20'), statut=Devis.Statut.BROUILLON,
                mode_installation='agricole',
                etude_params={'saisies_economie_pompage': saisies})
            for j, (desig, qte, pu) in enumerate(
                    [('Pompe immergée 4 kW', '1', '18000'),
                     ('Panneau mono 550W', '10', '1100')]):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'A{i}-{j}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                    remise=Decimal('0'))

    def test_devis_agricoles_pente_nulle(self):
        """ERR-PERF-DEVIS-LISTE-AGRICOLE-N1 — la liste ne calcule ni
        l'économie de pompage ni les réglages FDA / SAV (aucune clé de la
        liste ne les lit) : 5 puis 20 devis agricoles, pente 0 ± 1 ; le
        total affiché reste celui du moteur complet (règle #4)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        self._seed_agricoles(5)
        resp_5, ctx_5 = self._get_liste()
        self._seed_agricoles(15, start=5)
        resp_20, ctx_20 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_20)), 20)
        self.assertLessEqual(
            abs(len(ctx_20.captured_queries) - len(ctx_5.captured_queries)),
            1, 'Devis agricoles : le nombre de requêtes a grandi avec le '
               'nombre de lignes (économie de pompage calculée en liste ?).')
        self.assertEqual(_ecritures(ctx_20), [])
        for ligne in self._lignes(resp_20)[:3]:
            complet = build_quote_data(Devis.objects.get(pk=ligne['id']),
                                       {'pdf_mode': 'onepage'})
            self.assertEqual(ligne['total_affiche'], complet['display_total'])

    def test_carte_ab_en_liste(self):
        """La carte A/B reste servie EN LISTE, mêmes valeurs qu'au détail."""
        self._seed_devis(6)
        resp, _ctx = self._get_liste()
        lignes = self._lignes(resp)
        deux = [r for r in lignes if r.get('nb_options') == 2]
        self.assertTrue(deux)
        for ligne in lignes:
            detail = self.api.get('%s%s/' % (DEVIS_URL, ligne['id']))
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(ligne['total_affiche'],
                             detail.data['total_affiche'])
            self.assertEqual(ligne['nb_options'], detail.data['nb_options'])
            self.assertEqual(ligne['comparaison_options'],
                             detail.data['comparaison_options'])
        for ligne in deux:
            carte = ligne['comparaison_options']
            self.assertIsNotNone(carte['sans']['ttc'])
            self.assertIsNotNone(carte['avec']['ttc'])
