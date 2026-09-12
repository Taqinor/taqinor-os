"""Tests NTPAY2 — Interface comptable PARAMÉTRABLE (rubrique × analytique).

Couvre :
* RÉTRO-COMPATIBILITÉ STRICTE — sans aucune ligne de schéma, l'écriture de
  paie est identique à l'historique (mêmes comptes CGNC, au centime) ;
* le seed idempotent reproduit EXACTEMENT ces comptes ;
* un ``compte_debit`` custom sur une rubrique route sa part du brut vers ce
  compte, l'écriture restant équilibrée ;
* un compte absent du plan comptable est refusé avec un message qui le NOMME ;
* isolation société.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    ElementVariable,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
    SchemaComptablePaie,
)
from apps.paie.services import (
    ensure_defaults,
    ensure_schema_comptable_standard,
    generer_bulletin,
    journal_de_paie,
    livre_de_paie,
    reinitialiser_schema_comptable,
    resoudre_schema_comptable,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class SchemaComptableBase(TestCase):
    def _societe(self, slug):
        co = make_company(slug)
        ensure_defaults(co)
        return co

    def _periode(self, co, mois=6):
        return PeriodePaie.objects.create(company=co, annee=2026, mois=mois)

    def _bulletin(self, co, periode, matricule, salaire=Decimal('10000'),
                  prime=None):
        dossier = DossierEmploye.objects.create(
            company=co, matricule=matricule, nom='N' + matricule, prenom='P')
        profil = ProfilPaie.objects.create(
            company=co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        if prime is not None:
            rubrique, montant = prime
            ElementVariable.objects.create(
                company=co, periode=periode, profil=profil,
                type=ElementVariable.TYPE_PRIME, rubrique=rubrique,
                libelle=rubrique.libelle, montant=montant)
        bulletin = generer_bulletin(profil, periode)
        valider_bulletin(bulletin)
        return bulletin

    @staticmethod
    def _par_compte(ecriture):
        """``{numero: (debit, credit)}`` de l'écriture (débits/crédits sommés)."""
        resultat = {}
        for ligne in ecriture.lignes.all():
            debit, credit = resultat.get(
                ligne.compte.numero, (Decimal('0'), Decimal('0')))
            resultat[ligne.compte.numero] = (
                debit + ligne.debit, credit + ligne.credit)
        return resultat


class RetroCompatibiliteTests(SchemaComptableBase):
    """Sans schéma, RIEN ne bouge — et le schéma standard ne change rien non plus."""

    def test_sans_schema_les_comptes_restent_ceux_de_toujours(self):
        co = self._societe('ntpay2-sans')
        periode = self._periode(co)
        self._bulletin(co, periode, 'S1')
        self.assertFalse(resoudre_schema_comptable(co)['defini'])
        ecriture = journal_de_paie(periode)
        comptes = self._par_compte(ecriture)
        totaux = livre_de_paie(periode)['totaux']
        self.assertEqual(set(comptes), {'6171', '6174', '4441', '4452',
                                        '4432'})
        self.assertEqual(comptes['6171'][0], totaux['brut'])
        self.assertEqual(comptes['6174'][0], totaux['charges_patronales'])
        self.assertEqual(comptes['4452'][1], totaux['ir'])
        debits = sum(d for d, _ in comptes.values())
        credits = sum(c for _, c in comptes.values())
        self.assertEqual(debits, credits)

    def test_schema_standard_produit_la_meme_ecriture_au_centime(self):
        co_sans = self._societe('ntpay2-ref')
        periode_sans = self._periode(co_sans)
        self._bulletin(co_sans, periode_sans, 'R1')
        attendu = self._par_compte(journal_de_paie(periode_sans))

        co_avec = self._societe('ntpay2-std')
        ensure_schema_comptable_standard(co_avec)
        periode_avec = self._periode(co_avec)
        self._bulletin(co_avec, periode_avec, 'R1')
        obtenu = self._par_compte(journal_de_paie(periode_avec))

        self.assertEqual(obtenu, attendu)

    def test_seed_idempotent(self):
        co = self._societe('ntpay2-seed')
        self.assertEqual(ensure_schema_comptable_standard(co)['lignes'], 6)
        self.assertEqual(ensure_schema_comptable_standard(co)['lignes'], 0)
        self.assertEqual(
            SchemaComptablePaie.objects.filter(company=co).count(), 6)

    def test_seed_ne_touche_pas_une_ligne_editee(self):
        co = self._societe('ntpay2-edit')
        ensure_schema_comptable_standard(co)
        ligne = SchemaComptablePaie.objects.get(
            company=co, code_systeme=SchemaComptablePaie.CODE_BRUT)
        ligne.compte_debit = '6144'
        ligne.save(update_fields=['compte_debit'])
        ensure_schema_comptable_standard(co)
        ligne.refresh_from_db()
        self.assertEqual(ligne.compte_debit, '6144')

    def test_reinitialiser_rejoue_le_standard(self):
        co = self._societe('ntpay2-reset')
        ensure_schema_comptable_standard(co)
        SchemaComptablePaie.objects.filter(
            company=co, code_systeme=SchemaComptablePaie.CODE_BRUT
        ).update(compte_debit='6144')
        resultat = reinitialiser_schema_comptable(co)
        self.assertEqual(resultat['lignes'], 6)
        self.assertEqual(
            SchemaComptablePaie.objects.get(
                company=co,
                code_systeme=SchemaComptablePaie.CODE_BRUT).compte_debit,
            '6171')


