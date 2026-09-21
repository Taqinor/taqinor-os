"""Tests WIR89 — Cohérence n° CNSS paie ↔ RH (lecture seule, contrôle croisé).

Symétrique de ``test_arc25_coherence_rib.py`` (ARC25) : le ``ProfilPaie.
numero_cnss`` (source du bordereau de déclaration CNSS, PAIE31) est
indépendant du ``rh.DossierEmploye.cnss`` (n° CNSS de référence de la fiche
RH) : rien ne les rapprochait. WIR89 ajoute un CONTRÔLE croisé (jamais une
fusion) — divergence → notification interne, concordance → silence.

Couvre :
* divergence (deux n° CNSS non vides différents) → notification émise ;
* concordance → aucune notification ;
* robustesse au formatage : espaces ignorés (même numéro → silence) ;
* côté manquant (n° CNSS RH vide OU n° CNSS paie vide) → PAS de faux positif ;
* profils non affiliés CNSS exclus du contrôle ;
* isolation société (aucune fuite cross-tenant) ;
* ``declaration_cnss`` n'est jamais bloquée par le contrôle (best-effort) ;
* le sélecteur ``rh.cnss_par_employe`` renvoie le n° CNSS brut, scopé société ;
* aucune écriture sur ``rh`` ni fusion de numéro.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.selectors import divergences_cnss_periode
from apps.paie.services import (
    controler_coherence_cnss,
    declaration_cnss,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye
from apps.rh.selectors import cnss_par_employe


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class DivergenceCnssSelectorTests(TestCase):
    """Sélecteur ``divergences_cnss_periode`` — décision pure, sans notification."""

    def setUp(self):
        self.co = make_company('wir89-sel')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, cnss_paie, cnss_rh, affilie=True):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            cnss=cnss_rh)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=cnss_paie,
            affilie_cnss=affilie, affilie_amo=True)

    def test_divergence_detectee(self):
        profil = self._profil('D1', cnss_paie='111' * 5, cnss_rh='222' * 5)
        div = divergences_cnss_periode(self.periode)
        self.assertEqual(len(div), 1)
        self.assertEqual(div[0]['profil_id'], profil.id)
        self.assertEqual(div[0]['employe_id'], profil.employe_id)
        self.assertEqual(div[0]['cnss_paie'], '111' * 5)
        self.assertEqual(div[0]['cnss_rh'], '222' * 5)

    def test_concordance_silence(self):
        self._profil('OK1', cnss_paie='999' * 5, cnss_rh='999' * 5)
        self.assertEqual(divergences_cnss_periode(self.periode), [])

    def test_espaces_ignores_concordance(self):
        self._profil('SP1', cnss_paie='11 22 33', cnss_rh='112233')
        self.assertEqual(divergences_cnss_periode(self.periode), [])

    def test_cnss_rh_vide_pas_de_faux_positif(self):
        self._profil('RH0', cnss_paie='111' * 5, cnss_rh='')
        self.assertEqual(divergences_cnss_periode(self.periode), [])

    def test_cnss_paie_vide_pas_de_faux_positif(self):
        self._profil('PA0', cnss_paie='', cnss_rh='222' * 5)
        self.assertEqual(divergences_cnss_periode(self.periode), [])

    def test_non_affilie_cnss_exclu(self):
        self._profil('NA1', cnss_paie='111' * 5, cnss_rh='222' * 5,
                     affilie=False)
        self.assertEqual(divergences_cnss_periode(self.periode), [])

    def test_isolation_tenant(self):
        self._profil('T1', cnss_paie='111' * 5, cnss_rh='222' * 5)
        autre = make_company('wir89-sel-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        self.assertEqual(divergences_cnss_periode(periode_autre), [])


class ControlerCoherenceCnssNotificationTests(TestCase):
    """``controler_coherence_cnss`` — divergence → notification, sinon silence."""

    def setUp(self):
        self.co = make_company('wir89-notif')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, cnss_paie, cnss_rh):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            cnss=cnss_rh)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=cnss_paie,
            affilie_cnss=True, affilie_amo=True)

    def test_mismatch_emet_notification(self):
        self._profil('M1', cnss_paie='111' * 5, cnss_rh='222' * 5)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            div = controler_coherence_cnss(self.periode)
        self.assertEqual(len(div), 1)
        notify_many.assert_called_once()
        args, kwargs = notify_many.call_args
        self.assertEqual(args[1], 'paie_cnss_divergence')
        self.assertEqual(kwargs.get('company'), self.co)

    def test_match_silence(self):
        self._profil('S1', cnss_paie='777' * 5, cnss_rh='777' * 5)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            div = controler_coherence_cnss(self.periode)
        self.assertEqual(div, [])
        notify_many.assert_not_called()

    def test_notification_echec_non_bloquant(self):
        self._profil('E1', cnss_paie='111' * 5, cnss_rh='222' * 5)
        with mock.patch(
                'apps.notifications.services.notify_many',
                side_effect=RuntimeError('boom')):
            div = controler_coherence_cnss(self.periode)
        self.assertEqual(len(div), 1)


class DeclarationCnssHookTests(TestCase):
    """Le contrôle est câblé dans ``declaration_cnss`` (best-effort)."""

    def setUp(self):
        self.co = make_company('wir89-hook')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat, cnss_paie, cnss_rh):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            cnss=cnss_rh)
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=cnss_paie,
            affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return profil

    def test_declaration_invoque_le_controle_sur_divergence(self):
        self._bulletin_valide('H1', cnss_paie='111' * 5, cnss_rh='222' * 5)
        with mock.patch(
                'apps.paie.services.controler_coherence_cnss') as ctrl:
            resultat = declaration_cnss(self.periode)
        self.assertEqual(resultat['nombre_salaries'], 1)
        ctrl.assert_called_once_with(self.periode)

    def test_declaration_non_bloquee_par_echec_controle(self):
        self._bulletin_valide('H2', cnss_paie='111' * 5, cnss_rh='222' * 5)
        with mock.patch(
                'apps.paie.services.controler_coherence_cnss',
                side_effect=RuntimeError('boom')):
            resultat = declaration_cnss(self.periode)
        self.assertEqual(resultat['nombre_salaries'], 1)

    def test_notification_reelle_sur_divergence_via_declaration(self):
        self._bulletin_valide('H3', cnss_paie='111' * 5, cnss_rh='222' * 5)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            declaration_cnss(self.periode)
        notify_many.assert_called_once()

    def test_concordance_via_declaration_silence(self):
        self._bulletin_valide('H4', cnss_paie='555' * 5, cnss_rh='555' * 5)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            declaration_cnss(self.periode)
        notify_many.assert_not_called()


class CnssParEmployeSelectorTests(TestCase):
    """Sélecteur RH ``cnss_par_employe`` — lecture brute, scopée société."""

    def setUp(self):
        self.co = make_company('wir89-rh')

    def _dossier(self, mat, cnss):
        return DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P', cnss=cnss)

    def test_renvoie_cnss_brut(self):
        d1 = self._dossier('R1', '111 22 3')
        d2 = self._dossier('R2', '')
        out = cnss_par_employe(self.co, [d1.id, d2.id])
        self.assertEqual(out[d1.id], '111 22 3')
        self.assertEqual(out[d2.id], '')

    def test_scope_societe(self):
        d1 = self._dossier('S1', 'CNSS1')
        autre = make_company('wir89-rh-autre')
        d_autre = DossierEmploye.objects.create(
            company=autre, matricule='X', nom='X', prenom='Y', cnss='CNSS2')
        out = cnss_par_employe(self.co, [d1.id, d_autre.id])
        self.assertIn(d1.id, out)
        self.assertNotIn(d_autre.id, out)

    def test_arguments_vides(self):
        self.assertEqual(cnss_par_employe(self.co, []), {})
        self.assertEqual(cnss_par_employe(None, [1]), {})
