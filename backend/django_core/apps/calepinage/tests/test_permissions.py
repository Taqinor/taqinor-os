"""CAL6 — les deux codes de permission du module Calepinage.

Ce qui est prouvé ici :

* ``calepinage_voir`` / ``calepinage_gerer`` sont au CATALOGUE
  (``roles.ALL_PERMISSIONS``) — sans quoi aucun rôle fin, Directeur compris,
  ne les porterait et le module répondrait 403 à tout le monde (classe de bug
  WIR169) ;
* ils sont rattachés au module ``calepinage`` dans ``PERMISSION_MODULE``, donc
  l'éditeur de rôles les masque proprement quand le module est éteint ;
* ils ne sont PAS élevés : le module n'expose ni prix d'achat ni marge, donc
  il n'a besoin d'aucun code du palier sensible, et aucune permission élevée
  existante n'est touchée ;
* leur palier est EXACTEMENT celui de ``ventes`` : partout où un rôle porte
  ``ventes_voir`` il porte ``calepinage_voir``, partout où il porte
  ``ventes_creer`` il porte ``calepinage_gerer`` ;
* un porteur du code répond vrai à ``has_erp_permission``, un non-porteur
  répond faux (c'est ce que le socle ``ScopedPermission`` traduit en 403 dès
  que les viewsets existent) ;
* AUCUN littéral de permission ne vit hors de ``apps/calepinage/permissions.py``
  (source unique, patron ``apps/ao/permissions.py``).

Run :
    python manage.py test apps.calepinage.tests.test_permissions -v2
"""
import pathlib

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.calepinage.permissions import CAL_GERER, CAL_VOIR, CODES
from apps.roles.models import (
    ADMIN_VENTES_PERMISSIONS,
    ALL_PERMISSIONS,
    COMMERCIAL_PERMISSIONS,
    COMMERCIAL_RESP_PERMISSIONS,
    ELEVATED_PERMISSIONS,
    PERMISSION_MODULE,
    RESPONSABLE_PERMISSIONS,
    Role,
    UTILISATEUR_PERMISSIONS,
    VIEWER_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

#: Les listes de rôles où ``ventes_voir`` donne le droit de LIRE.
LISTES_LECTURE = (
    ('RESPONSABLE', RESPONSABLE_PERMISSIONS),
    ('UTILISATEUR', UTILISATEUR_PERMISSIONS),
    ('COMMERCIAL_RESP', COMMERCIAL_RESP_PERMISSIONS),
    ('COMMERCIAL', COMMERCIAL_PERMISSIONS),
    ('VIEWER', VIEWER_PERMISSIONS),
    ('ADMIN_VENTES', ADMIN_VENTES_PERMISSIONS),
)


class CatalogueTest(SimpleTestCase):
    """Les codes existent, sont uniques et sont correctement rattachés."""

    def test_codes_au_catalogue(self):
        for code in CODES:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_source_unique(self):
        self.assertEqual(CODES, ('calepinage_voir', 'calepinage_gerer'))
        self.assertEqual(CAL_VOIR, 'calepinage_voir')
        self.assertEqual(CAL_GERER, 'calepinage_gerer')

    def test_pas_de_doublon_au_catalogue(self):
        for code in CODES:
            self.assertEqual(ALL_PERMISSIONS.count(code), 1, code)

    def test_rattaches_au_module_calepinage(self):
        for code in CODES:
            self.assertEqual(PERMISSION_MODULE.get(code), 'calepinage', code)

    def test_aucun_code_eleve(self):
        """Le module n'expose ni prix d'achat ni marge : rien d'élevé."""
        for code in CODES:
            self.assertNotIn(code, ELEVATED_PERMISSIONS, code)


class PalierVentesTest(SimpleTestCase):
    """Le palier est EXACTEMENT celui de ``ventes`` — ni plus, ni moins."""

    def test_lecture_suit_ventes_voir(self):
        for nom, liste in LISTES_LECTURE:
            if 'ventes_voir' in liste:
                self.assertIn(CAL_VOIR, liste, nom)

    def test_ecriture_suit_ventes_creer(self):
        for nom, liste in LISTES_LECTURE:
            if 'ventes_creer' in liste:
                self.assertIn(CAL_GERER, liste, nom)

    def test_pas_d_ecriture_sans_ventes_creer(self):
        """Un rôle en lecture seule sur les devis ne gère pas un calepinage."""
        for nom, liste in LISTES_LECTURE:
            if 'ventes_creer' not in liste:
                self.assertNotIn(CAL_GERER, liste, nom)

    def test_viewer_et_utilisateur_en_lecture_seule(self):
        for liste in (VIEWER_PERMISSIONS, UTILISATEUR_PERMISSIONS):
            self.assertIn(CAL_VOIR, liste)
            self.assertNotIn(CAL_GERER, liste)


class LitteralUniqueTest(SimpleTestCase):
    """Aucun littéral de permission hors de ``permissions.py`` (patron AO)."""

    def test_aucun_litteral_ailleurs(self):
        coupables = []
        for fichier in RACINE_APP.rglob('*.py'):
            if fichier.name == 'permissions.py':
                continue
            if fichier.parent.name == 'tests':
                continue
            texte = fichier.read_text(encoding='utf-8')
            for code in CODES:
                if f"'{code}'" in texte or f'"{code}"' in texte:
                    coupables.append(f'{fichier.name}: {code}')
        self.assertEqual(
            coupables, [],
            "Littéral de permission hors de apps/calepinage/permissions.py "
            f"(source unique) : {coupables}. Importer CAL_VOIR/CAL_GERER.")


class PorteurDuCodeTest(TestCase):
    """Le socle de permissions répond vrai/faux selon le rôle porté."""

    def setUp(self):
        self.company = Company.objects.create(nom='Calepinage Co',
                                              slug='calepinage-co')

    def _utilisateur(self, identifiant, permissions):
        role = Role.objects.create(company=self.company, nom=identifiant,
                                   permissions=list(permissions))
        return User.objects.create_user(
            username=identifiant, password='x',
            company=self.company, role=role)

    def test_porteur_lecture(self):
        lecteur = self._utilisateur('cal_lecteur', [CAL_VOIR])
        self.assertTrue(lecteur.has_erp_permission(CAL_VOIR))
        self.assertFalse(lecteur.has_erp_permission(CAL_GERER))

    def test_porteur_ecriture(self):
        gestionnaire = self._utilisateur('cal_gestion', [CAL_VOIR, CAL_GERER])
        self.assertTrue(gestionnaire.has_erp_permission(CAL_VOIR))
        self.assertTrue(gestionnaire.has_erp_permission(CAL_GERER))

    def test_sans_le_code_rien(self):
        """Ni lecture ni écriture pour un rôle qui ne porte aucun code."""
        etranger = self._utilisateur('cal_etranger', ['crm_voir'])
        self.assertFalse(etranger.has_erp_permission(CAL_VOIR))
        self.assertFalse(etranger.has_erp_permission(CAL_GERER))
