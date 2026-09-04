"""Tests AUDV02 — l'écran Trésorerie (encours/lettrage, effets, alertes, RIB).

Six sélecteurs/services entièrement écrits et testés vivaient sans AUCUN
appelant HTTP : `encours_tiers`, `lignes_non_lettrees` (COMPTA22),
`echeancier_effets`, `total_effets_ouverts` (FG127/FG128),
`rapprochements_en_ecart` (FG131), `comptes_tresorerie_rib_invalides` et
`diagnostic_rib` (XACC24). Le comptable ne pouvait donc PAS répondre, depuis
un écran, à « combien ce client me doit-il vraiment ? », « combien ai-je en
portefeuille ? », « qu'est-ce qui bloque avant paiement ? » ni « ce RIB est-il
valide ? ».

Ce module affirme les deux moitiés du contrat (PACT10) : la VRAIE réponse de
chaque vue porte exactement les clés de l'exemple committé dans
`contract_samples/` — le même fichier que le test frontend IMPORTE — et le
comportement métier qui rend ces chiffres justes (encours = lignes NON
lettrées seulement ; totaux d'effets = OUVERTS seulement ; RIB vide jamais
signalé ; approbation RIB refusée à son propre demandeur).
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteTresorerie, DemandeApprobationRib, Effet)

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'

RIB_VALIDE_ANCIEN = '123456789012345678901213'
RIB_VALIDE_NOUVEAU = '070001234598765432109842'
RIB_INVALIDE = '070001234598765432109999'


def contrat(nom, variante='exemple'):
    return json.loads(
        (CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))[variante]


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FicheTiersEncoursTests(TestCase):
    """DRAFT165-9+10 — encours + lignes non lettrées d'un compte de tiers."""

    def setUp(self):
        self.co = make_company('audv02-tiers', 'AUDV02 Tiers')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv02-tiers-user')
        self.api = auth(self.user)
        self.clients = services.get_compte(self.co, '3421')
        self.banque = services.get_compte(self.co, '5141')
        # Facture 24 000 au débit du client, acompte 9 600 au crédit.
        services.creer_ecriture_od(
            self.co, date(2026, 6, 12), 'Facture SunRak',
            [{'compte': self.clients, 'debit': Decimal('24000'),
              'credit': Decimal('0'), 'libelle': 'Facture FAC-31'},
             {'compte': self.banque, 'debit': Decimal('0'),
              'credit': Decimal('24000'), 'libelle': 'Facture FAC-31'}])
        services.creer_ecriture_od(
            self.co, date(2026, 7, 3), 'Acompte SunRak',
            [{'compte': self.banque, 'debit': Decimal('9600'),
              'credit': Decimal('0'), 'libelle': 'Acompte'},
             {'compte': self.clients, 'debit': Decimal('0'),
              'credit': Decimal('9600'), 'libelle': 'Acompte'}])

    def _url(self, compte=None):
        return (f'/api/django/compta/comptes/'
                f'{(compte or self.clients).id}/fiche-tiers/')

    def test_encours_ne_compte_que_les_lignes_non_lettrees(self):
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Decimal(resp.data['encours']), Decimal('14400.00'))
        self.assertEqual(resp.data['nb_lignes_non_lettrees'], 2)

        # Lettrer les deux lignes ne peut pas se faire (elles ne soldent pas) :
        # on solde d'abord par une ligne de 14 400 au crédit, PUIS on lettre.
        services.creer_ecriture_od(
            self.co, date(2026, 7, 20), 'Solde SunRak',
            [{'compte': self.banque, 'debit': Decimal('14400'),
              'credit': Decimal('0'), 'libelle': 'Solde'},
             {'compte': self.clients, 'debit': Decimal('0'),
              'credit': Decimal('14400'), 'libelle': 'Solde'}])
        ids = [ligne.id
               for ligne in selectors.lignes_non_lettrees(self.co, self.clients)]
        selectors.lettrer(self.co, ids, 'A')

        resp = self.api.get(self._url())
        self.assertEqual(Decimal(resp.data['encours']), Decimal('0'))
        self.assertEqual(resp.data['nb_lignes_non_lettrees'], 0)
        self.assertEqual(resp.data['lignes_non_lettrees'], [])

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        resp = self.api.get(self._url())
        exemple = contrat('fiche_tiers_encours')
        self.assertEqual(sorted(exemple), sorted(resp.data))
        self.assertEqual(
            sorted(exemple['lignes_non_lettrees'][0]),
            sorted(resp.data['lignes_non_lettrees'][0]))

    def test_variante_vide_du_contrat_est_le_meme_jeu_de_cles(self):
        """Un compte sans mouvement doit rendre la MÊME forme, pas moins."""
        vide = services._assurer_compte(self.co, '3423')
        resp = self.api.get(self._url(vide))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(sorted(contrat('fiche_tiers_encours', 'exemple_vide')),
                         sorted(resp.data))
        self.assertEqual(resp.data['lignes_non_lettrees'], [])

    def test_scopee_par_societe(self):
        autre = make_company('audv02-tiers-autre', 'AUDV02 Autre')
        services.seed_plan_comptable(autre)
        compte_autre = services.get_compte(autre, '3421')
        resp = self.api.get(self._url(compte_autre))
        self.assertEqual(resp.status_code, 404)


