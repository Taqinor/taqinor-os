"""ZMKT6 — Bouton intelligent Participants d'une séquence + désinscription
manuelle.

Couvre : la vue liste les participants avec leur nœud courant et prochaine
échéance, la désinscription manuelle sort le participant, le compteur est
exact, tests multi-tenant.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import EtapeSequence, InscriptionSequence, SequenceRelance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ParticipantsSequenceTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt6', 'ZMKT6')
        self.seq = SequenceRelance.objects.create(company=self.co, nom='Seq')
        self.etape = EtapeSequence.objects.create(
            company=self.co, sequence=self.seq, ordre=1, delai_jours=3)

    def test_participants_liste_avec_prochaine_echeance(self):
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=1)
        participants = services.participants_sequence(self.seq)
        self.assertEqual(len(participants), 1)
        self.assertEqual(participants[0]['id'], insc.id)
        self.assertIsNotNone(participants[0]['prochaine_echeance'])

    def test_participants_filtrable_par_statut(self):
        insc1 = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=1)
        services.inscrire_lead_sequence(self.co, self.seq, lead_id=2)
        services.sortir_inscription(insc1, motif='manuel')
        actifs = services.participants_sequence(
            self.seq, statut=InscriptionSequence.Statut.ACTIF)
        self.assertEqual(len(actifs), 1)

    def test_desinscription_manuelle_sort_participant(self):
        insc = services.inscrire_lead_sequence(
            self.co, self.seq, lead_id=1)
        services.sortir_inscription(insc, motif='manuel')
        insc.refresh_from_db()
        self.assertEqual(insc.statut, InscriptionSequence.Statut.SORTI)
        self.assertEqual(insc.motif_sortie, 'manuel')

    def test_compteur_actifs_exact(self):
        services.inscrire_lead_sequence(self.co, self.seq, lead_id=1)
        services.inscrire_lead_sequence(self.co, self.seq, lead_id=2)
        insc3 = services.inscrire_lead_sequence(self.co, self.seq, lead_id=3)
        services.sortir_inscription(insc3, motif='manuel')
        self.assertEqual(services.nb_participants_actifs(self.seq), 2)

    def test_endpoint_participants(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        services.inscrire_lead_sequence(self.co, self.seq, lead_id=1)
        user = User.objects.create_user(
            username='zmkt6-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(
            f'/api/django/compta/sequences-relance/{self.seq.id}/participants/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['nb_actifs'], 1)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt6-b', 'ZMKT6-B')
        other_seq = SequenceRelance.objects.create(company=other, nom='OtherSeq')
        services.inscrire_lead_sequence(self.co, self.seq, lead_id=1)
        self.assertEqual(services.nb_participants_actifs(other_seq), 0)
