"""AGR514 (D-AGR-10) — J4 « preuve » omise sans réalisation éligible.

Le gabarit après-devis garde ses 10 barreaux (jamais un axe segment, CAD124) ;
c'est la DONNÉE qui décide : `parametres.selectors.realisation_pour_lead`
(filtré par segment, AGR513) renvoie `None` → la touche `j4_preuve` est
écartée, le trou de `ordre` est gardé. Le lead porte « Décision à plusieurs »
pour que la touche dominicale (MRY4) soit comptée : 10 barreaux au complet.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.crm.cadence_plan import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_realisations import Realisation
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.domain.envoi import mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()


class _Base(TestCase):
    slug = 'agr514'
    type_installation = Lead.TypeInstallation.AGRICOLE

    def setUp(self):
        self.company = Company.objects.create(nom=self.slug, slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Exploitant', owner=self.acteur,
            telephone='+212661112233', ville='Agadir',
            type_installation=self.type_installation,
            tags='Décision à plusieurs')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _realisation(self, segment, ville='Agadir'):
        return Realisation.objects.create(
            company=self.company, titre=f'Chantier {segment}', ville=ville,
            mise_en_service=datetime.date(2026, 7, 1),
            puissance_kwc=Decimal('6'), segment=segment,
            url_page=f'https://taqinor.ma/realisations/{segment}/')

    def _envoyer(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-1',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20.00'))
        mark_devis_sent(devis=devis, user=self.acteur)
        return devis

    def _cles_planifiees(self):
        partition = calculer_echeances_cadence(
            self.lead, 'apres_devis', datetime.datetime.now(
                datetime.timezone.utc))
        return [g.template_cle for g, _e in partition]

    def _cles_creees(self):
        return list(self.lead.relance_etapes.filter(cadence='apres_devis')
                    .values_list('template_cle', flat=True))


class LeadAgricoleTests(_Base):
    slug = 'agr514-agri'

    def test_sans_realisation_agricole_pas_de_j4(self):
        # Une réalisation RÉSIDENTIELLE n'est jamais servie à un agricole.
        self._realisation('residentiel')
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 9)
        self.assertNotIn('j4_preuve', cles)
        self.assertIn('dimanche_famille', cles)
        self.assertNotIn('j4_preuve', self._cles_creees())
        self.assertTrue(self._cles_creees())  # le suivi démarre bien

    def test_le_trou_de_numerotation_est_garde(self):
        # La cadence est RÉACTIVE : l'envoi ne matérialise que la touche 1,
        # les suivantes naissent une à une. Le trou se lit donc sur la
        # partition planifiée, dont chaque touche née hérite son `ordre`.
        self._envoyer()
        partition = calculer_echeances_cadence(
            self.lead, 'apres_devis', datetime.datetime.now(
                datetime.timezone.utc))
        ordres = [g.ordre for g, _e in partition]
        self.assertNotIn(4, ordres)
        self.assertIn(5, ordres)

    def test_avec_realisation_agricole_dix_touches_dont_j4(self):
        self._realisation('agricole')
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 10)
        self.assertIn('j4_preuve', cles)
        # Cadence RÉACTIVE : seule la touche 1 naît à l'envoi.
        self.assertEqual(self._cles_creees(), ['j1_pdf'])


class LeadResidentielTests(_Base):
    slug = 'agr514-resi'
    type_installation = Lead.TypeInstallation.RESIDENTIEL

    def test_residentiel_avec_realisations_garde_ses_dix_touches(self):
        self._realisation('residentiel')
        self._realisation('agricole')  # jamais servie ; n'ôte rien
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 10)
        self.assertIn('j4_preuve', cles)

    def _gabarit_v4(self):
        """CADV87 — la forme v4 (CADV24) : J4 et J6 retirés, ordre 7 = WhatsApp J10."""
        CadenceRelanceEtape.cadence_pour(self.company, 'apres_devis')
        rangs = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='apres_devis')
        rangs.filter(ordre__in=[4, 5]).update(actif=False)
        rangs.filter(ordre=7).update(delai_jours=10, template_cle='j6_garanties')

    def _cle_j10(self, frein):
        Lead.objects.filter(pk=self.lead.pk).update(frein_principal=frein)
        self.lead.refresh_from_db()
        partition = calculer_echeances_cadence(
            self.lead, 'apres_devis', datetime.datetime.now(datetime.timezone.utc))
        return {g.ordre: g.template_cle for g, _e in partition}[7]

    def test_le_j10_suit_le_frein_principal(self):
        """CADV87 (D-CADV-3) — deux leads du même gabarit, deux textes ; le gabarit
        n'est pas muté. Mutant : ignorer le frein ⇒ échec."""
        self._gabarit_v4()
        self._realisation('residentiel')
        self.assertEqual(self._cle_j10('confiance'), 'j4_preuve')
        self.assertEqual(self._cle_j10('compare'), 'j4_preuve')
        self.assertEqual(self._cle_j10('technique'), 'j6_garanties')
        self.assertEqual(self._cle_j10(None), 'j6_garanties')
        self.assertEqual(CadenceRelanceEtape.objects.get(
            company=self.company, cadence='apres_devis', ordre=7).template_cle,
            'j6_garanties')

    def test_sans_realisation_eligible_le_j10_garde_les_garanties(self):
        self._gabarit_v4()
        self.assertEqual(self._cle_j10('confiance'), 'j6_garanties')

    def test_une_cle_personnalisee_n_est_jamais_remplacee(self):
        self._gabarit_v4()
        self._realisation('residentiel')
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='apres_devis', ordre=7,
        ).update(template_cle='j9_validite')
        self.assertEqual(self._cle_j10('confiance'), 'j9_validite')

    def test_un_gabarit_qui_porte_sa_preuve_ne_la_dit_pas_deux_fois(self):
        """Le gabarit v3 (J4 preuve, J6 garanties) : le texte de J6 ne change pas."""
        self._realisation('residentiel')
        Lead.objects.filter(pk=self.lead.pk).update(frein_principal='confiance')
        self.lead.refresh_from_db()
        self.assertEqual(self._cles_planifiees().count('j4_preuve'), 1)
        self.assertIn('j6_garanties', self._cles_planifiees())

    def test_seule_la_cle_de_texte_change(self):
        self._gabarit_v4()
        self._realisation('residentiel')
        Lead.objects.filter(pk=self.lead.pk).update(frein_principal='confiance')
        self.lead.refresh_from_db()
        partition = dict(
            (g.ordre, g) for g, _e in calculer_echeances_cadence(
                self.lead, 'apres_devis', datetime.datetime.now(datetime.timezone.utc)))
        self.assertEqual(partition[7].canal, 'whatsapp')
        self.assertEqual(partition[7].delai_jours, 10)