class EcheancierEffetsTests(TestCase):
    """DRAFT165-11+12 — portefeuille d'effets AVEC ses totaux ouverts."""

    def setUp(self):
        self.co = make_company('audv02-effets', 'AUDV02 Effets')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.api = auth(make_user(self.co, 'audv02-effets-user'))
        self.a_recevoir = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('42000'),
            date_emission=date(2026, 7, 15), date_echeance=date(2026, 9, 15),
            numero='CHQ-4471203')
        services.enregistrer_effet(
            self.co, sens=Effet.Sens.PAYER, montant=Decimal('13500'),
            date_emission=date(2026, 7, 20), date_echeance=date(2026, 10, 20),
            numero='LCR-2026-018')

    URL = '/api/django/compta/effets/echeancier/'

    def test_totaux_par_sens_et_net(self):
        resp = self.api.get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb'], 2)
        self.assertEqual(Decimal(resp.data['total_a_recevoir']),
                         Decimal('42000'))
        self.assertEqual(Decimal(resp.data['total_a_payer']), Decimal('13500'))
        self.assertEqual(Decimal(resp.data['net']), Decimal('28500'))

    def test_un_effet_encaisse_quitte_les_totaux_ouverts(self):
        """Encaissé = déjà en banque : l'additionner double-compterait."""
        services.encaisser_effet(
            self.a_recevoir, date_encaissement=date(2026, 9, 15))
        resp = self.api.get(self.URL)
        self.assertEqual(Decimal(resp.data['total_a_recevoir']), Decimal('0'))
        # Il reste VISIBLE dans l'échéancier (historique), juste plus compté.
        self.assertEqual(resp.data['nb'], 2)

    def test_le_filtre_sens_ne_change_pas_les_totaux_de_la_societe(self):
        resp = self.api.get(self.URL, {'sens': Effet.Sens.RECEVOIR})
        self.assertEqual(resp.data['nb'], 1)
        self.assertEqual(Decimal(resp.data['total_a_payer']), Decimal('13500'))

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        resp = self.api.get(self.URL)
        exemple = contrat('effets_echeancier')
        self.assertEqual(sorted(exemple), sorted(resp.data))
        self.assertEqual(sorted(exemple['effets'][0]),
                         sorted(resp.data['effets'][0]))
        self.assertEqual(sorted(contrat('effets_echeancier', 'exemple_vide')),
                         sorted(resp.data))


