"""AFAC27 (C-AFAC-024) — tout avoir client passe par UN service
`creer_avoir_facture` : un retour crédite exactement ce qui a été facturé
pour ces unités (remise globale et palier d'arrondi repris, le retour qui
épuise les quantités porte le solde au centime), plafond lu sous
`select_for_update`, `avoir_cree` émis.

Rejoue FCOR-1 (avoir de retour `remise_globale 0.00`, 12 000 TTC crédités
pour 10 200 facturés, `avoir_cree` jamais émis) et L2-C-AFAC-024 (palier :
12 044,40 puis 400). Endpoints et service réels, aucun mock.

Écart assumé avec le texte de la tâche : les factures sont posées
directement (remise 15 % / palier 100) plutôt que par `facturer-complet` —
le service lit la facture, pas son chemin de création.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_retour_client_avoir"
"""
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class _Base:
    def _setup(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC27 Co', slug=f'afac27-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac27_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Retour', prenom='AFAC27',
            email=f'afac27-{_nxt()}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AFAC27-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _facture(self, *, pu, qte=2, remise_globale='0', arrondi_pas=0):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC27-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20.00'),
            remise_globale=Decimal(remise_globale), arrondi_pas=arrondi_pas)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal(qte), prix_unitaire=Decimal(pu),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return facture

    def _retour(self, facture, qte=1):
        return self.api.post(
            f'/api/django/ventes/factures/{facture.id}/retour-client/',
            {'motif': 't', 'restocker': False,
             'lignes': [{'produit': self.produit.id, 'quantite': qte}]},
            format='json')


class RetourClientAvoirTests(_Base, TestCase):
    def setUp(self):
        self._setup()

    def test_retour_partiel_facture_remisee_credite_net(self):
        from apps.ventes.models import Avoir
        facture = self._facture(pu='10000', remise_globale='15')
        self.assertEqual(facture.total_ttc, Decimal('20400.00'))
        r = self._retour(facture)
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(pk=r.data['id'])
        self.assertEqual(avoir.remise_globale, Decimal('15'))
        self.assertEqual(avoir.total_ttc, Decimal('10200.00'))

    def test_retour_total_en_deux_fois_egal_ttc(self):
        from apps.ventes.models import Facture
        facture = self._facture(pu='10000', remise_globale='15')
        r1 = self._retour(facture)
        r2 = self._retour(facture)
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.avoirs_total, Decimal('20400.00'))
        self.assertEqual(facture.montant_du, Decimal('0'))
        # CI #997 fuzz — plus rien de retournable : refus d'ÉTAT, 409.
        self.assertEqual(self._retour(facture).status_code, 409)

    def test_produit_inconnu_404_quantite_excessive_409(self):
        """api-fuzz (ENF11) : produit bien formé mais absent = 404 ; quantité
        au-delà du retournable = refus d'ÉTAT (409) ; aucun avoir créé."""
        from apps.ventes.models import Avoir
        facture = self._facture(pu='10000')
        for ligne, statut in (({'produit': 2147483647, 'quantite': '1'}, 404),
                              ({'produit': self.produit.id, 'quantite': '99'}, 409)):
            r = self.api.post(
                f'/api/django/facturation/factures/{facture.id}/retour-client/',
                {'motif': 'x', 'restocker': False, 'lignes': [ligne]},
                format='json')
            self.assertEqual(r.status_code, statut, r.data)
        self.assertFalse(Avoir.objects.filter(facture=facture).exists())

    def test_corps_fuzz_ligne_mal_typee_400(self):
        """api-fuzz (ENF11) : ``produit`` non entier / ``quantite`` vide
        levaient une 500 — le corps est validé par son sérialiseur déclaré
        (400 ``validation_error``), aucun avoir n'est créé."""
        from apps.ventes.models import Avoir
        facture = self._facture(pu='10000')
        r = self.api.post(
            f'/api/django/facturation/factures/{facture.id}/retour-client/',
            {'motif': '0', 'restocker': False,
             'lignes': [{'produit': [None, None], 'quantite': ''}]},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['error']['code'], 'validation_error')
        self.assertFalse(Avoir.objects.filter(facture=facture).exists())

    def test_retour_palier_arrondi(self):
        from apps.ventes.models import Avoir, Facture
        facture = self._facture(pu='10037', arrondi_pas=100)
        self.assertEqual(facture.total_ttc, Decimal('24000.00'))
        r1 = self._retour(facture)
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(Avoir.objects.get(pk=r1.data['id']).total_ttc,
                         Decimal('12000.00'))
        r2 = self._retour(facture)
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(Avoir.objects.get(pk=r2.data['id']).total_ttc,
                         Decimal('12000.00'))
        self.assertEqual(Facture.objects.get(pk=facture.pk).avoirs_total,
                         Decimal('24000.00'))

    def test_retour_emet_avoir_cree(self):
        from core.events import avoir_cree
        recus = []

        def _recepteur(sender, instance=None, **kwargs):
            recus.append(instance.pk)

        avoir_cree.connect(_recepteur, weak=False)
        try:
            facture = self._facture(pu='10000')
            r = self._retour(facture)
        finally:
            avoir_cree.disconnect(_recepteur)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(recus, [r.data['id']])


