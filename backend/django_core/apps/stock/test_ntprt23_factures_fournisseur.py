"""NTPRT23 — « Mes factures & statut de paiement », portail FOURNISSEUR.

Ce que la tâche exige, et ce que ce module vérifie :

1. **CRITÈRE D'ACCEPTATION — le statut affiché matche EXACTEMENT l'interne.**
   `statut`/`statut_display`/`montant_ttc`/`solde_du` sont, ligne à ligne, ceux
   du module comptabilité interne (`FactureFournisseur`) ; seul
   `statut_reglement` est dérivé, et il l'est de ces mêmes valeurs.
2. **Lecture STRICTEMENT seule.** Aucun service d'écriture n'est exposé au
   fournisseur, et le PATCH/DELETE interne de la facture reste hors de sa
   portée : le portail ne fait que consulter.
3. **Isolation.** Un `fournisseur_id` d'une autre société, ou absent, renvoie
   une liste VIDE — jamais les factures de la société entière.
4. **Aucun prix d'achat catalogue ne sort.**

Les dates sont FIGÉES (`a_la_date=`) : « en retard » se joue sur une comparaison
de dates, et un test qui lit l'horloge serait faux un jour sur trente.

Run :
    python manage.py test apps.stock.test_ntprt23_factures_fournisseur -v2
"""
import datetime
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.achats.models import (
    FactureFournisseur, PaiementFournisseur,
)
from apps.stock.models import Fournisseur, Produit
from apps.stock.selectors import (
    REGLEMENT_A_PAYER, REGLEMENT_EN_RETARD, REGLEMENT_PAYEE,
    factures_portail_fournisseur,
)
from authentication.models import Company

#: Prix d'achat catalogue DISTINCTIF (5 chiffres) : un petit nombre se
#: retrouverait par hasard dans un id ou un montant et rendrait l'assertion
#: d'absence fausse.
PRIX_ACHAT_SECRET = '61843.00'

#: Date de référence FIGÉE pour tous les calculs de retard de ce module.
AUJOURDHUI = datetime.date(2026, 6, 15)

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_fournisseur(company, nom):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


def make_facture(company, fournisseur, *, montant_ttc, date_echeance,
                 statut=FactureFournisseur.Statut.A_PAYER):
    return FactureFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'FF-NTPRT23-{next(_seq)}',
        date_facture=datetime.date(2026, 5, 1),
        date_echeance=date_echeance,
        montant_ht=montant_ttc, montant_tva=0, montant_ttc=montant_ttc,
        statut=statut)


class StatutReglementTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt23-co', 'NTPRT23 Société')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')

    def _lignes(self):
        return factures_portail_fournisseur(
            self.company, self.fournisseur.id, a_la_date=AUJOURDHUI)

    def _ligne_de(self, facture):
        return next(ligne for ligne in self._lignes()
                    if ligne['id'] == facture.id)

    def test_echeance_future_est_a_payer(self):
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=datetime.date(2026, 7, 1))
        ligne = self._ligne_de(facture)

        self.assertEqual(ligne['statut_reglement'], REGLEMENT_A_PAYER)
        self.assertEqual(ligne['statut_reglement_display'], 'À payer')
        self.assertEqual(ligne['jours_de_retard'], 0)

    def test_echeance_depassee_est_en_retard_avec_le_nombre_de_jours(self):
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=datetime.date(2026, 6, 5))
        ligne = self._ligne_de(facture)

        self.assertEqual(ligne['statut_reglement'], REGLEMENT_EN_RETARD)
        self.assertEqual(ligne['statut_reglement_display'], 'En retard')
        self.assertEqual(ligne['jours_de_retard'], 10)

    def test_echeance_du_jour_n_est_pas_encore_en_retard(self):
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=AUJOURDHUI)
        self.assertEqual(
            self._ligne_de(facture)['statut_reglement'], REGLEMENT_A_PAYER)

    def test_sans_echeance_jamais_en_retard(self):
        """On ne déclare pas un retard sur une échéance jamais fixée."""
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=None)
        ligne = self._ligne_de(facture)

        self.assertEqual(ligne['statut_reglement'], REGLEMENT_A_PAYER)
        self.assertEqual(ligne['jours_de_retard'], 0)

    def test_facture_payee_est_payee_meme_echue(self):
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=datetime.date(2026, 5, 10),
            statut=FactureFournisseur.Statut.PAYEE)
        ligne = self._ligne_de(facture)

        self.assertEqual(ligne['statut_reglement'], REGLEMENT_PAYEE)
        self.assertEqual(ligne['statut_reglement_display'], 'Payée')
        self.assertEqual(ligne['jours_de_retard'], 0)

    def test_facture_soldee_par_ses_paiements_est_payee(self):
        """Le solde prime : une facture intégralement réglée n'affiche jamais
        « à payer » au fournisseur, même si son statut n'a pas encore été
        recalculé."""
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=datetime.date(2026, 5, 10))
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('12000'),
            date_paiement=datetime.date(2026, 5, 9))

        ligne = self._ligne_de(facture)
        self.assertEqual(ligne['statut_reglement'], REGLEMENT_PAYEE)
        self.assertEqual(ligne['solde_du'], Decimal('0'))

    def test_facture_partiellement_payee_et_echue_reste_en_retard(self):
        facture = make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('12000'),
            date_echeance=datetime.date(2026, 6, 1),
            statut=FactureFournisseur.Statut.PARTIELLEMENT_PAYEE)
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture, montant=Decimal('5000'),
            date_paiement=datetime.date(2026, 5, 30))

        ligne = self._ligne_de(facture)
        self.assertEqual(ligne['statut_reglement'], REGLEMENT_EN_RETARD)
        self.assertEqual(ligne['jours_de_retard'], 14)
        self.assertEqual(ligne['solde_du'], Decimal('7000'))


class ConcordanceAvecLInterneTests(TestCase):
    """Le critère d'acceptation : « le statut matche exactement l'interne »."""

    def setUp(self):
        self.company = make_company('ntprt23-int-co', 'NTPRT23 Interne')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.factures = [
            make_facture(
                self.company, self.fournisseur, montant_ttc=Decimal('8000'),
                date_echeance=datetime.date(2026, 7, 1)),
            make_facture(
                self.company, self.fournisseur, montant_ttc=Decimal('4500'),
                date_echeance=datetime.date(2026, 6, 1)),
            make_facture(
                self.company, self.fournisseur, montant_ttc=Decimal('3000'),
                date_echeance=datetime.date(2026, 5, 2),
                statut=FactureFournisseur.Statut.PAYEE),
        ]

    def test_chaque_ligne_reprend_les_valeurs_de_la_base(self):
        lignes = {
            ligne['id']: ligne for ligne in factures_portail_fournisseur(
                self.company, self.fournisseur.id, a_la_date=AUJOURDHUI)}

        self.assertEqual(len(lignes), len(self.factures))
        for facture in self.factures:
            interne = FactureFournisseur.objects.get(pk=facture.pk)
            ligne = lignes[facture.pk]
            self.assertEqual(ligne['reference'], interne.reference)
            self.assertEqual(ligne['statut'], interne.statut)
            self.assertEqual(
                ligne['statut_display'], interne.get_statut_display())
            self.assertEqual(ligne['montant_ttc'], interne.montant_ttc)
            self.assertEqual(ligne['solde_du'], interne.solde_du)
            self.assertEqual(ligne['date_echeance'], interne.date_echeance)

    def test_le_statut_derive_suit_le_statut_interne_quand_il_change(self):
        facture = self.factures[1]
        avant = next(
            ligne for ligne in factures_portail_fournisseur(
                self.company, self.fournisseur.id, a_la_date=AUJOURDHUI)
            if ligne['id'] == facture.pk)
        self.assertEqual(avant['statut_reglement'], REGLEMENT_EN_RETARD)

        # L'interne solde la facture : le portail suit, sans action côté portail.
        facture.statut = FactureFournisseur.Statut.PAYEE
        facture.save(update_fields=['statut'])

        apres = next(
            ligne for ligne in factures_portail_fournisseur(
                self.company, self.fournisseur.id, a_la_date=AUJOURDHUI)
            if ligne['id'] == facture.pk)
        self.assertEqual(apres['statut_reglement'], REGLEMENT_PAYEE)
        self.assertEqual(apres['statut'], FactureFournisseur.Statut.PAYEE)


class IsolationFacturesFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt23-iso-co', 'NTPRT23 Isolation')
        self.autre_company = make_company('ntprt23-iso-co2', 'NTPRT23 Iso 2')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.f_etranger = make_fournisseur(self.autre_company, 'Gamma')

        self.facture_a = make_facture(
            self.company, self.f_a, montant_ttc=Decimal('8000'),
            date_echeance=datetime.date(2026, 7, 1))
        self.facture_b = make_facture(
            self.company, self.f_b, montant_ttc=Decimal('9000'),
            date_echeance=datetime.date(2026, 7, 1))
        self.facture_etrangere = make_facture(
            self.autre_company, self.f_etranger, montant_ttc=Decimal('1000'),
            date_echeance=datetime.date(2026, 7, 1))

    def test_chaque_fournisseur_ne_voit_que_ses_factures(self):
        ids_a = [ligne['id'] for ligne in factures_portail_fournisseur(
            self.company, self.f_a.id, a_la_date=AUJOURDHUI)]
        self.assertEqual(ids_a, [self.facture_a.id])
        self.assertNotIn(self.facture_b.id, ids_a)
        self.assertNotIn(self.facture_etrangere.id, ids_a)

    def test_un_fournisseur_d_une_autre_societe_rend_une_liste_vide(self):
        self.assertEqual(
            factures_portail_fournisseur(
                self.company, self.f_etranger.id, a_la_date=AUJOURDHUI),
            [])

    def test_sans_rattachement_la_liste_est_vide_jamais_toute_la_societe(self):
        self.assertEqual(
            factures_portail_fournisseur(self.company, None), [])
        self.assertEqual(
            factures_portail_fournisseur(None, self.f_a.id), [])


class AucuneFuiteDePrixDAchatTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt23-fuite-co', 'NTPRT23 Fuite')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        Produit.objects.create(
            company=self.company, nom='Onduleur NTPRT23', sku='OND-NTPRT23',
            prix_vente='9900.00', prix_achat=PRIX_ACHAT_SECRET)
        make_facture(
            self.company, self.fournisseur, montant_ttc=Decimal('8000'),
            date_echeance=datetime.date(2026, 7, 1))

    def test_le_prix_d_achat_catalogue_n_apparait_pas(self):
        charge = str(factures_portail_fournisseur(
            self.company, self.fournisseur.id, a_la_date=AUJOURDHUI))
        self.assertNotIn(PRIX_ACHAT_SECRET, charge)
        self.assertNotIn(PRIX_ACHAT_SECRET.split('.')[0], charge)
        for interdit in ('prix_achat', 'prix_achat_unitaire', 'marge'):
            self.assertNotIn(interdit, charge)


class LectureSeuleStricteTests(TestCase):
    """« Aucune modification possible côté fournisseur » — la liste est servie
    par un SÉLECTEUR, et consulter ne change rien."""

    def test_le_selecteur_ne_modifie_rien(self):
        company = make_company('ntprt23-ro-co', 'NTPRT23 Lecture seule')
        fournisseur = make_fournisseur(company, 'Alpha')
        facture = make_facture(
            company, fournisseur, montant_ttc=Decimal('8000'),
            date_echeance=datetime.date(2026, 5, 1))
        avant = (facture.statut, facture.montant_ttc, facture.date_echeance)

        factures_portail_fournisseur(
            company, fournisseur.id, a_la_date=AUJOURDHUI)

        facture.refresh_from_db()
        self.assertEqual(
            (facture.statut, facture.montant_ttc, facture.date_echeance),
            avant)
        self.assertEqual(
            PaiementFournisseur.objects.filter(facture=facture).count(), 0)
