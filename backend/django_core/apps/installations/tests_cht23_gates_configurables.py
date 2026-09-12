"""CHT23 — Gates : exigences photo/checklist configurables par étape.

``StageModele`` gagne deux champs additifs : ``photos_min`` (défaut 0) et
``checklist_pct_min`` (défaut 100). ADDITIF STRICT : à leurs valeurs par
défaut, ``services._gate_check_checklist``/``_gate_check_photos`` restent
l'ancien comportement OCTET POUR OCTET (« tous faits ») — ``photos_min`` > 0
AJOUTE une contrainte de comptage réel de photos (``records.Attachment``),
``checklist_pct_min`` < 100 assouplit en « ≥ pct % faits ».

Run :
    python manage.py test apps.installations.tests_cht23_gates_configurables -v2
"""
import itertools

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import (
    ChantierChecklistItem, ChecklistEtapeModele, ChecklistTemplate,
    Installation, StageModele,
)
from apps.installations.services import ensure_checklist_items, stage_gate_status
from apps.records.models import Attachment
from authentication.models import Company

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht23-co-{n}', defaults={'nom': nom or f'CHT23 Co {n}'})
    return company


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CHT23',
        email=f'cht23-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CHT23-{n}', client=client,
        type_installation='residentiel')


def make_checklist_items(company, installation, n_faits, n_total):
    """Dénominateur EXACT garanti : un template TYPÉ (résidentiel) de
    `n_total` étapes — `ensure_checklist_items` (appelée par les gates) ne
    matérialise que LUI, jamais les étapes du template « Défaut » système
    (leçon CI ronde 2 : des items créés à la main s'additionnaient aux 8
    étapes Défaut matérialisées paresseusement → 13 au dénominateur)."""
    n = next(_seq)
    template = ChecklistTemplate.objects.create(
        company=company, nom=f'CHT23 typé {n}',
        type_installation='residentiel', actif=True)
    for i in range(n_total):
        ChecklistEtapeModele.objects.create(
            company=company, template=template, cle=f'item-{i}',
            libelle=f'Étape {i}', ordre=i)
    items = ensure_checklist_items(installation)
    faits = [it for it in items][:n_faits]
    ChantierChecklistItem.objects.filter(
        id__in=[it.id for it in faits]).update(fait=True)
    return items


def make_photo(company, installation):
    ct = ContentType.objects.get_for_model(Installation)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=installation.id,
        file_key=f'photo-{next(_seq)}.jpg', filename='photo.jpg',
        mime='image/jpeg')


def make_stage(company, **kwargs):
    n = next(_seq)
    defaults = dict(
        company=company, cle=f'gate-{n}', libelle='Gate CHT23',
        bloquant=True)
    defaults.update(kwargs)
    return StageModele.objects.create(**defaults)


class TestStageModeleDefauts(TestCase):
    def test_defauts_sont_le_comportement_historique(self):
        company = make_company()
        stage = make_stage(company)
        self.assertEqual(stage.photos_min, 0)
        self.assertEqual(stage.checklist_pct_min, 100)


class TestGateChecklistPourcentageConfigurable(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        make_checklist_items(self.company, self.inst, n_faits=4, n_total=5)

    def test_defaut_100_bloque_a_4_sur_5(self):
        stage = make_stage(
            self.company, exige_checklist=True, checklist_pct_min=100)
        etat = stage_gate_status(self.inst, stage)
        self.assertFalse(etat['satisfait'])
        self.assertTrue(any('Checklist incomplète' in r for r in etat['raisons']))

    def test_pct_80_passe_a_4_sur_5(self):
        stage = make_stage(
            self.company, exige_checklist=True, checklist_pct_min=80)
        etat = stage_gate_status(self.inst, stage)
        self.assertTrue(etat['satisfait'], etat['raisons'])

    def test_pct_90_bloque_encore_a_4_sur_5(self):
        stage = make_stage(
            self.company, exige_checklist=True, checklist_pct_min=90)
        etat = stage_gate_status(self.inst, stage)
        self.assertFalse(etat['satisfait'])

    def test_checklist_complete_satisfait_quel_que_soit_le_pct(self):
        autre_inst = make_installation(self.company)
        make_checklist_items(self.company, autre_inst, n_faits=5, n_total=5)
        stage = make_stage(
            self.company, exige_checklist=True, checklist_pct_min=80)
        etat = stage_gate_status(autre_inst, stage)
        self.assertTrue(etat['satisfait'])


class TestGatePhotosMinimumConfigurable(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)

    def test_defaut_0_ne_compte_aucune_photo(self):
        stage = make_stage(self.company, exige_photos=True, photos_min=0)
        etat = stage_gate_status(self.inst, stage)
        self.assertTrue(etat['satisfait'])

    def test_photos_min_3_bloque_a_2_photos(self):
        make_photo(self.company, self.inst)
        make_photo(self.company, self.inst)
        stage = make_stage(self.company, exige_photos=True, photos_min=3)
        etat = stage_gate_status(self.inst, stage)
        self.assertFalse(etat['satisfait'])
        self.assertTrue(
            any('Photos insuffisantes' in r for r in etat['raisons']))

    def test_photos_min_3_satisfait_a_3_photos(self):
        for _ in range(3):
            make_photo(self.company, self.inst)
        stage = make_stage(self.company, exige_photos=True, photos_min=3)
        etat = stage_gate_status(self.inst, stage)
        self.assertTrue(etat['satisfait'], etat['raisons'])

    def test_checklist_photo_obligatoire_manquante_bloque_avant_le_comptage(self):
        """Le gate historique (item `photo_obligatoire` non fait) reste
        inconditionnel — il bloque même si `photos_min` serait satisfait."""
        ChantierChecklistItem.objects.create(
            company=self.company, installation=self.inst, cle='pose',
            libelle='Pose panneaux', photo_obligatoire=True, fait=False)
        for _ in range(5):
            make_photo(self.company, self.inst)
        stage = make_stage(self.company, exige_photos=True, photos_min=3)
        etat = stage_gate_status(self.inst, stage)
        self.assertFalse(etat['satisfait'])
        self.assertTrue(
            any('Photos requises manquantes' in r for r in etat['raisons']))
