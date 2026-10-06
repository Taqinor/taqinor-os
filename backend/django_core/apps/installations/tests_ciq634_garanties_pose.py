"""CIQ634 — garanties de pose et d'étanchéité : durées saisies, sans défaut,
dans la pièce « Garanties » du pack de remise."""
import datetime

from django.test import TestCase

from apps.installations.models import Installation
from apps.installations.serializers import InstallationSerializer
from apps.installations.services import (
    GARANTIE_NON_RENSEIGNEE, assemble_handover_pieces,
)
from authentication.models import Company


class GarantiesPoseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ634', slug='ciq634-co')
        self._n = 0

    def _chantier(self, type_installation='industriel', **extra):
        self._n += 10
        return Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ634-{self._n}',
            type_installation=type_installation, **extra)

    def _garanties(self, chantier):
        pieces = assemble_handover_pieces(chantier)['pieces']
        return next(p for p in pieces if p['type'] == 'garanties')

    def test_durees_vides_non_renseignee_sans_defaut(self):
        chantier = self._chantier()
        self.assertIsNone(chantier.garantie_installation_mois)
        self.assertIsNone(chantier.garantie_etancheite_mois)
        piece = self._garanties(chantier)
        self.assertEqual(len(piece['installateur']), 2)
        for ligne in piece['installateur']:
            self.assertIsNone(ligne['duree_mois'])
            self.assertIn(GARANTIE_NON_RENSEIGNEE, ligne['texte'])
        self.assertIn(GARANTIE_NON_RENSEIGNEE, piece['reference'])

    def test_24_mois_fin_egale_reception_provisoire_plus_24_mois(self):
        chantier = self._chantier(
            garantie_installation_mois=24,
            garantie_installation_perimetre='Pose et câblage',
            date_reception=datetime.date(2026, 10, 13))
        piece = self._garanties(chantier)
        pose = next(g for g in piece['installateur']
                    if g['type'] == 'installation')
        self.assertEqual(pose['date_fin'], '2028-10-13')
        self.assertIn('13/10/2028', pose['texte'])
        self.assertIn('Pose et câblage', pose['texte'])
        self.assertIn('13/10/2028', piece['reference'])
        etanch = next(g for g in piece['installateur']
                      if g['type'] == 'etancheite')
        self.assertIn(GARANTIE_NON_RENSEIGNEE, etanch['texte'])

    def test_sans_reception_la_fin_n_est_pas_inventee(self):
        chantier = self._chantier(garantie_etancheite_mois=36)
        piece = self._garanties(chantier)
        etanch = next(g for g in piece['installateur']
                      if g['type'] == 'etancheite')
        self.assertIsNone(etanch['date_fin'])
        self.assertIn('réception provisoire', etanch['texte'])

    def test_residentiel_inchange(self):
        chantier = self._chantier(
            type_installation='residentiel', garantie_installation_mois=24)
        piece = self._garanties(chantier)
        self.assertNotIn('installateur', piece)
        self.assertIsNone(piece['reference'])

    def test_champs_saisissables_par_la_societe(self):
        chantier = self._chantier()
        ser = InstallationSerializer(
            chantier, data={'garantie_installation_mois': 12,
                            'garantie_etancheite_perimetre': 'Membrane'},
            partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        chantier.refresh_from_db()
        self.assertEqual(chantier.garantie_installation_mois, 12)
        self.assertEqual(chantier.garantie_etancheite_perimetre, 'Membrane')
