"""CAD107 — un lead perdu qui revient : UN seul comportement, trois chemins.

Le meilleur signal d'achat qui existe — un client perdu qui revient — avait
trois sorties différentes :

  * le PATCH de la fiche ne traitait que le passage `not old.perdu →
    new.perdu` : DÉCOCHER « Perdu » ne déclenchait rien du tout ;
  * le lot `unset_perdu` appelait le filet ;
  * `reactivate_lead_on_new_touch` (nouvelle demande entrante) ne créait
    aucune `RelanceEtape`.

Et dans les trois cas la prise de contact ne pouvait de toute façon pas
repartir (garde « déjà contacté ») : au mieux une étape nue.

Le comportement unique REUTILISE la cadence RÉVEIL — jamais une nouvelle
cadence (CADX), et c'est exactement ce à quoi elle sert : reprendre le
contact d'un dossier mis de côté, sans rejouer six appels en quatorze jours à
quelqu'un qu'on a déjà travaillé. La reprise est VISIBLE : une note de
chatter la dit, et la touche apparaît dans la file (`relance_date`).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'
LEADS_URL = '/api/django/crm/leads/'
BULK_URL = '/api/django/crm/leads/bulk/'


class _Base(TestCase):
    slug = 'cad107'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD107 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='admin', company=self.company)

    def _lead_perdu(self, prenom='Aziz', **kw):
        champs = {'company': self.company, 'nom': 'Benali', 'prenom': prenom,
                  'ville': 'Bouskoura', 'owner': self.acteur,
                  'telephone': MOBILE, 'stage': stages.CONTACTED,
                  'perdu': True, 'motif_perte': 'Prix'}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def _ouvertes(self, lead):
        return lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)

    def _cadences_ouvertes(self, lead):
        return set(self._ouvertes(lead).values_list('cadence', flat=True))


class LesTroisCheminsProduisentLaMemeRepriseTests(_Base):
    """Le « Done = »."""

    slug = 'cad107-trois'

    def test_chemin_1_le_PATCH_qui_decoche_perdu_pose_la_reprise(self):
        lead = self._lead_perdu()
        resp = self._api().patch(
            f'{LEADS_URL}{lead.pk}/', {'perdu': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_chemin_2_le_lot_unset_perdu_pose_la_meme(self):
        lead = self._lead_perdu()
        resp = self._api().post(
            BULK_URL, {'ids': [lead.pk], 'action': 'unset_perdu'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_chemin_3_une_nouvelle_demande_entrante_pose_la_meme(self):
        lead = self._lead_perdu()
        self.assertTrue(services.reactivate_lead_on_new_touch(lead))
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_les_trois_chemins_posent_le_MEME_nombre_de_touches(self):
        a = self._lead_perdu('Aziz')
        b = self._lead_perdu('Karim', telephone='+212661000003')
        c = self._lead_perdu('Samir', telephone='+212661000004')
        self._api().patch(f'{LEADS_URL}{a.pk}/', {'perdu': False},
                          format='json')
        self._api().post(BULK_URL, {'ids': [b.pk], 'action': 'unset_perdu'},
                         format='json')
        services.reactivate_lead_on_new_touch(c)
        comptes = {self._ouvertes(x).count() for x in (a, b, c)}
        self.assertEqual(len(comptes), 1, comptes)
        self.assertNotIn(0, comptes)


class LaRepriseEstVISIBLETests(_Base):
    """« L'écran affiche ce qui vient d'être posé. »

    Le lead de ces deux tests est un dossier DÉJÀ ROUVERT (`perdu=False`) :
    `reprendre_cadence_apres_reouverture` refuse délibérément un lead encore
    perdu — « ce n'est pas une réouverture », no-op vérifié par
    `LesNoOpDeliberesTests.test_un_lead_encore_PERDU_ne_recoit_rien`. Les
    appeler sur un lead `perdu=True` demandait au moteur l'exact contraire de
    ce que le même module exige ailleurs.
    """

    slug = 'cad107-visible'

    def test_une_note_de_chatter_dit_que_le_dossier_est_rouvert(self):
        lead = self._lead_perdu(perdu=False)
        etapes = services.reprendre_cadence_apres_reouverture(
            lead, self.acteur, origine='fiche rouverte')
        self.assertTrue(etapes)
        notes = [n.body for n in LeadActivity.objects.filter(lead=lead)]
        self.assertTrue(
            any('cadence de reprise posée' in (b or '') for b in notes),
            notes)

    def test_la_prochaine_touche_remonte_dans_la_file(self):
        lead = self._lead_perdu(perdu=False)
        self.assertTrue(
            services.reprendre_cadence_apres_reouverture(lead, self.acteur))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.relance_date)
        prochaine = self._ouvertes(lead).order_by('due_date').first()
        self.assertEqual(lead.relance_date, prochaine.due_date)


class LesNoOpDeliberesTests(_Base):
    """Ce que la reprise ne fait JAMAIS."""

    slug = 'cad107-noop'

    def test_un_lead_DEJA_suivi_ne_recoit_pas_une_seconde_cadence(self):
        """CADX — jamais deux cadences en parallèle."""
        lead = self._lead_perdu(perdu=False)
        deja = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=1,
            due_date=lead.date_creation.date(),
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Le PDF s’ouvre bien ?')
        self.assertEqual(
            services.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])
        self.assertEqual([e.pk for e in self._ouvertes(lead)], [deja.pk])

    def test_un_lead_encore_PERDU_ne_recoit_rien(self):
        lead = self._lead_perdu()
        self.assertEqual(
            services.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def test_un_lead_quon_ne_relance_plus_ne_recoit_rien(self):
        lead = self._lead_perdu(perdu=False, ne_plus_contacter=True)
        self.assertEqual(
            services.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def test_un_lead_SIGNE_ou_FROID_ne_recoit_rien(self):
        for etape in (stages.SIGNED, stages.COLD):
            with self.subTest(stage=etape):
                lead = self._lead_perdu(perdu=False, stage=etape)
                self.assertEqual(
                    services.reprendre_cadence_apres_reouverture(
                        lead, self.acteur), [])

    def test_un_lead_archive_ne_recoit_rien(self):
        lead = self._lead_perdu(perdu=False, is_archived=True)
        self.assertEqual(
            services.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def test_la_cadence_posee_est_bien_le_REVEIL_jamais_une_neuve(self):
        """Garde-fou CADX : aucune cadence n'est inventée pour l'occasion."""
        lead = self._lead_perdu(perdu=False)
        etapes = services.reprendre_cadence_apres_reouverture(
            lead, self.acteur)
        self.assertTrue(etapes)
        self.assertEqual({e.cadence for e in etapes}, {'reveil'})
