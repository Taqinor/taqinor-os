"""CAL9 — « une seule variante retenue », deux verrous et un garde de surface.

Ce qui est prouvé ici :

* la BASE refuse une deuxième variante retenue sur le même calepinage
  (``IntegrityError``) ;
* le champ ``retenue`` n'est écrivable QUE depuis le service de variantes :
  une écriture directe est refusée en français, en NOMMANT le champ ;
* deux calepinages différents ont chacun leur variante retenue — la
  contrainte est par calepinage, pas par société ;
* le garde est par THREAD : ouvrir la bascule dans un fil n'ouvre pas la
  porte dans un autre ;
* GARDE DE SURFACE — aucun autre fichier du module n'écrit ``retenue`` : si
  une lane ajoute une écriture directe ailleurs (vue, sérialiseur, autre
  service), ce test rougit.

Run :
    python manage.py test apps.calepinage.tests.test_variantes -v2
"""
import ast
import pathlib
import threading

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import (
    bascule_autorisee,
    bascule_en_cours,
)
from apps.crm.models import Client
from authentication.models import Company

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

#: Les appels de queryset qui LISENT : un ``retenue=`` posé là est un critère
#: de recherche, jamais une écriture. Tout AUTRE appel portant ``retenue=`` en
#: mot-clé (``create``, ``update``, ``update_or_create``…) écrit le champ.
LECTURES_QUERYSET = frozenset({
    'filter', 'exclude', 'get', 'count', 'exists', 'annotate', 'aggregate',
    'values', 'values_list', 'order_by', 'distinct', 'first', 'last',
})

#: Les seuls fichiers autorisés à écrire ``retenue`` : le chemin d'écriture
#: unique, et la déclaration du champ dans le modèle.
FICHIERS_AUTORISES = {'services/variantes.py', 'models.py'}


def _ecritures_retenue(source):
    """Les lignes qui ÉCRIVENT ``retenue``, lues en AST — jamais en regex.

    Une expression régulière sur « retenue suivi de = » ne distingue pas une
    ÉCRITURE d'une LECTURE : elle rougissait sur ``.filter(retenue=True)``
    (un critère de recherche) et sur la variable locale homonyme
    ``retenue = next(...)`` (qui ne touche aucun champ), tout en ratant une
    écriture répartie sur deux lignes. L'AST tranche exactement :

    * affectation d'ATTRIBUT (``variante.retenue = True``) — une écriture ;
    * mot-clé ``retenue=`` d'un appel qui n'est PAS une lecture de queryset
      (``create``, ``update``, ``update_or_create``…) — une écriture, même
      écrite sur plusieurs lignes ;
    * tout le reste (filtres, variables locales homonymes) — pas une écriture.
    """
    lignes = set()
    for noeud in ast.walk(ast.parse(source)):
        cibles = ()
        if isinstance(noeud, ast.Assign):
            cibles = noeud.targets
        elif isinstance(noeud, (ast.AnnAssign, ast.AugAssign)):
            cibles = (noeud.target,)
        for cible in cibles:
            if isinstance(cible, ast.Attribute) and cible.attr == 'retenue':
                lignes.add(cible.lineno)
        if isinstance(noeud, ast.Call):
            appele = (noeud.func.attr
                      if isinstance(noeud.func, ast.Attribute) else '')
            if appele in LECTURES_QUERYSET:
                continue
            for mot in noeud.keywords:
                if mot.arg == 'retenue':
                    lignes.add(mot.value.lineno)
    return sorted(lignes)


class BaseVariantes(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Variantes Co',
                                              slug='variantes-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.pivot = Calepinage.objects.create(company=self.company,
                                               client=self.client_a)

    def _variante(self, nom, retenue=False):
        if retenue:
            with bascule_autorisee():
                return CalepinageVariante.objects.create(
                    company=self.company, calepinage=self.pivot,
                    nom=nom, retenue=True)
        return CalepinageVariante.objects.create(
            company=self.company, calepinage=self.pivot, nom=nom)


