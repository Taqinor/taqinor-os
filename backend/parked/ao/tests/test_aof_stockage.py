"""AOF150 — archivage MinIO IMMUABLE + manifeste de pack.

Ce qui est prouvé ici :

* la clé porte l'indice ET l'empreinte, et **un artefact ne s'écrase jamais**
  (contrainte en base + refus explicite) ;
* le pack courant est un MANIFESTE de clés : **une pièce périmée est
  STRUCTURELLEMENT exclue**, elle ne « risque » pas d'y entrer ;
* l'écriture est **en flux, à mémoire BORNÉE** : le téléverseur ne voit jamais
  plus d'un morceau à la fois (un worker Celery sature sinon) ;
* aucun nouveau ``FileField`` (garde plateforme).

Run :
    python manage.py test apps.ao.tests.test_aof_stockage -v2
"""
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.fabrique import stockage
from apps.ao.fabrique.coherence import empreinte_dossier
from apps.ao.models import AppelOffre, ArtefactAO, ManifestePack
from authentication.models import Company

EMPREINTE_A = 'a' * 64
EMPREINTE_B = 'b' * 64


class TeleverseurEspion:
    """Téléverseur de test : mesure le pic mémoire réellement détenu."""

    def __init__(self):
        self.pic_octets = 0
        self.morceaux_vus = 0
        self.cles = []

    def __call__(self, cle, morceaux, mime):
        self.cles.append(cle)
        taille = 0
        for morceau in morceaux:
            self.morceaux_vus += 1
            self.pic_octets = max(self.pic_octets, len(morceau))
            taille += len(morceau)
        return taille, ''


class TestCleImmuable(SimpleTestCase):
    def test_la_forme_de_la_cle(self):
        self.assertEqual(
            stockage.cle_artefact(7, 42, '04', 'B', 'abcdef1234567890', 'pdf'),
            'ao/7/42/04/B-abcdef12.pdf')

    def test_la_cle_est_prefixee_par_la_societe(self):
        cle = stockage.cle_artefact(7, 42, '04', 'A', EMPREINTE_A)
        self.assertTrue(cle.startswith('ao/7/'))

    def test_deux_indices_ne_partagent_jamais_une_cle(self):
        a = stockage.cle_artefact(7, 42, '04', 'A', EMPREINTE_A)
        b = stockage.cle_artefact(7, 42, '04', 'B', EMPREINTE_B)
        self.assertNotEqual(a, b)

    def test_deux_empreintes_ne_partagent_jamais_une_cle(self):
        a = stockage.cle_artefact(7, 42, '04', 'A', EMPREINTE_A)
        b = stockage.cle_artefact(7, 42, '04', 'A', EMPREINTE_B)
        self.assertNotEqual(a, b)


class BaseStockage(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF150 Co',
                                              slug='aof150-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-150-1', objet='Stockage')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)
        self.espion = TeleverseurEspion()

    def _ecrire(self, code, indice, empreinte, morceaux=None):
        return stockage.ecrire_artefact(
            self.dossier, code=code, indice=indice, empreinte=empreinte,
            morceaux=morceaux if morceaux is not None else [b'%PDF-1.4'],
            televerseur=self.espion)


class TestAucunEcrasement(BaseStockage):
    def test_un_artefact_s_archive(self):
        artefact = self._ecrire('04', 'A', EMPREINTE_A)
        self.assertEqual(artefact.cle,
                         f'ao/{self.company.id}/{self.dossier.id}/04/'
                         f'A-aaaaaaaa.pdf')
        self.assertEqual(artefact.taille, 8)

    def test_reecrire_la_meme_cle_est_REFUSE(self):
        self._ecrire('04', 'A', EMPREINTE_A)
        with self.assertRaises(stockage.EcrasementRefuse) as ctx:
            self._ecrire('04', 'A', EMPREINTE_A)
        self.assertIn('IMMUABLE', str(ctx.exception))

    def test_l_unicite_de_la_cle_est_en_BASE(self):
        artefact = self._ecrire('04', 'A', EMPREINTE_A)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ArtefactAO.objects.create(
                company=self.company, dossier=self.dossier, code='ZZ',
                indice='A', empreinte=EMPREINTE_A, cle=artefact.cle)

    def test_un_indice_superieur_coexiste_avec_le_precedent(self):
        self._ecrire('04', 'A', EMPREINTE_A)
        self._ecrire('04', 'B', EMPREINTE_B)
        self.assertEqual(ArtefactAO.objects.filter(
            dossier=self.dossier, code='04').count(), 2)

    def test_aucun_filefield_sur_l_artefact(self):
        types = {f.__class__.__name__
                 for f in ArtefactAO._meta.get_fields()}
        self.assertNotIn('FileField', types)


