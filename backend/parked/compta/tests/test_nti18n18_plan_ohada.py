"""NTI18N18 — plan comptable OHADA / SYSCOHADA révisé, table additive.

Ce que ces tests PROUVENT :

* la table est purement additive — une société sans compte OHADA se comporte
  comme avant (``plan_ohada_actif`` faux, plan CGNC intact) ;
* la GATE tient : ``actif=True`` est refusé tant que le pack pays de la
  société ne vaut pas ``SN_CI`` — et ``CompanyProfile.pack_pays`` n'existant
  pas encore (NTI18N16, GATED-founder), la lecture défensive rend `''` donc
  AUCUNE société ne passe la gate aujourd'hui ;
* l'erreur est portée par LE CHAMP fautif (``actif``/``classe``/``numero``),
  jamais un refus générique ;
* la correspondance CGNC ↔ OHADA reste VIDE par défaut (aucune équivalence
  supposée) ;
* les huit classes déclarées sont bien celles du SYSCOHADA révisé et
  DIFFÈRENT du CGNC sur les classes 3, 4 et 8.
"""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from ..models import (
    PACK_PAYS_OHADA,
    CompteComptable,
    PlanComptable,
    PlanComptableOHADA,
    pack_pays_societe,
    plan_ohada_actif,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


class ClassesSyscohadaTests(SimpleTestCase):
    """Le jeu de classes OHADA est distinct du jeu CGNC (pas de DB)."""

    def test_huit_classes_declarees(self):
        self.assertEqual(
            [int(v) for v in PlanComptableOHADA.Classe.values],
            [1, 2, 3, 4, 5, 6, 7, 8])

    def test_classes_3_4_8_divergent_du_cgnc(self):
        ohada = dict(PlanComptableOHADA.Classe.choices)
        cgnc = dict(CompteComptable.Classe.choices)
        for numero in (3, 4, 8):
            self.assertNotEqual(
                ohada[numero], cgnc[numero],
                f'La classe {numero} doit porter un libellé propre à chaque '
                'norme (une énumération partagée en afficherait un faux).')

    def test_classes_2_et_5_portent_le_meme_intitule(self):
        """Actif immobilisé et Trésorerie sont nommés pareil des deux côtés —
        ce qui NE vaut PAS correspondance de comptes (voir
        docs/ohada-mapping.md)."""
        ohada = dict(PlanComptableOHADA.Classe.choices)
        cgnc = dict(CompteComptable.Classe.choices)
        self.assertEqual(ohada[2], cgnc[2])
        self.assertEqual(ohada[5], cgnc[5])


class PlanOhadaGateTests(TestCase):
    def setUp(self):
        self.company = make_company('nti18n18-sn', 'NTI18N18 Sénégal')

    def test_pack_pays_absent_lu_defensivement(self):
        """``CompanyProfile.pack_pays`` n'existe pas encore (NTI18N16) : la
        lecture rend `''`, jamais une exception ni une valeur supposée."""
        self.assertEqual(pack_pays_societe(self.company), '')

    def test_pack_pays_societe_none(self):
        self.assertEqual(pack_pays_societe(None), '')

    def test_activation_refusee_hors_pack_sn_ci(self):
        compte = PlanComptableOHADA(
            company=self.company, numero='4111',
            intitule='Clients', classe=4, actif=True)
        with self.assertRaises(ValidationError) as ctx:
            compte.full_clean()
        self.assertIn('actif', ctx.exception.message_dict)
        self.assertIn(
            PACK_PAYS_OHADA, ' '.join(ctx.exception.message_dict['actif']))

    def test_compte_inactif_accepte(self):
        """Décrire un plan OHADA (pour le soumettre à validation) est permis ;
        l'ACTIVER ne l'est pas."""
        compte = PlanComptableOHADA(
            company=self.company, numero='4111',
            intitule='Clients', classe=4)
        compte.full_clean()
        compte.save()
        self.assertFalse(compte.actif)
        self.assertEqual(compte.compte_cgnc_equivalent, '')

    def test_plan_ohada_actif_faux_sans_pack_pays(self):
        PlanComptableOHADA.objects.create(
            company=self.company, numero='4111', intitule='Clients',
            classe=4, actif=True)
        self.assertFalse(plan_ohada_actif(self.company))

    def test_plan_ohada_actif_faux_sans_compte(self):
        self.assertFalse(plan_ohada_actif(self.company))


class PlanOhadaChampFautifTests(TestCase):
    def setUp(self):
        self.company = make_company('nti18n18-ci', "NTI18N18 Côte d'Ivoire")

    def test_numero_non_numerique_pointe_numero(self):
        compte = PlanComptableOHADA(
            company=self.company, numero='4111-A',
            intitule='Clients', classe=4)
        with self.assertRaises(ValidationError) as ctx:
            compte.full_clean()
        self.assertIn('numero', ctx.exception.message_dict)

    def test_classe_incoherente_pointe_classe(self):
        compte = PlanComptableOHADA(
            company=self.company, numero='4111',
            intitule='Clients', classe=6)
        with self.assertRaises(ValidationError) as ctx:
            compte.full_clean()
        self.assertIn('classe', ctx.exception.message_dict)

    def test_classe_deduite_du_premier_chiffre(self):
        compte = PlanComptableOHADA(
            company=self.company, numero='6011',
            intitule='Achats de marchandises', classe=0)
        compte.save()
        compte.refresh_from_db()
        self.assertEqual(compte.classe, 6)

    def test_numero_unique_par_societe(self):
        from django.db import IntegrityError, transaction

        PlanComptableOHADA.objects.create(
            company=self.company, numero='4111', intitule='Clients', classe=4)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlanComptableOHADA.objects.create(
                    company=self.company, numero='4111',
                    intitule='Clients (doublon)', classe=4)

    def test_meme_numero_autorise_sur_une_autre_societe(self):
        autre = make_company('nti18n18-autre', 'NTI18N18 Autre')
        PlanComptableOHADA.objects.create(
            company=self.company, numero='4111', intitule='Clients', classe=4)
        PlanComptableOHADA.objects.create(
            company=autre, numero='4111', intitule='Clients', classe=4)
        self.assertEqual(PlanComptableOHADA.objects.count(), 2)


class PlanCgncIntactTests(TestCase):
    """Le référentiel CGNC existant n'est pas touché par NTI18N18."""

    def setUp(self):
        self.company = make_company('nti18n18-ma', 'NTI18N18 Maroc')

    def test_plan_cgnc_et_comptes_inchanges(self):
        plan = PlanComptable.objects.create(company=self.company)
        compte = CompteComptable.objects.create(
            company=self.company, plan=plan, numero='3421',
            intitule='Clients', classe=3)
        self.assertEqual(plan.code, 'CGNC')
        self.assertEqual(compte.classe, 3)
        # Aucune ligne OHADA : la société reste en CGNC.
        self.assertFalse(
            PlanComptableOHADA.objects.filter(company=self.company).exists())
        self.assertFalse(plan_ohada_actif(self.company))
