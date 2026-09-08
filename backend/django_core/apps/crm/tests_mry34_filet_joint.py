"""MRY34 — le filet « client joint » : jamais un lead SANS prochaine étape.

Le trou que ce fichier verrouille (incident du 07/09/2026) : marquer une
touche « joint » arrête la cadence de contact (MRY9), la clôture MRY11 est
DÉLIBÉRÉMENT sautée (on ne parque pas au froid un client qu'on vient de
joindre)… et rien ne posait de suite. Onze touches barrées « joint », plus
aucune prochaine étape : le lead le plus chaud du jour sortait de toutes les
files de relance.

Le filet : quand une issue de succès (« joint » / « intéressé ») laisse le
lead sans AUCUNE touche ouverte, une étape `generique` « envoyer le devis ou
fixer un rappel » est posée à demain. Si Meryem saisit une date de rappel en
marquant la touche, `reporter_prochaine_touche` déplace ce filet sur SA date.

RELANCE-SUITE (fondateur 08/09/2026, lead test1 aa) : la suite suit le CANAL
de la touche aboutie — message répondu → « appeler le client » ; appel fait →
« préparer et envoyer le devis » — et le plan après-devis ne démarre qu'à
l'ENVOI du devis (un brouillon jamais envoyé faisait sauter l'appel et
l'envoi : « je fais le devis, je l'envoie, PUIS vos étapes viennent »).
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    FILET_APPEL_LIBELLE, FILET_JOINT_LIBELLE, FILET_REFUS_LIBELLE,
    initialiser_plan_relance, marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry34'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _fait(self, etape, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            corps, format='json')

    def _filets(self):
        return self.lead.relance_etapes.filter(
            cadence='generique', libelle=FILET_JOINT_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE)


class FiletJointTests(_Base):
    slug = 'mry34-filet'

    def setUp(self):
        super().setUp()
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')

    def test_joint_pose_le_filet_quand_plus_rien_nest_ouvert(self):
        resp = self._fait(self.etapes[2], outcome='joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        filets = self._filets()
        self.assertEqual(filets.count(), 1)
        self.lead.refresh_from_db()
        # La prochaine étape du lead EST le filet — plus jamais un lead joint
        # sans `relance_date`.
        self.assertEqual(self.lead.relance_date, filets.get().due_date)
        self.assertNotEqual(self.lead.stage, stages.COLD)

    def test_le_filet_porte_une_note_chatter_systeme(self):
        self._fait(self.etapes[2], outcome='joint')
        notes = LeadActivity.objects.filter(
            lead=self.lead, user=None, kind=LeadActivity.Kind.NOTE,
            body__contains=FILET_JOINT_LIBELLE)
        self.assertEqual(notes.count(), 1)

    def test_une_date_de_rappel_saisie_deplace_le_filet(self):
        """« Rappelez-moi le… » saisi AVEC l'issue « joint » : avant MRY34,
        `reporter_prochaine_touche` ne trouvait plus aucune touche ouverte et
        le rappel demandé était PERDU en silence."""
        resp = self._fait(
            self.etapes[2], outcome='joint',
            rappel_le='2027-03-15', rappel_heure='10:00')
        self.assertEqual(resp.status_code, 200, resp.data)
        filets = self._filets()
        self.assertEqual(filets.count(), 1)
        self.assertEqual(filets.get().due_date, datetime.date(2027, 3, 15))

    def test_interesse_avec_apres_devis_ouvert_ne_pose_rien(self):
        """La cadence après devis continue (MRY9) : le lead A déjà une
        prochaine étape — le filet serait un doublon."""
        initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='apres_devis')
        self._fait(self.etapes[2], outcome='interesse')
        self.assertEqual(self._filets().count(), 0)

    def test_refus_pose_une_etape_de_decision_jamais_le_filet_joint(self):
        """QJ-INVARIANT : un refus ne pose jamais le filet « envoyer le
        devis » — mais le dossier ne disparaît pas : une étape « décider la
        suite » (perdu + motif, MRY22 — décision humaine) reste ouverte."""
        self._fait(self.etapes[2], outcome='refuse')
        self.assertEqual(self._filets().count(), 0)
        decisions = self.lead.relance_etapes.filter(
            cadence='generique', libelle=FILET_REFUS_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(decisions.count(), 1)

    def test_etape_generique_traitee_avec_devis_demarre_l_apres_devis(self):
        """Cas AR (07/09/2026) : le filet « envoyer le devis » coché — devis
        parti par WhatsApp, statut resté « brouillon » — doit DÉMARRER le
        vrai plan après-devis, jamais laisser zéro étape."""
        self._fait(self.etapes[2], outcome='joint')
        filet = self._filets().get()
        from apps.crm.models import Client as ClientCrm
        from apps.ventes.models import Devis
        client = ClientCrm.objects.create(
            company=self.company, nom='AR', email='mry34-ar@example.com')
        Devis.objects.create(
            company=self.company, reference='DEV-MRY34-0001', client=client,
            lead=self.lead, taux_tva=Decimal('20'))
        marquer_etape_relance(
            filet, self.acteur, RelanceEtape.Statut.FAIT,
            note='Devis envoyé par WhatsApp')
        apres = self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=RelanceEtape.Statut.A_FAIRE)
        self.assertGreater(apres.count(), 0)

    # ── RELANCE-SUITE (fondateur 08/09/2026) ───────────────────────────────
    def _touche(self, canal):
        return next(e for e in self.etapes if e.canal == canal)

    def _brouillon(self, reference):
        from apps.crm.models import Client as ClientCrm
        from apps.ventes.models import Devis
        client = ClientCrm.objects.create(
            company=self.company, nom=reference,
            email=f'{reference.lower()}@example.com')
        return Devis.objects.create(
            company=self.company, reference=reference, client=client,
            lead=self.lead, taux_tva=Decimal('20'),
            statut=Devis.Statut.BROUILLON)

    def _ouvertes(self, **filtre):
        return self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE, **filtre)

    def test_joint_sur_un_message_pose_un_appel_jamais_le_suivi_de_proposition(self):
        """Le client a RÉPONDU au WhatsApp d'identité (« appelez-moi ») alors
        qu'un devis BROUILLON existe : la suite est de L'APPELER — jamais le
        plan après-devis, jamais l'étape « envoyer le devis »."""
        self._brouillon('DEV-MRY34-BR1')
        resp = self._fait(
            self._touche(RelanceEtape.Canal.WHATSAPP), outcome='joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ouvertes(cadence='apres_devis').count(), 0)
        ouvertes = list(self._ouvertes())
        self.assertEqual(len(ouvertes), 1)
        appel = ouvertes[0]
        self.assertEqual(appel.libelle, FILET_APPEL_LIBELLE)
        self.assertEqual(appel.canal, RelanceEtape.Canal.APPEL)
        self.assertGreaterEqual(
            appel.due_date,
            timezone.now().astimezone(horaires.CASABLANCA).date())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertEqual(self.lead.relance_date, appel.due_date)

    def test_joint_sur_un_appel_pose_preparer_le_devis_meme_avec_un_brouillon(self):
        self._brouillon('DEV-MRY34-BR2')
        self._fait(self._touche(RelanceEtape.Canal.APPEL), outcome='joint')
        self.assertEqual(self._ouvertes(cadence='apres_devis').count(), 0)
        self.assertEqual(self._filets().count(), 1)

    def test_le_suivi_de_proposition_demarre_a_l_envoi_du_devis(self):
        """Message répondu → appel ; appel fait → « préparer et envoyer le
        devis » ; l'ENVOI du devis (acte explicite) démarre le plan
        après-devis et ferme l'étape « préparer et envoyer » sans objet."""
        devis = self._brouillon('DEV-MRY34-BR3')
        self._fait(self._touche(RelanceEtape.Canal.WHATSAPP), outcome='joint')
        appel = self._ouvertes(libelle=FILET_APPEL_LIBELLE).get()
        marquer_etape_relance(appel, self.acteur, RelanceEtape.Statut.FAIT)
        self.assertEqual(self._ouvertes(cadence='apres_devis').count(), 0)
        self.assertEqual(self._filets().count(), 1)
        from apps.ventes.services import mark_devis_sent
        mark_devis_sent(devis=devis, user=self.acteur)
        self.assertGreater(self._ouvertes(cadence='apres_devis').count(), 0)
        self.assertEqual(self._filets().count(), 0)

    def test_refus_sur_la_DERNIERE_touche_ne_cloture_pas_en_injoignable(self):
        """B1 (revue Fable 07/09/2026) — le client a RÉPONDU : refus sur la
        dernière touche ⇒ jamais le Froid « Injoignable » ni les réveils
        J30/J60 « vous étiez injoignable » ; l'étape « décider la suite »
        reste la seule route."""
        for etape in self.etapes[:-1]:
            marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome='non_joint')
        self._fait(self.etapes[-1], outcome='refuse')
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)
        self.assertNotIn('Injoignable', self.lead.tags or '')
        self.assertEqual(
            self.lead.relance_etapes.filter(cadence='reveil').count(), 0)
        decisions = self.lead.relance_etapes.filter(
            cadence='generique', libelle=FILET_REFUS_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(decisions.count(), 1)

    def test_joint_au_reveil_sort_le_lead_du_froid_avec_une_suite(self):
        """M1 (revue Fable 07/09/2026) — un client JOINT pendant un réveil
        sort du parking : les réveils restants sont annulés, le lead remonte
        à CONTACTED et une prochaine étape existe."""
        self.lead.stage = stages.COLD
        self.lead.save(update_fields=['stage'])
        reveils = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='reveil')
        self.assertGreater(len(reveils), 1)
        self._fait(reveils[0], outcome='joint')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertEqual(
            self.lead.relance_etapes.filter(
                cadence='reveil',
                statut=RelanceEtape.Statut.A_FAIRE).count(), 0)
        self.assertTrue(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists())

    def test_le_plan_apres_devis_pose_la_validite_de_la_proposition(self):
        """VALID1 (07/09/2026) — le démarrage du plan après-devis pose
        ``Devis.date_validite`` (si vide) à la date de la DERNIÈRE touche du
        plan : la phrase « validité de la proposition » des messages
        WhatsApp cesse d'être omise. Une validité déjà posée n'est jamais
        écrasée."""
        self._fait(self.etapes[2], outcome='joint')
        filet = self._filets().get()
        from apps.crm.models import Client as ClientCrm
        from apps.ventes.models import Devis
        client = ClientCrm.objects.create(
            company=self.company, nom='VAL', email='mry34-val@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-MRY34-0002', client=client,
            lead=self.lead, taux_tva=Decimal('20'))
        self.assertIsNone(devis.date_validite)
        marquer_etape_relance(
            filet, self.acteur, RelanceEtape.Statut.FAIT)
        devis.refresh_from_db()
        derniere = (self.lead.relance_etapes
                    .filter(cadence='apres_devis')
                    .order_by('-due_date').first())
        self.assertIsNotNone(devis.date_validite)
        self.assertEqual(devis.date_validite, derniere.due_date)

    def test_etape_generique_traitee_sans_devis_en_repose_une(self):
        """QJ-INVARIANT : sans devis, cocher le filet en repose un — la
        liste de relances ne se termine que par Froid ou Signé."""
        self._fait(self.etapes[2], outcome='joint')
        filet = self._filets().get()
        marquer_etape_relance(
            filet, self.acteur, RelanceEtape.Statut.FAIT)
        self.assertEqual(self._filets().count(), 1)

    def test_un_lead_signe_ne_recoit_pas_de_filet(self):
        self.lead.stage = stages.SIGNED
        self.lead.save(update_fields=['stage'])
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        self.assertEqual(self._filets().count(), 0)

    def test_une_activite_systeme_ne_pose_rien(self):
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=None,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        self.assertEqual(self._filets().count(), 0)

    def test_joint_sans_aucune_cadence_pose_aussi_le_filet(self):
        """Le journal d'appel direct (log-interaction) compte autant que la
        touche : un client joint doit avoir une suite, cadence ou pas."""
        seul = Lead.objects.create(
            company=self.company, nom='Sans cadence', owner=self.acteur)
        LeadActivity.objects.create(
            company=self.company, lead=seul, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        self.assertEqual(
            seul.relance_etapes.filter(
                cadence='generique',
                statut=RelanceEtape.Statut.A_FAIRE).count(), 1)


class RattrapageCommandeTests(_Base):
    """`assurer_prochaines_etapes` — les leads déjà tombés dans le trou."""

    slug = 'mry34-rattrapage'

    def _lead_coince(self, nom):
        """Un lead joint AVANT le filet : issue de succès au chatter, plus
        aucune touche ouverte (l'état exact laissé par le bug)."""
        lead = Lead.objects.create(
            company=self.company, nom=nom, owner=self.acteur)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).delete()
        Lead.objects.filter(pk=lead.pk).update(relance_date=None)
        return lead

    def test_dry_run_liste_sans_rien_ecrire(self):
        coince = self._lead_coince('Coincé')
        sortie = StringIO()
        call_command('assurer_prochaines_etapes', stdout=sortie)
        self.assertIn('Dry-run', sortie.getvalue())
        self.assertEqual(
            coince.relance_etapes.filter(
                statut=RelanceEtape.Statut.A_FAIRE).count(), 0)

    def test_apply_pose_le_filet_dans_la_limite(self):
        premier = self._lead_coince('Coincé 1')
        second = self._lead_coince('Coincé 2')
        sortie = StringIO()
        call_command(
            'assurer_prochaines_etapes', '--apply', '--limite', '1',
            stdout=sortie)
        poses = RelanceEtape.objects.filter(
            lead__in=[premier, second], cadence='generique',
            statut=RelanceEtape.Statut.A_FAIRE).count()
        self.assertEqual(poses, 1)
        self.assertIn('1 étape(s) posée(s)', sortie.getvalue())

    def test_apply_ignore_les_leads_deja_pourvus(self):
        pourvu = self._lead_coince('Pourvu')
        initialiser_plan_relance(
            pourvu, self.acteur, depart=LUNDI, cadence='contact')
        call_command(
            'assurer_prochaines_etapes', '--apply', stdout=StringIO())
        self.assertEqual(
            pourvu.relance_etapes.filter(cadence='generique').count(), 0)
