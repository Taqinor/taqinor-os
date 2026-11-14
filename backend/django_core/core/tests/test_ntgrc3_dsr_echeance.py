"""NTGRC3 — échéance légale 30 jours + garde de transition sur les DSR.

``core`` reste FONDATION : ce module n'importe AUCUNE app métier.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest
from core.views import DataSubjectRequestViewSet

User = get_user_model()


class EcheanceLegaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 SA', slug='ntgrc3')

    def test_echeance_posee_a_la_creation(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        self.assertIsNotNone(demande.date_echeance)
        ecart = (demande.date_echeance - demande.created_at).total_seconds()
        self.assertAlmostEqual(ecart, 30 * 24 * 3600, delta=5)

    def test_echeance_jamais_recalculee(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        posee = demande.date_echeance
        demande.subject_identifier = 'autre@b.ma'
        demande.save()
        demande.refresh_from_db()
        self.assertEqual(demande.date_echeance, posee)

    def test_demande_en_retard_remonte_dans_le_selector(self):
        passe = timezone.now() - timezone.timedelta(days=1)
        en_retard = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='retard@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe)
        DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a_temps@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        resultats = list(dsr.demandes_en_retard(self.company))
        self.assertEqual([d.pk for d in resultats], [en_retard.pk])

    def test_demande_close_nest_plus_en_retard(self):
        passe = timezone.now() - timezone.timedelta(days=1)
        DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='close@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe,
            statut=DataSubjectRequest.STATUT_TRAITEE)
        self.assertEqual(list(dsr.demandes_en_retard(self.company)), [])

    def test_selector_borne_a_la_societe(self):
        autre = Company.objects.create(nom='NTGRC3 B', slug='ntgrc3-b')
        passe = timezone.now() - timezone.timedelta(days=1)
        DataSubjectRequest.objects.create(
            company=autre, subject_identifier='x@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe)
        self.assertEqual(list(dsr.demandes_en_retard(self.company)), [])


class MachineAEtatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 M', slug='ntgrc3-m')

    def _demande(self, **kw):
        kw.setdefault('kind', DataSubjectRequest.KIND_ACCESS)
        return DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma', **kw)

    def test_recue_passe_en_verification(self):
        demande = self._demande()
        dsr.prendre_en_charge(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut,
                         DataSubjectRequest.STATUT_EN_VERIFICATION)

    def test_prise_en_charge_deux_fois_est_interdite(self):
        demande = self._demande()
        dsr.prendre_en_charge(demande)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.prendre_en_charge(demande)

    def test_demande_traitee_ne_se_retraite_pas(self):
        demande = self._demande(statut=DataSubjectRequest.STATUT_TRAITEE)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.traiter_demande(demande)

    def test_effacement_en_echec_partiel_reste_relancable(self):
        """ASOC65 (D-ASOC-6) — une source d'effacement en échec ⇒ « partielle »,
        relancée la source réparée ⇒ « traitee » ; un accès en échec reste
        « traitee » (inchangé)."""
        sauvegarde = dict(dsr._PROVIDERS)
        etat = {'casse': True}

        def _erase(co, subj):
            if etat['casse']:
                raise RuntimeError('stockage indisponible')
            return 2

        def _boom(co, subj):
            raise RuntimeError('export KO')

        try:
            dsr._PROVIDERS.clear()
            dsr.register_dsr_provider('crm', erase=lambda co, subj: 1)
            dsr.register_dsr_provider('stock', export=_boom, erase=_erase)
            demande = self._demande(kind=DataSubjectRequest.KIND_ERASURE)
            dsr.traiter_demande(demande)
            demande.refresh_from_db()
            self.assertEqual(demande.statut, DataSubjectRequest.STATUT_PARTIELLE)
            self.assertIn('erreur', demande.resultat['stock'])
            self.assertEqual(demande.resultat['crm'], 1)
            self.assertIn(demande, list(dsr.demandes_en_retard(
                self.company, now=demande.date_echeance
                + timezone.timedelta(days=1))))
            etat['casse'] = False
            dsr.traiter_demande(demande)
            demande.refresh_from_db()
            self.assertEqual(demande.statut, DataSubjectRequest.STATUT_TRAITEE)
            self.assertIsNotNone(demande.traitee_le)
            acces = DataSubjectRequest.objects.create(
                company=self.company, subject_identifier='a@b.ma',
                kind=DataSubjectRequest.KIND_ACCESS)
            dsr.traiter_demande(acces)
            self.assertEqual(acces.statut, DataSubjectRequest.STATUT_TRAITEE)
        finally:
            dsr._PROVIDERS.clear()
            dsr._PROVIDERS.update(sauvegarde)

    def test_effacement_supprime_l_export_des_demandes_d_acces(self):
        """ASUP14 (D-ASUP-4) — l'effacement traité par le Directeur
        (``dsr_traiter``) supprime l'export stocké des demandes d'accès et de
        rectification de la même personne ; statut et date restent ; l'autre
        personne intacte ; aucune demande supprimée."""
        from importlib import import_module

        from django.apps import apps as django_apps
        registre = import_module('apps.roles.permissions_registre')
        directeur = User.objects.create_user(
            username='asup14_directeur', password='x', company=self.company,
            role=django_apps.get_model('roles', 'Role').objects.create(
                company=self.company, nom='ASUP14 Directeur',
                permissions=list(registre.DIRECTEUR_PERMISSIONS)))
        sauvegarde = dict(dsr._PROVIDERS)
        try:
            dsr._PROVIDERS.clear()
            dsr.register_dsr_provider(
                'crm', export=lambda co, subj: {'identite': subj}, erase=lambda co, subj: 1)
            acces = self._demande()
            rectif = self._demande(kind=DataSubjectRequest.KIND_RECTIFICATION)
            autre = DataSubjectRequest.objects.create(
                company=self.company, subject_identifier='autre@b.ma',
                kind=DataSubjectRequest.KIND_ACCESS)
            for demande in (acces, rectif, autre):
                dsr.traiter_demande(demande)
            avant = {d.pk: (d.statut, d.traitee_le) for d in (acces, rectif, autre)}
            effacement = self._demande(kind=DataSubjectRequest.KIND_ERASURE)
            requete = APIRequestFactory().post(f'/dsr-requests/{effacement.pk}/traiter/')
            force_authenticate(requete, user=directeur)
            reponse = DataSubjectRequestViewSet.as_view({'post': 'traiter'})(requete, pk=effacement.pk)
            self.assertEqual(reponse.status_code, 200, reponse.data)
            for demande in (acces, rectif):
                demande.refresh_from_db()
                self.assertEqual((demande.statut, demande.traitee_le), avant[demande.pk])
                self.assertEqual(set(demande.resultat), {'export_supprime_le', 'motif'})
                self.assertEqual(demande.resultat['motif'], 'effacement')
            autre.refresh_from_db()
            self.assertEqual(autre.resultat, {'crm': {'identite': 'autre@b.ma'}, 'core': {'consentements': []}})
            self.assertEqual(DataSubjectRequest.objects.filter(company=self.company).count(), 4)
        finally:
            dsr._PROVIDERS.clear()
            dsr._PROVIDERS.update(sauvegarde)

    def test_echec_differe_les_sources_d_ordre_superieur(self):
        """ASOC65 — ventes en échec ⇒ le CRM (erase_order=100, porteur de
        l'identité) n'est PAS lancé : « partielle », puis la relance efface
        ventes ET le CRM ⇒ « traitee »."""
        sauvegarde = dict(dsr._PROVIDERS)
        etat = {'casse': True, 'crm': 0}

        def _ventes(co, subj):
            if etat['casse']:
                raise RuntimeError('ventes indisponible')
            return 3

        def _crm(co, subj):
            etat['crm'] += 1
            return 1

        try:
            dsr._PROVIDERS.clear()
            dsr.register_dsr_provider('crm', erase=_crm, erase_order=100)
            dsr.register_dsr_provider('ventes', erase=_ventes)
            demande = self._demande(kind=DataSubjectRequest.KIND_ERASURE)
            dsr.traiter_demande(demande)
            demande.refresh_from_db()
            self.assertEqual(demande.statut, DataSubjectRequest.STATUT_PARTIELLE)
            self.assertEqual(etat['crm'], 0)
            self.assertEqual(demande.resultat['crm'],
                             {'erreur': 'différé : source précédente en échec'})
            etat['casse'] = False
            dsr.traiter_demande(demande)
            demande.refresh_from_db()
            self.assertEqual(demande.statut, DataSubjectRequest.STATUT_TRAITEE)
            self.assertEqual((etat['crm'], demande.resultat['ventes']), (1, 3))
        finally:
            dsr._PROVIDERS.clear()
            dsr._PROVIDERS.update(sauvegarde)

    def test_refus_est_terminal(self):
        demande = self._demande()
        dsr.refuser_demande(demande, motif='Identité non prouvée.')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_REFUSEE)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.prendre_en_charge(demande)

    def test_message_derreur_nomme_les_deux_statuts(self):
        demande = self._demande(statut=DataSubjectRequest.STATUT_TRAITEE)
        with self.assertRaises(dsr.TransitionInterdite) as ctx:
            dsr.prendre_en_charge(demande)
        message = str(ctx.exception)
        self.assertIn('Traitée', message)
        self.assertIn("En vérification d'identité", message)


class EndpointTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 E', slug='ntgrc3-e')
        cls.admin = User.objects.create_user(
            username='ntgrc3_admin', password='x', role_legacy='admin',
            company=cls.company)

    def _post(self, demande, action_name):
        factory = APIRequestFactory()
        request = factory.post(f'/dsr-requests/{demande.pk}/{action_name}/')
        force_authenticate(request, user=self.admin)
        view = DataSubjectRequestViewSet.as_view(
            {'post': action_name.replace('-', '_')})
        return view(request, pk=demande.pk)

    def test_prendre_en_charge_puis_transition_illegale_renvoie_409(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        r = self._post(demande, 'prendre-en-charge')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'],
                         DataSubjectRequest.STATUT_EN_VERIFICATION)

        r2 = self._post(demande, 'prendre-en-charge')
        # ERR-ENF11-FUZZ-CORE — conflit d'état : 409, plus 400.
        self.assertEqual(r2.status_code, 409, r2.data)
        # Corps documenté `{detail}` (lu par l'écran Confidentialité).
        self.assertIn('Transition impossible', r2.data['detail'])

    def test_lechance_est_exposee_en_lecture_seule(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        r = self._post(demande, 'prendre-en-charge')
        self.assertIn('date_echeance', r.data)
        from core.serializers import DataSubjectRequestSerializer
        self.assertTrue(
            DataSubjectRequestSerializer().fields['date_echeance'].read_only)
