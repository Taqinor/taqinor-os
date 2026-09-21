"""Tests NTPAY7 — `PaysPaie` + dispatcher de calcul par pays.

Couvre : NON-RÉGRESSION AU CENTIME (profil sans pays et profil ``pays = MA``
donnent EXACTEMENT le même bulletin que ``calculer_bulletin_ma``), l'ossature
du dispatcher (registre ``MOTEURS_PAYS``), le refus explicite d'un pays
désactivé ou sans moteur livré, le seed idempotent du pays MA et l'isolation
société.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from authentication.models import Company
from apps.paie import services as paie_services
from apps.paie.models import ElementVariable, PaysPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    MOTEURS_PAYS,
    calculer_bulletin,
    calculer_bulletin_ma,
    ensure_defaults,
    ensure_pays_paie_standard,
    moteur_du_profil,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class DispatcherPaysTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay7')
        ensure_defaults(self.co)
        ensure_pays_paie_standard(self.co)
        self.pays_ma = PaysPaie.objects.get(
            company=self.co, code_iso=PaysPaie.CODE_MA)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, *, pays=None):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier, pays=pays,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('11000'),
            affilie_cnss=True, affilie_amo=True)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime',
            montant=Decimal('850'))
        return profil

    @staticmethod
    def _montants(resultat):
        return {
            cle: valeur for cle, valeur in resultat.items()
            if isinstance(valeur, Decimal)
        }

    def test_profil_sans_pays_identique_au_moteur_ma(self):
        profil = self._profil('S1')
        via_dispatcher = calculer_bulletin(profil, self.periode)
        direct = calculer_bulletin_ma(profil, self.periode)
        self.assertEqual(self._montants(via_dispatcher),
                         self._montants(direct))
        self.assertGreater(via_dispatcher['net_a_payer'], 0)

    def test_profil_pays_ma_identique_a_profil_sans_pays(self):
        sans = calculer_bulletin(self._profil('S2'), self.periode)
        avec = calculer_bulletin(
            self._profil('S3', pays=self.pays_ma), self.periode)
        self.assertEqual(self._montants(sans), self._montants(avec))

    def test_registre_expose_le_moteur_ma(self):
        self.assertIs(MOTEURS_PAYS['MA'], calculer_bulletin_ma)
        self.assertEqual(
            moteur_du_profil(self._profil('S4')), calculer_bulletin_ma)
        self.assertEqual(
            moteur_du_profil(self._profil('S5', pays=self.pays_ma)),
            calculer_bulletin_ma)

    def test_dispatcher_route_vers_le_moteur_du_pays(self):
        """L'ossature route bien : un moteur factice enregistré est appelé."""
        pays_test = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_FR, libelle='France',
            devise='EUR', moteur='TEST')
        appels = []

        def _moteur_test(profil, periode, personnes_a_charge=0):
            appels.append((profil.id, periode.id, personnes_a_charge))
            return {'net_a_payer': Decimal('42.00')}

        MOTEURS_PAYS['TEST'] = _moteur_test
        try:
            profil = self._profil('S6', pays=pays_test)
            resultat = calculer_bulletin(profil, self.periode, 2)
        finally:
            MOTEURS_PAYS.pop('TEST', None)
        self.assertEqual(resultat['net_a_payer'], Decimal('42.00'))
        self.assertEqual(appels, [(profil.id, self.periode.id, 2)])

    def test_pays_desactive_refuse_en_nommant_le_pays(self):
        pays = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_SN, libelle='Sénégal',
            devise='XOF', actif=False)
        profil = self._profil('S7', pays=pays)
        with self.assertRaises(DjangoValidationError) as ctx:
            calculer_bulletin(profil, self.periode)
        self.assertIn('pays', ctx.exception.message_dict)
        self.assertIn('Sénégal', ' '.join(ctx.exception.message_dict['pays']))

    def test_pays_sans_moteur_livre_refuse(self):
        pays = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_CI,
            libelle="Côte d'Ivoire", devise='XOF')
        profil = self._profil('S8', pays=pays)
        with self.assertRaises(DjangoValidationError) as ctx:
            calculer_bulletin(profil, self.periode)
        self.assertIn('CI', ' '.join(ctx.exception.message_dict['pays']))

    def test_packs_gates_absents_du_registre(self):
        """Les packs FR/SN/CI sont gatés fondateur : jamais enregistrés d'office.

        Quand un pack est livré ET activé par le fondateur (NTPAY9/10/11), ce
        test doit être mis à jour EN MÊME TEMPS que cette décision — c'est
        exactement le garde-fou voulu.
        """
        self.assertIn('MA', MOTEURS_PAYS)
        for code in ('FR', 'SN', 'CI'):
            self.assertNotIn(code, MOTEURS_PAYS)


class SeedPaysTests(TestCase):
    def test_seed_idempotent_et_ne_seme_que_le_maroc(self):
        co = make_company('ntpay7-seed')
        self.assertEqual(ensure_pays_paie_standard(co)['pays'], 1)
        self.assertEqual(ensure_pays_paie_standard(co)['pays'], 0)
        pays = PaysPaie.objects.filter(company=co)
        self.assertEqual([p.code_iso for p in pays], ['MA'])
        self.assertEqual(pays.first().devise, 'MAD')

    def test_seed_ne_touche_pas_une_ligne_editee(self):
        co = make_company('ntpay7-edit')
        ensure_pays_paie_standard(co)
        PaysPaie.objects.filter(company=co).update(libelle='Royaume du Maroc')
        ensure_pays_paie_standard(co)
        self.assertEqual(
            PaysPaie.objects.get(company=co).libelle, 'Royaume du Maroc')

    def test_isolation_societe(self):
        co_a = make_company('ntpay7-iso-a')
        co_b = make_company('ntpay7-iso-b')
        ensure_pays_paie_standard(co_a)
        self.assertFalse(PaysPaie.objects.filter(company=co_b).exists())
        self.assertEqual(
            paie_services.ensure_pays_paie_standard(co_b)['pays'], 1)
