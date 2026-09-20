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
import pathlib
import re
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

#: Une écriture du champ : ``retenue=...`` ou ``.retenue = ...``.
ECRITURE_RETENUE = re.compile(r'(\bretenue\s*=(?!=)|\.retenue\s*=(?!=))')

#: Les seuls fichiers autorisés à écrire ``retenue`` : le chemin d'écriture
#: unique, et la déclaration du champ dans le modèle.
FICHIERS_AUTORISES = {'services/variantes.py', 'models.py'}


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

    def test_aucune_ecriture_ailleurs(self):
        coupables = []
        for fichier in sorted(RACINE_APP.rglob('*.py')):
            relatif = fichier.relative_to(RACINE_APP).as_posix()
            if relatif in FICHIERS_AUTORISES:
                continue
            if relatif.startswith('tests/') or relatif.startswith('migrations/'):
                continue
            for numero, ligne in enumerate(
                    fichier.read_text(encoding='utf-8').splitlines(), 1):
                if ECRITURE_RETENUE.search(ligne):
                    coupables.append(f'{relatif}:{numero}')
        self.assertEqual(
            coupables, [],
            "Écriture directe du champ « retenue » hors du chemin unique "
            f"(services/variantes.py) : {coupables}.")
