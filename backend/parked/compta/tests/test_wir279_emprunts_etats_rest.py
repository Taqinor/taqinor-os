"""Tests WIR279 — exposition REST des emprunts/crédits-bails (XACC14) et des
états financiers paramétrables (XACC19).

Les deux fonctionnalités avaient modèle + service + selector COMPLETS et zéro
ViewSet : rien n'était atteignable hors admin Django (elles étaient d'ailleurs
listées « BACKEND-INCOMPLETE / GATED » dans docs/FRONTEND_GAP_PLAN.md).

Ce fichier vérifie que l'API rend EXACTEMENT ce que les tests de service
existants affirment (test_emprunts.py / test_etats_personnalises.py) — la vue
ne ré-implémente aucune règle — plus les trois garanties propres à la couche
REST : re-post explicitement refusé, formule illégale en 400 français (jamais
un 500), et isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    EcritureComptable, Emprunt, EtatPersonnalise, Journal, LigneEcriture)
from apps.roles.models import Role

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


class EmpruntRestTests(TestCase):
    def setUp(self):
        self.co = make_company('wir279-emp', 'WIR279 Emprunts')
        self.user = make_user(self.co, 'wir279-admin')
        self.api = auth(self.user)

    def _creer(self, **kwargs):
        corps = {
            'banque': 'Banque Populaire',
            'type_financement': 'emprunt',
            'capital': '120000.00',
            'taux_annuel': '6.000',
            'duree_mois': 12,
            'date_debut': '2026-01-01',
        }
        corps.update(kwargs)
        return self.api.post(EMPRUNTS, corps, format='json')

    # ── CRUD scopé ──────────────────────────────────────────────────────────
    def test_creation_pose_la_societe_cote_serveur(self):
        resp = self._creer()
        self.assertEqual(resp.status_code, 201, resp.data)
        emprunt = Emprunt.objects.get(pk=resp.data['id'])
        self.assertEqual(emprunt.company_id, self.co.id)
        # `company` n'est ni exposée ni acceptée du corps.
        self.assertNotIn('company', resp.data)

    def test_company_du_corps_est_ignoree(self):
        autre = make_company('wir279-autre', 'Autre Co')
        resp = self._creer(company=autre.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Emprunt.objects.get(pk=resp.data['id']).company_id, self.co.id)

    def test_capital_negatif_refuse_en_400(self):
        resp = self._creer(capital='0.00')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(Emprunt.objects.filter(company=self.co).count(), 0)

    # ── generer-tableau/ : MÊMES valeurs que le test de service ─────────────
    def test_generer_tableau_memes_valeurs_que_le_service(self):
        emprunt_id = self._creer().data['id']
        resp = self.api.post(f'{EMPRUNTS}{emprunt_id}/generer-tableau/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['emprunt'], emprunt_id)
        self.assertEqual(resp.data['nb_echeances'], 12)
        echeances = resp.data['echeances']
        self.assertEqual(len(echeances), 12)
        # Invariant du service (test_emprunts.py) : Σ principal == capital,
        # dernier capital restant dû nul.
        total = sum((Decimal(e['principal']) for e in echeances), Decimal('0'))
        self.assertEqual(total, Decimal('120000.00'))
        self.assertEqual(Decimal(echeances[-1]['capital_restant_du']),
                         Decimal('0.00'))
        self.assertFalse(any(e['posted'] for e in echeances))

    def test_regeneration_refusee_si_une_echeance_est_postee(self):
        emprunt_id = self._creer().data['id']
        self.api.post(f'{EMPRUNTS}{emprunt_id}/generer-tableau/')
        premiere = Emprunt.objects.get(pk=emprunt_id).echeances.order_by(
            'numero').first()
        self.assertEqual(
            self.api.post(f'{ECHEANCES}{premiere.pk}/poster/').status_code, 201)
        resp = self.api.post(f'{EMPRUNTS}{emprunt_id}/generer-tableau/')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Isolation ───────────────────────────────────────────────────────────
    def test_isolation_societe(self):
        emprunt_id = self._creer().data['id']
        autre = make_company('wir279-autre2', 'Autre Co 2')
        api_autre = auth(make_user(autre, 'wir279-autre-admin'))
        self.assertEqual(
            api_autre.get(f'{EMPRUNTS}{emprunt_id}/').status_code, 404)
        self.assertEqual(
            api_autre.post(
                f'{EMPRUNTS}{emprunt_id}/generer-tableau/').status_code, 404)
        liste = api_autre.get(EMPRUNTS)
        self.assertEqual(liste.status_code, 200)
        resultats = liste.data.get('results', liste.data)
        self.assertEqual(len(resultats), 0)

    # ── Permission de saisie ────────────────────────────────────────────────
    def test_role_sans_compta_saisir_ne_cree_ni_ne_genere(self):
        role = Role.objects.create(
            company=self.co, nom='Commercial WIR279',
            permissions=['crm_voir', 'crm_creer'])
        commercial = make_user(self.co, 'wir279-commercial')
        commercial.role = role
        commercial.save()
        api = auth(commercial)
        self.assertEqual(api.post(EMPRUNTS, {}, format='json').status_code, 403)
        emprunt_id = self._creer().data['id']
        self.assertEqual(
            api.post(f'{EMPRUNTS}{emprunt_id}/generer-tableau/').status_code,
            403)


class EcheanceEmpruntRestTests(TestCase):
    def setUp(self):
        self.co = make_company('wir279-ech', 'WIR279 Échéances')
        self.user = make_user(self.co, 'wir279-ech-admin')
        self.api = auth(self.user)
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('60000'), taux_annuel=Decimal('4.5'),
            duree_mois=6, date_debut=date(2026, 1, 1))
        services.generer_tableau_amortissement(self.emprunt)
        self.premiere = self.emprunt.echeances.order_by('numero').first()

    def test_liste_lecture_seule_filtrable_par_emprunt(self):
        resp = self.api.get(ECHEANCES, {'emprunt': self.emprunt.pk})
        self.assertEqual(resp.status_code, 200)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 6)

    def test_aucune_ecriture_directe_sur_les_echeances(self):
        # Une échéance naît du tableau et ne change qu'en étant POSTÉE.
        self.assertEqual(
            self.api.post(ECHEANCES, {}, format='json').status_code, 405)
        self.assertEqual(
            self.api.patch(f'{ECHEANCES}{self.premiere.pk}/',
                           {'principal': '1.00'}, format='json').status_code,
            405)
        self.assertEqual(
            self.api.delete(f'{ECHEANCES}{self.premiere.pk}/').status_code, 405)

    def test_poster_ecrit_une_ecriture_equilibree(self):
        resp = self.api.post(f'{ECHEANCES}{self.premiere.pk}/poster/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['posted'])
        self.assertEqual(resp.data['echeance'], self.premiere.pk)
        self.assertEqual(resp.data['reference'],
                         f'EMPR-{self.emprunt.pk}-{self.premiere.numero}')
        lignes = LigneEcriture.objects.filter(
            ecriture_id=resp.data['ecriture_id'])
        debit = sum((ln.debit for ln in lignes), Decimal('0'))
        credit = sum((ln.credit for ln in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, self.premiere.mensualite)

    def test_ecriture_postee_une_seule_fois(self):
        premier = self.api.post(f'{ECHEANCES}{self.premiere.pk}/poster/')
        self.assertEqual(premier.status_code, 201, premier.data)
        second = self.api.post(f'{ECHEANCES}{self.premiere.pk}/poster/')
        # Le re-post est REFUSÉ explicitement (et non un 200 trompeur).
        self.assertEqual(second.status_code, 400, second.data)
        self.assertIn('déjà postée', second.data['detail'])
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='echeance_emprunt',
                source_id=self.premiere.pk).count(), 1)

    def test_isolation_societe(self):
        autre = make_company('wir279-ech-autre', 'Autre Co 3')
        api_autre = auth(make_user(autre, 'wir279-ech-autre-admin'))
        self.assertEqual(
            api_autre.post(
                f'{ECHEANCES}{self.premiere.pk}/poster/').status_code, 404)
        self.premiere.refresh_from_db()
        self.assertFalse(self.premiere.posted)


def _poster_vente_charge(company, date_ecr, montant_vente, montant_charge):
    """Même fixture que test_etats_personnalises.py (vente 7111 + charge 6111)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        services.seed_journaux(company)
        journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    compte_vente = services._assurer_compte(company, '7111')
    compte_charge = services._assurer_compte(company, '6111')
    compte_tresorerie = services._assurer_compte(company, '5141')
    services.creer_ecriture(
        company, journal, date_ecr, 'Vente test', [
            {'compte': compte_tresorerie, 'debit': Decimal(montant_vente),
             'credit': Decimal('0'), 'libelle': 'Vente'},
            {'compte': compte_vente, 'debit': Decimal('0'),
             'credit': Decimal(montant_vente), 'libelle': 'Vente'},
        ], statut=EcritureComptable.Statut.VALIDEE)
    services.creer_ecriture(
        company, journal, date_ecr, 'Charge test', [
            {'compte': compte_charge, 'debit': Decimal(montant_charge),
             'credit': Decimal('0'), 'libelle': 'Charge'},
            {'compte': compte_tresorerie, 'debit': Decimal('0'),
             'credit': Decimal(montant_charge), 'libelle': 'Charge'},
        ], statut=EcritureComptable.Statut.VALIDEE)


