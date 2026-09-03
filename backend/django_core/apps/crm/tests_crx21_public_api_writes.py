"""CRX21 — l'API publique d'écriture atteint la parité du PATCH de l'écran.

``update_lead_from_public_api`` écrivait ``Lead`` sans AUCUNE des gardes ni
aucun des effets de ``LeadViewSet.perform_update`` :

  * un lead PERDU pouvait changer d'étape par une intégration, alors que le
    ``LeadSerializer`` le refuse depuis toujours ;
  * une intégration pouvait RECULER ou ROUVRIR un pipeline (SIGNED → NEW) ;
  * aucun des 4 effets (émission ``lead_stage_changed``, ``first_contacted_at``
    FG28, recalcul du score QJ6, activité de relance) ne partait ;
  * un changement de téléphone/email n'était PAS répercuté sur les colonnes
    indexées ``phone_normalise``/``email_normalise`` — la dédup QW10 restait
    aveugle : le lead se retrouvait sous son ANCIEN numéro et introuvable sous
    le nouveau (chemins publicapi bulk ET PATCH unitaire).
"""
from django.test import TestCase

from apps.crm import stages
from apps.crm.models import (
    Lead, LeadPlaybookProgress, Playbook, PlaybookEtape, PlaybookTache,
)
from apps.crm.services import (
    find_duplicates_by_contact, normalize_email, normalize_phone,
    update_lead_from_public_api,
)
from authentication.models import Company


class GardesEtapePublicApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX21 gardes', slug='taqinor-crx21-gardes')

    def _lead(self, **kwargs):
        params = {'company': self.company, 'nom': 'Lead CRX21'}
        params.update(kwargs)
        return Lead.objects.create(**params)

    def test_lead_perdu_refuse_le_changement_d_etape(self):
        lead = self._lead(stage=stages.CONTACTED, perdu=True)
        with self.assertRaises(ValueError) as ctx:
            update_lead_from_public_api(
                company=self.company, lead_id=lead.pk,
                fields={'stage': stages.QUOTE_SENT})
        self.assertIn('perdu', str(ctx.exception).lower())
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_lead_perdu_accepte_les_autres_champs(self):
        """Le verrou vise l'ÉTAPE, pas la fiche entière."""
        lead = self._lead(stage=stages.CONTACTED, perdu=True)
        update_lead_from_public_api(
            company=self.company, lead_id=lead.pk, fields={'ville': 'Agadir'})
        lead.refresh_from_db()
        self.assertEqual(lead.ville, 'Agadir')

    def test_recul_de_funnel_refuse(self):
        lead = self._lead(stage=stages.SIGNED)
        with self.assertRaises(ValueError) as ctx:
            update_lead_from_public_api(
                company=self.company, lead_id=lead.pk,
                fields={'stage': stages.NEW})
        self.assertIn('recule', str(ctx.exception).lower())
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)

    def test_avance_de_funnel_acceptee(self):
        lead = self._lead(stage=stages.NEW)
        update_lead_from_public_api(
            company=self.company, lead_id=lead.pk,
            fields={'stage': stages.QUOTE_SENT})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)

    def test_reactivation_depuis_froid_acceptee(self):
        """COLD est un PARKING : en sortir n'est pas un recul (_bulk_stage_allowed)."""
        lead = self._lead(stage=stages.COLD)
        update_lead_from_public_api(
            company=self.company, lead_id=lead.pk,
            fields={'stage': stages.CONTACTED})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_mise_au_parking_froid_acceptee(self):
        lead = self._lead(stage=stages.QUOTE_SENT)
        update_lead_from_public_api(
            company=self.company, lead_id=lead.pk, fields={'stage': stages.COLD})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)

    def test_meme_etape_ne_declenche_aucune_garde(self):
        lead = self._lead(stage=stages.SIGNED, perdu=True)
        update_lead_from_public_api(
            company=self.company, lead_id=lead.pk,
            fields={'stage': stages.SIGNED, 'ville': 'Safi'})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertEqual(lead.ville, 'Safi')

    def test_etape_inconnue_reste_refusee(self):
        lead = self._lead(stage=stages.NEW)
        with self.assertRaises(ValueError):
            update_lead_from_public_api(
                company=self.company, lead_id=lead.pk,
                fields={'stage': 'PAS_UNE_ETAPE'})


class EffetsInternesPublicApiTests(TestCase):
    """Les 4 effets de ``perform_update`` partent aussi depuis l'API publique."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX21 effets', slug='taqinor-crx21-effets')
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook CRX21', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache = PlaybookTache.objects.create(
            etape=self.etape, libelle='Relancer', obligatoire=True, ordre=1)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead effets', stage=stages.NEW)

    def test_emission_du_signal_declenche_le_playbook(self):
        self.assertFalse(
            LeadPlaybookProgress.objects.filter(lead=self.lead).exists())
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'stage': stages.QUOTE_SENT})
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(
                lead=self.lead, tache=self.tache).count(),
            1)

    def test_first_contacted_at_pose_a_la_sortie_de_new(self):
        self.assertIsNone(self.lead.first_contacted_at)
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'stage': stages.CONTACTED})
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_score_recalcule_et_persiste(self):
        from apps.crm.scoring import compute_score

        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'telephone': '0612345678', 'email': 'contact@exemple.ma',
                    'ville': 'Casablanca'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, compute_score(self.lead))

    def test_aucun_effet_quand_rien_ne_change(self):
        """Un appel qui n'écrit rien ne pose pas ``first_contacted_at``."""
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'stage': stages.NEW})
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.first_contacted_at)


class ColonnesDeriveesPublicApiTests(TestCase):
    """La dédup INDEXÉE (QW10) suit le téléphone/email écrits par l'API."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX21 dedup', slug='taqinor-crx21-dedup')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead dédup', stage=stages.NEW,
            telephone='0612345678', email='ancien@exemple.ma')

    def test_changement_de_telephone_met_a_jour_la_colonne_indexee(self):
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'telephone': '0700112233'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.phone_normalise, normalize_phone('0700112233'))

    def test_dedup_trouve_le_lead_sous_son_nouveau_numero(self):
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'telephone': '0700112233'})
        trouves = find_duplicates_by_contact(
            self.company, phone='+212 700 11 22 33')
        self.assertEqual([lead.pk for lead in trouves], [self.lead.pk])

    def test_dedup_ne_trouve_plus_le_lead_sous_l_ancien_numero(self):
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'telephone': '0700112233'})
        self.assertEqual(
            find_duplicates_by_contact(self.company, phone='0612345678'), [])

    def test_changement_d_email_met_a_jour_la_colonne_indexee(self):
        update_lead_from_public_api(
            company=self.company, lead_id=self.lead.pk,
            fields={'email': 'Nouveau@Exemple.MA'})
        self.lead.refresh_from_db()
        self.assertEqual(
            self.lead.email_normalise, normalize_email('Nouveau@Exemple.MA'))
        trouves = find_duplicates_by_contact(
            self.company, email='nouveau@exemple.ma')
        self.assertEqual([lead.pk for lead in trouves], [self.lead.pk])
