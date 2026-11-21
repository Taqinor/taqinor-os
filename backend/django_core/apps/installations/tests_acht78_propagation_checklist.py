"""ACHT78 (C-ACHT-073) — règle de propagation du modèle de checklist (D-ACHT-2,
ACHT95 option a) : la checklist d'un chantier est figée à sa première
matérialisation ; un chantier réceptionné/clôturé n'est jamais modifié ; un
chantier jamais ouvert reçoit le modèle courant ; la relecture est idempotente.

Rejoue COUT-9 : clôturé `items apres relecture 9 (avant 8)`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht78_propagation_checklist"
"""
from django.test import TestCase

from authentication.models import Company

from apps.installations.models import (
    ChantierChecklistItem, ChecklistEtapeModele, ChecklistTemplate,
    Installation,
)
from apps.installations.services import (
    DEFAULT_CHECKLIST_ETAPES, ensure_checklist_items, ensure_default_template,
)


class PropagationChecklistTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACHT78', slug='acht78-co')
        # protege=True : `ensure_default_template` ne reconnaît comme « Défaut »
        # que le template protégé (sinon il en crée un second, amorcé à 8).
        self.tpl = ChecklistTemplate.objects.create(
            company=self.co, nom='Défaut', protege=True)
        for i in range(8):
            ChecklistEtapeModele.objects.create(
                company=self.co, template=self.tpl, cle=f'e{i}',
                libelle=f'Étape {i}', ordre=i)
        self.cloture = Installation.objects.create(
            company=self.co, reference='CH-CLOS',
            statut=Installation.Statut.CLOTURE)
        self.en_cours = Installation.objects.create(
            company=self.co, reference='CH-COURS',
            statut=Installation.Statut.EN_COURS)
        self.jamais_ouvert = Installation.objects.create(
            company=self.co, reference='CH-NEUF',
            statut=Installation.Statut.EN_COURS)
        # Le clôturé et l'en-cours ont déjà leurs 8 étapes matérialisées
        # (avant la clôture pour le premier).
        for inst in (self.cloture, self.en_cours):
            Installation.objects.filter(pk=inst.pk).update(
                statut=Installation.Statut.EN_COURS)
            inst.refresh_from_db()
            self.assertEqual(len(ensure_checklist_items(inst)), 8)
        Installation.objects.filter(pk=self.cloture.pk).update(
            statut=Installation.Statut.CLOTURE)
        self.cloture.refresh_from_db()

    def _modifier_le_modele(self):
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.tpl, cle='nouvelle',
            libelle='Nouvelle étape', ordre=9)
        ChecklistEtapeModele.objects.filter(
            template=self.tpl, cle='e0').update(libelle='RENOMME')

    def _lire(self, inst):
        return [(i.cle, i.libelle) for i in ensure_checklist_items(inst)]

    def test_cloture_et_en_cours_figes_puis_neuf_recoit_le_modele(self):
        avant_clos = self._lire(self.cloture)
        avant_cours = self._lire(self.en_cours)
        self._modifier_le_modele()
        for _ in range(2):           # relecture idempotente
            self.assertEqual(self._lire(self.cloture), avant_clos)
            self.assertEqual(self._lire(self.en_cours), avant_cours)
        self.assertEqual(len(avant_clos), 8)
        neuf = self._lire(self.jamais_ouvert)
        self.assertEqual(len(neuf), 9)
        self.assertIn(('e0', 'RENOMME'), neuf)
        self.assertEqual(self._lire(self.jamais_ouvert), neuf)

    def test_cloture_jamais_ouvert_reste_vide(self):
        vide = Installation.objects.create(
            company=self.co, reference='CH-CLOS-VIDE',
            statut=Installation.Statut.CLOTURE)
        self.assertEqual(ensure_checklist_items(vide), [])
        self.assertEqual(ChantierChecklistItem.objects.filter(
            installation=vide).count(), 0)


