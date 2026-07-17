"""XMKT1 — Moteur d'exécution réel des séquences de relance.

Couvre : inscription (idempotente, une seule inscription active par lead),
exécution des étapes dues (J+delai), sortie automatique sur devis
accepté/refusé (via ``core.events``), isolation multi-tenant.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import (
    EtapeSequence, ExecutionEtapeSequence, InscriptionSequence,
    SequenceRelance,
)
from core.events import devis_accepted, devis_refused

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


class _FakeDevis:
    """Objet minimal portant les attributs lus par le récepteur compta.

    ``pk`` est présent mais ``None`` : un stub non persisté n'a pas de clé
    primaire. Les récepteurs abonnés au signal PARTAGÉ ``devis_accepted`` /
    ``devis_refused`` gardent ce cas (``getattr(devis, 'pk', None) is None`` →
    no-op) ; exposer l'attribut évite un ``AttributeError`` chez un récepteur
    qui lirait ``devis.pk`` directement, sans changer la sémantique « aucun
    vrai devis » du stub.
    """
    def __init__(self, company, lead_id):
        self.company = company
        self.lead_id = lead_id
        self.statut = 'accepte'
        self.pk = None


def make_sequence(co, stage_declencheur=''):
    seq = SequenceRelance.objects.create(
        company=co, nom='Drip', stage_declencheur=stage_declencheur)
    EtapeSequence.objects.create(
        company=co, sequence=seq, ordre=1, delai_jours=0,
        canal=EtapeSequence.Canal.WHATSAPP)
    EtapeSequence.objects.create(
        company=co, sequence=seq, ordre=2, delai_jours=3,
        canal=EtapeSequence.Canal.EMAIL)
    return seq


class InscriptionSequenceTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt1', 'XMKT1')
        self.user = make_user(self.co, 'xmkt1-user')

    def test_inscription_pointe_premiere_etape(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(
            self.co, seq, lead_id=42, lead_reference='Lead 42')
        self.assertEqual(insc.statut, InscriptionSequence.Statut.ACTIF)
        self.assertEqual(insc.etape_courante.ordre, 1)

    def test_inscription_idempotente(self):
        seq = make_sequence(self.co)
        insc1 = services.inscrire_lead_sequence(self.co, seq, lead_id=1)
        insc2 = services.inscrire_lead_sequence(self.co, seq, lead_id=1)
        self.assertEqual(insc1.id, insc2.id)
        self.assertEqual(
            InscriptionSequence.objects.filter(
                sequence=seq, lead_id=1).count(), 1)

    def test_inscrire_leads_pour_stage_ne_declenche_que_les_sequences_actives(self):
        seq_matching = make_sequence(self.co, stage_declencheur='QUOTE_SENT')
        seq_other = make_sequence(self.co, stage_declencheur='NEW')
        inscriptions = services.inscrire_leads_pour_stage(
            self.co, 'QUOTE_SENT', lead_id=7, lead_reference='Lead 7')
        self.assertEqual(len(inscriptions), 1)
        self.assertEqual(inscriptions[0].sequence_id, seq_matching.id)
        self.assertFalse(
            InscriptionSequence.objects.filter(sequence=seq_other).exists())

    def test_executer_etapes_dues_execute_puis_avance(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(self.co, seq, lead_id=2)
        # J0 : la première étape est due immédiatement.
        executions = services.executer_etapes_dues(self.co)
        self.assertEqual(len(executions), 1)
        insc.refresh_from_db()
        self.assertEqual(insc.etape_courante.ordre, 2)
        self.assertEqual(insc.statut, InscriptionSequence.Statut.ACTIF)
        self.assertEqual(
            ExecutionEtapeSequence.objects.filter(inscription=insc).count(), 1)

        # Pas encore J+3 : rien de nouveau à exécuter.
        executions_trop_tot = services.executer_etapes_dues(self.co)
        self.assertEqual(len(executions_trop_tot), 0)

        # À J+3, la deuxième (dernière) étape s'exécute et termine l'inscription.
        plus_tard = timezone.now() + timedelta(days=3, minutes=1)
        executions_j3 = services.executer_etapes_dues(self.co, maintenant=plus_tard)
        self.assertEqual(len(executions_j3), 1)
        insc.refresh_from_db()
        self.assertIsNone(insc.etape_courante)
        self.assertEqual(insc.statut, InscriptionSequence.Statut.TERMINE)

    def test_sortie_automatique_sur_devis_accepte(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(self.co, seq, lead_id=9)
        devis = _FakeDevis(self.co, lead_id=9)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        insc.refresh_from_db()
        self.assertEqual(insc.statut, InscriptionSequence.Statut.SORTI)
        self.assertEqual(insc.motif_sortie, 'devis_accepte')

    def test_sortie_automatique_sur_devis_refuse(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(self.co, seq, lead_id=11)
        devis = _FakeDevis(self.co, lead_id=11)
        devis_refused.send(
            sender=None, devis=devis, user=self.user, motif_refus='prix')
        insc.refresh_from_db()
        self.assertEqual(insc.statut, InscriptionSequence.Statut.SORTI)
        self.assertEqual(insc.motif_sortie, 'devis_refuse')

    def test_sortie_manuelle_idempotente(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(self.co, seq, lead_id=13)
        services.sortir_inscription(insc, motif='desinscription')
        services.sortir_inscription(insc, motif='autre_motif')
        insc.refresh_from_db()
        # Le second appel ne doit rien changer (déjà sorti).
        self.assertEqual(insc.motif_sortie, 'desinscription')

    def test_etape_executee_hors_integration_reste_planifiee_noop(self):
        seq = make_sequence(self.co)
        services.inscrire_lead_sequence(self.co, seq, lead_id=3)
        # Épingle `maintenant` à DEMAIN midi UTC : (1) dans la fenêtre ouvrée
        # 08h-20h (sinon l'étape WhatsApp J0 est rejetée « hors_fenetre »,
        # silence nuit/fériés XMKT7), ET (2) TOUJOURS après la création de
        # l'inscription (aujourd'hui) — sinon, si la suite tourne l'après-midi,
        # midi-aujourd'hui serait AVANT l'inscription et l'étape J0 ne serait
        # pas encore due → liste vide (IndexError). Ce test porte sur l'ABSENCE
        # d'intégration WhatsApp/Brevo, pas sur l'heure réelle de la CI.
        # … et (3) un JOUR OUVRÉ : « demain » nu tombait le samedi chaque
        # vendredi (et la veille des fériés) → rejet hors_fenetre au lieu de
        # planifie — test flaky par date, corrigé en avançant jusqu'au
        # prochain jour ouvré via le MÊME sélecteur que le code testé.
        from apps.notifications.selectors import est_hors_fenetre_silence
        maintenant = (timezone.now() + timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0)
        for _ in range(14):
            if not est_hors_fenetre_silence(maintenant, self.co):
                break
            maintenant += timedelta(days=1)
        executions = services.executer_etapes_dues(self.co, maintenant=maintenant)
        self.assertEqual(executions[0].resultat, 'planifie')
        self.assertEqual(executions[0].erreur, '')

    def test_isolation_multi_tenant(self):
        co2 = make_company('xmkt1-b', 'XMKT1-B')
        seq1 = make_sequence(self.co)
        seq2 = make_sequence(co2)
        services.inscrire_lead_sequence(self.co, seq1, lead_id=5)
        services.inscrire_lead_sequence(co2, seq2, lead_id=5)
        exec_co1 = services.executer_etapes_dues(self.co)
        self.assertEqual(len(exec_co1), 1)
        self.assertEqual(exec_co1[0].company_id, self.co.id)


class InscriptionSequenceApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt1-api', 'XMKT1 API')
        self.user = make_user(self.co, 'xmkt1-api-user')

    def test_inscrire_endpoint_scope_company(self):
        seq = make_sequence(self.co)
        api = auth(self.user)
        resp = api.post('/api/django/compta/inscriptions-sequence/inscrire/', {
            'sequence': seq.id, 'lead_id': 21, 'lead_reference': 'Lead 21',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        insc = InscriptionSequence.objects.get(id=resp.data['id'])
        self.assertEqual(insc.company_id, self.co.id)

    def test_inscrire_sequence_dune_autre_societe_404(self):
        other = make_company('xmkt1-other', 'Other')
        seq = make_sequence(other)
        api = auth(self.user)
        resp = api.post('/api/django/compta/inscriptions-sequence/inscrire/', {
            'sequence': seq.id, 'lead_id': 22,
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_sortir_endpoint(self):
        seq = make_sequence(self.co)
        insc = services.inscrire_lead_sequence(self.co, seq, lead_id=23)
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/inscriptions-sequence/{insc.id}/sortir/',
            {'motif': 'desinscription'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], InscriptionSequence.Statut.SORTI)

    def test_trace_visible_via_endpoint(self):
        seq = make_sequence(self.co)
        services.inscrire_lead_sequence(self.co, seq, lead_id=24)
        services.executer_etapes_dues(self.co)
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/inscriptions-sequence/?sequence={seq.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]['executions']), 1)