class EtatPersonnaliseRestTests(TestCase):
    def setUp(self):
        self.co = make_company('wir279-etat', 'WIR279 États')
        self.user = make_user(self.co, 'wir279-etat-admin')
        self.api = auth(self.user)
        _poster_vente_charge(self.co, date(2026, 3, 15), 50000, 20000)

    def _corps(self, formule='+71,-61'):
        return {
            'libelle': 'Marge par activité',
            'description': 'Marge brute par activité',
            'lignes': [
                {'libelle': 'PRODUITS', 'type_ligne': 'titre', 'ordre': 0},
                {'libelle': 'Marge brute', 'type_ligne': 'total',
                 'formule': formule, 'ordre': 1},
            ],
            'colonnes': [
                {'libelle': 'Exercice', 'type_colonne': 'periode',
                 'date_debut': '2026-01-01', 'date_fin': '2026-12-31',
                 'ordre': 0},
            ],
        }

    def test_route_distincte_de_etats(self):
        # `etats/` (états FIGÉS, EtatsComptablesViewSet) et
        # `etats-personnalises/` sont DEUX ressources : la seconde ne doit
        # jamais avoir absorbé la première.
        self.assertEqual(
            self.api.get('/api/django/compta/etats/balance/').status_code, 200)
        self.assertEqual(self.api.get(ETATS).status_code, 200)

    def test_creation_route_par_le_service(self):
        resp = self.api.post(ETATS, self._corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        etat = EtatPersonnalise.objects.get(pk=resp.data['id'])
        self.assertEqual(etat.company_id, self.co.id)
        self.assertEqual(etat.lignes.count(), 2)
        self.assertEqual(etat.colonnes.count(), 1)
        self.assertEqual(etat.created_by_id, self.user.id)

    def test_formule_illegale_400_francais_jamais_500(self):
        resp = self.api.post(ETATS, self._corps(formule='abc'), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Terme invalide', str(resp.data['detail']))
        # Rien n'est persisté : le service valide AVANT de créer.
        self.assertEqual(
            EtatPersonnalise.objects.filter(company=self.co).count(), 0)

    def test_evaluer_memes_valeurs_que_le_selector(self):
        etat_id = self.api.post(ETATS, self._corps(), format='json').data['id']
        resp = self.api.post(f'{ETATS}{etat_id}/evaluer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etat'], etat_id)

        attendu = selectors.evaluer_etat_personnalise(
            EtatPersonnalise.objects.get(pk=etat_id))
        colonne_id = attendu['colonnes'][0]['id']
        self.assertEqual(
            [c['id'] for c in resp.data['colonnes']],
            [c['id'] for c in attendu['colonnes']])

        # La ligne TITRE n'a aucune valeur ; la ligne TOTAL porte celle du
        # selector, sérialisée en TEXTE et indexée par ID DE COLONNE.
        titre, total = resp.data['lignes']
        self.assertEqual(titre['type_ligne'], 'titre')
        self.assertEqual(titre['valeurs'], {})
        self.assertEqual(total['type_ligne'], 'total')
        self.assertEqual(
            Decimal(total['valeurs'][str(colonne_id)]),
            attendu['lignes'][1]['valeurs'][colonne_id])

    def test_isolation_societe(self):
        etat_id = self.api.post(ETATS, self._corps(), format='json').data['id']
        autre = make_company('wir279-etat-autre', 'Autre Co 4')
        api_autre = auth(make_user(autre, 'wir279-etat-autre-admin'))
        self.assertEqual(
            api_autre.get(f'{ETATS}{etat_id}/').status_code, 404)
        self.assertEqual(
            api_autre.post(f'{ETATS}{etat_id}/evaluer/').status_code, 404)
        liste = api_autre.get(ETATS)
        resultats = liste.data.get('results', liste.data)
        self.assertEqual(len(resultats), 0)
