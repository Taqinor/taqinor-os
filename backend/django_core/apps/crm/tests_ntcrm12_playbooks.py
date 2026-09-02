"""NTCRM12 — Playbooks de vente par étape STAGES.py."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import (
    Lead, LeadPlaybookProgress, Playbook, PlaybookEtape, PlaybookTache,
)
from apps.crm.services import generer_playbook_progress
from apps.roles.models import Role

User = get_user_model()


class PlaybookProgressGenerationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM12', slug='taqinor-ntcrm12')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm12', password='x', company=self.company, role=self.role)
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook devis envoyé', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache_obligatoire = PlaybookTache.objects.create(
            etape=self.etape, libelle='Appeler le client', obligatoire=True, ordre=1)
        self.tache_optionnelle = PlaybookTache.objects.create(
            etape=self.etape, libelle='Envoyer une brochure', obligatoire=False, ordre=2)

    def test_lead_passant_a_quote_sent_genere_les_taches(self):
        lead = Lead.objects.create(company=self.company, nom='Lead QS', stage=stages.NEW)
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(len(created), 2)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 2)

    def test_generation_idempotente_rejouee_ne_duplique_pas(self):
        lead = Lead.objects.create(company=self.company, nom='Lead QS2', stage=stages.NEW)
        generer_playbook_progress(lead, stages.QUOTE_SENT)
        generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(lead=lead).count(), 2)

    def test_playbook_inactif_ne_genere_rien(self):
        self.playbook.actif = False
        self.playbook.save(update_fields=['actif'])
        lead = Lead.objects.create(company=self.company, nom='Lead inactif', stage=stages.NEW)
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(created, [])


class PlaybookEndToEndApiTests(TestCase):
    """Chaîne complète : PATCH stage sur /crm/leads/{id}/ → signal
    lead_stage_changed → génération auto → cocher via leads/{id}/playbook/."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM12 E2E', slug='taqinor-ntcrm12-e2e')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm12_e2e', password='x', company=self.company, role=self.role)
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook E2E', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache = PlaybookTache.objects.create(
            etape=self.etape, libelle='Confirmer réception devis', obligatoire=True, ordre=1)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead E2E', stage=stages.NEW)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_changement_stage_via_api_genere_puis_cocher_tache(self):
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/', {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = self.client_api.get(
            f'/api/django/crm/leads/{self.lead.pk}/playbook/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        progress_id = resp.data[0]['id']
        self.assertFalse(resp.data[0]['fait'])

        resp = self.client_api.post(
            f'/api/django/crm/leads/{self.lead.pk}/playbook/',
            {'tache': self.tache.pk, 'fait': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        progress = LeadPlaybookProgress.objects.get(pk=progress_id)
        self.assertTrue(progress.fait)
        self.assertEqual(progress.fait_par, self.user)
        self.assertIsNotNone(progress.fait_le)

    def test_changement_stage_non_bloque_meme_avec_taches_obligatoires(self):
        # Le changement de stage réussit MÊME si aucune tâche n'est cochée —
        # jamais un blocage dur (playbook.bloquant=False par défaut).
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/', {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)


class PlaybookEnfantsScopeTests(TestCase):
    """CRX14 — étapes et tâches de playbook : le 500 est réparé et la
    frontière société passe par le playbook parent.

    ``PlaybookEtape``/``PlaybookTache`` n'ont pas de champ ``company`` : le
    ``get_queryset`` hérité filtrait sur ``company`` (``FieldError`` → 500)
    AVANT d'atteindre le re-scope ``playbook__company`` — aucune lecture d'un
    objet existant, aucun update, aucun delete ne fonctionnait.
    """

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX14', slug='taqinor-crx14')
        self.autre = Company.objects.create(
            nom='Taqinor CRX14 autre', slug='taqinor-crx14-autre')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_crx14', password='x', company=self.company,
            role=self.role)

        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook maison', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache = PlaybookTache.objects.create(
            etape=self.etape, libelle='Appeler', obligatoire=True, ordre=1)

        self.playbook_autre = Playbook.objects.create(
            company=self.autre, nom='Playbook voisin', actif=True)
        self.etape_autre = PlaybookEtape.objects.create(
            playbook=self.playbook_autre, stage=stages.QUOTE_SENT, ordre=1)
        self.tache_autre = PlaybookTache.objects.create(
            etape=self.etape_autre, libelle='Voisine', ordre=1)

        self.api = APIClient()
        self.api.force_authenticate(self.user)

    @staticmethod
    def _ids(data):
        rows = data.get('results') if isinstance(data, dict) else data
        return [row['id'] for row in rows]

    # ── Le 500 réparé (rouge avant CRX14) ───────────────────────────────────

    def test_liste_etapes_repond_200_et_ne_montre_que_sa_societe(self):
        resp = self.api.get('/api/django/crm/playbook-etapes/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        ids = self._ids(resp.data)
        self.assertIn(self.etape.pk, ids)
        self.assertNotIn(self.etape_autre.pk, ids)

    def test_liste_taches_repond_200_et_ne_montre_que_sa_societe(self):
        resp = self.api.get('/api/django/crm/playbook-taches/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        ids = self._ids(resp.data)
        self.assertIn(self.tache.pk, ids)
        self.assertNotIn(self.tache_autre.pk, ids)

    def test_patch_etape_fonctionne(self):
        resp = self.api.patch(
            f'/api/django/crm/playbook-etapes/{self.etape.pk}/', {'ordre': 5})
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.ordre, 5)

    def test_patch_tache_fonctionne(self):
        resp = self.api.patch(
            f'/api/django/crm/playbook-taches/{self.tache.pk}/',
            {'libelle': 'Rappeler'})
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.libelle, 'Rappeler')

    def test_delete_tache_fonctionne(self):
        resp = self.api.delete(
            f'/api/django/crm/playbook-taches/{self.tache.pk}/')
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', resp))
        self.assertFalse(
            PlaybookTache.objects.filter(pk=self.tache.pk).exists())

    # ── Isolation société ───────────────────────────────────────────────────

    def test_etape_autre_societe_invisible_et_non_modifiable(self):
        url = f'/api/django/crm/playbook-etapes/{self.etape_autre.pk}/'
        self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(self.api.patch(url, {'ordre': 9}).status_code, 404)
        self.assertEqual(self.api.delete(url).status_code, 404)
        self.etape_autre.refresh_from_db()
        self.assertEqual(self.etape_autre.ordre, 1)

    def test_tache_autre_societe_invisible_et_non_modifiable(self):
        url = f'/api/django/crm/playbook-taches/{self.tache_autre.pk}/'
        self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(
            self.api.patch(url, {'libelle': 'Piratée'}).status_code, 404)
        self.assertEqual(self.api.delete(url).status_code, 404)
        self.tache_autre.refresh_from_db()
        self.assertEqual(self.tache_autre.libelle, 'Voisine')

    # ── Validation du parent à l'écriture ───────────────────────────────────

    def test_creation_etape_sur_playbook_etranger_refusee(self):
        resp = self.api.post('/api/django/crm/playbook-etapes/', {
            'playbook': self.playbook_autre.pk,
            'stage': stages.FOLLOW_UP, 'ordre': 2,
        })
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        # Le refus vient bien de la garde de parent (et non d'une unicité
        # fortuite) : le couple (playbook voisin, FOLLOW_UP) n'existe pas.
        self.assertIn('playbook', resp.data)
        self.assertFalse(
            PlaybookEtape.objects.filter(
                playbook=self.playbook_autre, stage=stages.FOLLOW_UP).exists())

    def test_creation_tache_sur_etape_etrangere_refusee(self):
        resp = self.api.post('/api/django/crm/playbook-taches/', {
            'etape': self.etape_autre.pk, 'libelle': 'Injectée', 'ordre': 2,
        })
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertIn('etape', resp.data)
        self.assertFalse(
            PlaybookTache.objects.filter(libelle='Injectée').exists())

    def test_patch_ne_peut_pas_deplacer_une_etape_vers_un_playbook_etranger(self):
        # Étape cible SIGNED : le couple (playbook voisin, SIGNED) n'existe
        # pas, donc l'unicité (playbook, stage) passe et c'est bien la garde de
        # parent qui refuse.
        resp = self.api.patch(
            f'/api/django/crm/playbook-etapes/{self.etape.pk}/',
            {'playbook': self.playbook_autre.pk, 'stage': stages.SIGNED})
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertIn('playbook', resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.playbook_id, self.playbook.pk)
        self.assertEqual(self.etape.stage, stages.QUOTE_SENT)

    def test_creation_legitime_reste_possible(self):
        resp = self.api.post('/api/django/crm/playbook-etapes/', {
            'playbook': self.playbook.pk,
            'stage': stages.FOLLOW_UP, 'ordre': 2,
        })
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        etape_id = resp.data['id']
        resp = self.api.post('/api/django/crm/playbook-taches/', {
            'etape': etape_id, 'libelle': 'Relancer', 'ordre': 1,
        })
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
