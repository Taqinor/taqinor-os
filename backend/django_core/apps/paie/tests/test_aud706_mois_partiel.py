"""Tests AUD706 — mois partiel : proratisation embauche/sortie + jours CNSS.

Constat d'audit : ``calculer_salaire_base_periode`` ne recevait jamais
``date_embauche``/``date_sortie`` (seules les absences saisies réduisaient les
jours), et ``declaration_cnss`` déclarait ``jours_declares=26`` en dur pour
CHAQUE bulletin. Un salarié embauché le 20/06 était donc payé le mois entier
ET déclaré présent tout le mois.

Ancre arithmétique de la tâche : salaire 8 000 MAD mensuel,
``jours_travail_mensuel=26``, embauche le 20/06 → 19 jours du mois hors
contrat → 8 000 × (26 − 19) / 26 = 8 000 × 7 / 26 ≈ 2 153,85 MAD, et
``jours_declares`` ≈ 7 (au lieu de 26).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_salaire_base_periode,
    declaration_cnss,
    ensure_defaults,
    generer_bulletin,
    jours_declares_cnss,
    jours_hors_contrat_periode,
    jours_payes_periode,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class MoisPartielTests(TestCase):
    def setUp(self):
        self.co = make_company('aud706')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, *, date_embauche=None, date_sortie=None,
                salaire=Decimal('8000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P', date_embauche=date_embauche, date_sortie=date_sortie)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, jours_travail_mensuel=26,
            affilie_cnss=True, affilie_amo=True,
            numero_cnss='123456789')

    # ── Salaire de base proraté ────────────────────────────────────────────

    def test_embauche_en_cours_de_mois_prorate(self):
        """Embauché le 20/06 sans absence saisie → 8000 × 7/26, pas 8000."""
        profil = self._profil('A1', date_embauche='2026-06-20')
        montant = calculer_salaire_base_periode(profil, self.periode)
        self.assertEqual(montant, Decimal('2153.85'))
        self.assertNotEqual(montant, Decimal('8000.00'))

    def test_sortie_en_cours_de_mois_prorate(self):
        """Sorti le 10/06 → 20 jours du mois hors contrat (26 − 20 = 6)."""
        profil = self._profil('A2', date_sortie='2026-06-10')
        self.assertEqual(jours_hors_contrat_periode(profil, self.periode),
                         Decimal('20'))
        # 8 000 × 6 / 26 = 1 846,153… → arrondi maison au centime.
        montant = calculer_salaire_base_periode(profil, self.periode)
        self.assertEqual(montant, Decimal('1846.15'))

    def test_mois_complet_inchange(self):
        """Non-régression : embauche antérieure au mois → plein salaire."""
        profil = self._profil('A3', date_embauche='2020-01-01')
        self.assertEqual(jours_hors_contrat_periode(profil, self.periode),
                         Decimal('0'))
        self.assertEqual(calculer_salaire_base_periode(profil, self.periode),
                         Decimal('8000.00'))

    def test_sans_date_embauche_inchange(self):
        """Non-régression : dossier sans date d'embauche → aucune proration."""
        profil = self._profil('A4')
        self.assertEqual(calculer_salaire_base_periode(profil, self.periode),
                         Decimal('8000.00'))

    def test_absence_et_hors_contrat_se_cumulent(self):
        """Embauche le 20/06 + 1 jour d'absence non rémunérée → 26−19−1 = 6."""
        profil = self._profil('A5', date_embauche='2026-06-20')
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=profil,
            type=ElementVariable.TYPE_ABSENCE, libelle='Absence',
            quantite=Decimal('1'), montant=Decimal('0'),
            source=ElementVariable.SOURCE_MANUEL)
        self.assertEqual(jours_payes_periode(profil, self.periode),
                         Decimal('6'))

    def test_jours_payes_borne_a_zero(self):
        """Embauche APRÈS la fin du mois → 0 jour payé, jamais un négatif."""
        profil = self._profil('A6', date_embauche='2026-07-15')
        self.assertEqual(jours_payes_periode(profil, self.periode),
                         Decimal('0'))
        self.assertEqual(calculer_salaire_base_periode(profil, self.periode),
                         Decimal('0.00'))

    # ── Jours déclarés à la CNSS ───────────────────────────────────────────

    def test_declaration_cnss_derive_les_jours(self):
        """Le BDS ne déclare plus 26 en dur : 7 jours pour l'embauche du 20."""
        profil = self._profil('B1', date_embauche='2026-06-20')
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)

        self.assertEqual(jours_declares_cnss(profil, self.periode), 7)
        decl = declaration_cnss(self.periode)
        self.assertEqual(len(decl['lignes']), 1)
        self.assertEqual(decl['lignes'][0]['jours_declares'], 7)

    def test_declaration_cnss_mois_complet_reste_a_26(self):
        """Non-régression : un mois complet reste déclaré à la norme (26)."""
        profil = self._profil('B2', date_embauche='2019-03-01')
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)

        decl = declaration_cnss(self.periode)
        self.assertEqual(decl['lignes'][0]['jours_declares'], 26)
