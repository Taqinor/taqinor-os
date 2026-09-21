"""Tests ARC25 — Cohérence RIB paie ↔ RH (lecture seule, contrôle croisé).

Le ``ProfilPaie.rib`` (source de la ligne de virement PAIE30) est indépendant
du ``rh.DossierEmploye.rib`` (RIB de référence de la fiche RH) : rien ne les
rapprochait. ARC25 ajoute un CONTRÔLE croisé (jamais une fusion) au moment de la
génération de l'ordre de virement — divergence → notification interne,
concordance → silence.

Couvre :
* divergence (deux RIB non vides différents) → notification émise ;
* concordance → aucune notification ;
* robustesse au formatage : espaces ignorés (même compte → silence) ;
* côté manquant (RIB RH vide OU RIB paie vide) → PAS de faux positif ;
* profils hors virement (chèque/espèces) exclus du contrôle ;
* isolation société (aucune fuite cross-tenant) ;
* ``generer_ordre_virement`` n'est jamais bloqué par le contrôle (best-effort) ;
* le sélecteur ``rh.ribs_par_employe`` renvoie le RIB brut, scopé société ;
* aucune écriture sur ``rh`` ni fusion de RIB.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import OrdreVirement, PeriodePaie, ProfilPaie
from apps.paie.selectors import divergences_rib_periode
from apps.paie.services import (
    controler_coherence_rib,
    ensure_defaults,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye
from apps.rh.selectors import ribs_par_employe


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class CoherenceRibSelectorTests(TestCase):
    """Sélecteur ``divergences_rib_periode`` — décision pure, sans notification."""

    def setUp(self):
        self.co = make_company('arc25-sel')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, rib_paie, rib_rh,
                mode=ProfilPaie.MODE_PAIEMENT_VIREMENT):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            rib=rib_rh)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib=rib_paie,
            mode_paiement=mode, affilie_cnss=True, affilie_amo=True)

    def test_divergence_detectee(self):
        profil = self._profil('D1', rib_paie='RIB' + '1' * 20,
                              rib_rh='RIB' + '2' * 20)
        div = divergences_rib_periode(self.periode)
        self.assertEqual(len(div), 1)
        self.assertEqual(div[0]['profil_id'], profil.id)
        self.assertEqual(div[0]['employe_id'], profil.employe_id)
        self.assertEqual(div[0]['rib_paie'], 'RIB' + '1' * 20)
        self.assertEqual(div[0]['rib_rh'], 'RIB' + '2' * 20)

    def test_concordance_silence(self):
        self._profil('OK1', rib_paie='RIB' + '9' * 20,
                     rib_rh='RIB' + '9' * 20)
        self.assertEqual(divergences_rib_periode(self.periode), [])

    def test_espaces_ignores_concordance(self):
        # Même compte formaté différemment (espaces) → PAS une divergence.
        self._profil('SP1', rib_paie='011 780 0000012345678901 23',
                     rib_rh='0117800000012345678901 23')
        self.assertEqual(divergences_rib_periode(self.periode), [])

    def test_rib_rh_vide_pas_de_faux_positif(self):
        # Référence RH non renseignée → on ne compare pas à du vide.
        self._profil('RH0', rib_paie='RIB' + '1' * 20, rib_rh='')
        self.assertEqual(divergences_rib_periode(self.periode), [])

    def test_rib_paie_vide_pas_de_faux_positif(self):
        # RIB paie vide → déjà couvert par ZPAI2 (rib_manquant_virement), pas ici.
        self._profil('PA0', rib_paie='', rib_rh='RIB' + '2' * 20)
        self.assertEqual(divergences_rib_periode(self.periode), [])

    def test_mode_especes_exclu(self):
        # Un profil réglé hors virement n'entre pas dans le contrôle de virement.
        self._profil('ESP1', rib_paie='RIB' + '1' * 20, rib_rh='RIB' + '2' * 20,
                     mode=ProfilPaie.MODE_PAIEMENT_ESPECES)
        self.assertEqual(divergences_rib_periode(self.periode), [])

    def test_isolation_tenant(self):
        self._profil('T1', rib_paie='RIB' + '1' * 20, rib_rh='RIB' + '2' * 20)
        autre = make_company('arc25-sel-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        # La divergence de la 1ʳᵉ société ne remonte pas dans la 2ᵉ.
        self.assertEqual(divergences_rib_periode(periode_autre), [])


class ControlerCoherenceRibNotificationTests(TestCase):
    """``controler_coherence_rib`` — divergence → notification, sinon silence."""

    def setUp(self):
        self.co = make_company('arc25-notif')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, rib_paie, rib_rh):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            rib=rib_rh)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib=rib_paie,
            mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT,
            affilie_cnss=True, affilie_amo=True)

    def test_mismatch_emet_notification(self):
        self._profil('M1', rib_paie='RIB' + '1' * 20, rib_rh='RIB' + '2' * 20)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            div = controler_coherence_rib(self.periode)
        self.assertEqual(len(div), 1)
        notify_many.assert_called_once()
        args, kwargs = notify_many.call_args
        # Event scopé paie + société propagée côté serveur.
        self.assertEqual(args[1], 'paie_rib_divergence')
        self.assertEqual(kwargs.get('company'), self.co)

    def test_match_silence(self):
        self._profil('S1', rib_paie='RIB' + '7' * 20, rib_rh='RIB' + '7' * 20)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            div = controler_coherence_rib(self.periode)
        self.assertEqual(div, [])
        notify_many.assert_not_called()

    def test_notification_echec_non_bloquant(self):
        # Une notification qui lève ne doit jamais casser le contrôle.
        self._profil('E1', rib_paie='RIB' + '1' * 20, rib_rh='RIB' + '2' * 20)
        with mock.patch(
                'apps.notifications.services.notify_many',
                side_effect=RuntimeError('boom')):
            div = controler_coherence_rib(self.periode)
        # Les divergences restent renvoyées malgré l'échec d'envoi.
        self.assertEqual(len(div), 1)


class GenererOrdreVirementHookTests(TestCase):
    """Le contrôle est câblé dans ``generer_ordre_virement`` (best-effort)."""

    def setUp(self):
        self.co = make_company('arc25-hook')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat, rib_paie, rib_rh):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            rib=rib_rh)
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib=rib_paie,
            mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT,
            affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return profil

    def test_generation_invoque_le_controle_sur_divergence(self):
        self._bulletin_valide('H1', rib_paie='RIB' + '1' * 20,
                              rib_rh='RIB' + '2' * 20)
        with mock.patch(
                'apps.paie.services.controler_coherence_rib') as ctrl:
            ordre = generer_ordre_virement(self.periode)
        # L'ordre est bien produit ET le contrôle a été déclenché.
        self.assertEqual(ordre.statut, OrdreVirement.STATUT_BROUILLON)
        ctrl.assert_called_once_with(self.periode)

    def test_generation_non_bloquee_par_echec_controle(self):
        self._bulletin_valide('H2', rib_paie='RIB' + '1' * 20,
                              rib_rh='RIB' + '2' * 20)
        # Même si le contrôle lève, la génération de l'ordre aboutit.
        with mock.patch(
                'apps.paie.services.controler_coherence_rib',
                side_effect=RuntimeError('boom')):
            ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.nombre_lignes, 1)

    def test_notification_reelle_sur_divergence_via_generation(self):
        # Bout en bout : divergence → notify_many appelé au run de virement.
        self._bulletin_valide('H3', rib_paie='RIB' + '1' * 20,
                              rib_rh='RIB' + '2' * 20)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            generer_ordre_virement(self.periode)
        notify_many.assert_called_once()

    def test_concordance_via_generation_silence(self):
        self._bulletin_valide('H4', rib_paie='RIB' + '5' * 20,
                              rib_rh='RIB' + '5' * 20)
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            generer_ordre_virement(self.periode)
        notify_many.assert_not_called()


class RibsParEmployeSelectorTests(TestCase):
    """Sélecteur RH ``ribs_par_employe`` — lecture brute, scopée société."""

    def setUp(self):
        self.co = make_company('arc25-rh')

    def _dossier(self, mat, rib):
        return DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P', rib=rib)

    def test_renvoie_rib_brut(self):
        d1 = self._dossier('R1', '011 780 000')
        d2 = self._dossier('R2', '')
        out = ribs_par_employe(self.co, [d1.id, d2.id])
        # RIB brut (espaces conservés) ; un dossier sans RIB renvoie ''.
        self.assertEqual(out[d1.id], '011 780 000')
        self.assertEqual(out[d2.id], '')

    def test_scope_societe(self):
        d1 = self._dossier('S1', 'RIB1')
        autre = make_company('arc25-rh-autre')
        d_autre = DossierEmploye.objects.create(
            company=autre, matricule='X', nom='X', prenom='Y', rib='RIB2')
        out = ribs_par_employe(self.co, [d1.id, d_autre.id])
        # Le dossier d'une autre société est absent (pas de fuite cross-tenant).
        self.assertIn(d1.id, out)
        self.assertNotIn(d_autre.id, out)

    def test_arguments_vides(self):
        self.assertEqual(ribs_par_employe(self.co, []), {})
        self.assertEqual(ribs_par_employe(None, [1]), {})
