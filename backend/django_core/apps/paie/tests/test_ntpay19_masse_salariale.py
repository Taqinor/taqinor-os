"""Tests NTPAY19 — Rapport « Masse salariale » par période / service / site.

Couvre : le regroupement par département ET par site sur une fenêtre de 3
mois, la cohérence des totaux avec la somme des bulletins VALIDÉS, l'exclusion
des brouillons, le groupe « sans rattachement » (jamais d'affectation
inventée), l'effectif DISTINCT, l'export CSV téléchargeable, le rendu HTML et
l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.selectors import rapport_masse_salariale
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    rapport_masse_salariale as service_rapport,
    valider_bulletin,
)
from apps.rh.models import Departement, DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class MasseSalarialeTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay19')
        ensure_defaults(self.co)
        self.periodes = [
            PeriodePaie.objects.create(company=self.co, annee=2026, mois=mois)
            for mois in (4, 5, 6)
        ]
        self.technique = Departement.objects.create(
            company=self.co, nom='Technique')
        self.admin = Departement.objects.create(
            company=self.co, nom='Administration')

    def _profil(self, matricule, salaire, *, departement=None, zone=''):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P', departement=departement, zone_intervention=zone)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _valider_sur_toutes_les_periodes(self, profil):
        for periode in self.periodes:
            valider_bulletin(generer_bulletin(profil, periode))

    def test_groupement_par_departement_sur_trois_mois(self):
        technicien = self._profil('T1', Decimal('10000'),
                                  departement=self.technique)
        assistante = self._profil('A1', Decimal('7000'),
                                  departement=self.admin)
        self._valider_sur_toutes_les_periodes(technicien)
        self._valider_sur_toutes_les_periodes(assistante)

        rapport = rapport_masse_salariale(
            self.co, (2026, 4), (2026, 6), group_by='departement')
        self.assertEqual(rapport['nombre_periodes'], 3)
        self.assertEqual(rapport['nombre_bulletins'], 6)
        par_libelle = {g['libelle']: g for g in rapport['groupes']}
        self.assertIn('Technique', par_libelle)
        self.assertIn('Administration', par_libelle)
        # 3 mois × 10 000 de brut pour le technicien.
        self.assertEqual(par_libelle['Technique']['brut'],
                         Decimal('30000.00'))
        self.assertEqual(par_libelle['Technique']['effectif'], 1)
        self.assertEqual(
            rapport['totaux']['brut'],
            par_libelle['Technique']['brut']
            + par_libelle['Administration']['brut'])
        self.assertEqual(rapport['totaux']['effectif'], 2)
        # Coût total = brut + charges patronales, groupe par groupe.
        for groupe in rapport['groupes']:
            self.assertEqual(
                groupe['cout_total'],
                groupe['brut'] + groupe['charges_patronales'])
            self.assertGreater(groupe['charges_patronales'], 0)

    def test_fenetre_restreinte(self):
        profil = self._profil('T2', Decimal('10000'),
                              departement=self.technique)
        self._valider_sur_toutes_les_periodes(profil)
        rapport = rapport_masse_salariale(
            self.co, (2026, 5), (2026, 5), group_by='departement')
        self.assertEqual(rapport['nombre_bulletins'], 1)
        self.assertEqual(rapport['totaux']['brut'], Decimal('10000.00'))

    def test_groupement_par_site(self):
        casa = self._profil('S1', Decimal('9000'), zone='Casablanca')
        rabat = self._profil('S2', Decimal('8000'), zone='Rabat')
        sans = self._profil('S3', Decimal('6000'))
        for profil in (casa, rabat, sans):
            valider_bulletin(generer_bulletin(profil, self.periodes[0]))

        rapport = rapport_masse_salariale(
            self.co, (2026, 4), (2026, 4), group_by='site')
        par_libelle = {g['libelle']: g for g in rapport['groupes']}
        self.assertEqual(par_libelle['Casablanca']['brut'],
                         Decimal('9000.00'))
        self.assertEqual(par_libelle['Rabat']['brut'], Decimal('8000.00'))
        self.assertEqual(par_libelle['Sans site déclaré']['brut'],
                         Decimal('6000.00'))

    def test_sans_departement_n_invente_aucune_affectation(self):
        profil = self._profil('N1', Decimal('5000'))
        valider_bulletin(generer_bulletin(profil, self.periodes[0]))
        rapport = rapport_masse_salariale(
            self.co, (2026, 4), (2026, 4), group_by='departement')
        self.assertEqual(len(rapport['groupes']), 1)
        self.assertEqual(rapport['groupes'][0]['libelle'], 'Sans département')

    def test_brouillon_exclu(self):
        valide = self._profil('B1', Decimal('10000'),
                              departement=self.technique)
        brouillon = self._profil('B2', Decimal('99000'),
                                 departement=self.technique)
        valider_bulletin(generer_bulletin(valide, self.periodes[0]))
        generer_bulletin(brouillon, self.periodes[0])  # reste brouillon
        rapport = rapport_masse_salariale(
            self.co, (2026, 4), (2026, 4), group_by='departement')
        self.assertEqual(rapport['totaux']['brut'], Decimal('10000.00'))
        self.assertEqual(rapport['totaux']['effectif'], 1)

    def test_effectif_distinct_sur_plusieurs_mois(self):
        profil = self._profil('E1', Decimal('10000'),
                              departement=self.technique)
        self._valider_sur_toutes_les_periodes(profil)
        rapport = rapport_masse_salariale(
            self.co, (2026, 4), (2026, 6), group_by='departement')
        # 3 bulletins, mais UN seul salarié.
        self.assertEqual(rapport['nombre_bulletins'], 3)
        self.assertEqual(rapport['totaux']['effectif'], 1)

    def test_group_by_invalide(self):
        with self.assertRaises(ValueError):
            rapport_masse_salariale(
                self.co, (2026, 4), (2026, 6), group_by='lune')

    def test_point_d_entree_services_delegue_au_selecteur(self):
        profil = self._profil('D1', Decimal('10000'),
                              departement=self.technique)
        valider_bulletin(generer_bulletin(profil, self.periodes[0]))
        self.assertEqual(
            service_rapport(self.co, (2026, 4), (2026, 4)),
            rapport_masse_salariale(self.co, (2026, 4), (2026, 4)))

    def test_bornes_acceptent_chaine_et_periode(self):
        profil = self._profil('F1', Decimal('10000'),
                              departement=self.technique)
        valider_bulletin(generer_bulletin(profil, self.periodes[0]))
        par_chaine = rapport_masse_salariale(self.co, '2026-04', '2026-04')
        par_objet = rapport_masse_salariale(
            self.co, self.periodes[0], self.periodes[0])
        self.assertEqual(par_chaine['totaux'], par_objet['totaux'])

    def test_rendu_html(self):
        profil = self._profil('H1', Decimal('10000'),
                              departement=self.technique)
        self._valider_sur_toutes_les_periodes(profil)
        rapport = rapport_masse_salariale(self.co, (2026, 4), (2026, 6))
        html = builders.render_masse_salariale_html(
            rapport, builders.employeur_context(self.co),
            today=date(2026, 7, 5))
        self.assertIn('Masse salariale', html)
        self.assertIn('04/2026 → 06/2026', html)
        self.assertIn('Technique', html)
        self.assertIn(builders._fmt(rapport['totaux']['cout_total']), html)

    def test_isolation_societe(self):
        autre = make_company('ntpay19-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=4)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil_autre = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('80000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil_autre, periode_autre))

        profil = self._profil('I1', Decimal('10000'),
                              departement=self.technique)
        valider_bulletin(generer_bulletin(profil, self.periodes[0]))
        rapport = rapport_masse_salariale(self.co, (2026, 4), (2026, 4))
        self.assertEqual(rapport['totaux']['brut'], Decimal('10000.00'))


class MasseSalarialeApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay19-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay19-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=4)
        departement = Departement.objects.create(
            company=self.co, nom='Technique')
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P',
            departement=departement)
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, periode))
        self.url = '/api/django/paie/periodes/rapports/masse-salariale/'

    def test_json(self):
        rep = self.api.get(f'{self.url}?debut=2026-04&fin=2026-04')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['group_by'], 'departement')
        self.assertEqual(rep.data['totaux']['effectif'], 1)

    def test_sans_bornes_est_400(self):
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 400)

    def test_group_by_invalide_est_400(self):
        rep = self.api.get(f'{self.url}?debut=2026-04&fin=2026-04&group_by=lune')
        self.assertEqual(rep.status_code, 400)

    def test_export_csv(self):
        rep = self.api.get(
            f'{self.url}?debut=2026-04&fin=2026-04&export=csv')
        self.assertEqual(rep.status_code, 200)
        self.assertIn('text/csv', rep['Content-Type'])
        self.assertIn('attachment', rep['Content-Disposition'])
        contenu = rep.content.decode('utf-8')
        self.assertIn('Technique', contenu)
        self.assertIn('Total', contenu)
