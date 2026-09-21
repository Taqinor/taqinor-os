"""Tests NTPAY1 — Re-calcul rétroactif d'un barème/paramètre versionné.

Couvre :
* ``detecter_periodes_impactees`` — seules les périodes FIGÉES (validée /
  clôturée) dont le mois est couvert par la nouvelle ``date_effet`` remontent ;
* ``appliquer_rappel_retroactif`` — écart par salarié = (IR nouveau − IR
  retenu) sur les mois régularisés, porté en bulletin de type ``rappel`` sur la
  période courante, les bulletins d'origine restant INTACTS ;
* le sens NÉGATIF (trop-perçu) comme le sens positif (rappel dû) ;
* l'isolation multi-société ;
* les gardes (période cible clôturée, bulletin déjà présent sur la cible).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import BaremeIR, BulletinPaie, PeriodePaie, ProfilPaie, TrancheIR
from apps.paie.services import (
    appliquer_rappel_retroactif,
    detecter_periodes_impactees,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class RappelRetroactifBase(TestCase):
    """Socle : une société, un salarié, trois mois validés + un mois courant."""

    def setUp(self):
        self.co = make_company('ntpay1')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='R1', nom='Alaoui', prenom='Samir')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'),
            affilie_cnss=True, affilie_amo=True)
        self.mois_figes = []
        for mois in (3, 4, 5):
            periode = PeriodePaie.objects.create(
                company=self.co, annee=2026, mois=mois)
            bulletin = generer_bulletin(self.profil, periode)
            valider_bulletin(bulletin)
            periode.statut = PeriodePaie.STATUT_VALIDEE
            periode.save(update_fields=['statut'])
            self.mois_figes.append((periode, bulletin))
        self.periode_courante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _publier_bareme(self, date_effet, taux_derniere_tranche):
        """Publie un barème IR daté de ``date_effet`` (tranches simplifiées).

        Les bornes reprennent le barème semé par ``ensure_defaults`` ; seul le
        TAUX de la tranche haute bouge — c'est le levier qui fait diverger l'IR.
        """
        bareme = BaremeIR.objects.create(
            company=self.co, libelle='Barème IR révisé',
            date_effet=date_effet)
        source = (
            BaremeIR.objects
            .filter(company=self.co, date_effet=date(2026, 1, 1))
            .first()
        )
        for tranche in source.tranches.all().order_by('ordre'):
            taux = tranche.taux
            if tranche.borne_max is None or tranche.borne_max >= Decimal(
                    '15000'):
                taux = taux_derniere_tranche
            TrancheIR.objects.create(
                company=self.co, bareme=bareme,
                borne_min=tranche.borne_min, borne_max=tranche.borne_max,
                taux=taux, somme_a_deduire=tranche.somme_a_deduire,
                ordre=tranche.ordre)
        return bareme


class DetectionTests(RappelRetroactifBase):
    def test_detecte_les_trois_mois_figes(self):
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('40'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        self.assertEqual([p.mois for p in impactees], [3, 4, 5])

    def test_ignore_les_mois_anterieurs_a_la_date_effet(self):
        bareme = self._publier_bareme(date(2026, 5, 1), Decimal('40'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        self.assertEqual([p.mois for p in impactees], [5])

    def test_ignore_une_periode_brouillon(self):
        bareme = self._publier_bareme(date(2026, 2, 1), Decimal('40'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        self.assertNotIn(self.periode_courante.id, [p.id for p in impactees])

    def test_exige_exactement_un_jeu(self):
        with self.assertRaises(ValueError):
            detecter_periodes_impactees(self.co)

    def test_isolation_societe(self):
        autre = make_company('ntpay1-autre')
        ensure_defaults(autre)
        bareme_autre = BaremeIR.objects.create(
            company=autre, libelle='X', date_effet=date(2026, 3, 1))
        with self.assertRaises(ValueError):
            detecter_periodes_impactees(self.co, bareme=bareme_autre)
        # Les périodes de la société courante ne remontent jamais pour l'autre.
        self.assertEqual(
            detecter_periodes_impactees(autre, bareme=bareme_autre), [])


class RappelRetroactifTests(RappelRetroactifBase):
    def _ir_recalcule(self, bulletin):
        from apps.paie.services import calculer_bulletin
        return calculer_bulletin(
            bulletin.profil, bulletin.periode,
            bulletin.personnes_a_charge)['ir']

    def test_rappel_du_egale_la_somme_des_ecarts_ir(self):
        ir_retenus = [b.ir for _, b in self.mois_figes]
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('45'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        attendu = sum(
            (self._ir_recalcule(b) - ir
             for (_, b), ir in zip(self.mois_figes, ir_retenus)),
            Decimal('0'))
        self.assertGreater(attendu, 0)  # taux relevé → IR dû en plus

        resultat = appliquer_rappel_retroactif(
            self.periode_courante, impactees, motif='Barème révisé')
        self.assertEqual(resultat['nombre_salaries'], 1)
        rappel = resultat['bulletins'][0]
        self.assertEqual(rappel.type_bulletin, BulletinPaie.TYPE_RAPPEL)
        self.assertEqual(rappel.periode_id, self.periode_courante.id)
        self.assertEqual(rappel.ir, attendu)
        self.assertEqual(resultat['total_ecart_ir'], attendu)
        # Une ligne RAPPEL-RETRO par mois régularisé.
        self.assertEqual(rappel.lignes.count(), 3)
        self.assertTrue(
            all(ligne.code == 'RAPPEL-RETRO' for ligne in rappel.lignes.all()))

    def test_trop_percu_donne_un_ecart_negatif(self):
        ir_retenus = [b.ir for _, b in self.mois_figes]
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('20'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        attendu = sum(
            (self._ir_recalcule(b) - ir
             for (_, b), ir in zip(self.mois_figes, ir_retenus)),
            Decimal('0'))
        self.assertLess(attendu, 0)  # taux abaissé → trop-perçu à restituer
        resultat = appliquer_rappel_retroactif(
            self.periode_courante, impactees)
        rappel = resultat['bulletins'][0]
        self.assertEqual(rappel.ir, attendu)
        self.assertGreater(rappel.net_a_payer, 0)  # moins d'IR ⇒ net rendu

    def test_bulletins_origine_intacts(self):
        avant = [(b.id, b.ir, b.net_a_payer, b.statut)
                 for _, b in self.mois_figes]
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('45'))
        appliquer_rappel_retroactif(
            self.periode_courante,
            detecter_periodes_impactees(self.co, bareme=bareme))
        for bulletin_id, ir, net, statut in avant:
            fige = BulletinPaie.objects.get(pk=bulletin_id)
            self.assertEqual(fige.ir, ir)
            self.assertEqual(fige.net_a_payer, net)
            self.assertEqual(fige.statut, statut)

    def test_cumul_annuel_integre_le_rappel(self):
        from apps.paie.services import recalculer_cumul_annuel

        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('45'))
        resultat = appliquer_rappel_retroactif(
            self.periode_courante,
            detecter_periodes_impactees(self.co, bareme=bareme))
        rappel = resultat['bulletins'][0]
        cumul_avant = recalculer_cumul_annuel(self.profil, 2026)
        ir_avant = cumul_avant.ir
        valider_bulletin(rappel)
        cumul_apres = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(cumul_apres.ir, ir_avant + rappel.ir)

    def test_refuse_periode_cible_cloturee(self):
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('45'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        self.periode_courante.statut = PeriodePaie.STATUT_CLOTUREE
        self.periode_courante.save(update_fields=['statut'])
        with self.assertRaises(DjangoValidationError):
            appliquer_rappel_retroactif(self.periode_courante, impactees)

    def test_refuse_si_un_bulletin_existe_deja_sur_la_cible(self):
        generer_bulletin(self.profil, self.periode_courante)
        bareme = self._publier_bareme(date(2026, 3, 1), Decimal('45'))
        impactees = detecter_periodes_impactees(self.co, bareme=bareme)
        with self.assertRaises(DjangoValidationError) as ctx:
            appliquer_rappel_retroactif(self.periode_courante, impactees)
        self.assertIn('Alaoui', ' '.join(ctx.exception.messages))

    def test_refuse_une_liste_vide(self):
        with self.assertRaises(DjangoValidationError):
            appliquer_rappel_retroactif(self.periode_courante, [])
