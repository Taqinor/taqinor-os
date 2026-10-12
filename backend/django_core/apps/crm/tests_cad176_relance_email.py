"""CAD176 — la touche e-mail rend enfin un texte, et l'adresse atteint la file.

Constat (audit CAD86, note du 24/09/2026 dans docs/crm/messages_meryem.md) :
le seul barreau e-mail de tout le référentiel (barreau 3, J+10, cadence
``generique`` historique) n'avait AUCUNE clé de gabarit — ``message_pour_etape``
rendait une chaîne vide (panneau « Texte de l'e-mail » à « — », bouton Copier
désactivé) — et le contrat ``relance_etape_v2`` ne servait jamais l'adresse
e-mail du lead : le bouton « E-mail » de la ligne n'avait aucun destinataire
à montrer.

Ce fichier verrouille :
  * le barreau 3 de ``CADENCE_RELANCE_DEFAUT`` porte désormais
    ``template_cle='relance_email_j10'`` — vérifié par le SEED (nouvelle
    société), même chemin que toute autre clé du référentiel ;
  * la migration de données 0110 (même patron que 0081/``etiqueter_generique``
    dans ``tests_mry4_cadence_v2.py``) pose la clé sur un barreau déjà seedé
    AVANT CAD176 (société existante), sans jamais toucher un barreau que la
    société aurait personnalisé (``template_cle`` déjà non vide) ;
  * ``message_pour_etape`` rend un texte NON VIDE pour ce gabarit (le ✎ texte
    par défaut de ``MESSAGE_TEMPLATE_DEFAULTS``) — l'envoi reste MANUEL (D5) :
    aucun appel SendGrid, ``send_mail`` ni client réseau n'est exercé ici ;
  * ``RelanceEtapeSerializer`` sert désormais ``lead_email``, avec EXACTEMENT
    le masquage PII de ``lead_telephone``/``lead_whatsapp`` (CAD82) ;
  * le contrat partagé ``contract_samples/relance_etape_v2.json`` (PACT10)
    porte la même forme que ce que le serveur sert réellement.
"""
import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.serializers_cadence import RelanceEtapeSerializer
from apps.crm.cadence_messages import message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCE_RELANCE_DEFAUT, Cadence, CadenceRelanceEtape, CanalRelance,
)
from apps.roles.models import Role

User = get_user_model()

JOUR = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class BarreauDefautTests(TestCase):
    """Le RÉFÉRENTIEL (``CADENCE_RELANCE_DEFAUT``) et son SEED."""

    def test_le_barreau_3_porte_la_cle_dans_le_referentiel(self):
        barreau = next(e for e in CADENCE_RELANCE_DEFAUT if e['ordre'] == 3)
        self.assertEqual(barreau['canal'], CanalRelance.EMAIL)
        self.assertEqual(barreau['template_cle'], 'relance_email_j10')

    def test_une_societe_neuve_seede_la_cle_directement(self):
        company = _company('cad176-seed-neuf')
        CadenceRelanceEtape.seed_cadence(company, Cadence.GENERIQUE)
        barreau = CadenceRelanceEtape.objects.get(
            company=company, cadence=Cadence.GENERIQUE, ordre=3)
        self.assertEqual(barreau.canal, CanalRelance.EMAIL)
        self.assertEqual(barreau.template_cle, 'relance_email_j10')


class MigrationBackfillTests(TestCase):
    """La migration de données 0110 — appelée telle quelle, jamais un
    ``MigrationExecutor`` (même patron que ``tests_mry4_cadence_v2.
    MigrationEtiquetteGeneriqueTests`` pour la migration sœur 0081)."""

    class _RegistreSimule:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == (
                'parametres', 'CadenceRelanceEtape')
            return CadenceRelanceEtape

    def _module(self):
        from importlib import import_module
        # Nom de module commençant par un chiffre : `import_module` seul
        # peut le charger.
        return import_module(
            'apps.parametres.migrations.'
            '0110_cad176_relance_email_template_cle')

    def test_backfill_pose_la_cle_sur_un_barreau_deja_seede(self):
        company = _company('cad176-mig-ancien')
        # Barreau tel qu'une société créée AVANT CAD176 le porte : seedé sans
        # `template_cle` (le référentiel ne l'avait pas encore).
        barreau = CadenceRelanceEtape.objects.create(
            company=company, cadence=Cadence.GENERIQUE, ordre=3,
            delai_jours=10, canal=CanalRelance.EMAIL,
            libelle='Relance e-mail', actif=True)
        self.assertEqual(barreau.template_cle, '')
        self._module().poser_la_cle(self._RegistreSimule, None)
        barreau.refresh_from_db()
        self.assertEqual(barreau.template_cle, 'relance_email_j10')

    def test_backfill_ne_touche_jamais_un_barreau_personnalise(self):
        """Une société qui a DÉJÀ choisi un autre gabarit pour ce barreau
        n'est jamais écrasée par le backfill (`template_cle` non vide)."""
        company = _company('cad176-mig-perso')
        barreau = CadenceRelanceEtape.objects.create(
            company=company, cadence=Cadence.GENERIQUE, ordre=3,
            delai_jours=10, canal=CanalRelance.EMAIL,
            libelle='Relance e-mail', actif=True,
            template_cle='dossier_8221')
        self._module().poser_la_cle(self._RegistreSimule, None)
        barreau.refresh_from_db()
        self.assertEqual(barreau.template_cle, 'dossier_8221')

    def test_backfill_ne_touche_pas_un_autre_ordre_ou_canal(self):
        """Filtre étroit : seul (generique, ordre 3, email) est visé — les
        quatre autres barreaux de la cadence restent muets (comportement
        inchangé)."""
        company = _company('cad176-mig-autres')
        appel = CadenceRelanceEtape.objects.create(
            company=company, cadence=Cadence.GENERIQUE, ordre=1,
            delai_jours=2, canal=CanalRelance.APPEL,
            libelle='Premier rappel', actif=True)
        self._module().poser_la_cle(self._RegistreSimule, None)
        appel.refresh_from_db()
        self.assertEqual(appel.template_cle, '')


