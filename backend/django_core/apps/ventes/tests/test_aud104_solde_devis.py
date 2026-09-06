"""AUD104 (FICHE-SOLDE) — ``solde_devis`` lit ``Facture.montant_paye``.

``utils/echeancier.solde_devis`` re-sommait ``p.montant`` sur
``f.paiements.all()`` avec sa PROPRE formule, et divergeait de la référence
canonique ``Facture.montant_paye`` sur TROIS termes : elle EXCLUT les paiements
rejetés (YLEDG5), AJOUTE les escomptes (XFAC12) et AJOUTE les avances
ventilées (XFAC1). Les avoirs, eux, étaient déjà traités — ce n'était pas un
oubli global mais une ré-implémentation partielle, d'autant plus trompeuse
qu'elle est servie sur l'écran devis.

S'y ajoute le résidu PAY-2 : ``montant_paye`` ne filtrait pas le statut du
paiement SOURCE d'une affectation, et ``rejeter_paiement`` ne faisait RIEN
quand le paiement rejeté était une AVANCE (``facture`` vide) — les factures
qu'elle avait soldées restaient payées avec l'argent d'un chèque impayé.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis, Paiement
from apps.ventes.utils.echeancier import solde_devis
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class _BaseSolde(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aud104-co', defaults={'nom': 'AUD104 Co'})
        self.user = User.objects.create_user(
            username=f'aud104_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD104', prenom='Client',
            email='aud104@example.com', telephone='+212600000105')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD104-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=20)

    def _devis_avec_facture(self, ttc=Decimal('12000')):
        """Devis accepté + UNE facture de tranche couvrant tout son TTC."""
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD104-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD104-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc)
        return devis, facture


class TestTroisDivergencesFermees(_BaseSolde):
    """(a) chèque rejeté, (b) escompte, (c) avance ventilée."""

    def test_a_cheque_rejete_ne_compte_plus_dans_le_solde_devis(self):
        from apps.ventes.domain.recouvrement import rejeter_paiement

        devis, facture = self._devis_avec_facture(Decimal('12000'))
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('12000'),
            date_paiement=date(2026, 3, 1), mode='cheque')
        rejeter_paiement(paiement=paiement, motif='Chèque sans provision',
                         user=self.user)
        facture.refresh_from_db()
        solde = solde_devis(devis)
        self.assertEqual(solde['paye'], Decimal('0.00'))
        self.assertEqual(solde['restant'], facture.montant_du)

    def test_b_devis_solde_par_escompte_affiche_restant_zero(self):
        devis, facture = self._devis_avec_facture(Decimal('12000'))
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('11800'),
            escompte_montant=Decimal('200'),
            date_paiement=date(2026, 3, 1), mode='virement')
        solde = solde_devis(devis)
        self.assertEqual(solde['paye'], Decimal('12000.00'))
        self.assertEqual(solde['restant'], Decimal('0.00'))

    def test_c_devis_solde_par_avance_ventilee_affiche_restant_zero(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )

        devis, facture = self._devis_avec_facture(Decimal('12000'))
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('12000'), date_paiement=timezone.localdate(),
            mode='virement', created_by=self.user)
        ventiler_avance(paiement=avance, facture=facture,
                        montant=Decimal('12000'), user=self.user)
        solde = solde_devis(devis)
        self.assertEqual(solde['paye'], Decimal('12000.00'))
        self.assertEqual(solde['restant'], Decimal('0.00'))


class TestRejetDuneAvanceDejaVentilee(_BaseSolde):
    """(d) — le résidu PAY-2, rouge avant AUD104."""

    def test_rejet_dune_avance_rouvre_les_factures_ventilees(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )
        from apps.ventes.domain.recouvrement import rejeter_paiement

        _devis, facture = self._devis_avec_facture(Decimal('12000'))
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('12000'), date_paiement=timezone.localdate(),
            mode='cheque', created_by=self.user)
        ventiler_avance(paiement=avance, facture=facture,
                        montant=Decimal('12000'), user=self.user)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_paye, Decimal('12000.00'))

        rejeter_paiement(paiement=avance, motif='Chèque impayé',
                         user=self.user)

        facture.refresh_from_db()
        self.assertEqual(facture.montant_paye, Decimal('0.00'))
        self.assertEqual(facture.montant_du, Decimal('12000.00'))
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_rejet_dune_avance_repasse_en_retard_si_echeance_depassee(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )
        from apps.ventes.domain.recouvrement import rejeter_paiement

        _devis, facture = self._devis_avec_facture(Decimal('12000'))
        facture.date_echeance = timezone.localdate() - timedelta(days=10)
        facture.save(update_fields=['date_echeance'])
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('12000'), date_paiement=timezone.localdate(),
            mode='cheque', created_by=self.user)
        ventiler_avance(paiement=avance, facture=facture,
                        montant=Decimal('12000'), user=self.user)
        rejeter_paiement(paiement=avance, motif='Chèque impayé',
                         user=self.user)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EN_RETARD)


class TestMontantPayeFiltreLesAffectationsRejetees(_BaseSolde):
    """PAY-2 — le terme ``via_affectation`` filtre le statut de la source."""

    def test_affectation_dun_paiement_rejete_sort_de_montant_paye(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )

        _devis, facture = self._devis_avec_facture(Decimal('12000'))
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('12000'), date_paiement=timezone.localdate(),
            mode='cheque', created_by=self.user)
        ventiler_avance(paiement=avance, facture=facture,
                        montant=Decimal('12000'), user=self.user)
        # Rejet POSÉ DIRECTEMENT sur le modèle (sans passer par le service) :
        # la propriété doit déjà, à elle seule, exclure cette affectation.
        Paiement.objects.filter(pk=avance.pk).update(
            statut=Paiement.Statut.REJETE)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_paye, Decimal('0.00'))
