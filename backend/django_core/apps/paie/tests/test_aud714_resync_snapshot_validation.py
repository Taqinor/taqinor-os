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

    def test_periode_avec_deux_bulletins_du_meme_profil_nest_pas_rejouee(self):
        """Cible ambiguë (deux bulletins du profil dans la période) → no-op.

        ``generer_bulletin`` vise par (période, profil) : rejouer le moteur
        écraserait l'AUTRE bulletin au lieu de resynchroniser celui-ci. La
        garde préfère alors ne rien rejouer — limitation assumée et couverte.
        """
        origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(origine)
        # La période suivante porte DEUX bulletins du même profil : un normal
        # en brouillon + l'extourne du bulletin de juin.
        normal = generer_bulletin(self.profil, self.periode_suivante)
        annulation = creer_bulletin_annulation(origine, self.periode_suivante)
        net_annulation = Decimal(annulation.net_a_payer)
        brut_normal = Decimal(normal.brut)

        ElementVariable.objects.create(
            company=self.co, periode=self.periode_suivante, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime tardive',
            quantite=Decimal('1'), montant=Decimal('1000'),
            source=ElementVariable.SOURCE_MANUEL)

        valider_bulletin(normal)
        normal.refresh_from_db()
        annulation.refresh_from_db()

        # Aucun rejeu : l'extourne est intacte et le normal garde son snapshot.
        self.assertEqual(Decimal(annulation.net_a_payer), net_annulation)
        self.assertEqual(Decimal(normal.brut), brut_normal)
        self.assertEqual(normal.statut, BulletinPaie.STATUT_VALIDE)