class MessageRenduTests(TestCase):
    """``message_pour_etape`` — LECTURE PURE, jamais un envoi (décision D5)."""

    def setUp(self):
        self.company = _company('cad176-message')
        self.acteur = User.objects.create_user(
            username='cad176-message-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Fassi', prenom='Karim',
            stage=stages.CONTACTED, email='karim.fassi@example.ma',
            telephone='+212661000176')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=3, canal=RelanceEtape.Canal.EMAIL,
            libelle='Relance e-mail', template_cle='relance_email_j10',
            due_at=JOUR, due_date=JOUR.date())

    def test_le_texte_n_est_plus_vide(self):
        rendu = message_pour_etape(
            self.etape, request=None, user=self.acteur)
        self.assertTrue(rendu['message'].strip())
        # Les placeholders {conseiller}/{marque} sont résolus (jamais un
        # prénom codé en dur dans le texte du gabarit — le conseiller affiché
        # vient du responsable du lead, résolu côté serveur).
        self.assertNotIn('{conseiller}', rendu['message'])
        self.assertNotIn('{marque}', rendu['message'])


class SerializerLeadEmailTests(TestCase):
    """``RelanceEtapeSerializer.lead_email`` — MÊME masquage que
    ``lead_telephone``/``lead_whatsapp`` (CAD82)."""

    def setUp(self):
        self.company = _company('cad176-serializer')
        role_sans_pii = Role.objects.create(
            company=self.company, nom='CAD176 sans PII',
            permissions=['crm_voir'])
        role_pii = Role.objects.create(
            company=self.company, nom='CAD176 avec PII',
            permissions=['crm_voir', 'client_pii_voir'])
        self.sans_pii = User.objects.create_user(
            username='cad176-sans-pii', password='x', role=role_sans_pii,
            company=self.company)
        self.avec_pii = User.objects.create_user(
            username='cad176-avec-pii', password='x', role=role_pii,
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Chraibi', prenom='Samira',
            stage=stages.CONTACTED, email='samira.chraibi@example.ma')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=3, canal=RelanceEtape.Canal.EMAIL,
            libelle='Relance e-mail', template_cle='relance_email_j10',
            due_at=JOUR, due_date=JOUR.date())

    def _donnees(self, user):
        return RelanceEtapeSerializer(
            self.etape,
            context={'request': SimpleNamespace(user=user)}).data

    def test_adresse_visible_avec_les_droits(self):
        donnees = self._donnees(self.avec_pii)
        self.assertEqual(donnees['lead_email'], 'samira.chraibi@example.ma')
        self.assertIs(donnees['lead_pii_masquee'], False)

    def test_adresse_masquee_sans_les_droits(self):
        donnees = self._donnees(self.sans_pii)
        self.assertEqual(donnees['lead_email'], '')
        self.assertIs(donnees['lead_pii_masquee'], True)

    def test_adresse_absente_de_la_fiche_n_est_pas_un_masquage(self):
        self.lead.email = ''
        self.lead.save(update_fields=['email'])
        donnees = self._donnees(self.avec_pii)
        self.assertEqual(donnees['lead_email'], '')
        self.assertIs(donnees['lead_pii_masquee'], False)

    def test_la_forme_est_celle_du_contrat(self):
        """PACT10 — les clés du sérialiseur sont EXACTEMENT celles des lignes
        committées de ``relance_etape_v2.json`` : ``lead_email`` y figure
        désormais partout (CAD176), jamais seulement sur une ligne."""
        contrat = _contrat('relance_etape_v2')
        attendu = set(contrat['exemple']['results'][0])
        self.assertIn('lead_email', attendu)
        self.assertEqual(set(self._donnees(self.avec_pii)), attendu)
        for variante in ('exemple_generique', 'exemple_dernier_reveil',
                         'exemple_pii_masquee', 'exemple_whatsapp_uniquement',
                         'exemple_debrief_visite'):
            for ligne in contrat[variante]['results']:
                self.assertEqual(set(ligne), attendu)
