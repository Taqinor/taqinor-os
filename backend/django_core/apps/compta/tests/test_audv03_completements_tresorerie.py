"""Tests AUDV03 — les six compléments trésorerie deviennent ATTEIGNABLES.

Chacune de ces six capacités était un service complet, testé unitairement, et
sans le moindre appelant de production :

* `transferer_tva_encaissement` (XACC1) — importé dans `receivers.py` comme
  « point d'intégration » mais jamais appelé : la TVA d'une société au régime
  ENCAISSEMENT restait indéfiniment en compte d'attente 44551, donc la
  déclaration sortait fausse ;
* `recalculer_indemnite_chantier` (FG136) — un PATCH sur le GPS enregistrait
  de nouvelles coordonnées EN GARDANT les anciens montants ;
* `provisionner_compte_portail` (FG228) — le `perform_create` du ViewSet
  créait un compte de plus à chaque POST et ne réactivait jamais un compte
  désactivé ;
* `creer_ecriture_numerotee` + `sequence_piece_journal` (COMPTA4) — une OD
  manuelle sortait sans numéro de pièce, et aucun écran ne pouvait annoncer
  celui qui serait attribué ;
* `poster_dotation_etalement` (XACC15) — l'échéancier était généré puis jamais
  étalé : la charge restait immobilisée au débit de 3491.

Les deux nouveaux agrégats sont affirmés contre leur exemple committé (PACT10).
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import receivers  # noqa: F401  (câblage ready())
from apps.compta import services
from apps.compta.models import (
    BaremeIndemnite, ComptePortailClient, EcritureComptable, Journal,
    PlanComptable,
)
from apps.crm.models import Client
from core.events import paiement_enregistre

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'


def contrat(nom, variante='exemple'):
    return json.loads(
        (CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))[variante]


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FakeDoc(SimpleNamespace):
    """Stub duck-typé d'un document ventes (lu par valeur, jamais importé)."""


@override_settings(COMPTA_AUTO_ECRITURES=True)
class TvaEncaissementSurEvenementTests(TestCase):
    """DRAFT165-17 — la TVA quitte le compte d'attente AU PAIEMENT."""

    def setUp(self):
        self.co = make_company('audv03-tva', 'AUDV03 TVA')
        self.plan = services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _paiement(self, montant):
        facture = _FakeDoc(
            id=1, company=self.co, reference='FAC-AUDV03', client_id=42,
            total_ht=Decimal('1000'), total_tva=Decimal('200'),
            total_ttc=Decimal('1200'), montant_du=Decimal('0'))
        return _FakeDoc(
            id=91, company=self.co, montant=Decimal(montant),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)

    def _transferts(self):
        return EcritureComptable.objects.filter(
            company=self.co, source_type='tva_encaissement')

    def test_regime_encaissement_le_signal_transfere_la_tva(self):
        self.plan.regime_tva = PlanComptable.RegimeTVA.ENCAISSEMENT
        self.plan.save(update_fields=['regime_tva'])
        paiement = self._paiement('600')
        paiement_enregistre.send(
            sender=_FakeDoc, instance=paiement, company=self.co)
        self.assertEqual(self._transferts().count(), 1)
        # 600 réglés sur 1200 TTC = 50 % → la moitié de la TVA (200) = 100.
        ecriture = self._transferts().first()
        self.assertEqual(ecriture.total_debit, Decimal('100.00'))
        self.assertTrue(ecriture.est_equilibree)

    def test_le_signal_rejoue_ne_double_pas_le_transfert(self):
        self.plan.regime_tva = PlanComptable.RegimeTVA.ENCAISSEMENT
        self.plan.save(update_fields=['regime_tva'])
        paiement = self._paiement('1200')
        for _ in range(2):
            paiement_enregistre.send(
                sender=_FakeDoc, instance=paiement, company=self.co)
        self.assertEqual(self._transferts().count(), 1)

    def test_regime_debit_le_signal_ne_transfere_rien(self):
        """Non-régression : le régime par défaut est INCHANGÉ."""
        paiement = self._paiement('1200')
        paiement_enregistre.send(
            sender=_FakeDoc, instance=paiement, company=self.co)
        self.assertEqual(self._transferts().count(), 0)


