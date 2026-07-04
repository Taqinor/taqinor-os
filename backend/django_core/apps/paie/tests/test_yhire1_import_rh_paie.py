"""Tests YHIRE1 — Câbler réellement l'import RH → paie des éléments variables.

L'ancien ``_elements_rh_du_dossier`` renvoyait toujours ``[]`` (stub). Couvre :
* les heures sup VALORISÉES (``rh.HeuresSupp``) sont importées en
  ``ElementVariable`` type HS, montant déjà majoré ;
* les absences VALIDÉES d'un ``TypeAbsence`` non rémunéré sont importées et
  réduisent le bulletin recalculé ; un congé rémunéré n'a AUCUN impact sur le
  net ;
* les primes ``PrimeAttribuee`` VALIDÉES du mois sont importées ;
* l'import est ré-exécutable (les éléments ``source=rh`` sont purgés/recréés,
  la saisie manuelle intacte).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    generer_bulletin,
    importer_elements_rh,
)
from apps.rh import services as rh_services
from apps.rh.models import (
    DemandeConge, DossierEmploye, HeuresSupp, PrimeAttribuee, TypeAbsence,
    TypePrime,
)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ImporterElementsRhTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire1')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='Nom', prenom='Prenom')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True,
            affilie_amo=True)

    def _hs(self, date_str, heures, **kw):
        hs = HeuresSupp(
            company=self.co, employe=self.dossier, date=date_str,
            heures_travaillees=Decimal(str(heures)), **kw)
        rh_services.appliquer_majoration(hs)
        hs.save()
        return hs

    def _type_absence(self, code, remunere):
        return TypeAbsence.objects.create(
            company=self.co, code=code, libelle=code, remunere=remunere)

    def _demande_conge(self, type_absence, date_debut, date_fin, jours):
        return DemandeConge.objects.create(
            company=self.co, employe=self.dossier, type_absence=type_absence,
            date_debut=date_debut, date_fin=date_fin, jours=Decimal(jours),
            statut=DemandeConge.Statut.VALIDEE)

    def _prime(self, annee, mois, montant, statut=PrimeAttribuee.Statut.VALIDEE):
        type_prime = TypePrime.objects.create(
            company=self.co, code='PR1', libelle='Prime test')
        return PrimeAttribuee.objects.create(
            company=self.co, type_prime=type_prime, employe=self.dossier,
            annee=annee, mois=mois, montant=Decimal(montant), statut=statut)

    def test_import_heures_sup(self):
        self._hs('2026-06-10', 10)  # seuil 8h -> 2h HS jour (25%)
        importes = importer_elements_rh(self.periode)
        self.assertGreater(importes, 0)
        els = ElementVariable.objects.filter(
            periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_HS, source=ElementVariable.SOURCE_RH)
        self.assertEqual(els.count(), 1)
        el = els.first()
        self.assertEqual(el.quantite, Decimal('2.00'))
        self.assertGreater(el.montant, Decimal('0'))
        self.assertEqual(el.categorie_hs, ElementVariable.HS_JOUR)

    def test_import_absence_non_remuneree_reduit_le_net(self):
        type_abs = self._type_absence('SS', remunere=False)
        self._demande_conge(type_abs, '2026-06-05', '2026-06-06', 2)
        importer_elements_rh(self.periode)
        el = ElementVariable.objects.get(
            periode=self.periode, type=ElementVariable.TYPE_ABSENCE,
            source=ElementVariable.SOURCE_RH)
        self.assertEqual(el.quantite, Decimal('2'))
        self.assertFalse(el.remunere)

        bulletin = generer_bulletin(self.profil, self.periode)
        bulletin_sans_absence = calculer_bulletin(
            ProfilPaie.objects.create(
                company=self.co,
                employe=DossierEmploye.objects.create(
                    company=self.co, matricule='E2', nom='N', prenom='P'),
                type_remuneration=ProfilPaie.TYPE_MENSUEL,
                salaire_base=Decimal('10000'), affilie_cnss=True,
                affilie_amo=True),
            self.periode)
        self.assertLess(bulletin.brut, bulletin_sans_absence['brut'])

    def test_import_absence_remuneree_aucun_impact_sur_net(self):
        type_abs = self._type_absence('CP', remunere=True)
        self._demande_conge(type_abs, '2026-06-05', '2026-06-06', 2)
        importer_elements_rh(self.periode)
        # Une absence rémunérée n'est PAS importée en ligne impactante :
        # aucun ElementVariable TYPE_ABSENCE source=rh n'est créé pour elle.
        self.assertFalse(
            ElementVariable.objects.filter(
                periode=self.periode, type=ElementVariable.TYPE_ABSENCE,
                source=ElementVariable.SOURCE_RH).exists())
        bulletin = generer_bulletin(self.profil, self.periode)
        self.assertEqual(bulletin.brut, Decimal('10000.00'))

    def test_import_prime_validee(self):
        self._prime(2026, 6, '500')
        importer_elements_rh(self.periode)
        el = ElementVariable.objects.get(
            periode=self.periode, type=ElementVariable.TYPE_PRIME,
            source=ElementVariable.SOURCE_RH)
        self.assertEqual(el.montant, Decimal('500'))

    def test_prime_proposee_non_importee(self):
        self._prime(2026, 6, '500', statut=PrimeAttribuee.Statut.PROPOSEE)
        importer_elements_rh(self.periode)
        self.assertFalse(
            ElementVariable.objects.filter(
                periode=self.periode, type=ElementVariable.TYPE_PRIME,
                source=ElementVariable.SOURCE_RH).exists())

    def test_reimport_ne_duplique_pas_et_preserve_saisie_manuelle(self):
        manuel = ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Manuel',
            montant=Decimal('100'), source=ElementVariable.SOURCE_MANUEL)
        self._prime(2026, 6, '500')
        importer_elements_rh(self.periode)
        importer_elements_rh(self.periode)  # ré-import
        rh_primes = ElementVariable.objects.filter(
            periode=self.periode, type=ElementVariable.TYPE_PRIME,
            source=ElementVariable.SOURCE_RH)
        self.assertEqual(rh_primes.count(), 1)
        manuel.refresh_from_db()
        self.assertEqual(manuel.montant, Decimal('100'))

    def test_profil_absent_ignore_sans_erreur(self):
        dossier_sans_profil = DossierEmploye.objects.create(
            company=self.co, matricule='E3', nom='N', prenom='P')
        self._prime(2026, 6, '500')
        # Ne doit pas lever : le dossier sans profil est simplement ignoré.
        importer_elements_rh(self.periode)
        self.assertFalse(
            ElementVariable.objects.filter(
                profil__employe=dossier_sans_profil).exists())