# ── AGR531 — le sérialiseur de touche sert `lead_segment` ──────────────────


class LeadSegmentServiTests(_Base):
    """AGR531 (contrat `relance_etape_v2.json`, AGR500) — chaque touche sert
    `lead_segment` = `Lead.type_installation` ('' si non renseigné), en
    lecture seule et sans requête de plus pour la liste."""
    slug = 'agr531-segment'

    def setUp(self):
        super().setUp()
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self._envoyer()

    def _liste(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get('/api/django/crm/relance-etapes/',
                                {'scope': 'all', 'lead': self.lead.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = resp.data.get('results', resp.data)
        self.assertTrue(lignes)
        return lignes, len(ctx.captured_queries)

    def test_lead_agricole_sert_agricole(self):
        lignes, _n = self._liste()
        for ligne in lignes:
            self.assertEqual(ligne['lead_segment'], 'agricole')

    def test_lead_sans_type_sert_une_chaine_vide_sans_requete_de_plus(self):
        _lignes, avant = self._liste()
        Lead.objects.filter(pk=self.lead.pk).update(type_installation=None)
        lignes, apres = self._liste()
        for ligne in lignes:
            self.assertEqual(ligne['lead_segment'], '')
        self.assertEqual(apres, avant)

    def test_la_cle_est_dans_l_exemple_du_contrat(self):
        import json
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'relance_etape_v2.json').read_text(encoding='utf-8'))
        self.assertIn('lead_segment', contrat['exemple']['results'][0])
        self.assertNotIn('ajout_lead_segment', contrat)
