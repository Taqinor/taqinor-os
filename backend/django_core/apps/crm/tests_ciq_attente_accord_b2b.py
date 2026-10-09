"""CIQ508 — « En attente d'un accord » rendu B2B : raison typée OBLIGATOIRE,
étiquette par raison, notes neutres pour les pros.

On ÉTEND AGR520 (rien n'est construit deux fois) : même veille que « Plus
tard », mêmes cadences, même date obligatoire ; en plus, la RAISON de
l'attente (liste fermée du contrat CIQ10) pose l'étiquette de la raison,
s'écrit dans l'historique et — au-delà d'un mois — dans la note de la
première touche du réveil daté. Aucune étape de STAGES.py, aucun barreau,
aucune colonne « période de décision ».

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.parcours_suivi_outils import refus_variantes_segment, table
from apps.crm.services import (
    RAISONS_ATTENTE, TAG_ATTENTE_ACCORD, calculer_echeances_cadence)
from apps.crm.views import _DEFAULT_TAGS
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
J10 = (MERCREDI + datetime.timedelta(days=10)).date()
J60 = (MERCREDI + datetime.timedelta(days=60)).date()

TAGS = {
    'direction': 'Attend la direction / le comité',
    'financement': "Attend la banque / l'organisme de financement",
    'bailleur_murs': 'Attend le bailleur des murs',
    'budget_exercice': "Budget de l'exercice suivant",
    'consultation': 'Consultation en cours',
    'administration': TAG_ATTENTE_ACCORD,
}


class _Base(TestCase):
    slug = 'ciq508'
    segment = 'industriel'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CIQ508 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Usine', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000508',
            whatsapp='+212661000508', type_installation=self.segment)
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', MERCREDI, gabarits=gabarits)
        gabarit, echeance = next(
            (g, e) for g, e in echeances if g.ordre == 4)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', cadence_depart=MERCREDI)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _attente(self, **corps):
        corps.setdefault('rappel_heure', '11:00')
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/fait/',
            {'reponse': 'attente_accord', **corps}, format='json')


class RaisonObligatoireTests(_Base):
    slug = 'ciq508-raison'

    def test_a_sans_raison_400_nomme_le_champ(self):
        resp = self._attente(rappel_le=J10.isoformat())
        self.assertEqual(resp.status_code, 400)
        self.assertIn('raison_attente', resp.data['erreurs'])
        self.lead.refresh_from_db()
        for etiquette in TAGS.values():
            self.assertNotIn(etiquette, self.lead.tags or '')
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_b_raison_inconnue_400_liste_les_valeurs(self):
        resp = self._attente(rappel_le=J10.isoformat(),
                             raison_attente='famille')
        self.assertEqual(resp.status_code, 400)
        message = resp.data['erreurs']['raison_attente']
        self.assertIn('raison_attente', message)
        for valeur in TAGS:
            self.assertIn(valeur, message)

    def test_la_liste_du_serveur_est_celle_du_contrat(self):
        import json
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).parent / 'contract_samples'
             / 'relance_etape_v2.json').read_text(encoding='utf-8'))
        self.assertEqual(
            [r[0] for r in RAISONS_ATTENTE],
            contrat['ajout_ciq10_raison_attente']['raisons'])


class EtiquetteParRaisonTests(_Base):
    slug = 'ciq508-etiquette'

    def test_c_direction_a_j10_etiquette_de_la_raison_meme_touche(self):
        resp = self._attente(rappel_le=J10.isoformat(),
                             raison_attente='direction')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIn('Attend la direction / le comité', self.lead.tags)
        self.assertNotIn(TAG_ATTENTE_ACCORD, self.lead.tags)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.etape.ordre, 4)
        self.assertGreaterEqual(self.etape.due_date, J10)
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE, due_date__lt=J10).exists())
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_chaque_raison_pose_son_etiquette_seedee(self):
        for valeur, _libelle, etiquette in RAISONS_ATTENTE:
            self.assertEqual(etiquette, TAGS[valeur], valeur)
            self.assertIn(etiquette, _DEFAULT_TAGS, valeur)

    def test_l_historique_dit_la_raison_et_la_date(self):
        self._attente(rappel_le=J10.isoformat(), raison_attente='financement')
        ligne = LeadActivity.objects.filter(
            lead=self.lead, outcome='rappel').get()
        self.assertIn(
            "En attente d'un accord — La banque / l'organisme de financement"
            f" — rappel le {J10:%d/%m}", ligne.body)

    def test_changer_de_raison_remplace_l_etiquette(self):
        self._attente(rappel_le=J10.isoformat(), raison_attente='direction')
        # La touche (déplacée) reste à faire : une seconde réponse change la
        # raison — le dossier n'attend qu'une chose à la fois.
        self._attente(rappel_le=J10.isoformat(), raison_attente='bailleur_murs')
        self.lead.refresh_from_db()
        self.assertIn('Attend le bailleur des murs', self.lead.tags)
        self.assertNotIn('Attend la direction / le comité', self.lead.tags)


class ReveilDateTests(_Base):
    slug = 'ciq508-reveil'

    def test_d_a_j60_reveil_date_appel_note_porte_la_raison_jamais_froid(self):
        resp = self._attente(rappel_le=J60.isoformat(),
                             raison_attente='budget_exercice')
        self.assertEqual(resp.status_code, 200, resp.data)
        reveil = (self.lead.relance_etapes
                  .filter(cadence='reveil',
                          statut=RelanceEtape.Statut.A_FAIRE)
                  .order_by('due_at').first())
        self.assertIsNotNone(reveil)
        self.assertEqual(reveil.canal, RelanceEtape.Canal.APPEL)
        self.assertGreaterEqual(reveil.due_date, J60)
        self.assertIn("Rappel convenu — Le budget de l'exercice suivant",
                      reveil.note)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertIn("Budget de l'exercice suivant", self.lead.tags)

    def test_a_j10_aucune_note_de_rappel_convenu_ailleurs(self):
        self._attente(rappel_le=J10.isoformat(), raison_attente='direction')
        self.assertFalse(self.lead.relance_etapes.filter(
            note__startswith='Rappel convenu').exists())


class AgricoleAdministrationTests(_Base):
    """(e) Agricole + ``administration`` ⇒ le comportement d'AGR520."""

    slug = 'ciq508-agr'
    segment = 'agricole'

    def test_e_agricole_administration_comme_agr520(self):
        resp = self._attente(rappel_le=J10.isoformat(),
                             raison_attente='administration')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIn(TAG_ATTENTE_ACCORD, self.lead.tags)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.etape.ordre, 4)
        self.assertGreaterEqual(self.etape.due_date, J10)
        self.assertEqual(self.lead.stage, stages.CONTACTED)


