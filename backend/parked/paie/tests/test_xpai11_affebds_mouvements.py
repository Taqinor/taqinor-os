"""Tests XPAI11 — AFFEBDS + déclarations de mouvement CNSS.

Couvre : ``rapprocher_affebds`` parse le fichier importé et rapproche contre
les ``ProfilPaie`` (rapprochés/manquants/en trop), aucun écrit sur les
profils ; ``mouvements_cnss_periode`` liste les entrées (embauchés sans n°
CNSS) et les sorties (via ``rh.selectors.sortie_employe``, aucun écrit sur
rh).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    mouvements_cnss_periode,
    parser_affebds,
    rapprocher_affebds,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ParserAffebdsTests(TestCase):
    def test_parse_lignes_simples(self):
        contenu = "111;Ali\n222;Sara\n# commentaire\n\n333;Omar"
        lignes = parser_affebds(contenu)
        self.assertEqual(len(lignes), 3)
        self.assertEqual(lignes[0], {'numero_cnss': '111', 'nom': 'Ali'})

    def test_ignore_lignes_vides_et_sans_numero(self):
        contenu = ";SansNumero\n444;Valide\n"
        lignes = parser_affebds(contenu)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['numero_cnss'], '444')


class RapprocherAffebdsTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai11-affebds')

    def _profil(self, mat, numero_cnss, actif=True):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss=numero_cnss, actif=actif)

    def test_rapproche_numeros_correspondants(self):
        self._profil('A1', '111')
        rapport = rapprocher_affebds(self.co, '111;NomFichier')
        self.assertEqual(len(rapport['rapproches']), 1)
        self.assertEqual(len(rapport['manquants']), 0)
        self.assertEqual(len(rapport['en_trop']), 0)

    def test_manquant_dans_fichier_absent_des_profils(self):
        rapport = rapprocher_affebds(self.co, '999;Inconnu')
        self.assertEqual(len(rapport['manquants']), 1)
        self.assertEqual(rapport['manquants'][0]['numero_cnss'], '999')

    def test_en_trop_profil_sans_correspondance_fichier(self):
        self._profil('B1', '222')
        rapport = rapprocher_affebds(self.co, '')
        self.assertEqual(len(rapport['en_trop']), 1)
        self.assertEqual(rapport['en_trop'][0]['numero_cnss'], '222')

    def test_aucun_ecrit_sur_profils(self):
        profil = self._profil('C1', '333')
        rapprocher_affebds(self.co, '333;Nom')
        profil.refresh_from_db()
        self.assertEqual(profil.numero_cnss, '333')  # inchangé

    def test_isolation_tenant(self):
        autre = make_company('xpai11-affebds-autre')
        self._profil('D1', '444')
        rapport = rapprocher_affebds(autre, '444;Nom')
        # Le profil "444" appartient à une autre société -> pas rapproché.
        self.assertEqual(len(rapport['rapproches']), 0)
        self.assertEqual(len(rapport['manquants']), 1)


class MouvementsCnssPeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai11-mouv')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_entree_sans_numero_cnss(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='NomE1', prenom='P')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss='', actif=True)
        mouvements = mouvements_cnss_periode(self.periode)
        self.assertEqual(len(mouvements['entrees']), 1)

    def test_pas_entree_avec_numero_cnss(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='F1', nom='NomF1', prenom='P')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss='555', actif=True)
        mouvements = mouvements_cnss_periode(self.periode)
        self.assertEqual(len(mouvements['entrees']), 0)

    def test_sortie_detectee_via_selector_rh(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='G1', nom='NomG1', prenom='P',
            statut=DossierEmploye.Statut.SORTI,
            date_sortie=date(2026, 6, 15),
            motif_sortie=DossierEmploye.MotifSortie.DEMISSION)
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss='666', actif=False)
        mouvements = mouvements_cnss_periode(self.periode)
        self.assertEqual(len(mouvements['sorties']), 1)
        self.assertEqual(mouvements['sorties'][0]['motif_sortie'], 'demission')

    def test_sortie_hors_periode_non_listee(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='H1', nom='NomH1', prenom='P',
            statut=DossierEmploye.Statut.SORTI,
            date_sortie=date(2026, 5, 10))
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss='777', actif=False)
        mouvements = mouvements_cnss_periode(self.periode)
        self.assertEqual(len(mouvements['sorties']), 0)

    def test_aucun_ecrit_sur_rh(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='I1', nom='NomI1', prenom='P',
            date_sortie=date(2026, 6, 20))
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True,
            numero_cnss='888', actif=True)
        mouvements_cnss_periode(self.periode)
        dossier.refresh_from_db()
        self.assertEqual(dossier.date_sortie, date(2026, 6, 20))  # inchangé
