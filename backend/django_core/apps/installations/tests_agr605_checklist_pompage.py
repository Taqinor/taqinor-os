"""AGR605 — checklist « Pompage solaire » et plan d'interventions agricole
semés (idempotents), sans « Onduleur raccordé » ni « raccordement ».

Run :
    python manage.py test apps.installations.tests_agr605_checklist_pompage -v2
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations.models import (
    ChecklistEtapeModele, ChecklistTemplate, Installation, Intervention,
    TypeInterventionPlan,
)
from apps.installations.services import (
    POMPAGE_CHECKLIST_ETAPES, ensure_checklist_items,
    ensure_plan_interventions_agricole, ensure_template_agricole,
)
from apps.installations.tests import auth, make_accepted_devis, make_company

User = get_user_model()

CLES_POMPAGE = [
    'materiel_recu', 'forage_verifie', 'structure_sol_posee',
    'panneaux_poses', 'coffret_dc_terre', 'cable_colonne_poses',
    'pompe_descendue', 'variateur_parametre', 'recette_pompage',
    'etiquette_sav', 'client_forme', 'photos_prises', 'pv_reception_signe',
]


class _Base(TestCase):
    slug = 'agr605'

    def setUp(self):
        self.company = make_company(slug=f'{self.slug}-co', nom='AGR605 Co')
        self.user = User.objects.create_user(
            username=f'{self.slug}_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)

    def _make_inst(self, type_install):
        devis, _, _ = make_accepted_devis(self.company)
        devis.mode_installation = type_install
        devis.save(update_fields=['mode_installation'])
        r = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Installation.objects.get(pk=r.data['id'])


class ChecklistPompageTests(_Base):
    def test_chantier_agricole_recoit_13_etapes_dans_l_ordre(self):
        inst = self._make_inst('agricole')
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        items = r.data['items']
        self.assertEqual([it['cle'] for it in items], CLES_POMPAGE)
        self.assertNotIn('onduleur_raccorde', [it['cle'] for it in items])
        self.assertEqual(
            sum(1 for it in items if it['photo_obligatoire']), 5)
        self.assertEqual(sum(1 for it in items if it['capture_serie']), 3)
        tmpl = ChecklistTemplate.objects.get(
            company=self.company, type_installation='agricole')
        self.assertEqual(tmpl.nom, 'Pompage solaire')
        self.assertFalse(tmpl.protege)
        # Le seul template protégé reste le « Défaut ».
        self.assertEqual(
            ChecklistTemplate.objects.filter(
                company=self.company, protege=True).count(), 1)

    def test_aucun_chiffre_dans_les_libelles(self):
        for _cle, libelle, _c, _p in POMPAGE_CHECKLIST_ETAPES:
            self.assertIsNone(re.search(r'\d', libelle), libelle)

    def test_idempotent_et_jamais_recree_si_desactive(self):
        self.assertIsNotNone(ensure_template_agricole(self.company))
        self.assertIsNone(ensure_template_agricole(self.company))
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, type_installation='agricole').count(), 1)
        self.assertEqual(ChecklistEtapeModele.objects.filter(
            company=self.company,
            template__type_installation='agricole').count(), 13)
        ChecklistTemplate.objects.filter(
            company=self.company, type_installation='agricole').update(
            actif=False, nom='Renommé')
        self.assertIsNone(ensure_template_agricole(self.company))
        inst = self._make_inst('agricole')
        ensure_checklist_items(inst)  # repli sur le « Défaut »
        self.assertEqual(ChecklistTemplate.objects.filter(
            company=self.company, type_installation='agricole').count(), 1)

    def test_residentiel_garde_le_defaut_8_etapes(self):
        inst = self._make_inst('residentiel')
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['items']), 8)
        self.assertIn('onduleur_raccorde',
                      [it['cle'] for it in r.data['items']])
        self.assertFalse(ChecklistTemplate.objects.filter(
            company=self.company, type_installation='agricole').exists())


class PlanInterventionsPompageTests(_Base):
    slug = 'agr605p'

    def test_creer_interventions_standard_agricole(self):
        inst = self._make_inst('agricole')
        url = (f'/api/django/installations/chantiers/{inst.id}/'
               'creer-interventions-standard/')
        r = self.api.post(url, {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data['created']), 3)
        types = list(Intervention.objects.filter(installation=inst)
                     .values_list('type_intervention', flat=True))
        self.assertEqual(sorted(types),
                         ['controle', 'mise_en_service', 'pose'])
        self.assertNotIn('raccordement', types)
        controle = Intervention.objects.get(
            installation=inst, type_intervention='controle')
        self.assertIn('30 premiers jours', controle.compte_rendu)
        # 2e appel : rien de plus.
        r2 = self.api.post(url, {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(
            Intervention.objects.filter(installation=inst).count(), 3)
        self.assertEqual(ensure_plan_interventions_agricole(self.company), 0)
        self.assertEqual(TypeInterventionPlan.objects.filter(
            company=self.company, type_installation='agricole').count(), 3)

    def test_residentiel_sans_plan_inchange(self):
        inst = self._make_inst('residentiel')
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst.id}/'
            'creer-interventions-standard/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            r.data['detail'], 'Aucun plan standard défini pour ce type.')
        self.assertFalse(TypeInterventionPlan.objects.filter(
            company=self.company).exists())
