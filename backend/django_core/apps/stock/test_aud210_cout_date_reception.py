"""AUD210 — le coût du stock est daté sur la RÉCEPTION réelle, pas sur la
création du bon de commande.

Défaut d'origine : `average_cost_with_source` (borne de revalorisation),
`fifo_cost_with_source` (ordre des couches) et `_cout_moyen_produit_a_date`
(valorisation CGNC à date) filtraient/ordonnaient tous les trois sur
``bon_commande__date_creation``. Un BCF saisi en janvier et réceptionné en mars
pesait donc dans le coût moyen daté du 1er février, alors que la marchandise
n'était pas encore en stock — le critère temporel du COÛT divergeait de celui,
correct, de la QUANTITÉ (reconstruite depuis les `MouvementStock`).

INTERNE — les coûts d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_aud210_cout_date_reception -v 2
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    _cout_moyen_produit_a_date, average_cost_with_source,
    fifo_cost_with_source,
)


def make_company(slug='aud210-co', nom='AUD210 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud210Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Importateur AUD210')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD210', sku='AUD210-1',
            prix_achat=Decimal('900'), prix_vente=Decimal('1500'),
            quantite_stock=0)

    def _bcf(self, *, ref, cree_le, quantite, prix, recu_le=None):
        """BCF daté `cree_le`, reçu `quantite` — avec un document de réception
        confirmé daté `recu_le` quand il est fourni."""
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref, fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=datetime.datetime.combine(
                cree_le, datetime.time(12, 0)))
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(str(prix)), quantite_recue=quantite)
        if recu_le is not None:
            reception = ReceptionFournisseur.objects.create(
                company=self.company, reference=f'REC-{ref}', bon_commande=bc,
                statut=ReceptionFournisseur.Statut.CONFIRME,
                date_reception=recu_le)
            LigneReceptionFournisseur.objects.create(
                reception=reception, ligne_commande=ligne,
                produit=self.produit, quantite=quantite)
        self.produit.quantite_stock += quantite
        self.produit.save(update_fields=['quantite_stock'])
        return bc


class TestCoutMoyenADate(Aud210Base):
    """XSTK13 — valorisation CGNC à date."""

    def test_bcf_janvier_receptionne_en_mars_exclu_au_1er_fevrier(self):
        self._bcf(ref='BCF-JAN', cree_le=datetime.date(2026, 1, 5),
                  quantite=10, prix='1000',
                  recu_le=datetime.date(2026, 3, 10))

        cout, source = _cout_moyen_produit_a_date(
            self.produit, datetime.date(2026, 2, 1))

        # Aucune entrée en stock au 1er février : repli catalogue.
        # Avant AUD210 : 1000,00 / 'achats'.
        self.assertEqual(source, 'catalogue')
        self.assertEqual(cout, Decimal('900'))

    def test_meme_bcf_compte_apres_sa_reception(self):
        self._bcf(ref='BCF-JAN', cree_le=datetime.date(2026, 1, 5),
                  quantite=10, prix='1000',
                  recu_le=datetime.date(2026, 3, 10))

        cout, source = _cout_moyen_produit_a_date(
            self.produit, datetime.date(2026, 3, 31))

        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1000.00'))

    def test_le_jour_meme_de_la_reception_compte(self):
        self._bcf(ref='BCF-JAN', cree_le=datetime.date(2026, 1, 5),
                  quantite=10, prix='1000',
                  recu_le=datetime.date(2026, 3, 10))

        cout, _ = _cout_moyen_produit_a_date(
            self.produit, datetime.date(2026, 3, 10))
        self.assertEqual(cout, Decimal('1000.00'))

    def test_sans_document_de_reception_repli_sur_la_date_du_bcf(self):
        """Comportement historique préservé : un BCF reçu par l'action
        `recevoir` (sans ReceptionFournisseur) reste daté sur sa création."""
        self._bcf(ref='BCF-DIRECT', cree_le=datetime.date(2026, 1, 5),
                  quantite=10, prix='1000')

        cout, source = _cout_moyen_produit_a_date(
            self.produit, datetime.date(2026, 2, 1))

        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1000.00'))

    def test_reception_non_confirmee_ne_date_pas_l_entree(self):
        """Une réception encore en brouillon n'est pas une entrée en stock :
        on retombe sur la date du BCF."""
        bc = self._bcf(ref='BCF-BROUILLON', cree_le=datetime.date(2026, 1, 5),
                       quantite=10, prix='1000')
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-BROUILLON', bon_commande=bc,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            date_reception=datetime.date(2026, 3, 10))
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=bc.lignes.first(),
            produit=self.produit, quantite=10)

        cout, source = _cout_moyen_produit_a_date(
            self.produit, datetime.date(2026, 2, 1))
        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1000.00'))


class TestFifoOrdonneParReception(Aud210Base):
    """FG67 — les couches FIFO restantes sont les dernières ENTRÉES."""

    def test_couches_ordonnees_par_date_de_reception(self):
        # Commandé en premier (janvier) mais reçu en dernier (mars).
        self._bcf(ref='BCF-A', cree_le=datetime.date(2026, 1, 5),
                  quantite=6, prix='1100',
                  recu_le=datetime.date(2026, 3, 10))
        # Commandé après (février) mais reçu avant (février).
        self._bcf(ref='BCF-B', cree_le=datetime.date(2026, 2, 1),
                  quantite=4, prix='900',
                  recu_le=datetime.date(2026, 2, 2))
        # Il ne reste que 6 unités : les 6 dernières ENTRÉES sont celles de
        # mars (à 1100). Avant AUD210, l'ordre par date de BCF donnait les
        # 4 unités de février à 900 + 2 de janvier à 1100.
        self.produit.quantite_stock = 6
        self.produit.save(update_fields=['quantite_stock'])

        cout, source = fifo_cost_with_source(self.produit)

        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1100.00'))


class TestRevalorisationBorneeParReception(Aud210Base):
    """XSTK14 — la couche de départ ne doit supplanter que les entrées
    ANTÉRIEURES à la validation."""

    def _revalo_validee(self, nouveau_cout, quantite_snapshot, valide_le):
        from apps.stock.models import RevalorisationStock
        ancien = Decimal('1000')
        nouveau = Decimal(nouveau_cout)
        revalo = RevalorisationStock.objects.create(
            company=self.company, produit=self.produit,
            ancien_cout=ancien, nouveau_cout=nouveau,
            quantite_snapshot=quantite_snapshot,
            delta_valeur=(nouveau - ancien) * quantite_snapshot,
            motif='Baisse marché',
            statut=RevalorisationStock.Statut.VALIDEE)
        RevalorisationStock.objects.filter(pk=revalo.pk).update(
            date_validation=valide_le)
        revalo.refresh_from_db()
        return revalo

    def test_bcf_ancien_receptionne_apres_la_revalo_est_compte(self):
        from django.utils import timezone
        # BCF de janvier, réceptionné en mars.
        self._bcf(ref='BCF-JAN', cree_le=datetime.date(2026, 1, 5),
                  quantite=10, prix='1400',
                  recu_le=datetime.date(2026, 3, 10))
        # Revalorisation validée le 1er février : 10 unités à 1200.
        self._revalo_validee(
            '1200', 10,
            timezone.make_aware(datetime.datetime(2026, 2, 1, 9, 0)))

        cout, source = average_cost_with_source(self.produit)

        # La marchandise est entrée APRÈS la revalorisation : elle se moyenne
        # avec la couche de départ — (10*1200 + 10*1400)/20 = 1300.
        # Avant AUD210, datée sur le BCF de janvier, elle était supplantée et
        # le coût restait 1200.
        self.assertEqual(source, 'revalorisation')
        self.assertEqual(cout, Decimal('1300.00'))
