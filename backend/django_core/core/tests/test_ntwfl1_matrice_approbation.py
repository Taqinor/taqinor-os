"""Tests NTWFL1 — matrice d'approbation d'entreprise unifiée.

Couvre :
- ``MatriceApprobation.couvre`` / ``largeur_intervalle`` (bornes, département).
- ``core.selectors.resoudre_matrice`` : la ligne la plus spécifique gagne
  (département+montant > département seul > montant seul > défaut société-large).
- Isolation tenant (une ligne d'une autre société n'est jamais renvoyée).
- ``parametres.ApprovalPolicy.requires_approval`` consulte la matrice EN
  PREMIER puis retombe sur la politique historique sans matrice correspondante.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from core.models import MatriceApprobation
from core.selectors import resoudre_matrice


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_matrice(company, type_objet='purchase_order', **kwargs):
    defaults = {
        'departement': '',
        'montant_min': None,
        'montant_max': None,
        'chaine_paliers': [
            {'palier': 1, 'nombre_approbateurs_requis': 1,
             'role_requis': 'responsable'},
        ],
        'actif': True,
    }
    defaults.update(kwargs)
    return MatriceApprobation.objects.create(
        company=company, type_objet=type_objet, **defaults)


class MatriceApprobationModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('taqinor-ntwfl1', 'Taqinor NTWFL1')

    def test_couvre_departement_vide_couvre_tous(self):
        m = make_matrice(self.company, departement='')
        self.assertTrue(m.couvre(1000, 'Achats'))
        self.assertTrue(m.couvre(1000, None))

    def test_couvre_departement_specifique_refuse_autre(self):
        m = make_matrice(self.company, departement='Achats')
        self.assertTrue(m.couvre(1000, 'Achats'))
        self.assertFalse(m.couvre(1000, 'RH'))
        self.assertFalse(m.couvre(1000, None))

    def test_couvre_bornes_montant(self):
        m = make_matrice(
            self.company, montant_min=Decimal('50000'), montant_max=None)
        self.assertFalse(m.couvre(Decimal('49999.99')))
        self.assertTrue(m.couvre(Decimal('50000')))
        self.assertTrue(m.couvre(Decimal('999999')))

    def test_largeur_intervalle_ouvert_vs_borne(self):
        ouvert = make_matrice(self.company, montant_min=None, montant_max=None)
        borne = make_matrice(
            self.company, montant_min=Decimal('0'), montant_max=Decimal('100'))
        self.assertIsNone(ouvert.largeur_intervalle())
        self.assertEqual(borne.largeur_intervalle(), Decimal('100'))


class ResoudreMatriceTests(TestCase):
    """Acceptance NTWFL1 : « Bon de commande × Achats × >50 000 MAD → 2
    paliers (Responsable puis Admin) » résout correctement, et la règle la
    plus spécifique prime sur une règle générique société-large."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('taqinor-ntwfl1b', 'Taqinor NTWFL1 B')
        cls.autre = make_company('taqinor-ntwfl1c', 'Taqinor NTWFL1 C')

    def test_specificite_departement_montant_prime_sur_defaut(self):
        # Règle générique société-large.
        make_matrice(
            self.company, type_objet='purchase_order', departement='',
            montant_min=None, montant_max=None,
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        # Règle spécifique Achats > 50 000 MAD, 2 paliers.
        specifique = make_matrice(
            self.company, type_objet='purchase_order', departement='Achats',
            montant_min=Decimal('50000'), montant_max=None,
            chaine_paliers=[
                {'palier': 1, 'nombre_approbateurs_requis': 1,
                 'role_requis': 'responsable'},
                {'palier': 2, 'nombre_approbateurs_requis': 1,
                 'role_requis': 'admin'},
            ])

        resolue = resoudre_matrice(
            self.company, 'purchase_order', montant=Decimal('75000'),
            departement='Achats')
        self.assertEqual(resolue.id, specifique.id)
        self.assertEqual(len(resolue.chaine_paliers), 2)

    def test_montant_hors_matrice_specifique_retombe_sur_generique(self):
        generique = make_matrice(
            self.company, type_objet='purchase_order', departement='',
            montant_min=None, montant_max=None)
        make_matrice(
            self.company, type_objet='purchase_order', departement='Achats',
            montant_min=Decimal('50000'), montant_max=None)

        resolue = resoudre_matrice(
            self.company, 'purchase_order', montant=Decimal('1000'),
            departement='Achats')
        self.assertEqual(resolue.id, generique.id)

    def test_aucune_ligne_ne_matche_renvoie_none(self):
        resolue = resoudre_matrice(
            self.company, 'contract', montant=Decimal('1'), departement=None)
        self.assertIsNone(resolue)

    def test_isolation_tenant(self):
        make_matrice(self.autre, type_objet='purchase_order', departement='')
        resolue = resoudre_matrice(
            self.company, 'purchase_order', montant=Decimal('10'))
        self.assertIsNone(resolue)

    def test_ligne_inactive_ignoree(self):
        make_matrice(
            self.company, type_objet='expense', departement='', actif=False)
        resolue = resoudre_matrice(self.company, 'expense', montant=10)
        self.assertIsNone(resolue)


class ApprovalPolicyMatriceCompatTests(TestCase):
    """FG25 devient une vue de compatibilité : matrice d'abord, repli inchangé."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('taqinor-ntwfl1d', 'Taqinor NTWFL1 D')

    def test_matrice_prime_sans_politique_configuree(self):
        from apps.parametres.models_approvals import ApprovalPolicy
        make_matrice(self.company, type_objet='discount', departement='')
        self.assertTrue(
            ApprovalPolicy.requires_approval(self.company, 'discount', 10))

    def test_sans_matrice_repli_sur_politique_historique_inchange(self):
        from apps.parametres.models_approvals import ApprovalPolicy
        # Aucune matrice, aucune politique -> False (comportement historique).
        self.assertFalse(
            ApprovalPolicy.requires_approval(self.company, 'discount', 10))
        ApprovalPolicy.objects.create(
            company=self.company, action_type='discount', seuil=Decimal('5'),
            approver_tier='admin', enabled=True)
        self.assertTrue(
            ApprovalPolicy.requires_approval(self.company, 'discount', 10))
        self.assertFalse(
            ApprovalPolicy.requires_approval(self.company, 'discount', 1))