class ContrainteBaseTest(BaseVariantes):
    def test_deuxieme_retenue_leve_integrity_error(self):
        self._variante('A', retenue=True)
        with bascule_autorisee():
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    CalepinageVariante.objects.create(
                        company=self.company, calepinage=self.pivot,
                        nom='B', retenue=True)

    def test_un_calepinage_par_retenue(self):
        """La contrainte est PAR CALEPINAGE, pas par société."""
        autre = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        self._variante('A', retenue=True)
        with bascule_autorisee():
            CalepinageVariante.objects.create(company=self.company,
                                              calepinage=autre,
                                              nom='A bis', retenue=True)
        self.assertEqual(
            CalepinageVariante.objects.filter(retenue=True).count(), 2)

    def test_plusieurs_non_retenues(self):
        self._variante('A')
        self._variante('B')
        self._variante('C')
        self.assertEqual(self.pivot.variantes.filter(retenue=True).count(), 0)


class CheminEcritureUniqueTest(BaseVariantes):
    def test_ecriture_directe_refusee_en_nommant_le_champ(self):
        with self.assertRaises(ValidationError) as capture:
            CalepinageVariante.objects.create(company=self.company,
                                              calepinage=self.pivot,
                                              nom='Directe', retenue=True)
        self.assertIn('retenue', capture.exception.message_dict)

    def test_bascule_manuelle_sur_une_variante_existante_refusee(self):
        variante = self._variante('A')
        variante.retenue = True
        with self.assertRaises(ValidationError):
            variante.save()

    def test_hors_contexte_la_porte_est_fermee(self):
        self.assertFalse(bascule_en_cours())
        with bascule_autorisee():
            self.assertTrue(bascule_en_cours())
        self.assertFalse(bascule_en_cours())

    def test_contexte_reentrant(self):
        with bascule_autorisee():
            with bascule_autorisee():
                self.assertTrue(bascule_en_cours())
            self.assertTrue(bascule_en_cours())
        self.assertFalse(bascule_en_cours())


class GardeParThreadTest(SimpleTestCase):
    def test_un_thread_n_ouvre_pas_la_porte_d_un_autre(self):
        vu = {}

        def _observer():
            vu['ailleurs'] = bascule_en_cours()

        with bascule_autorisee():
            fil = threading.Thread(target=_observer)
            fil.start()
            fil.join()
        self.assertFalse(vu['ailleurs'])


class GardeDeSurfaceTest(SimpleTestCase):
    """Aucun AUTRE fichier du module n'écrit ``retenue``."""

    def test_le_motif_attrape_une_vraie_ecriture(self):
        """Le garde reste un garde : il voit l'écriture qu'il interdit."""
        self.assertTrue(_ecritures_retenue('variante.retenue = True'))
        self.assertTrue(_ecritures_retenue('    obj.retenue = False'))
        # …et il ne voit PAS une lecture (variable locale, filtre de requête).
        self.assertFalse(_ecritures_retenue(
            'retenue = next((v for v in lignes if v.retenue), None)'))
        self.assertFalse(_ecritures_retenue(
            'qs.filter(calepinage=calepinage, retenue=True)'))
        self.assertFalse(_ecritures_retenue('if v.retenue == True:\n    pass'))

    def test_aucune_ecriture_ailleurs(self):
        coupables = []
        for fichier in sorted(RACINE_APP.rglob('*.py')):
            relatif = fichier.relative_to(RACINE_APP).as_posix()
            if relatif in FICHIERS_AUTORISES:
                continue
            if relatif.startswith('tests/') or relatif.startswith('migrations/'):
                continue
            for numero in _ecritures_retenue(
                    fichier.read_text(encoding='utf-8')):
                coupables.append(f'{relatif}:{numero}')
        self.assertEqual(
            coupables, [],
            "Écriture directe du champ « retenue » hors du chemin unique "
            f"(services/variantes.py) : {coupables}.")
