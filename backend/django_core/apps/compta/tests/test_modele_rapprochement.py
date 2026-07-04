"""XACC4 — Modèles de rapprochement (règles de contrepartie automatique).

Couvre :

* une ligne « AGIOS » matche la règle et l'écriture 6147x/5141 est créée et
  pointée ;
* le verrou de période est respecté ;
* CRUD ``modeles-rapprochement/`` company-scopé ;
* la TVA optionnelle ventile correctement HT/TVA sur la contrepartie ;
* idempotence (rejouer sur une ligne déjà pointée ne recrée rien).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, LigneReleve, ModeleRapprochement,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ModeleRapprochementServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc4', 'XACC4 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('-150'))
        self.modele = ModeleRapprochement.objects.create(
            company=self.co, libelle='Agios bancaires',
            motif='AGIOS', compte_contrepartie=services.get_compte(self.co, '6147'))

    def test_ligne_agios_matche_et_poste_ecriture_pointee(self):
        ligne = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 10),
            libelle='FRAIS AGIOS JANVIER', montant=Decimal('-45'))
        ecr = services.appliquer_modele_rapprochement(ligne)
        self.assertTrue(ecr.est_equilibree)
        contrepartie = ecr.lignes.get(compte__numero='6147')
        banque = ecr.lignes.get(compte__numero='5141')
        self.assertEqual(contrepartie.debit, Decimal('45'))
        self.assertEqual(banque.credit, Decimal('45'))
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, LigneReleve.Statut.RAPPROCHEE)

    def test_montant_fixe_impose_le_montant(self):
        self.modele.montant_fixe = Decimal('30')
        self.modele.save(update_fields=['montant_fixe'])
        ligne = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 12),
            libelle='AGIOS DIVERS', montant=Decimal('-99'))
        ecr = services.appliquer_modele_rapprochement(ligne)
        self.assertEqual(ecr.total_debit, Decimal('30'))

    def test_taux_tva_ventile_ht_et_tva(self):
        self.modele.taux_tva = Decimal('20')
        self.modele.save(update_fields=['taux_tva'])
        ligne = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 15),
            libelle='AGIOS TTC', montant=Decimal('-120'))
        ecr = services.appliquer_modele_rapprochement(ligne)
        self.assertTrue(ecr.est_equilibree)
        contrepartie = ecr.lignes.get(compte__numero='6147')
        tva = ecr.lignes.get(compte__numero='34552')
        self.assertEqual(contrepartie.debit, Decimal('100.00'))
        self.assertEqual(tva.debit, Decimal('20.00'))

    def test_aucune_regle_ne_correspond_leve_erreur(self):
        ligne = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 18),
            libelle='VIREMENT SANS RAPPORT', montant=Decimal('-10'))
        with self.assertRaises(ValidationError):
            services.appliquer_modele_rapprochement(ligne)

    def test_verrou_de_periode_respecte(self):
        periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier 2026')
        services.cloturer_periode(periode)
        ligne = LigneReleve.objects.create(
            company=self.co, rapprochement=self.rap,
            date_operation=date(2026, 1, 20), libelle='AGIOS BLOQUE',
            montant=Decimal('-20'))
        with self.assertRaises(ValidationError):
            services.appliquer_modele_rapprochement(ligne)

    def test_idempotent_ligne_deja_pointee(self):
        ligne = services.ajouter_ligne_releve(
            self.rap, date_operation=date(2026, 1, 22),
            libelle='AGIOS REJOUE', montant=Decimal('-15'))
        a = services.appliquer_modele_rapprochement(ligne)
        ligne.refresh_from_db()
        b = services.appliquer_modele_rapprochement(ligne)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='modele_rapprochement').count(), 1)

    def test_priorite_choisit_la_regle_la_plus_prioritaire(self):
        ModeleRapprochement.objects.create(
            company=self.co, libelle='Générique', motif='A',
            compte_contrepartie=services.get_compte(self.co, '6111'),
            priorite=200)
        modele = services.modele_correspondant(self.co, 'FRAIS AGIOS')
        self.assertEqual(modele.id, self.modele.id)  # priorité 100 < 200.


class ModeleRapprochementAPITests(TestCase):
    def setUp(self):
        self.co = make_company('xacc4-api', 'XACC4 API Co')
        services.seed_plan_comptable(self.co)
        self.co_b = make_company('xacc4-api-b', 'XACC4 API Co B')
        services.seed_plan_comptable(self.co_b)
        self.user = make_user(self.co, 'admin-xacc4')
        self.api = auth(self.user)

    def test_crud_company_scope(self):
        compte = services.get_compte(self.co, '6147')
        resp = self.api.post('/api/django/compta/modeles-rapprochement/', {
            'libelle': 'Frais CB', 'motif': 'COMMISSION',
            'compte_contrepartie': compte.id,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        modele_id = resp.data['id']

        # Une société B ne voit pas les modèles de A.
        user_b = make_user(self.co_b, 'admin-xacc4-b')
        resp_b = auth(user_b).get('/api/django/compta/modeles-rapprochement/')
        ids_b = [m['id'] for m in resp_b.data.get(
            'results', resp_b.data if isinstance(resp_b.data, list) else [])]
        self.assertNotIn(modele_id, ids_b)

    def test_compte_contrepartie_autre_societe_refuse(self):
        compte_b = services.get_compte(self.co_b, '6147')
        resp = self.api.post('/api/django/compta/modeles-rapprochement/', {
            'libelle': 'Frais CB', 'motif': 'COMMISSION',
            'compte_contrepartie': compte_b.id,
        })
        self.assertEqual(resp.status_code, 400)
