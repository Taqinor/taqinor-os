"""PV55 — les zones de toiture entrent ENFIN dans le document de calepinage.

``calepinage_io.document_entree`` écrivait ``'zones': []`` EN DUR. Le moteur
sait consommer quatre natures de contour depuis AOF57 ; aucune ne lui parvenait
jamais. Une servitude ou une bande coupe-feu tracée par le dessinateur ne
changeait donc rien au compte publié — silencieusement, ce qui est la pire
forme de panne : le chiffre reste plausible.

Ce que ce module VERROUILLE :

  1. **Une zone INTERDITE fait baisser le compte** — c'est la preuve que la
     donnée voyage vraiment jusqu'au moteur, et pas seulement jusqu'au JSON.
  2. **Une zone PRÉFÉRÉE ne change JAMAIS un compte** — c'est une propriété du
     moteur (bonus DOUX de départage) : la publier depuis l'AO ne doit pas la
     retourner.
  3. **La forme est celle du contrat** (``serialisation._zone_depuis``) et la
     ``nature`` passe TELLE QUELLE — ``ZoneAO.Nature`` reprend les valeurs de
     ``NatureZone`` précisément pour qu'aucune traduction ne s'intercale.
  4. **Un tracé à moitié fait est un REFUS NOMMÉ**, jamais une zone ignorée
     qui laisserait croire qu'elle bloque.

Run :
    python manage.py test apps.ao.tests.test_pv55_zones_document -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ao import calepinage_io, calepinage_service
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ToitureAO, ZoneAO,
)
from authentication.models import Company
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.types import NatureZone

CODE_KIT = 'AO-TABLE-PORTRAIT'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': [CODE_KIT],
    'pas_recherche_m': 0.01,
}

#: Bande PLEINE LARGEUR au milieu du toit : elle traverse exactement la rangée
#: médiane, si bien que son effet sur le compte est franc et non ambigu.
BANDE_MEDIANE = [[0.0, 5.0], [30.0, 5.0], [30.0, 11.0], [0.0, 11.0]]


class BasePv55(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV55 Co', slug='pv55-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-55-1', objet='Zones')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code=CODE_KIT,
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _zone(self, nature, sommets=None, repere='Z1', retrait='0.00'):
        return ZoneAO.objects.create(
            company=self.company, toiture=self.toiture, repere=repere,
            nature=nature,
            sommets=BANDE_MEDIANE if sommets is None else sommets,
            retrait_m=Decimal(retrait))

    def _modules(self):
        return calepinage_service.calepiner(
            calepinage_io.document_entree(self.toiture), company=self.company,
            tiroirs=False, suggestions=False)['total_modules']


class LesZonesArriventJusquAuMoteur(BasePv55):
    """Le JSON ne suffit pas : c'est le COMPTE qui prouve le câblage."""

    def test_une_zone_interdite_fait_baisser_le_compte(self):
        sans_zone = self._modules()
        self.assertGreater(sans_zone, 0)
        self._zone(ZoneAO.Nature.INTERDITE)
        self.assertLess(self._modules(), sans_zone)

    def test_une_zone_reservee_fait_aussi_baisser_le_compte(self):
        """``RESERVEE`` retire la surface comme ``INTERDITE`` (chiffrée à part)."""
        sans_zone = self._modules()
        self._zone(ZoneAO.Nature.RESERVEE)
        self.assertLess(self._modules(), sans_zone)

    def test_une_zone_preferee_ne_change_JAMAIS_le_compte(self):
        """Propriété du moteur : un bonus DOUX ne peut pas coûter un module."""
        sans_zone = self._modules()
        self._zone(ZoneAO.Nature.PREFEREE)
        self.assertEqual(self._modules(), sans_zone)

    def test_une_zone_enveloppe_ne_retire_rien(self):
        sans_zone = self._modules()
        self._zone(ZoneAO.Nature.ENVELOPPE)
        self.assertEqual(self._modules(), sans_zone)

    def test_une_zone_d_une_autre_toiture_n_entre_pas(self):
        """Les zones sont lues PAR TOITURE : celle du voisin ne compte pas."""
        sans_zone = self._modules()
        autre = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment,
            code_document='06H', contour_local_m=[[0, 0], [10, 0], [10, 10],
                                                  [0, 10]])
        ZoneAO.objects.create(company=self.company, toiture=autre,
                              repere='ZX', nature=ZoneAO.Nature.INTERDITE,
                              sommets=BANDE_MEDIANE)
        self.assertEqual(self._modules(), sans_zone)


