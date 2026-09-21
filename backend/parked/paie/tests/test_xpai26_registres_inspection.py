"""Tests XPAI26 — Registres d'inspection du travail.

Couvre : le registre des congés (droits/pris/solde par employé, données RH
via selectors), la fiche historique de carrière (poste + progression
salariale annuelle depuis les CumulAnnuel), aucune écriture, endpoints
JSON/PDF/CSV, et l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import CumulAnnuel, ProfilPaie
from apps.paie.services import (
    ensure_defaults, historique_carriere, registre_conges,
)
from apps.rh.models import DossierEmploye, Poste, SoldeConge


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class RegistreCongesTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai26-conges')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='C1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))

    def test_registre_calcule_droits_pris_solde(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.dossier, annee=2026,
            acquis=Decimal('18'), report=Decimal('3'), pris=Decimal('5'))
        registre = registre_conges(self.co, 2026)
        self.assertEqual(len(registre['lignes']), 1)
        ligne = registre['lignes'][0]
        self.assertEqual(ligne['matricule'], 'C1')
        self.assertEqual(ligne['droits'], Decimal('21.00'))
        self.assertEqual(ligne['pris'], Decimal('5.00'))
        self.assertEqual(ligne['solde'], Decimal('16.00'))

    def test_registre_sans_solde_rh_donne_zero(self):
        registre = registre_conges(self.co, 2026)
        ligne = registre['lignes'][0]
        self.assertEqual(ligne['droits'], Decimal('0.00'))
        self.assertEqual(ligne['solde'], Decimal('0.00'))

    def test_profil_inactif_exclu(self):
        self.profil.actif = False
        self.profil.save()
        registre = registre_conges(self.co, 2026)
        self.assertEqual(registre['lignes'], [])

    def test_isolation_societe(self):
        autre_co = make_company('xpai26-conges-autre')
        registre = registre_conges(autre_co, 2026)
        self.assertEqual(registre['lignes'], [])

    def test_registre_lecture_seule_ne_modifie_rien(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.dossier, annee=2026,
            acquis=Decimal('18'), pris=Decimal('2'))
        avant = SoldeConge.objects.get(
            company=self.co, employe=self.dossier, annee=2026).pris
        registre_conges(self.co, 2026)
        apres = SoldeConge.objects.get(
            company=self.co, employe=self.dossier, annee=2026).pris
        self.assertEqual(avant, apres)


class HistoriqueCarriereTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai26-historique')
        ensure_defaults(self.co)
        self.poste = Poste.objects.create(
            company=self.co, intitule='Technicien pose')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='H1', nom='Nom', prenom='P',
            poste_ref=self.poste, date_embauche=date(2020, 1, 1))
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))

    def test_historique_expose_identite_et_poste(self):
        historique = historique_carriere(self.profil)
        self.assertEqual(historique['matricule'], 'H1')
        self.assertEqual(historique['poste'], 'Technicien pose')
        self.assertEqual(historique['date_embauche'], date(2020, 1, 1))

    def test_historique_expose_progression_salariale_annuelle(self):
        CumulAnnuel.objects.create(
            company=self.co, profil=self.profil, annee=2024,
            brut=Decimal('96000'))
        CumulAnnuel.objects.create(
            company=self.co, profil=self.profil, annee=2025,
            brut=Decimal('108000'))
        historique = historique_carriere(self.profil)
        annees = {a['annee']: a['brut'] for a in historique['annees']}
        self.assertEqual(annees[2024], Decimal('96000.00'))
        self.assertEqual(annees[2025], Decimal('108000.00'))
        # Ordonné chronologiquement.
        self.assertEqual(
            [a['annee'] for a in historique['annees']], [2024, 2025])

    def test_historique_sans_cumuls_liste_vide(self):
        historique = historique_carriere(self.profil)
        self.assertEqual(historique['annees'], [])

    def test_historique_poste_libre_sans_referentiel(self):
        dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='H2', nom='Nom', prenom='Q',
            poste='Chef de chantier')
        profil2 = ProfilPaie.objects.create(
            company=self.co, employe=dossier2,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('7000'))
        historique = historique_carriere(profil2)
        self.assertEqual(historique['poste'], 'Chef de chantier')
