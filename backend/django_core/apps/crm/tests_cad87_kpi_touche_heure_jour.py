"""CAD87 — les trois mesures qui prouveraient que la cadence marche.

Audit L3 du 21/09/2026, section CAD-I. Ce fichier verrouille ce qui fait
qu'un tel chiffre est honnête — ou ne vaut rien :

  * le taux de joint est croisé par (ordre de touche × heure × jour de
    semaine × canal), à l'heure de CASABLANCA : c'est la seule forme qui
    réponde à « à quelle heure et quel jour joint-on le plus ? » ;
  * une ANNULATION MOTEUR n'entre jamais au dénominateur — personne ne l'a
    tentée ;
  * dénominateur 0 → ``null``, jamais un 0 % qui se lirait comme un échec ;
  * multi-tenant : une société ne voit pas les touches de l'autre ;
  * et les deux défauts de ``kpi_cadences`` nommés par l'audit : le miroir
    Odoo n'écrase plus « joints sous 5 jours », et les premières issues sont
    lues en UNE requête groupée, plus une par lead.

Le temps est GELÉ : « les 90 derniers jours », « à 18 h », « un dimanche »
sont exactement les questions qu'une horloge vivante rend instables.
``date_creation`` et ``created_at`` sont en ``auto_now_add`` : ils se
rétrodatent par ``.update()`` après la création, jamais en argument (qui
serait ignoré en silence).
"""
import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, mesure_cadence, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import kpi_cadences
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 12 h à Casablanca — jour ouvré, en pleine fenêtre.
MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()

MESURE_URL = '/api/django/crm/leads/mesure-cadence/'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _quand(jours_avant, heure=10, minute=0):
    """Un instant local de Casablanca, ``jours_avant`` jours avant le gel."""
    return datetime.datetime.combine(
        AUJOURDHUI - datetime.timedelta(days=jours_avant),
        datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad87'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = self._lead('Aziz', stage=stages.CONTACTED)

    def _lead(self, nom, *, cree_il_y_a=None, company=None, **extra):
        """Un lead, éventuellement RÉTRODATÉ (``date_creation`` auto_now_add)."""
        lead = Lead.objects.create(
            company=company or self.company, nom=nom,
            owner=self.acteur, **extra)
        if cree_il_y_a is not None:
            Lead.objects.filter(pk=lead.pk).update(
                date_creation=_quand(cree_il_y_a, 9))
            lead.refresh_from_db(fields=['date_creation'])
        return lead

    def _activite(self, lead, *, quand, outcome='', company=None, user=-1,
                  **extra):
        """Une ligne de chatter à un instant PRÉCIS (``created_at`` auto)."""
        activite = LeadActivity.objects.create(
            company=company or self.company, lead=lead,
            user=(self.acteur if user == -1 else user),
            kind=extra.pop('kind', LeadActivity.Kind.APPEL),
            body=extra.pop('body', 'Touche marquée faite.'),
            outcome=outcome, **extra)
        LeadActivity.objects.filter(pk=activite.pk).update(created_at=quand)
        activite.refresh_from_db(fields=['created_at'])
        return activite

    def _touche(self, *, statut='fait', traite_jours=3, heure=10, ordre=1,
                canal=RelanceEtape.Canal.APPEL, lead=None, company=None,
                traite_par=-1):
        instant = _quand(traite_jours, heure)
        return RelanceEtape.objects.create(
            company=company or self.company, lead=lead or self.lead,
            cadence='contact', ordre=ordre, due_at=instant,
            due_date=instant.date(), canal=canal, libelle='Appel',
            statut=statut, traite_le=instant,
            traite_par=(self.acteur if traite_par == -1 else traite_par))

    def _issue(self, touche, outcome, *, decalage_secondes=1):
        """L'issue de la touche, telle que la clôture l'écrit.

        Deux chemins selon l'état du schéma : la colonne de CAD118 quand elle
        existe, la ligne de chatter écrite par la même requête sinon."""
        if mesure_cadence._colonne_issue_disponible():
            setattr(touche, mesure_cadence.CHAMP_ISSUE, outcome)
            touche.save(update_fields=[mesure_cadence.CHAMP_ISSUE])
        return self._activite(
            touche.lead, outcome=outcome, company=touche.company,
            quand=touche.traite_le + datetime.timedelta(
                seconds=decalage_secondes))

    def _api(self, user=None):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer '
                               f'{AccessToken.for_user(user or self.acteur)}')
        return api


