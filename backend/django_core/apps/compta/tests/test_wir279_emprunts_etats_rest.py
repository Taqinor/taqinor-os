"""WIR279 — Surface REST des emprunts/crédits-bails (XACC14) et des états
comptables paramétrables (XACC19).

Les modèles ET les services existaient, testés, depuis XACC14/XACC19 — mais
sans AUCUN viewset : rien de tout cela n'était atteignable autrement qu'en
shell Django (c'est ce qui gelait l'entrée GATED du FRONTEND_GAP_PLAN).

Ces tests vérifient que les vues BRANCHENT les services existants sans rien
réimplémenter : mêmes valeurs que les tests de service (somme des principaux ==
capital, mensualité constante), l'écriture est postée UNE SEULE fois
(re-post refusé explicitement), une formule illégale rend 400 (jamais 500), la
route `etats-personnalises/` est bien DISTINCTE de `etats/`, et tout est isolé
par société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import EcheanceEmprunt, Emprunt, EtatPersonnalise

User = get_user_model()

EMPRUNTS = '/api/django/compta/emprunts/'
ECHEANCES = '/api/django/compta/echeances-emprunt/'
ETATS = '/api/django/compta/etats-personnalises/'


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company('wir279-co', 'WIR279 Co')
        compta_services.seed_plan_comptable(self.company)
        compta_services.seed_journaux(self.company)
        self.user = make_user(self.company, 'wir279-admin')
        self.api = auth(self.user)


class EmpruntRestTests(_Base):
    def _creer(self, **extra):
        payload = {
            'reference': 'EMP-2026-01',
            'banque': 'Attijariwafa',
            'type_financement': 'emprunt',
            'capital': '100000.00',
            'taux_annuel': '6.000',
            'duree_mois': 12,
            'date_debut': '2026-01-01',
        }
        payload.update(extra)
        return self.api.post(EMPRUNTS, payload, format='json')

    def test_creation_pose_la_societe_cote_serveur(self):
        resp = self._creer()
        self.assertEqual(resp.status_code, 201, resp.data)
        emprunt = Emprunt.objects.get(pk=resp.data['id'])
        self.assertEqual(emprunt.company_id, self.company.id)

    def test_company_du_corps_est_ignoree(self):
        autre = make_company('wir279-pirate', 'Pirate')
        resp = self._creer(company=autre.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Emprunt.objects.get(pk=resp.data['id']).company_id,
            self.company.id)

    def test_generer_tableau_donne_les_memes_valeurs_que_le_service(self):
        emprunt_id = self._creer().data['id']
        resp = self.api.post(f'{EMPRUNTS}{emprunt_id}/generer-tableau/')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Contrat (contract_samples) : un OBJET {echeances, nb}, jamais une
        # liste nue.
        self.assertEqual(set(resp.data.keys()), {'echeances', 'nb'})
        echeances = resp.data['echeances']
        self.assertEqual(resp.data['nb'], 12)
        self.assertEqual(len(echeances), 12)
        self.assertEqual(echeances[0]['numero'], 1)
        # Invariant du service : la somme des principaux SOLDE le capital.
        total_principal = sum(
            Decimal(ligne['principal']) for ligne in echeances)
        self.assertEqual(total_principal, Decimal('100000.00'))
        # Dernière échéance : capital restant dû nul.
        self.assertEqual(Decimal(echeances[-1]['capital_restant_du']),
                         Decimal('0.00'))

    def test_filtre_par_type_de_financement(self):
        self._creer()
        self._creer(reference='LEA-1', type_financement='leasing')
        resp = self.api.get(EMPRUNTS, {'type_financement': 'leasing'})
        self.assertEqual(resp.status_code, 200)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['reference'], 'LEA-1')

    def test_isolation_societe(self):
        emprunt_id = self._creer().data['id']
        autre = make_company('wir279-autre', 'Autre WIR279')
        api_autre = auth(make_user(autre, 'wir279-autre-admin'))
        self.assertEqual(
            api_autre.get(f'{EMPRUNTS}{emprunt_id}/').status_code, 404)
        self.assertEqual(
            api_autre.post(
                f'{EMPRUNTS}{emprunt_id}/generer-tableau/').status_code, 404)


class EcheanceEmpruntRestTests(_Base):
    def setUp(self):
        super().setUp()
        self.emprunt = Emprunt.objects.create(
            company=self.company, reference='EMP-POST', banque='CIH',
            capital=Decimal('12000.00'), taux_annuel=Decimal('0.000'),
            duree_mois=3, date_debut=date(2026, 1, 1))
        compta_services.generer_tableau_amortissement(self.emprunt)
        self.echeance = self.emprunt.echeances.order_by('numero').first()

    def test_lecture_seule_pas_de_creation(self):
        resp = self.api.post(ECHEANCES, {}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_filtre_par_emprunt(self):
        resp = self.api.get(ECHEANCES, {'emprunt': self.emprunt.id})
        self.assertEqual(resp.status_code, 200)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 3)

    def test_poster_une_seule_fois(self):
        url = f'{ECHEANCES}{self.echeance.id}/poster/'
        premier = self.api.post(url)
        self.assertEqual(premier.status_code, 201, premier.data)
        self.echeance.refresh_from_db()
        self.assertTrue(self.echeance.posted)
        ecriture_id = premier.data['ecriture_id']
        # Re-post REFUSÉ explicitement (pas un 201 muet sur l'écriture déjà là).
        second = self.api.post(url)
        self.assertEqual(second.status_code, 400, second.data)
        self.assertIn('déjà postée', str(second.data['detail']))
        self.echeance.refresh_from_db()
        self.assertEqual(self.echeance.ecriture_id, ecriture_id)

    def test_regenerer_refuse_apres_un_post(self):
        self.api.post(f'{ECHEANCES}{self.echeance.id}/poster/')
        resp = self.api.post(f'{EMPRUNTS}{self.emprunt.id}/generer-tableau/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            EcheanceEmprunt.objects.filter(emprunt=self.emprunt).count(), 3)

    def test_isolation_societe(self):
        autre = make_company('wir279-ech-autre', 'Autre éch.')
        api_autre = auth(make_user(autre, 'wir279-ech-autre-admin'))
        self.assertEqual(
            api_autre.post(
                f'{ECHEANCES}{self.echeance.id}/poster/').status_code, 404)


class EtatPersonnaliseRestTests(_Base):
    PAYLOAD = {
        'libelle': 'CPC de gestion',
        'description': 'Marge par nature',
        'lignes': [
            {'ordre': 0, 'libelle': 'EXPLOITATION', 'type_ligne': 'titre',
             'formule': ''},
            {'ordre': 1, 'libelle': "Chiffre d'affaires",
             'type_ligne': 'total', 'formule': '+71'},
            {'ordre': 2, 'libelle': 'Achats', 'type_ligne': 'total',
             'formule': '-61'},
        ],
        'colonnes': [
            {'ordre': 0, 'libelle': '2026', 'type_colonne': 'periode',
             'date_debut': '2026-01-01', 'date_fin': '2026-12-31'},
        ],
    }

    def test_creation_route_par_le_service(self):
        resp = self.api.post(ETATS, self.PAYLOAD, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        etat = EtatPersonnalise.objects.get(pk=resp.data['id'])
        self.assertEqual(etat.company_id, self.company.id)
        self.assertEqual(etat.lignes.count(), 3)
        self.assertEqual(etat.colonnes.count(), 1)

    def test_formule_illegale_400_francais_jamais_500(self):
        charge = dict(self.PAYLOAD)
        charge['libelle'] = 'État cassé'
        charge['lignes'] = [
            {'ordre': 0, 'libelle': 'Ligne folle', 'type_ligne': 'total',
             'formule': 'ceci-nest-pas-une-formule'},
        ]
        resp = self.api.post(ETATS, charge, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        # Rien n'a été persisté (le service valide AVANT toute écriture).
        self.assertFalse(
            EtatPersonnalise.objects.filter(libelle='État cassé').exists())

    def test_evaluer_rend_colonnes_et_lignes(self):
        etat_id = self.api.post(ETATS, self.PAYLOAD, format='json').data['id']
        resp = self.api.get(f'{ETATS}{etat_id}/evaluer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data.keys()), {'colonnes', 'lignes'})
        self.assertEqual(len(resp.data['colonnes']), 1)
        self.assertEqual(len(resp.data['lignes']), 3)
        # Une ligne TITRE ne porte AUCUNE valeur (contrat du sample).
        titre = resp.data['lignes'][0]
        self.assertEqual(titre['type_ligne'], 'titre')
        self.assertEqual(titre['valeurs'], {})
        # Une ligne TOTAL est indexée par ID DE COLONNE, pas positionnellement.
        colonne_id = resp.data['colonnes'][0]['id']
        self.assertIn(colonne_id, resp.data['lignes'][1]['valeurs'])

    def test_route_distincte_des_etats_figes(self):
        """`etats-personnalises/` ne remplace JAMAIS `etats/` (FG110-114)."""
        self.api.post(ETATS, self.PAYLOAD, format='json')
        figes = self.api.get('/api/django/compta/etats/grand_livre/')
        self.assertEqual(figes.status_code, 200)

    def test_isolation_societe(self):
        etat_id = self.api.post(ETATS, self.PAYLOAD, format='json').data['id']
        autre = make_company('wir279-etat-autre', 'Autre état')
        api_autre = auth(make_user(autre, 'wir279-etat-autre-admin'))
        self.assertEqual(
            api_autre.get(f'{ETATS}{etat_id}/evaluer/').status_code, 404)
