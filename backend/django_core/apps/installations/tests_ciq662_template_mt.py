"""CIQ662 — checklist de chantier MT semée (supplément au socle C&I).

Run :
    python manage.py test apps.installations.tests_ciq662_template_mt -v 2
"""
import re

from django.test import TestCase

from apps.installations.models import ChecklistTemplate, Installation
from apps.installations.services import (
    CI_CHECKLIST_ETAPES, CI_MT_ETAPES_SUPPLEMENT, CI_MT_TEMPLATE_NOM,
    CI_TEMPLATE_NOM, ensure_checklist_items, ensure_template_ci,
    ensure_template_ci_mt, template_for_installation,
)
from authentication.models import Company

ORDRE_MT = [
    'materiel_recu', 'plan_prevention_signe', 'acces_protections',
    'structure_posee', 'panneaux_poses', 'chaines_dc_reperees',
    'onduleurs_poses', 'raccordement_tgbt',
    'poste_livraison_controle', 'reglages_protection_appliques',
    'essais_injection_decouplage', 'mise_sous_tension_distributeur',
    'compteur_production_pose',
    'supervision_compteur', 'recette_enregistree', 'client_forme',
    'photos_prises', 'pv_reception_signe', 'schema_electrique_valide',
]


class TemplateMTTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ662', slug='ciq662-co')
        self._n = 0

    def _chantier(self, niveau):
        self._n += 10
        return Installation.objects.create(
            company=self.company, reference=f'CHT-662-{self._n}',
            type_installation='industriel', niveau_tension=niveau)

    def test_chantier_mt_recoit_le_template_mt_dans_l_ordre(self):
        chantier = self._chantier('mt')
        template = template_for_installation(chantier)
        self.assertEqual(template.nom, CI_MT_TEMPLATE_NOM)
        self.assertEqual(template.niveau_tension, 'mt')
        self.assertEqual(template.type_installation, 'industriel')
        items = ensure_checklist_items(chantier)
        self.assertEqual([it.cle for it in items], ORDRE_MT)

    def test_photos_aux_etapes_de_controle(self):
        items = {it.cle: it for it in ensure_checklist_items(
            self._chantier('mt'))}
        for cle in ('poste_livraison_controle',
                    'reglages_protection_appliques',
                    'mise_sous_tension_distributeur'):
            self.assertTrue(items[cle].photo_obligatoire, cle)
        self.assertFalse(items['compteur_production_pose'].capture_serie)

    def test_chantier_bt_template_ci_bt_inchange(self):
        for niveau in ('bt', None):
            chantier = self._chantier(niveau)
            self.assertEqual(
                template_for_installation(chantier).nom, CI_TEMPLATE_NOM)
            self.assertEqual(
                [it.cle for it in ensure_checklist_items(chantier)],
                [e[0] for e in CI_CHECKLIST_ETAPES])

    def test_deuxieme_appel_ne_cree_rien(self):
        self.assertIsNotNone(ensure_template_ci_mt(self.company))
        self.assertIsNone(ensure_template_ci_mt(self.company))
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, nom=CI_MT_TEMPLATE_NOM).count(), 1)

    def test_template_desactive_jamais_recree(self):
        template = ensure_template_ci_mt(self.company)
        template.actif = False
        template.save(update_fields=['actif'])
        self.assertIsNone(ensure_template_ci_mt(self.company))
        # Désactivé : le chantier MT retombe sur le template C&I tous niveaux.
        ensure_template_ci(self.company)
        chantier = self._chantier('mt')
        self.assertEqual(
            template_for_installation(chantier).nom, CI_TEMPLATE_NOM)
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, nom=CI_MT_TEMPLATE_NOM).count(), 1)

    def test_aucun_chiffre_dans_les_libelles_du_supplement(self):
        for _cle, libelle, _capture, _photo in CI_MT_ETAPES_SUPPLEMENT:
            self.assertIsNone(re.search(r'\d', libelle), libelle)
