"""CIQ624 — consignes de sécurité C&I et option « sécurité signée avant
démarrage ».
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations.field_capture import (
    CONSIGNES_CI, ensure_consignes_ci, ensure_safety_signoff,
    seed_safety_slots)
from apps.installations.models import (
    Installation, Intervention, SafetyChecklistSlot)
from apps.installations.services import (
    TransitionRefusee, changer_statut_intervention)
from apps.parametres.models import CompanyProfile
from authentication.models import Company

User = get_user_model()


class ConsignesCITest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ624', slug='ciq624-co')
        self.user = User.objects.create_user(
            username='ciq624', password='x', role_legacy='responsable',
            company=self.company)
        self._n = 0

    def _intervention(self, type_installation='industriel', niveau=None):
        self._n += 10
        inst = Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ624-{self._n}',
            type_installation=type_installation, niveau_tension=niveau)
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            statut=Intervention.Statut.PRETE)

    def _cles(self, intervention):
        return {it.cle for it in ensure_safety_signoff(intervention)
                .items.all()}

    def test_quatre_consignes_plus_huit_communes_une_seule_fois(self):
        seed_safety_slots(self.company)
        self.assertEqual(SafetyChecklistSlot.objects.filter(
            company=self.company).count(), 4)
        ensure_safety_signoff(self._intervention('industriel', 'bt'))
        ensure_safety_signoff(self._intervention('industriel', 'bt'))
        communes = [c for c, _l, n in CONSIGNES_CI if n is None]
        self.assertEqual(len(communes), 8)
        self.assertEqual(SafetyChecklistSlot.objects.filter(
            company=self.company, cle__in=communes).count(), 8)
        self.assertEqual(ensure_consignes_ci(self.company), 0)

    def test_supprimee_ou_desactivee_jamais_recreee(self):
        ensure_consignes_ci(self.company)
        SafetyChecklistSlot.objects.filter(
            company=self.company, cle='ci_permis_feu').delete()
        SafetyChecklistSlot.objects.filter(
            company=self.company, cle='ci_extincteur').update(actif=False)
        self.assertEqual(ensure_consignes_ci(self.company), 0)
        self.assertFalse(SafetyChecklistSlot.objects.filter(
            company=self.company, cle='ci_permis_feu').exists())

    def test_consigne_mt_seulement_sur_chantier_mt(self):
        self.assertIn('ci_consignation_poste_mt',
                      self._cles(self._intervention('industriel', 'mt')))
        bt = self._cles(self._intervention('industriel', 'bt'))
        self.assertNotIn('ci_consignation_poste_mt', bt)
        self.assertIn('ci_hauteur', bt)

    def test_residentiel_sans_consignes_ci(self):
        cles = self._cles(self._intervention('residentiel'))
        self.assertFalse(any(c.startswith('ci_') for c in cles))

    def test_aucun_chiffre_ni_article(self):
        for _cle, libelle, _niveau in CONSIGNES_CI:
            self.assertIsNone(re.search(r'\d|art\.', libelle), libelle)

    def _reglage(self, valeur):
        profil = CompanyProfile.get(self.company)
        profil.securite_obligatoire_avant_demarrage = valeur
        profil.save()

    def test_reglage_vrai_signoff_non_signe_refuse(self):
        self._reglage(True)
        intervention = self._intervention('industriel', 'bt')
        with self.assertRaises(TransitionRefusee) as ctx:
            changer_statut_intervention(
                intervention, Intervention.Statut.SUR_SITE, self.user)
        message = ctx.exception.raisons[0]
        self.assertIn('Points non cochés', message)
        self.assertIn('Extincteur à portée', message)
        signoff = ensure_safety_signoff(intervention)
        signoff.signe = True
        signoff.save(update_fields=['signe'])
        recu = changer_statut_intervention(
            intervention, Intervention.Statut.SUR_SITE, self.user)
        self.assertEqual(recu['nouveau'], 'sur_site')

    def test_reglage_faux_comportement_actuel(self):
        self._reglage(False)
        intervention = self._intervention('industriel', 'bt')
        recu = changer_statut_intervention(
            intervention, Intervention.Statut.SUR_SITE, self.user)
        self.assertEqual(recu['nouveau'], 'sur_site')
