"""AUD705 — le n° CNSS du salarié ne part plus silencieusement vide.

ÉTAT AVANT LE FIX. ``bulletin_context`` imprime ``profil.numero_cnss or ''``
sans erreur ni blocage si le numéro est vide, et le numéro existe en DEUX
exemplaires indépendants — ``ProfilPaie.numero_cnss`` et
``rh.DossierEmploye.cnss``, tous deux ``blank=True``. Un salarié affilié CNSS
dont la fiche RH porte le numéro pouvait donc être payé, déclaré et recevoir
son bulletin avec un n° CNSS VIDE, sans la moindre alerte.

CE QUI EXISTAIT DÉJÀ (vérifié, non refait ici) : WIR89 compare bien les deux
numéros — ``apps.paie.selectors.divergences_cnss_periode`` +
``services.controler_coherence_cnss`` émettent une notification interne sur
DIVERGENCE, et ``avertissements_periode`` portait déjà ``cnss_manquant``.
Restaient ouverts : l'OMISSION (numéro connu côté RH, absent côté paie) ne
bloquait rien, et la DIVERGENCE ne remontait qu'au moment de la déclaration —
donc après le départ des bulletins.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    NumeroCnssManquant,
    avertissements_periode,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


class NumeroCnssValidationTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud705', nom='AUD705')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, *, cnss_rh='', cnss_paie='',
                affilie_cnss=True):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P', cnss=cnss_rh)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=cnss_paie,
            affilie_cnss=affilie_cnss, affilie_amo=True)

    def test_numero_connu_en_rh_et_absent_en_paie_bloque(self):
        """LE CŒUR DU CONSTAT : l'information existe, elle est ignorée."""
        profil = self._profil('C1', cnss_rh='123456789', cnss_paie='')
        bulletin = generer_bulletin(profil, self.periode)
        with self.assertRaises(NumeroCnssManquant):
            valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'brouillon')

    def test_numero_repris_en_paie_valide_normalement(self):
        profil = self._profil('C2', cnss_rh='123456789',
                              cnss_paie='123456789')
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'valide')

    def test_profil_non_affilie_cnss_non_concerne(self):
        profil = self._profil('C3', cnss_rh='123456789', cnss_paie='',
                              affilie_cnss=False)
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'valide')

    def test_aucun_numero_nulle_part_ne_bloque_pas(self):
        """Non-régression : une société qui n'a pas encore saisi ses numéros
        n'est pas empêchée de payer — c'est déjà un avertissement bloquant du
        panneau, pas un refus rétroactif."""
        profil = self._profil('C4', cnss_rh='', cnss_paie='')
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'valide')

    def test_divergence_ne_bloque_pas_mais_est_signalee_avant_de_payer(self):
        """WIR89 : un humain tranche. Mais l'écart remonte AVANT la paie."""
        profil = self._profil('C5', cnss_rh='111111111',
                              cnss_paie='222222222')
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'valide')

        types = [a['type'] for a in avertissements_periode(self.periode)]
        self.assertIn('cnss_divergent', types)
        divergent = next(a for a in avertissements_periode(self.periode)
                         if a['type'] == 'cnss_divergent')
        self.assertEqual(divergent['gravite'], 'avertissement')
        self.assertEqual(divergent['employe_id'], profil.employe_id)
        # Donnée sensible : aucun numéro dans le message (doctrine WIR89).
        self.assertNotIn('111111111', divergent['message'])
        self.assertNotIn('222222222', divergent['message'])

    def test_concordance_ne_signale_rien(self):
        self._profil('C6', cnss_rh='999888777', cnss_paie='999888777')
        types = [a['type'] for a in avertissements_periode(self.periode)]
        self.assertNotIn('cnss_divergent', types)