class DecisionAPlusieursNotesTests(TestCase):
    """(f) ``decision_famille`` / ``decision_proprietaire`` : notes NEUTRES
    sur un lead commercial ou industriel, inchangées ailleurs."""

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CIQ508 Decision', slug='ciq508-decision')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='ciq508-decision-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _repondre(self, segment, reponse, rang):
        lead = Lead.objects.create(
            company=self.company, nom=f'L{rang}', stage=stages.CONTACTED,
            owner=self.acteur, telephone=f'+2126610005{rang:02d}',
            type_installation=segment)
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=1,
            due_at=MERCREDI, due_date=MERCREDI.date(), canal='whatsapp',
            libelle='Le PDF s\'ouvre bien ?', template_cle='j1_pdf')
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'reponse': reponse}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        return etape.note

    def test_f_industriel_et_commercial_notes_neutres(self):
        for rang, segment in enumerate(('industriel', 'commercial')):
            famille = self._repondre(segment, 'decision_famille', rang)
            self.assertIn('direction / associés', famille)
            self.assertNotIn('famille', famille)
            proprietaire = self._repondre(
                segment, 'decision_proprietaire', rang + 10)
            self.assertIn('bailleur des murs', proprietaire)
            self.assertNotIn('propriétaire décide', proprietaire)

    def test_f_residentiel_et_agricole_inchanges_octet_pour_octet(self):
        for rang, segment in enumerate(('residentiel', 'agricole', '')):
            famille = self._repondre(segment, 'decision_famille', 20 + rang)
            self.assertEqual(
                famille, services.REPONSES_TOUCHE['decision_famille']['note'])
            proprietaire = self._repondre(
                segment, 'decision_proprietaire', 30 + rang)
            self.assertEqual(
                proprietaire,
                services.REPONSES_TOUCHE['decision_proprietaire']['note'])