class RetourTvaAuTauxDeLaLigneTests(_Base, TestCase):
    """ERR-RETOUR-CLIENT-TVA-MELANGEE (29/10/2026) — un retour figé (palier
    repris au prorata, ou solde au centime du dernier retour) créditait au
    taux MÉLANGÉ de la facture, dans un seul panier au taux d'en-tête : un
    panneau à 10 % crédité dans un panier à 20 %, un onduleur crédité d'un HT
    supérieur au HT net de sa ligne. La TVA suit le taux de chaque ligne
    rendue (le calcul de ``creer-avoir``) ; le HT ne dépasse jamais le HT net
    après remise."""

    def setUp(self):
        self._setup()
        from apps.stock.models import Produit
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'AFAC27-P-{_nxt()}',
            prix_vente=Decimal('1234.57'), quantite_stock=10)

    def _facture_mixte(self, *, qte_panneau=1, arrondi_pas=0):
        """Onduleur 12 345,67 à 20 % + panneaux 1 234,57 à 10 %, remise 5 %."""
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC27-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('5'), arrondi_pas=arrondi_pas)
        for produit, qte, pu, taux in (
                (self.produit, '1', '12345.67', '20.00'),
                (self.panneau, qte_panneau, '1234.57', '10.00')):
            LigneFacture.objects.create(
                facture=facture, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), taux_tva=Decimal(taux))
        return facture

    def _retour_de(self, facture, produit):
        from apps.ventes.models import Avoir
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/retour-client/',
            {'motif': 't', 'restocker': False,
             'lignes': [{'produit': produit.id, 'quantite': '1'}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Avoir.objects.get(pk=r.data['id'])

    def _assert_au_taux_de_la_ligne(self, avoir, taux, ht_net_ligne):
        paniers = [(Decimal(str(b['taux'])), Decimal(str(b['base_ht'])),
                    Decimal(str(b['montant']))) for b in avoir.tva_par_taux]
        self.assertEqual([p[0] for p in paniers], [Decimal(taux)], paniers)
        _, base, tva = paniers[0]
        self.assertEqual(base, avoir.total_ht)
        self.assertEqual(tva, avoir.total_tva)
        self.assertLessEqual(avoir.total_ht, Decimal(ht_net_ligne))
        self.assertLessEqual(abs(base * Decimal(taux) / 100 - tva),
                             Decimal('0.01'))
        self.assertEqual(avoir.total_ht + avoir.total_tva, avoir.total_ttc)
        self.assertEqual(len(avoir.ventilation_tva or paniers), 1)

    def test_retour_panneau_10_pct_egal_creer_avoir(self):
        avoir = self._retour_de(self._facture_mixte(), self.panneau)
        self.assertEqual(
            [(Decimal(str(b['taux'])), b['base_ht'], b['montant'])
             for b in avoir.tva_par_taux],
            [(Decimal('10'), Decimal('1172.84'), Decimal('117.28'))])
        self.assertEqual(avoir.total_ttc, Decimal('1290.12'))

    def test_retour_palier_panneau_au_taux_de_sa_ligne(self):
        facture = self._facture_mixte(qte_panneau=8, arrondi_pas=100)
        self.assertEqual(facture.total_ttc, Decimal('24300.00'))
        avoir = self._retour_de(facture, self.panneau)
        self.assertLess(avoir.total_ttc, Decimal('1290.12'))  # palier au prorata
        self._assert_au_taux_de_la_ligne(avoir, '10', '1172.84')
        self.assertTrue(avoir.ventilation_tva)

    def test_retour_palier_onduleur_ht_sous_le_ht_net_de_la_ligne(self):
        facture = self._facture_mixte(qte_panneau=8, arrondi_pas=100)
        avoir = self._retour_de(facture, self.produit)
        self.assertLess(avoir.total_ttc, Decimal('14074.07'))
        self._assert_au_taux_de_la_ligne(avoir, '20', '11728.39')

    def test_dernier_retour_solde_au_centime_au_taux_de_la_ligne(self):
        from apps.ventes.models import Facture
        facture = self._facture_mixte(qte_panneau=2)
        self.assertEqual(facture.total_ttc, Decimal('16654.32'))
        self._retour_de(facture, self.produit)
        self._retour_de(facture, self.panneau)
        dernier = self._retour_de(facture, self.panneau)  # épuise la facture
        self.assertEqual(dernier.total_ttc, Decimal('1290.13'))
        self.assertEqual(dernier.total_ht, Decimal('1172.84'))
        self._assert_au_taux_de_la_ligne(dernier, '10', '1172.84')
        self.assertEqual(Facture.objects.get(pk=facture.pk).avoirs_total,
                         Decimal('16654.32'))


class RetoursConcurrentsTests(_Base, TransactionTestCase):
    def setUp(self):
        self._setup()

    def test_retours_concurrents_un_seul_passe(self):
        from apps.ventes.domain.facturation_ops import (
            AvoirRefuse, creer_avoir_facture,
        )
        from apps.ventes.models import Avoir, Facture
        facture = self._facture(pu='10000', qte=1)
        barriere = threading.Barrier(2)
        resultats = []

        def _retourner():
            try:
                barriere.wait(timeout=10)
                creer_avoir_facture(
                    facture=Facture.objects.get(pk=facture.pk),
                    user=self.admin, motif='t',
                    retour_lignes=[{'produit': self.produit.id,
                                    'quantite': 1}])
                resultats.append('ok')
            except AvoirRefuse:
                resultats.append('refus')
            finally:
                connection.close()

        fils = [threading.Thread(target=_retourner) for _ in range(2)]
        for f in fils:
            f.start()
        for f in fils:
            f.join(timeout=30)
        self.assertEqual(sorted(resultats), ['ok', 'refus'])
        self.assertEqual(Avoir.objects.filter(facture=facture).count(), 1)