class TestMemoireBornee(BaseStockage):
    def test_le_flux_est_consomme_morceau_par_morceau(self):
        morceaux = (b'x' * 1024 for _ in range(200))
        artefact = self._ecrire('05', 'A', EMPREINTE_A, morceaux=morceaux)
        self.assertEqual(artefact.taille, 200 * 1024)
        self.assertEqual(self.espion.morceaux_vus, 200)
        # Le pic détenu est la taille d'UN morceau, jamais celle du fichier.
        self.assertEqual(self.espion.pic_octets, 1024)
        self.assertLess(self.espion.pic_octets, artefact.taille)

    def test_un_generateur_paresseux_suffit(self):
        """Aucune liste n'est construite : un générateur pur passe."""
        def _flux():
            for _ in range(50):
                yield b'y' * 2048

        artefact = self._ecrire('06', 'A', EMPREINTE_A, morceaux=_flux())
        self.assertEqual(artefact.taille, 50 * 2048)
        self.assertEqual(self.espion.pic_octets, 2048)

    def test_le_plafond_de_morceau_est_declare(self):
        self.assertEqual(stockage.TAILLE_MORCEAU, 64 * 1024)


class TestManifeste(BaseStockage):
    def test_le_manifeste_ne_prend_que_l_empreinte_courante(self):
        courante = empreinte_dossier(self.dossier)
        a_jour = self._ecrire('04', 'A', courante)
        perime = self._ecrire('04', 'B', EMPREINTE_B)
        manifeste = stockage.construire_manifeste(self.dossier)
        cles = {a.cle for a in manifeste.artefacts.all()}
        self.assertIn(a_jour.cle, cles)
        self.assertNotIn(perime.cle, cles)

    def test_une_piece_perimee_est_STRUCTURELLEMENT_exclue(self):
        courante = empreinte_dossier(self.dossier)
        self._ecrire('04', 'A', courante)
        self._ecrire('05', 'A', EMPREINTE_B)
        manifeste = stockage.construire_manifeste(self.dossier)
        self.assertEqual(manifeste.artefacts_perimes(), [])

    def test_l_ancien_manifeste_reste_consultable_mais_non_courant(self):
        courante = empreinte_dossier(self.dossier)
        self._ecrire('04', 'A', courante)
        premier = stockage.construire_manifeste(self.dossier)
        second = stockage.construire_manifeste(self.dossier,
                                               empreinte=EMPREINTE_B)
        premier.refresh_from_db()
        self.assertFalse(premier.courant)
        self.assertTrue(second.courant)
        self.assertEqual(ManifestePack.objects.filter(
            dossier=self.dossier).count(), 2)
        self.assertEqual(stockage.manifeste_courant(self.dossier).pk,
                         second.pk)

    def test_un_seul_manifeste_courant_par_dossier_en_base(self):
        stockage.construire_manifeste(self.dossier)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ManifestePack.objects.create(
                company=self.company, dossier=self.dossier,
                empreinte=EMPREINTE_B, courant=True)

    def test_le_manifeste_est_une_liste_de_cles_pas_un_repertoire(self):
        courante = empreinte_dossier(self.dossier)
        self._ecrire('04', 'A', courante)
        self._ecrire('05', 'A', courante)
        manifeste = stockage.construire_manifeste(self.dossier)
        cles = sorted(a.cle for a in manifeste.artefacts.all())
        self.assertEqual(len(cles), 2)
        self.assertTrue(all(cle.startswith(f'ao/{self.company.id}/')
                            for cle in cles))

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF150 X', slug='aof150-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-150-X', objet='X')
        dossier_autre = services.creer_dossier_ao(autre, ao)
        stockage.ecrire_artefact(
            dossier_autre, code='04', indice='A', empreinte=EMPREINTE_A,
            morceaux=[b'%PDF-1.4'], televerseur=self.espion)
        manifeste = stockage.construire_manifeste(self.dossier)
        self.assertEqual(list(manifeste.artefacts.all()), [])