class TauxJointParCreneauTests(_Base):
    slug = 'cad87-creneau'

    def test_croise_ordre_canal_heure_et_jour(self):
        """Deux touches identiques sauf l'heure → deux cases distinctes."""
        self._issue(self._touche(traite_jours=3, heure=9, ordre=1), 'joint')
        self._issue(self._touche(traite_jours=3, heure=18, ordre=1),
                    'non_joint')

        lignes = mesure_cadence.taux_joint_par_creneau(self.company)
        self.assertEqual(len(lignes), 2, lignes)
        par_heure = {ligne['heure']: ligne for ligne in lignes}
        self.assertEqual(par_heure[9]['taux_joint_pct'], 100.0)
        self.assertEqual(par_heure[9]['joints'], 1)
        self.assertEqual(par_heure[18]['taux_joint_pct'], 0.0)
        # Le 10/09/2026 est un jeudi ; trois jours avant = un lundi (0).
        self.assertEqual(par_heure[9]['jour_semaine'], 0)
        self.assertEqual(par_heure[9]['canal'], RelanceEtape.Canal.APPEL)
        self.assertEqual(par_heure[9]['ordre'], 1)

    def test_heure_lue_a_casablanca_et_non_en_utc(self):
        """Une touche close à 18 h locale n'est pas rangée en case 17 h."""
        self._issue(self._touche(traite_jours=2, heure=18), 'joint')
        lignes = mesure_cadence.taux_joint_par_creneau(self.company)
        self.assertEqual([ligne['heure'] for ligne in lignes], [18])

    def test_annulation_moteur_jamais_au_denominateur(self):
        """Une cadence arrêtée par le moteur n'est le manquement de personne."""
        self._touche(statut=RelanceEtape.Statut.ANNULEE, traite_par=None)
        self.assertEqual(
            mesure_cadence.taux_joint_par_creneau(self.company), [])

    def test_touche_sautee_compte_au_denominateur_sans_joint(self):
        self._touche(statut=RelanceEtape.Statut.SAUTEE, heure=11)
        lignes = mesure_cadence.taux_joint_par_creneau(self.company)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['closes'], 1)
        self.assertEqual(lignes[0]['joints'], 0)
        self.assertEqual(lignes[0]['taux_joint_pct'], 0.0)

    def test_hors_periode_ignore(self):
        self._issue(self._touche(traite_jours=120, heure=10), 'joint')
        self.assertEqual(
            mesure_cadence.taux_joint_par_creneau(self.company, jours=90), [])

    def test_deux_canaux_a_la_meme_heure_restent_distincts(self):
        self._issue(self._touche(traite_jours=4, heure=8,
                                 canal=RelanceEtape.Canal.WHATSAPP), 'joint')
        self._issue(self._touche(traite_jours=4, heure=8,
                                 canal=RelanceEtape.Canal.APPEL), 'non_joint')
        lignes = mesure_cadence.taux_joint_par_creneau(self.company)
        self.assertEqual(
            {ligne['canal'] for ligne in lignes},
            {RelanceEtape.Canal.WHATSAPP, RelanceEtape.Canal.APPEL})


class SignaturesParTouchesTests(_Base):
    slug = 'cad87-signatures'

    def _signature(self, *, jours_avant, lead=None):
        return self._activite(
            lead or self.lead, quand=_quand(jours_avant, 16),
            kind=LeadActivity.Kind.NOTE, field='stage',
            new_value=stages.STAGE_LABELS[stages.SIGNED],
            body='Étape modifiée.')

    def test_distribution_compte_les_touches_closes_avant_la_signature(self):
        self._touche(traite_jours=10, ordre=1)
        self._touche(traite_jours=8, ordre=2)
        # Close APRÈS la signature : elle ne compte pas.
        self._touche(traite_jours=1, ordre=3)
        self._signature(jours_avant=5)

        self.assertEqual(
            mesure_cadence.signatures_par_touches_consommees(self.company),
            [{'touches': 2, 'signatures': 1}])

    def test_aucune_signature_rend_une_liste_vide(self):
        self._touche(traite_jours=4)
        self.assertEqual(
            mesure_cadence.signatures_par_touches_consommees(self.company), [])