class AlerteRibInvalideTests(TestCase):
    """DRAFT165-16 (XACC24) — warning RIB, jamais un blocage."""

    URL = '/api/django/compta/tresorerie/rib-invalides/'

    def setUp(self):
        self.co = make_company('audv02-rib', 'AUDV02 RIB')
        self.compte = services._assurer_compte(self.co, '5141')
        self.api = auth(make_user(self.co, 'audv02-rib-user'))

    def _compte_treso(self, libelle, rib):
        return CompteTresorerie.objects.create(
            company=self.co, libelle=libelle, compte_comptable=self.compte,
            rib=rib, solde_initial=Decimal('0'))

    def test_alerte_signale_la_cle_fausse(self):
        self._compte_treso('BP — Compte courant Casablanca', RIB_INVALIDE)
        resp = self.api.get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['nb'], 1)
        self.assertEqual(resp.data['comptes'][0]['rib'], RIB_INVALIDE)
        self.assertTrue(resp.data['comptes'][0]['erreurs'])

    def test_rib_vide_et_rib_valide_ne_sont_jamais_signales(self):
        self._compte_treso('Caisse (sans RIB)', '')
        self._compte_treso('Compte conforme', RIB_VALIDE_ANCIEN)
        resp = self.api.get(self.URL)
        self.assertEqual(resp.data['nb'], 0)
        self.assertEqual(sorted(contrat('comptes_rib_invalides', 'exemple_vide')),
                         sorted(resp.data))

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        self._compte_treso('BP — Compte courant Casablanca', RIB_INVALIDE)
        resp = self.api.get(self.URL)
        exemple = contrat('comptes_rib_invalides')
        self.assertEqual(sorted(exemple), sorted(resp.data))
        self.assertEqual(sorted(exemple['comptes'][0]),
                         sorted(resp.data['comptes'][0]))


class DiagnosticRibEtQuatreYeuxTests(TestCase):
    """DRAFT165-46/47/48 (XACC24) — diagnostic AVANT demande, 4 yeux à
    l'approbation."""

    DIAG = '/api/django/compta/approbations-rib/diagnostic-rib/'

    def setUp(self):
        self.co = make_company('audv02-4yeux', 'AUDV02 4 yeux')
        self.demandeur = make_user(self.co, 'audv02-demandeur')
        self.decideur = make_user(self.co, 'audv02-decideur')

    def test_diagnostic_signale_une_cle_fausse_sans_rien_bloquer(self):
        api = auth(self.demandeur)
        resp = api.get(self.DIAG, {'rib': RIB_INVALIDE})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['valide'])
        self.assertTrue(resp.data['erreurs'])
        resp = api.get(self.DIAG, {'rib': RIB_VALIDE_NOUVEAU})
        self.assertTrue(resp.data['valide'])

    def test_diagnostic_sans_parametre_est_un_400_francais(self):
        resp = auth(self.demandeur).get(self.DIAG)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rib', resp.data['detail'])

    def test_le_demandeur_ne_peut_pas_approuver_sa_propre_demande(self):
        api = auth(self.demandeur)
        creation = api.post('/api/django/compta/approbations-rib/', {
            'fournisseur_id': 601, 'fournisseur_nom': 'ACME',
            'ancien_rib': RIB_VALIDE_ANCIEN,
            'nouveau_rib': RIB_VALIDE_NOUVEAU,
        }, format='json')
        self.assertEqual(creation.status_code, 201, creation.content)
        demande_id = creation.data['id']

        refus = api.post(
            f'/api/django/compta/approbations-rib/{demande_id}/approuver/',
            {}, format='json')
        self.assertEqual(refus.status_code, 400, refus.content)
        demande = DemandeApprobationRib.objects.get(id=demande_id)
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.EN_ATTENTE)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_ANCIEN)

        # Un SECOND regard approuve : le nouveau RIB devient actif.
        ok = auth(self.decideur).post(
            f'/api/django/compta/approbations-rib/{demande_id}/approuver/',
            {'commentaire': 'RIB confirmé par téléphone.'}, format='json')
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.data['rib_actif'], RIB_VALIDE_NOUVEAU)

    def test_le_demandeur_peut_refuser_sa_propre_demande(self):
        """Renoncer à SA demande n'est pas un contournement des 4 yeux."""
        api = auth(self.demandeur)
        creation = api.post('/api/django/compta/approbations-rib/', {
            'fournisseur_id': 602, 'fournisseur_nom': 'ACME',
            'ancien_rib': RIB_VALIDE_ANCIEN,
            'nouveau_rib': RIB_VALIDE_NOUVEAU,
        }, format='json')
        resp = api.post(
            f'/api/django/compta/approbations-rib/{creation.data["id"]}/refuser/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'],
                         DemandeApprobationRib.Statut.REFUSEE)