class TvaEncaissementHorsAutoEcrituresTests(TestCase):
    """Le transfert suit le MÊME toggle que le reste de l'auto-génération."""

    def test_sans_auto_ecritures_aucun_transfert(self):
        co = make_company('audv03-tva-off', 'AUDV03 TVA OFF')
        plan = services.seed_plan_comptable(co)
        services.seed_journaux(co)
        plan.regime_tva = PlanComptable.RegimeTVA.ENCAISSEMENT
        plan.save(update_fields=['regime_tva'])
        facture = _FakeDoc(
            id=2, company=co, reference='FAC-OFF', client_id=1,
            total_ht=Decimal('1000'), total_tva=Decimal('200'),
            total_ttc=Decimal('1200'), montant_du=Decimal('0'))
        paiement = _FakeDoc(
            id=92, company=co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        paiement_enregistre.send(
            sender=_FakeDoc, instance=paiement, company=co)
        # 44551 n'a jamais été crédité automatiquement : transférer depuis un
        # compte d'attente vide fabriquerait un solde de toutes pièces.
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=co, source_type='tva_encaissement').count(), 0)


class IndemniteRecalculeeAEditionTests(TestCase):
    """DRAFT165-19 — éditer le GPS/les jours RECALCULE les montants."""

    def setUp(self):
        self.co = make_company('audv03-indem', 'AUDV03 Indemnités')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv03-indem-user')
        self.employe = make_user(self.co, 'audv03-indem-emp', role='normal')
        self.api = auth(self.user)
        self.bareme = BaremeIndemnite.objects.create(
            company=self.co, libelle='Standard', defaut=True,
            taux_km=Decimal('2.50'), per_diem=Decimal('150.00'))
        self.indem = services.creer_indemnite_chantier(
            self.co, employe=self.employe, date_deplacement=date(2026, 5, 4),
            bareme=self.bareme,
            depart_lat=Decimal('33.5731'), depart_lng=Decimal('-7.5898'),
            site_lat=Decimal('33.6731'), site_lng=Decimal('-7.5898'),
            nombre_jours=1, libelle_chantier='Chantier A', user=self.user)

    def test_patch_du_nombre_de_jours_recalcule_le_total(self):
        avant = Decimal(self.indem.montant_total)
        resp = self.api.patch(
            f'/api/django/compta/indemnites-chantier/{self.indem.id}/',
            {'nombre_jours': 3}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.indem.refresh_from_db()
        apres = Decimal(self.indem.montant_total)
        self.assertNotEqual(apres, avant)
        # Le per-diem est bien passé de 1 à 3 jours (150 → 450).
        self.assertEqual(
            Decimal(self.indem.montant_per_diem),
            Decimal(self.bareme.per_diem) * 3)
        # La réponse rend les montants À JOUR, pas ceux d'avant le PATCH.
        self.assertEqual(Decimal(resp.data['montant_total']), apres)

    def test_une_indemnite_engagee_refuse_l_edition(self):
        """Une indemnité SOUMISE est partie en validation : ses montants ne se
        réécrivent plus dans le dos du valideur (le service refuse, la vue
        rend un 400 français au lieu d'un enregistrement silencieux)."""
        services.soumettre_indemnite_chantier(self.indem)
        avant = Decimal(self.indem.montant_total)
        resp = self.api.patch(
            f'/api/django/compta/indemnites-chantier/{self.indem.id}/',
            {'nombre_jours': 9}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.indem.refresh_from_db()
        self.assertEqual(Decimal(self.indem.montant_total), avant)
        # La transaction a bien ANNULÉ la saisie : jamais de nouveaux jours
        # enregistrés avec les anciens montants (l'incohérence d'origine).
        self.assertEqual(self.indem.nombre_jours, 1)


class ProvisionnementComptePortailTests(TestCase):
    """DRAFT165-29 — provisionnement IDEMPOTENT + réactivation."""

    def setUp(self):
        self.co = make_company('audv03-portail', 'AUDV03 Portail')
        self.user = make_user(self.co, 'audv03-portail-user')
        self.api = auth(self.user)
        self.client_crm = Client.objects.create(
            company=self.co, nom='SunRak', prenom='SARL',
            email='audv03@example.com', telephone='+212600000031')

    URL = '/api/django/portail/comptes-portail/'

    def test_deux_creations_ne_font_qu_un_seul_compte(self):
        premier = self.api.post(
            self.URL, {'client': self.client_crm.id}, format='json')
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self.api.post(
            self.URL, {'client': self.client_crm.id}, format='json')
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(premier.data['id'], second.data['id'])
        self.assertEqual(
            ComptePortailClient.objects.filter(
                company=self.co, client=self.client_crm).count(), 1)

    def test_un_compte_desactive_est_REACTIVE_et_garde_son_token(self):
        creation = self.api.post(
            self.URL, {'client': self.client_crm.id}, format='json')
        compte = ComptePortailClient.objects.get(id=creation.data['id'])
        token = compte.token_acces
        compte.actif = False
        compte.save(update_fields=['actif'])

        rappel = self.api.post(
            self.URL, {'client': self.client_crm.id}, format='json')
        self.assertEqual(rappel.status_code, 201, rappel.content)
        compte.refresh_from_db()
        self.assertTrue(compte.actif)
        # Le lien déjà envoyé au client reste valable : on ne le casse pas.
        self.assertEqual(compte.token_acces, token)


class NumerotationEcritureODTests(TestCase):
    """DRAFT165-30/31 — numéro de pièce séquentiel + aperçu."""

    def setUp(self):
        self.co = make_company('audv03-od', 'AUDV03 OD')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv03-od-user')
        self.api = auth(self.user)
        self.journal = Journal.objects.get(company=self.co, code='OD')
        self.clients = services.get_compte(self.co, '3421')
        self.ventes = services.get_compte(self.co, '7121')

    def _corps(self, **extra):
        corps = {
            'journal': self.journal.id,
            'date_ecriture': '2026-09-01',
            'libelle': 'OD manuelle',
            'lignes': [
                {'compte': self.clients.id, 'debit': '120', 'credit': '0'},
                {'compte': self.ventes.id, 'debit': '0', 'credit': '120'},
            ],
        }
        corps.update(extra)
        return corps

    def test_sans_reference_le_serveur_numerote(self):
        resp = self.api.post(
            '/api/django/compta/ecritures/', self._corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['reference'].startswith('PC-OD-'))
        ecriture = EcritureComptable.objects.get(id=resp.data['id'])
        self.assertTrue(ecriture.est_equilibree)
        self.assertEqual(ecriture.lignes.count(), 2)

    def test_la_numerotation_est_sequentielle(self):
        premiere = self.api.post(
            '/api/django/compta/ecritures/', self._corps(), format='json')
        seconde = self.api.post(
            '/api/django/compta/ecritures/', self._corps(), format='json')
        self.assertNotEqual(premiere.data['reference'],
                            seconde.data['reference'])

    def test_une_reference_fournie_est_respectee(self):
        """Non-régression : le comportement historique ne bouge pas."""
        resp = self.api.post(
            '/api/django/compta/ecritures/',
            self._corps(reference='OD-MAISON-7'), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['reference'], 'OD-MAISON-7')

    def test_apercu_du_prochain_numero_ne_cree_rien(self):
        avant = EcritureComptable.objects.filter(company=self.co).count()
        resp = self.api.get('/api/django/compta/ecritures/prochain-numero/',
                            {'journal': self.journal.id})
        self.assertEqual(resp.status_code, 200, resp.content)
        # `detail` est le canal d'ERREUR de cette vue : il figure au contrat
        # (la garde `check_api_shapes` unifie toutes les branches) mais la
        # réponse de SUCCÈS ne le porte pas.
        exemple = contrat('ecriture_prochain_numero')
        self.assertEqual(sorted(set(exemple) - {'detail'}), sorted(resp.data))
        self.assertIsNone(exemple['detail'])
        self.assertEqual(resp.data['journal_code'], 'OD')
        self.assertTrue(resp.data['reference'].startswith('PC-OD-'))
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), avant)

    def test_apercu_annonce_le_numero_REELLEMENT_attribue(self):
        apercu = self.api.get('/api/django/compta/ecritures/prochain-numero/',
                              {'journal': self.journal.id}).data['reference']
        creee = self.api.post(
            '/api/django/compta/ecritures/', self._corps(), format='json')
        self.assertEqual(creee.data['reference'], apercu)

    def test_apercu_sans_journal_est_un_400_francais(self):
        resp = self.api.get('/api/django/compta/ecritures/prochain-numero/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('journal', resp.data['detail'])
        # L'erreur ne rend QUE `detail` : jamais un numéro partiel.
        self.assertEqual(
            sorted(resp.data),
            sorted(set(contrat('ecriture_prochain_numero', 'exemple_erreur'))
                   - {'pourquoi'}))

    def test_apercu_journal_d_une_autre_societe_est_un_404(self):
        autre = make_company('audv03-od-autre', 'AUDV03 OD Autre')
        services.seed_journaux(autre)
        journal_autre = Journal.objects.filter(company=autre, code='OD').first()
        resp = self.api.get('/api/django/compta/ecritures/prochain-numero/',
                            {'journal': journal_autre.id})
        self.assertEqual(resp.status_code, 404)


class PostageDotationEtalementTests(TestCase):
    """DRAFT165-35 — l'échéancier XACC15 s'étale enfin au grand livre."""

    def setUp(self):
        self.co = make_company('audv03-cca', 'AUDV03 CCA')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv03-cca-user')
        self.api = auth(self.user)
        self.charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('12000'),
            date_debut=date(2026, 1, 1), nb_mois=12,
            libelle='Assurance annuelle', user=self.user)
        self.dotation = self.charge.dotations.order_by('numero').first()

    def _url(self, charge=None):
        return (f'/api/django/compta/charges-avance/'
                f'{(charge or self.charge).id}/poster-dotation/')

    def test_postage_ecriture_equilibree_et_forme_du_contrat(self):
        resp = self.api.post(
            self._url(), {'dotation': self.dotation.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(sorted(contrat('dotation_etalement_poster')),
                         sorted(resp.data))
        self.assertTrue(resp.data['posted'])
        ecriture = EcritureComptable.objects.get(id=resp.data['ecriture_id'])
        self.assertTrue(ecriture.est_equilibree)
        # Débit du compte de charge, crédit 3491 (charges constatées d'avance).
        self.assertEqual(
            ecriture.lignes.get(compte__numero='3491').credit,
            Decimal(self.dotation.montant))

    def test_re_post_explicitement_refuse(self):
        self.api.post(self._url(), {'dotation': self.dotation.id},
                      format='json')
        second = self.api.post(
            self._url(), {'dotation': self.dotation.id}, format='json')
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn('déjà postée', second.data['detail'])

    def test_dotation_d_une_autre_charge_refusee(self):
        autre = services.etaler_charge_avance(
            self.co, montant_total=Decimal('600'),
            date_debut=date(2026, 1, 1), nb_mois=6, libelle='Loyer',
            user=self.user)
        etrangere = autre.dotations.order_by('numero').first()
        resp = self.api.post(
            self._url(), {'dotation': etrangere.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_scopee_par_societe(self):
        autre_co = make_company('audv03-cca-autre', 'AUDV03 CCA Autre')
        services.seed_plan_comptable(autre_co)
        services.seed_journaux(autre_co)
        charge_autre = services.etaler_charge_avance(
            autre_co, montant_total=Decimal('600'),
            date_debut=date(2026, 1, 1), nb_mois=6, libelle='Hors société')
        resp = self.api.post(
            self._url(charge_autre),
            {'dotation': charge_autre.dotations.first().id}, format='json')
        self.assertEqual(resp.status_code, 404)
