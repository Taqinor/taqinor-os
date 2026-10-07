"""CIQ611 — checklist de chantier C&I semée (socle commun + BT), choisie par
type ET par niveau de tension.

Run :
    python manage.py test apps.installations.tests_ciq611_template_ci -v 2
"""
import re

from django.test import TestCase

from apps.installations.models import (
    ChecklistEtapeModele, ChecklistTemplate, Installation)
from apps.installations.services import (
    CI_CHECKLIST_ETAPES, CI_TEMPLATE_NOM, POMPAGE_TEMPLATE_NOM,
    DEFAULT_TEMPLATE_NOM, ensure_checklist_items, ensure_template_ci,
    template_for_installation)
from authentication.models import Company

ORDRE_ATTENDU = [
    'materiel_recu', 'plan_prevention_signe', 'acces_protections',
    'structure_posee', 'panneaux_poses', 'chaines_dc_reperees',
    'onduleurs_poses', 'raccordement_tgbt', 'supervision_compteur',
    'recette_enregistree', 'client_forme', 'photos_prises',
    'pv_reception_signe', 'schema_electrique_valide',
]


class TemplateCITest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ611', slug='ciq611-co')
        self._n = 0

    def _chantier(self, type_installation, niveau=None):
        self._n += 10
        return Installation.objects.create(
            company=self.company, reference=f'CHT-611-{self._n}',
            type_installation=type_installation, niveau_tension=niveau)

    def test_industriel_bt_ou_sans_niveau_recoit_le_template_ci(self):
        for niveau in ('bt', None):  # MT : template dédié (CIQ662).
            chantier = self._chantier('industriel', niveau)
            template = template_for_installation(chantier)
            self.assertEqual(template.nom, CI_TEMPLATE_NOM)
            items = ensure_checklist_items(chantier)
            self.assertEqual([it.cle for it in items], ORDRE_ATTENDU)

    def test_photo_et_capture_aux_bonnes_etapes(self):
        items = {it.cle: it for it in ensure_checklist_items(
            self._chantier('industriel', 'bt'))}
        for cle in ('plan_prevention_signe', 'acces_protections',
                    'structure_posee', 'chaines_dc_reperees',
                    'onduleurs_poses', 'raccordement_tgbt'):
            self.assertTrue(items[cle].photo_obligatoire, cle)
        self.assertEqual(
            {cle for cle, it in items.items() if it.capture_serie},
            {'panneaux_poses', 'onduleurs_poses'})
        self.assertFalse(items['materiel_recu'].photo_obligatoire)

    def test_idempotent(self):
        self.assertIsNotNone(ensure_template_ci(self.company))
        self.assertIsNone(ensure_template_ci(self.company))
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, nom=CI_TEMPLATE_NOM).count(), 1)
        self.assertEqual(ChecklistEtapeModele.objects.filter(
            company=self.company, template__nom=CI_TEMPLATE_NOM).count(),
            len(CI_CHECKLIST_ETAPES))

    def test_desactive_ou_renomme_jamais_recree(self):
        template = ensure_template_ci(self.company)
        template.actif = False
        template.nom = 'Mon modèle pro'
        template.save()
        self.assertIsNone(ensure_template_ci(self.company))
        chantier = self._chantier('industriel', 'bt')
        # Template désactivé → repli « Défaut », jamais recréé.
        self.assertEqual(template_for_installation(chantier).nom,
                         DEFAULT_TEMPLATE_NOM)
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, type_installation='industriel').count(), 1)

    def test_template_par_niveau_choisi_en_premier(self):
        ensure_template_ci(self.company)
        mt = ChecklistTemplate.objects.create(
            company=self.company, nom='Site MT', type_installation='industriel',
            niveau_tension='mt', ordre=5)
        self.assertEqual(
            template_for_installation(self._chantier('industriel', 'mt')), mt)
        self.assertEqual(
            template_for_installation(
                self._chantier('industriel', 'bt')).nom, CI_TEMPLATE_NOM)

    def test_residentiel_et_agricole_inchanges(self):
        res = self._chantier('residentiel')
        self.assertEqual(template_for_installation(res).nom,
                         DEFAULT_TEMPLATE_NOM)
        agri = self._chantier('agricole')
        self.assertEqual(template_for_installation(agri).nom,
                         POMPAGE_TEMPLATE_NOM)
        self.assertFalse(ChecklistTemplate.objects.filter(
            company=self.company, nom=CI_TEMPLATE_NOM).exists())

    def test_aucune_valeur_numerique_dans_les_libelles(self):
        for _cle, libelle, _capture, _photo in CI_CHECKLIST_ETAPES:
            self.assertIsNone(re.search(r'\d', libelle), libelle)