class RoutageRubriqueTests(SchemaComptableBase):
    def setUp(self):
        self.co = self._societe('ntpay2-rubrique')
        ensure_schema_comptable_standard(self.co)
        self.periode = self._periode(self.co)
        self.rubrique = Rubrique.objects.create(
            company=self.co, code='PRIME_TRANSPORT',
            libelle='Prime de transport', type=Rubrique.TYPE_GAIN)

    def test_compte_custom_route_la_part_de_brut_de_la_rubrique(self):
        # « 6144 » n'a rien d'une prime de transport : c'est simplement un
        # compte RÉEL du plan CGNC semé, pour prouver le routage sans
        # inventer de numéro hors référentiel.
        SchemaComptablePaie.objects.create(
            company=self.co, rubrique=self.rubrique, compte_debit='6144',
            ordre=10)
        self._bulletin(self.co, self.periode, 'T1',
                       prime=(self.rubrique, Decimal('700')))
        ecriture = journal_de_paie(self.periode)
        comptes = self._par_compte(ecriture)
        totaux = livre_de_paie(self.periode)['totaux']

        self.assertIn('6144', comptes)
        self.assertEqual(comptes['6144'][0], Decimal('700.00'))
        # Le reliquat du brut reste sur le compte du poste « brut ».
        self.assertEqual(
            comptes['6171'][0], totaux['brut'] - Decimal('700.00'))
        # L'écriture reste équilibrée.
        self.assertEqual(
            sum(d for d, _ in comptes.values()),
            sum(c for _, c in comptes.values()))

    def test_rubrique_sans_element_ne_change_rien(self):
        SchemaComptablePaie.objects.create(
            company=self.co, rubrique=self.rubrique, compte_debit='6144',
            ordre=10)
        self._bulletin(self.co, self.periode, 'T2')
        comptes = self._par_compte(journal_de_paie(self.periode))
        self.assertNotIn('6144', comptes)
        self.assertEqual(
            comptes['6171'][0], livre_de_paie(self.periode)['totaux']['brut'])

    def test_compte_inconnu_nomme_le_compte_fautif(self):
        SchemaComptablePaie.objects.create(
            company=self.co, rubrique=self.rubrique,
            compte_debit='999999', ordre=10)
        self._bulletin(self.co, self.periode, 'T3',
                       prime=(self.rubrique, Decimal('500')))
        with self.assertRaises(DjangoValidationError) as ctx:
            journal_de_paie(self.periode)
        self.assertIn('999999', ' '.join(ctx.exception.messages))


class IsolationTests(SchemaComptableBase):
    def test_le_schema_d_une_societe_n_affecte_pas_l_autre(self):
        co_a = self._societe('ntpay2-iso-a')
        co_b = self._societe('ntpay2-iso-b')
        ensure_schema_comptable_standard(co_a)
        SchemaComptablePaie.objects.filter(
            company=co_a, code_systeme=SchemaComptablePaie.CODE_BRUT
        ).update(compte_debit='6144')

        self.assertFalse(resoudre_schema_comptable(co_b)['defini'])
        periode_b = self._periode(co_b)
        self._bulletin(co_b, periode_b, 'B1')
        comptes = self._par_compte(journal_de_paie(periode_b))
        self.assertIn('6171', comptes)
        self.assertNotIn('6144', comptes)