class TableDuParcoursTests(SimpleTestCase):
    def test_attente_accord_porte_la_raison_et_les_variantes_pro(self):
        modele = table()['modeles']['attente_accord']
        self.assertTrue(modele['raison'])
        self.assertEqual([r['valeur'] for r in modele['raisons']],
                         [r[0] for r in RAISONS_ATTENTE])
        for segment in ('commercial', 'industriel'):
            variante = modele['variantes_segment'][segment]
            self.assertEqual(variante['label'], "En attente d'un accord")
            self.assertEqual(variante['message'], 'attente_accord_accuse')
        self.assertEqual(refus_variantes_segment(modele), [])

    def test_variantes_pro_des_decisions_et_du_geste_piece_recue(self):
        t = table()
        for segment in ('commercial', 'industriel'):
            self.assertEqual(
                t['modeles']['decision_famille']['variantes_segment'][
                    segment]['label'],
                'Décision à plusieurs — direction / associés')
            self.assertEqual(
                t['modeles']['decision_proprietaire']['variantes_segment'][
                    segment]['label'],
                'Décision à plusieurs — bailleur / propriétaire des murs')
        geste = next(g for g in t['gestes'] if g['id'] == 'piece_recue')
        for segment in ('commercial', 'industriel'):
            self.assertIn(
                'ses factures ou relevés, un schéma électrique ou les pièces '
                'de la société',
                geste['variantes_segment'][segment]['effet'])
        # « Dimanche famille » reste le libellé du gabarit (CAD124).
        self.assertEqual(refus_variantes_segment(geste), [])

    def test_une_variante_ne_peut_pas_changer_la_cle_serveur(self):
        self.assertTrue(refus_variantes_segment(
            {'variantes_segment': {'commercial': {'reponse': 'plus_tard'}}}))
        self.assertTrue(refus_variantes_segment(
            {'variantes_segment': {'commercial': {'message': 'inconnu'}}}))
        self.assertEqual(refus_variantes_segment(
            {'variantes_segment': {'commercial': {
                'message': 'attente_accord_accuse'}}}), [])


class ValiditeARenouvelerTests(_Base):
    """CIQ512 — une décision attendue APRÈS la validité (même prolongée par
    CIQ510) pose UNE étape manuelle datée au jour de la validité ; aucun
    statut de devis ni étape de lead ne change (la bascule QJ5 reste seule)."""

    slug = 'ciq512-validite'

    def setUp(self):
        super().setUp()
        from decimal import Decimal
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        profil = CompanyProfile.objects.get(company=self.company)
        profil.quote_validity_days = 30
        profil.save(update_fields=['quote_validity_days'])
        client = Client.objects.create(
            company=self.company, nom='Usine', email='ciq512@example.test')
        self.validite = (MERCREDI + datetime.timedelta(days=30)).date()
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ512-0010',
            client=client, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20'), date_envoi=MERCREDI,
            date_validite=self.validite)
        self.libelle = 'Validité à renouveler — DEV-CIQ512-0010'

    def test_a_attente_j60_validite_j30_une_etape_datee_j30(self):
        resp = self._attente(rappel_le=J60.isoformat(),
                             raison_attente='direction')
        self.assertEqual(resp.status_code, 200, resp.data)
        etapes = self.lead.relance_etapes.filter(libelle=self.libelle)
        self.assertEqual(etapes.count(), 1)
        etape = etapes.get()
        self.assertEqual(etape.due_date, self.validite)
        self.assertEqual(etape.cadence, 'generique')
        # ACRM45 — l'étape porte désormais sa clé STABLE (retrouvée et
        # recalée par elle, jamais par son libellé).
        self.assertEqual(etape.cle, 'validite_a_renouveler')
        self.assertEqual(
            etape.note,
            f'La proposition DEV-CIQ512-0010 expire le '
            f'{self.validite:%d/%m}, avant la décision attendue le '
            f'{J60:%d/%m} : prévenez le client ; après expiration, '
            '« Renouveler » crée une nouvelle version que vous re-tarifez')

    def test_b_attente_j10_aucune_etape(self):
        self._attente(rappel_le=J10.isoformat(), raison_attente='direction')
        self.assertFalse(
            self.lead.relance_etapes.filter(libelle=self.libelle).exists())

    def test_c_rejouer_une_seule_etape(self):
        from apps.crm.services import poser_etape_validite_a_renouveler
        self._attente(rappel_le=J60.isoformat(), raison_attente='direction')
        poser_etape_validite_a_renouveler(self.lead, J60)
        poser_etape_validite_a_renouveler(self.lead, J60)
        self.assertEqual(
            self.lead.relance_etapes.filter(libelle=self.libelle).count(), 1)

    def test_d_le_devis_reste_envoye_et_l_etape_du_lead_ne_bouge_pas(self):
        self._attente(rappel_le=J60.isoformat(), raison_attente='direction')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')
        self.assertEqual(self.devis.date_validite, self.validite)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
