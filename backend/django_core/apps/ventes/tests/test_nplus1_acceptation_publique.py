"""NPLUS1 (27/08/2026) — LE POST D'ACCEPTATION PUBLIQUE NE RECHARGE PLUS EN
CASCADE CE QU'IL A DÉJÀ EN MAIN.

Un seul POST ``/proposal/<token>/accept/`` rechargeait, chacun de son côté :

  * le devis verrouillé SANS ses relations — ``client``, ``company`` et
    ``lead`` étaient ensuite relus paresseusement par l'enregistrement de
    signature, les emails et la notification vendeur ;
  * les lignes + produits par ``compute_content_hash`` (empreinte de
    signature) PUIS par ``option_totaux`` (acompte de l'email) ;
  * les lignes une fois de plus dans un ``prefetch_related`` MORT du moteur
    PDF (``generate_premium_devis_pdf``), que ``build_quote_data`` ignorait.

Les correctifs sont tous RÉTRO-COMPATIBLES (paramètres optionnels par défaut
``None``) : ce module prouve donc les deux moitiés — la BAISSE de requêtes ET
l'égalité stricte des résultats (un hash de signature qui changerait rendrait
invérifiable toute signature déjà stockée).

MESURE EN DELTA, jamais un nombre absolu : le chemin d'acceptation traverse le
moteur PDF, les emails et les notifications ; épingler « N requêtes » y serait
un test à casser au premier changement voisin. On compare donc DEUX
acceptations identiques — l'une normale, l'autre avec les paramètres
``lignes`` neutralisés — et on exige que la première fasse STRICTEMENT moins
de requêtes sur les lignes.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_nplus1_acceptation_publique"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')

#: Table des lignes de devis — la trace SQL que ce chantier fait baisser.
TABLE_LIGNES = 'ventes_lignedevis'


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AcceptationNPlus1Tests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='NPLUS1 Co')
        self.seller = User.objects.create_user(
            username='nplus1_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NPLUS1',
            email='nplus1@example.test', telephone='+212600000091')
        self.api = APIClient()
        self.compteur = 0

    def _produit(self, nom, sku):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=100)

    def _devis(self, statut=Devis.Statut.ENVOYE):
        """Devis mono-option à trois lignes (le cas le plus courant)."""
        self.compteur += 1
        suffixe = f'NP{self.compteur:02d}'
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{suffixe}',
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'),
            created_by=self.seller)
        for i, (nom, qte) in enumerate((
                ('Panneau Canadien Solar 710W', '10'),
                ('Onduleur réseau Huawei 10kW Triphasé', '1'),
                ('Installation', '1'))):
            LigneDevis.objects.create(
                devis=devis, produit=self._produit(nom, f'{suffixe}-{i}'),
                designation=nom, quantite=Decimal(qte),
                prix_unitaire=Decimal('1000'), remise=Decimal('0'))
        return devis

    # ── Les paramètres, un par un : même résultat, moins de requêtes ─────────

    def test_option_totaux_avec_lignes_prechargees_ne_requete_plus(self):
        from apps.ventes.utils.options import option_totaux

        devis = self._devis()
        lignes = list(devis.lignes.select_related('produit').all())

        with CaptureQueriesContext(connection) as sans:
            attendu = option_totaux(devis)
        with CaptureQueriesContext(connection) as avec:
            obtenu = option_totaux(devis, lignes=lignes)

        self.assertEqual(obtenu, attendu, 'les totaux doivent être identiques')
        self.assertLess(len(avec.captured_queries),
                        len(sans.captured_queries))

    def test_next_tranche_avec_lignes_prechargees_donne_la_meme_tranche(self):
        from apps.ventes.utils.echeancier import next_tranche

        devis = self._devis()
        lignes = list(devis.lignes.select_related('produit').all())

        self.assertEqual(next_tranche(devis, lignes=lignes),
                         next_tranche(devis))

    def test_le_hash_de_signature_est_le_meme_sans_aucune_requete(self):
        """Un hash qui changerait rendrait invérifiable toute signature déjà
        stockée : l'égalité est ici une garantie de sécurité, pas de confort."""
        devis = self._devis()
        attendu = DevisSignature.compute_content_hash(devis)
        # Lignes volontairement DÉSORDONNÉES : le modèle doit les retrier par
        # ``id``, comme le faisait la requête ``order_by('id')``.
        lignes = list(devis.lignes.select_related('produit').all())[::-1]

        with self.assertNumQueries(0):
            obtenu = DevisSignature.compute_content_hash(devis, lignes=lignes)

        self.assertEqual(obtenu, attendu)

    # ── Le chemin complet ───────────────────────────────────────────────────

    def _post_accept(self, devis):
        """POST d'acceptation publique ; renvoie (réponse, requêtes lignes).

        Le stockage du PDF signé est neutralisé DES DEUX CÔTÉS de la mesure :
        il rend un PDF entier (WeasyPrint + MinIO) dont le bruit noierait le
        signal, et il n'est pas ce que ce chantier change.
        """
        link = ShareLink.for_devis(devis)
        with patch('apps.ventes.services._store_signed_pdf'):
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.post(
                    f'/api/django/public/proposal/{link.token}/accept/',
                    {'nom': 'Client NPLUS1', 'consent_esign': True},
                    format='json')
        lignes_sql = [q['sql'] for q in ctx.captured_queries
                      if TABLE_LIGNES in q['sql']
                      and q['sql'].lstrip().upper().startswith('SELECT')]
        return resp, lignes_sql

    def test_le_post_accept_charge_les_lignes_moins_souvent_qu_avant(self):
        from apps.ventes.utils import options as options_utils

        # 1) Le chemin corrigé.
        resp, apres = self._post_accept(self._devis())
        self.assertEqual(resp.status_code, 200, resp.data)

        # 2) LE MÊME chemin, paramètres ``lignes`` neutralisés — c'est-à-dire
        #    le comportement d'avant le correctif, mesuré dans la même course.
        _hash_reel = DevisSignature.compute_content_hash

        def _hash_sans_lignes(devis, lignes=None):
            return _hash_reel(devis)

        _totaux_reel = options_utils.option_totaux

        def _totaux_sans_lignes(devis, option=None, lignes=None):
            return _totaux_reel(devis, option)

        with patch.object(DevisSignature, 'compute_content_hash',
                          staticmethod(_hash_sans_lignes)), \
                patch.object(options_utils, 'option_totaux',
                             _totaux_sans_lignes):
            resp2, avant = self._post_accept(self._devis())
        self.assertEqual(resp2.status_code, 200, resp2.data)

        self.assertLess(
            len(apres), len(avant),
            'le chemin d\'acceptation doit charger les lignes MOINS souvent '
            f'qu\'avant le correctif ({len(apres)} vs {len(avant)} requêtes)')

    def test_l_instance_verrouillee_porte_deja_client_et_company(self):
        """La relecture verrouillée joint ses relations : les consommateurs en
        aval (signature, emails, notification vendeur) ne les relisent plus une
        par une."""
        captures = {}

        def _capture(*, devis, user, lignes=None):
            captures['devis'] = devis

        with patch('apps.ventes.services._store_signed_pdf'), \
                patch('apps.ventes.services._send_acceptance_emails',
                      side_effect=_capture):
            resp, _lignes_sql = self._post_accept(self._devis())
        self.assertEqual(resp.status_code, 200, resp.data)

        devis = captures['devis']
        with self.assertNumQueries(0):
            self.assertIsNotNone(devis.client)
            self.assertIsNotNone(devis.company)
            self.assertIsNone(devis.lead)