class PartContactEtLangueTests(_Base):
    slug = 'cad87-part'

    def test_part_whatsapp_only_et_darija(self):
        self.lead.contact_preference = Lead.ContactPreference.WHATSAPP_ONLY
        self.lead.langue_preferee = Lead.LanguePreferee.DARIJA
        self.lead.save(update_fields=['contact_preference',
                                      'langue_preferee'])
        self._lead('Fatima', stage=stages.NEW)
        part = mesure_cadence.part_contact_et_langue(self.company)
        self.assertEqual(part['nb_leads'], 2)
        self.assertEqual(part['whatsapp_only'], 1)
        self.assertEqual(part['whatsapp_only_pct'], 50.0)
        self.assertEqual(part['darija_pct'], 50.0)

    def test_denominateur_vide_rend_null(self):
        self.lead.delete()
        part = mesure_cadence.part_contact_et_langue(self.company)
        self.assertEqual(part['nb_leads'], 0)
        self.assertIsNone(part['whatsapp_only_pct'])
        self.assertIsNone(part['darija_pct'])

    def test_miroir_odoo_ecarte(self):
        self._lead('Miroir', source=Lead.Source.ODOO_IMPORT_TEST,
                   stage=stages.NEW)
        self.assertEqual(
            mesure_cadence.part_contact_et_langue(self.company)['nb_leads'], 1)


class IsolationEtContratTests(_Base):
    slug = 'cad87-isolation'

    def test_une_societe_ne_voit_pas_les_touches_de_lautre(self):
        autre = _company('cad87-isolation-autre')
        autre_user = User.objects.create_user(
            username='cad87-autre', password='x', role_legacy='responsable',
            company=autre)
        autre_lead = Lead.objects.create(company=autre, nom='Voisin',
                                         stage=stages.CONTACTED)
        touche = self._touche(lead=autre_lead, company=autre,
                              traite_par=autre_user, heure=15)
        self._activite(autre_lead, company=autre, user=autre_user,
                       outcome='joint',
                       quand=touche.traite_le + datetime.timedelta(seconds=1))

        self.assertEqual(
            mesure_cadence.taux_joint_par_creneau(self.company), [])
        self.assertEqual(
            len(mesure_cadence.taux_joint_par_creneau(autre)), 1)

    def test_endpoint_a_la_forme_de_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'mesure_cadence.json').read_text(encoding='utf-8'))
        resp = self._api().get(MESURE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(echantillon['exemple']))
        self.assertEqual(
            set(resp.data['part_contact_et_langue']),
            set(echantillon['exemple']['part_contact_et_langue']))

    def test_endpoint_borne_le_parametre_jours(self):
        resp = self._api().get(MESURE_URL, {'jours': '9999'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['jours'], 365)
        resp = self._api().get(MESURE_URL, {'jours': 'abc'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['jours'],
                         mesure_cadence.JOURS_MESURE_DEFAUT)


class KpiCadencesCorrigeTests(_Base):
    """Les deux défauts de `kpi_cadences` nommés par l'audit (round 2)."""

    slug = 'cad87-kpi'

    def _lead_joint(self, nom):
        lead = self._lead(nom, cree_il_y_a=2, stage=stages.NEW)
        self._activite(
            lead, outcome='joint',
            quand=lead.date_creation + datetime.timedelta(hours=1))
        return lead

    def test_import_odoo_ne_fait_plus_plonger_joints_sous_5j(self):
        """Un import n'a changé aucun comportement : le chiffre non plus."""
        self._lead_joint('Natif')
        avant = kpi_cadences(self.company)['joints_sous_5j_pct']

        for index in range(20):
            self._lead(f'Odoo {index}', cree_il_y_a=2,
                       source=Lead.Source.ODOO_IMPORT_TEST, stage=stages.NEW)
        self.assertEqual(kpi_cadences(self.company)['joints_sous_5j_pct'],
                         avant)

    def test_leads_archives_ecartes(self):
        self._lead('Archivé', cree_il_y_a=2, is_archived=True,
                   stage=stages.NEW)
        self._lead_joint('Natif')
        # `self.lead` (créé par `_Base`) n'est pas joint : 1 joint sur 2.
        self.assertEqual(kpi_cadences(self.company)['joints_sous_5j_pct'],
                         50.0)

    def test_premieres_issues_ne_font_plus_une_requete_par_lead(self):
        """Le nombre de requêtes ne croît plus avec le nombre de leads."""
        for index in range(3):
            self._lead_joint(f'Trois {index}')
        with CaptureQueriesContext(connection) as petit:
            kpi_cadences(self.company)
        for index in range(9):
            self._lead_joint(f'Douze {index}')
        with CaptureQueriesContext(connection) as grand:
            kpi_cadences(self.company)
        self.assertEqual(len(grand), len(petit))
