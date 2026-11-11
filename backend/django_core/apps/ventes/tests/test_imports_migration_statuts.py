"""AANA70 — migration de devis et de factures (NTMIG10) : un statut source non
reconnu est une LIGNE D'ERREUR nommant la valeur, jamais un « brouillon » muet.

Un statut vide reste « brouillon » (absence de statut) ; les valeurs connues
(`accepté`, `paid`) gardent leur correspondance.

Test-du-test : remettre le repli ``BROUILLON`` dans ``_statut_devis`` /
``_statut_facture`` ⇒ ``test_statut_inconnu_refuse`` échoue.
"""
from django.test import TestCase

from apps.ventes.domain.imports import creer_devis_import, creer_facture_import
from apps.ventes.models import Devis, Facture
from apps.ventes.tests.test_l_niv_niveau import make_client, make_company


class StatutsMigrationTests(TestCase):

    def setUp(self):
        self.company = make_company('aana70')
        self.client_obj = make_client(self.company)
        self.base = {'client_email': self.client_obj.email}
        # ADRG62 — émettre/payer à l'import exige le droit du geste : le
        # rôle LIVRÉ Directeur les porte (palier administrateur + encaisser).
        self.directeur = self._compte('Directeur')

    def _compte(self, nom):
        from django.contrib.auth import get_user_model
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        role = Role.objects.create(
            company=self.company, nom=nom, est_systeme=True,
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)[nom]))
        return get_user_model().objects.create_user(
            username=f'adrg62-{nom.replace(" ", "-").lower()}', password='x',
            company=self.company, role_legacy='normal', role=role)

    def _ligne(self, statut):
        return {**self.base, 'statut': statut}

    def test_statut_inconnu_refuse(self):
        avant = (Devis.objects.count(), Facture.objects.count())
        for creer in (creer_devis_import, creer_facture_import):
            etat, motif, objet = creer(self.company, self._ligne('won_partial'))
            self.assertEqual(etat, 'erreur')
            self.assertIn('won_partial', motif)
            self.assertIsNone(objet)
        self.assertEqual((Devis.objects.count(), Facture.objects.count()), avant)

    def test_statut_vide_reste_brouillon(self):
        _, _, devis = creer_devis_import(self.company, self._ligne(''))
        _, _, facture = creer_facture_import(self.company, self._ligne(None))
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)

    def test_statuts_connus_inchanges(self):
        _, _, devis = creer_devis_import(self.company, self._ligne('accepté'))
        _, _, facture = creer_facture_import(
            self.company, self._ligne('paid'), user=self.directeur)
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)

    def test_facture_importee_serie_configuree_et_echeance(self):
        """AARG17 — une facture migrée « posted » prend le préfixe du profil,
        une échéance appliquée et un ``facture_emise`` ; « paid » : numéro et
        échéance sans événement ; brouillon : référence provisoire.
        Mutant : remettre le préfixe 'FAC' ⇒ échec."""
        from datetime import timedelta

        from core.events import facture_emise

        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.doc_prefixes = {'facture': 'FA'}
        prof.save(update_fields=['doc_prefixes'])
        recus = []

        def _capter(sender, instance, **kwargs):
            recus.append(instance.pk)
        facture_emise.connect(_capter, weak=False, dispatch_uid='aarg17')
        self.addCleanup(facture_emise.disconnect, dispatch_uid='aarg17')

        _, _, emise = creer_facture_import(
            self.company, {**self._ligne('posted'), 'reference_source': 'OD-12'},
            user=self.directeur)
        _, _, payee = creer_facture_import(
            self.company, self._ligne('paid'), user=self.directeur)
        _, _, brouillon = creer_facture_import(self.company, self._ligne('draft'))

        for facture in (emise, payee):
            relue = Facture.objects.get(pk=facture.pk)
            self.assertTrue(relue.reference.startswith('FA-'), relue.reference)
            self.assertEqual(
                relue.date_echeance, relue.date_emission + timedelta(days=30))
        self.assertNotEqual(emise.reference, payee.reference)
        self.assertEqual(recus, [emise.pk])
        self.assertTrue(
            Facture.objects.get(pk=brouillon.pk).reference.startswith('BROUILLON-'))

    def test_statut_importe_borne_par_le_droit_du_geste(self):
        """ADRG62 (C-ADRG-001) — hors brouillon, le statut importé exige le
        droit du geste qui le pose : Admin Ventes (sans ``encaisser``) ne crée
        pas d'« émise » ; Commercial (``encaisser`` sans palier administrateur)
        ne crée pas de « payée » ; Commercial « émise », Directeur « payée » et
        Admin Ventes « brouillon » passent. Aucune facture pour les refus.
        Mutant : retirer l'appel à ``peut_encaisser`` ⇒ échec."""
        admin_ventes = self._compte('Admin Ventes')
        commercial = self._compte('Commercial')
        avant = Facture.objects.filter(company=self.company).count()
        for user, statut, motif in ((admin_ventes, 'emise', 'Encaisser'),
                                    (commercial, 'paid', "réservé à l'administrateur")):
            etat, raison, objet = creer_facture_import(
                self.company, self._ligne(statut), user=user)
            self.assertEqual((etat, objet), ('erreur', None), (statut, raison))
            self.assertIn(motif, raison)
        self.assertEqual(Facture.objects.filter(company=self.company).count(), avant)
        crees = [creer_facture_import(self.company, self._ligne(s), user=u)
                 for u, s in ((commercial, 'emise'), (self.directeur, 'paid'),
                              (admin_ventes, 'draft'))]
        self.assertEqual([c[0] for c in crees], ['cree'] * 3, crees)
        self.assertFalse(crees[0][2].reference.startswith('BROUILLON-'))
        self.assertFalse(crees[1][2].reference.startswith('BROUILLON-'))
        self.assertTrue(crees[2][2].reference.startswith('BROUILLON-'))