class AmorcageEtapesDefautTests(TestCase):
    """ENF18 — `ChecklistEtapeModele.amorcer_etapes`, l'amorçage de
    `ensure_default_template` : idempotent, et jamais d'étape orpheline."""

    def test_amorcage_idempotent_et_template_nul_refuse(self):
        co = Company.objects.create(nom='ENF18', slug='enf18-checklist')
        tpl = ensure_default_template(co)
        self.assertEqual(tpl.etapes.count(), len(DEFAULT_CHECKLIST_ETAPES))
        ChecklistEtapeModele.amorcer_etapes(co, tpl, DEFAULT_CHECKLIST_ETAPES)
        self.assertEqual(tpl.etapes.count(), len(DEFAULT_CHECKLIST_ETAPES))
        with self.assertRaises(ValueError):
            ChecklistEtapeModele.amorcer_etapes(co, None, DEFAULT_CHECKLIST_ETAPES)
        self.assertFalse(ChecklistEtapeModele.objects.filter(
            company=co, template__isnull=True).exists())


#: ACAL597 — le sélecteur est importé DANS la fonction : on le patche à sa
#: SOURCE (classe de rouge CI n° 9).
CIBLE_POSE = 'apps.calepinage.selectors_chantier.points_de_controle_pose'
POINTS = {'calepinage_id': 1, 'omissions': [], 'points': [
    {'code': 'systeme_fixation', 'source': 'calepinage',
     'libelle': 'Système de fixation : Rail alu (RAIL-1)'},
    {'code': 'chaine', 'source': 'affectation',
     'libelle': 'Chaîne 1 : ' + 'module ' * 30},
    {'code': 'chaine', 'source': 'affectation', 'libelle': 'Chaîne 2'},
]}


class PointsDePoseCalepinageTests(TestCase):
    """ACAL597 — les points de pose du calepinage retenu suivent les étapes
    du modèle, à la PREMIÈRE matérialisation seulement."""

    def setUp(self):
        from decimal import Decimal

        from apps.crm.models import Client
        from apps.ventes.models import Devis

        self.co = Company.objects.create(nom='ACAL597', slug='acal597-co')
        tpl = ChecklistTemplate.objects.create(
            company=self.co, nom='Défaut', protege=True)
        for i in range(3):
            ChecklistEtapeModele.objects.create(
                company=self.co, template=tpl, cle=f'e{i}',
                libelle=f'Étape {i}', ordre=i)
        client = Client.objects.create(company=self.co, nom='Pose',
                                       email='acal597@example.invalid')
        devis = Devis.objects.create(company=self.co, reference='DEV-ACAL597',
                                     client=client, taux_tva=Decimal('20'))
        self.chantier = Installation.objects.create(
            company=self.co, reference='CH-ACAL597', devis=devis,
            statut=Installation.Statut.EN_COURS)

    def _items(self, points):
        from unittest import mock

        with mock.patch(CIBLE_POSE, return_value=points):
            return [(i.cle, i.libelle, i.ordre, i.capture_serie,
                     i.photo_obligatoire)
                    for i in ensure_checklist_items(self.chantier)]

    def test_items_cal_apres_les_etapes_du_modele(self):
        items = self._items(POINTS)
        self.assertEqual([i[0] for i in items],
                         ['e0', 'e1', 'e2', 'cal_systeme_fixation',
                          'cal_chaine_1', 'cal_chaine_2'])
        self.assertEqual([i[2] for i in items[3:]], [3, 4, 5])
        self.assertEqual(len(items[4][1]), 120)
        self.assertTrue(all(i[3] is False and i[4] is False
                            for i in items[3:]))

    def test_seconde_materialisation_sans_doublon(self):
        premiere = self._items(POINTS)
        self.assertEqual(self._items(POINTS), premiere)
        self.assertEqual(ChantierChecklistItem.objects.filter(
            installation=self.chantier).count(), 6)

    def test_calepinage_modifie_ensuite_checklist_inchangee(self):
        premiere = self._items(POINTS)
        autres = {'calepinage_id': 1, 'omissions': [], 'points': [
            {'code': 'chaine', 'source': 'affectation', 'libelle': 'Ch. 9'}]}
        self.assertEqual(self._items(autres), premiere)

    def test_sans_calepinage_retenu_checklist_d_aujourd_hui(self):
        self.assertEqual([i[0] for i in self._items(None)],
                         ['e0', 'e1', 'e2'])
