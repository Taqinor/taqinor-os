"""Tests AUD714 — `valider_bulletin` resynchronise le snapshot avant de figer.

Constat d'audit : `valider_bulletin` basculait le statut sans jamais rappeler
`generer_bulletin` (le seul point d'écriture du snapshot), mais recalculait
juste après un bulletin LIVE pour en extraire `net_avant_saisie` — la base
d'imputation des saisies-arrêt. Un `ElementVariable` ajouté entre `generer` et
`valider` était donc ABSENT du document figé remis au salarié tout en pesant
sur l'imputation réelle : deux vérités pour le même bulletin.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    BulletinPaie, ElementVariable, PeriodePaie, ProfilPaie,
)
from apps.paie.services import (
    creer_bulletin_annulation,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ResyncSnapshotValidationTests(TestCase):
    def setUp(self):
        self.co = make_company('aud714')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.periode_suivante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True)

    def test_element_ajoute_apres_generation_entre_dans_le_bulletin_fige(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        brut_avant = Decimal(bulletin.brut)
        self.assertFalse(bulletin.lignes.filter(libelle='Prime tardive').exists())

        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime tardive',
            quantite=Decimal('1'), montant=Decimal('1000'),
            source=ElementVariable.SOURCE_MANUEL)

        valider_bulletin(bulletin)
        bulletin.refresh_from_db()

        self.assertEqual(Decimal(bulletin.brut), brut_avant + Decimal('1000'))
        self.assertTrue(bulletin.lignes.filter(libelle='Prime tardive').exists())
        self.assertEqual(bulletin.statut, BulletinPaie.STATUT_VALIDE)

    def test_bulletin_inchange_reste_identique(self):
        """Non-régression : sans nouvel élément, aucun montant ne bouge."""
        bulletin = generer_bulletin(self.profil, self.periode)
        avant = {champ: Decimal(getattr(bulletin, champ))
                 for champ in BulletinPaie.SNAPSHOT_FIELDS}
        nb_lignes = bulletin.lignes.count()

        valider_bulletin(bulletin)
        bulletin.refresh_from_db()

        for champ, valeur in avant.items():
            self.assertEqual(Decimal(getattr(bulletin, champ)), valeur, champ)
        self.assertEqual(bulletin.lignes.count(), nb_lignes)

    def test_annulation_nest_jamais_rejouee_par_le_moteur(self):
        """Un bulletin d'annulation garde ses montants NÉGATIFS recopiés."""
        origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(origine)
        annulation = creer_bulletin_annulation(origine, self.periode_suivante)
        attendu = Decimal(annulation.net_a_payer)
        self.assertLess(attendu, Decimal('0'))

        valider_bulletin(annulation)
        annulation.refresh_from_db()
        self.assertEqual(Decimal(annulation.net_a_payer), attendu)
        self.assertEqual(
            annulation.type_bulletin, BulletinPaie.TYPE_ANNULATION)

    def test_periode_portant_deja_un_bulletin_du_profil_refuse_lextourne(self):
        """Deux bulletins d'un même profil dans une période : IMPOSSIBLE.

        ``BulletinPaie`` porte ``unique_together = ('periode', 'profil')``
        depuis PAIE17 (migration 0010) : la « cible ambiguë » que la garde de
        ``_resynchroniser_snapshot_avant_validation`` évite est inatteignable
        par la base — cette garde reste en défense en profondeur, mais le
        scénario ne peut PAS être construit. Ce qui se teste réellement ici,
        c'est que l'extourne le dise explicitement (``ValueError`` → 400) au
        lieu de lever une ``IntegrityError`` brute (500, et bloc
        ``transaction.atomic`` appelant cassé).
        """
        origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(origine)
        # La période suivante porte déjà le bulletin normal du même profil.
        normal = generer_bulletin(self.profil, self.periode_suivante)

        with self.assertRaises(ValueError):
            creer_bulletin_annulation(origine, self.periode_suivante)

        # L'extourne refusée n'a rien laissé derrière elle et le bulletin
        # normal de la période se valide normalement.
        self.assertEqual(
            BulletinPaie.objects.filter(
                periode=self.periode_suivante, profil=self.profil).count(), 1)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode_suivante, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime tardive',
            quantite=Decimal('1'), montant=Decimal('1000'),
            source=ElementVariable.SOURCE_MANUEL)
        valider_bulletin(normal)
        normal.refresh_from_db()
        self.assertEqual(normal.statut, BulletinPaie.STATUT_VALIDE)