class LaFormeEstCelleDuContrat(BasePv55):
    """``serialisation._zone_depuis`` doit relire ce qu'on écrit, sans glose."""

    def test_les_cles_sont_celles_du_contrat(self):
        self._zone(ZoneAO.Nature.INTERDITE, retrait='0.25')
        zones = calepinage_io.document_entree(self.toiture)['zones']
        self.assertEqual(len(zones), 1)
        self.assertEqual(set(zones[0]), {'repere', 'nature', 'sommets',
                                         'hauteur_m', 'retrait_m'})
        self.assertEqual(zones[0]['repere'], 'Z1')
        self.assertEqual(zones[0]['sommets'], BANDE_MEDIANE)
        self.assertEqual(zones[0]['retrait_m'], 0.25)
        self.assertIsNone(zones[0]['hauteur_m'])

    def test_la_nature_passe_telle_quelle(self):
        for nature in ZoneAO.Nature.values:
            ZoneAO.objects.filter(toiture=self.toiture).delete()
            self._zone(nature)
            zones = calepinage_io.document_entree(self.toiture)['zones']
            self.assertEqual(zones[0]['nature'], nature)
            # et le moteur la relit sans traduction
            self.assertEqual(NatureZone(zones[0]['nature']).value, nature)

    def test_le_document_est_relu_par_le_contrat(self):
        self._zone(ZoneAO.Nature.INTERDITE)
        document = calepinage_io.document_entree(self.toiture)
        entree = EntreeCalepinage.depuis_dict(document)
        self.assertEqual(len(entree.zones), 1)
        self.assertIs(entree.zones[0].nature, NatureZone.INTERDITE)
        self.assertEqual(len(entree.zones[0].sommets), 4)

    def test_les_zones_bougent_l_empreinte_d_entree(self):
        """Une zone fait partie de l'entrée : elle ne peut pas être invisible."""
        avant = calepinage_service.empreinte_document(
            calepinage_io.document_entree(self.toiture))
        self._zone(ZoneAO.Nature.INTERDITE)
        apres = calepinage_service.empreinte_document(
            calepinage_io.document_entree(self.toiture))
        self.assertNotEqual(avant, apres)

    def test_sans_zone_la_liste_reste_vide(self):
        self.assertEqual(
            calepinage_io.document_entree(self.toiture)['zones'], [])


class UnTraceAMoitieFaitEstRefuse(BasePv55):
    """Ignorer une zone interdite incomplète ferait croire qu'elle bloque."""

    def test_un_contour_de_deux_sommets_est_refuse_en_francais(self):
        ZoneAO.objects.create(
            company=self.company, toiture=self.toiture, repere='ZB',
            nature=ZoneAO.Nature.INTERDITE, sommets=[[0.0, 0.0], [1.0, 1.0]])
        with self.assertRaises(calepinage_io.EntreeInvalide) as capture:
            calepinage_io.document_entree(self.toiture)
        self.assertIn('ZB', str(capture.exception))

    def test_un_contour_vide_est_simplement_ignore(self):
        """Une zone en cours de saisie ne délimite rien : elle ne bloque rien."""
        sans_zone = self._modules()
        self._zone(ZoneAO.Nature.INTERDITE, sommets=[])
        self.assertEqual(
            calepinage_io.document_entree(self.toiture)['zones'], [])
        self.assertEqual(self._modules(), sans_zone)
