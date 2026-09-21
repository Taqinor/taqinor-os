"""Tests AUDV17 — conformité CNDP / loi 09-08 du pipeline marketing.

Six fonctions écrites, testées unitairement et JAMAIS appelées par le
pipeline d'envoi réel :

* `planifier_campagne` (XMKT7) — la seule façon de faire partir une campagne
  était `envoyer`, c'est-à-dire TOUT DE SUITE ; la file, le beat qui la dépile
  et la fenêtre de silence étaient tous inatteignables ;
* `cndp_footer_texte` (XMKT4) et `ajouter_mention_stop` (XMKT15) — les
  campagnes partaient sans mention légale ni mot-clé STOP obligatoire ;
* `filtrer_destinataires_sms` (XMKT15) — un fixe ou un numéro malformé partait
  au facturier : la société payait un SMS mort, invisible ;
* `importer_liste_opposition` (XMKT3) — une liste d'opposition reçue d'un
  partenaire ne pouvait pas entrer dans l'ERP, donc ses destinataires
  restaient ciblables ;
* `pointer_presence_via_qr_ou_recherche` (ZMKT18) — l'émargement se faisait à
  la main dans la liste, une personne à la fois.

Les campagnes partent par le canal `email` sans intégration Brevo (NO-OP
réseau, comportement par défaut) : ces tests portent donc sur ce que l'ERP
ÉCRIT et FILTRE, jamais sur un appel sortant.
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    Campagne, EnvoiCampagne, EvenementMarketing, InscriptionEvenement,
    SuppressionMarketing,
)

User = get_user_model()

CAMPAGNES = '/api/django/marketing/campagnes/'
INSCRIPTIONS = '/api/django/marketing/inscriptions-evenement/'


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PlanificationCampagneTests(TestCase):
    """DRAFT165-20 — brouillon → en_file, depuis un écran."""

    def setUp(self):
        self.co = make_company('audv17-plan', 'AUDV17 Planification')
        self.api = auth(make_user(self.co, 'audv17-plan-user'))
        self.campagne = Campagne.objects.create(
            company=self.co, nom='Relance printemps',
            canal=Campagne.Canal.EMAIL, objet='Offre', corps='Bonjour')

    def test_planifier_met_la_campagne_en_file(self):
        quand = (timezone.now() + timedelta(days=2)).isoformat()
        resp = self.api.post(
            f'{CAMPAGNES}{self.campagne.id}/planifier/',
            {'planifiee_le': quand}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.campagne.refresh_from_db()
        self.assertEqual(self.campagne.statut, Campagne.Statut.EN_FILE)
        self.assertIsNotNone(self.campagne.planifiee_le)

    def test_date_obligatoire(self):
        resp = self.api.post(
            f'{CAMPAGNES}{self.campagne.id}/planifier/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_scopee_par_societe(self):
        autre = make_company('audv17-plan-autre', 'AUDV17 Autre')
        campagne_autre = Campagne.objects.create(
            company=autre, nom='Hors société', canal=Campagne.Canal.EMAIL)
        resp = self.api.post(
            f'{CAMPAGNES}{campagne_autre.id}/planifier/',
            {'planifiee_le': timezone.now().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 404)


class ConformiteCndpAlEnvoiTests(TestCase):
    """DRAFT165-25/27/28 — pied CNDP, mention STOP, numéros validés."""

    def setUp(self):
        self.co = make_company('audv17-cndp', 'AUDV17 CNDP')
        self.api = auth(make_user(self.co, 'audv17-cndp-user'))

    def _campagne(self, canal, corps='Bonjour'):
        return Campagne.objects.create(
            company=self.co, nom=f'Campagne {canal}', canal=canal,
            objet='Offre', corps=corps)

    def _envoyer_sms(self, campagne, destinataires):
        """La fenêtre de silence (XMKT7) dépend de l'HEURE RÉELLE : un SMS ne
        part ni la nuit ni un jour férié. Sans neutralisation, ces tests
        passeraient ou échoueraient selon l'heure de la CI — une flakiness
        garantie. On ne teste pas la fenêtre ici (elle a ses propres tests) :
        on la met hors du chemin pour observer le FILTRAGE et les MENTIONS."""
        with mock.patch.object(services, '_hors_fenetre_silence',
                               return_value=False):
            return services.envoyer_campagne(
                campagne, destinataires=destinataires)

    def test_un_sms_part_toujours_avec_la_mention_stop(self):
        campagne = self._campagne(Campagne.Canal.SMS, corps='Promo -10%')
        self._envoyer_sms(campagne, ['+212612345678'])
        campagne.refresh_from_db()
        self.assertIn('stop', campagne.corps.lower())

    def test_la_mention_stop_n_est_jamais_doublee(self):
        campagne = self._campagne(
            Campagne.Canal.SMS, corps='Promo. Envoyez STOP pour arrêter.')
        avant = campagne.corps
        self._envoyer_sms(campagne, ['+212612345678'])
        campagne.refresh_from_db()
        self.assertEqual(campagne.corps, avant)

    def test_un_numero_fixe_ou_malforme_ne_part_pas_et_laisse_une_trace(self):
        campagne = self._campagne(Campagne.Canal.SMS, corps='Promo')
        self._envoyer_sms(campagne, [
            '+212612345678',   # mobile valide
            '+212522334455',   # fixe : jamais un SMS
            'pas-un-numero',
        ])
        campagne.refresh_from_db()
        self.assertEqual(campagne.nb_destinataires, 1)
        rebonds = EnvoiCampagne.objects.filter(
            campagne=campagne, statut=EnvoiCampagne.Statut.REBOND)
        self.assertEqual(rebonds.count(), 2)
        self.assertTrue(all(r.raison_smtp.startswith('numero_invalide:')
                            for r in rebonds))

    def test_email_sans_numero_cndp_reste_inchange(self):
        """Non-régression : sans déclaration renseignée, AUCUN pied ajouté."""
        campagne = self._campagne(Campagne.Canal.EMAIL, corps='Bonjour')
        services.envoyer_campagne(campagne, destinataires=['a@example.ma'])
        campagne.refresh_from_db()
        self.assertEqual(campagne.corps, 'Bonjour')

    def test_email_avec_numero_cndp_porte_le_pied_legal(self):
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.get(company=self.co)
        profil.numero_declaration_cndp = 'A-GC-123'
        profil.save(update_fields=['numero_declaration_cndp'])
        campagne = self._campagne(Campagne.Canal.EMAIL, corps='Bonjour')
        services.envoyer_campagne(campagne, destinataires=['a@example.ma'])
        campagne.refresh_from_db()
        self.assertIn('A-GC-123', campagne.corps)
        self.assertIn('CNDP', campagne.corps)

    def test_l_etat_de_conformite_est_lisible_depuis_l_ecran(self):
        resp = self.api.get(f'{CAMPAGNES}conformite-cndp/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            sorted(resp.data),
            ['double_optin_actif', 'mention_stop_sms', 'pied_cndp',
             'pied_cndp_configure'])
        # Sans numéro de déclaration : l'écran doit pouvoir DIRE que les
        # emails partent sans mention légale.
        self.assertFalse(resp.data['pied_cndp_configure'])
        self.assertIn('STOP', resp.data['mention_stop_sms'].upper())


class LienDesinscriptionTests(TestCase):
    """DRAFT165-21 — un lien de désinscription réel, par destinataire."""

    def setUp(self):
        self.co = make_company('audv17-desinsc', 'AUDV17 Désinscription')
        self.api = auth(make_user(self.co, 'audv17-desinsc-user'))
        self.campagne = Campagne.objects.create(
            company=self.co, nom='Newsletter', canal=Campagne.Canal.EMAIL)

    def test_le_lien_genere_desinscrit_REELLEMENT_ce_destinataire(self):
        resp = self.api.get(
            f'{CAMPAGNES}{self.campagne.id}/lien-desinscription/',
            {'destinataire': 'client@example.ma'})
        self.assertEqual(resp.status_code, 200, resp.content)
        token = resp.data['lien'].rstrip('/').rsplit('/', 1)[-1]
        ok, cible = services.desinscrire_via_token(token)
        self.assertTrue(ok, cible)
        self.assertEqual(cible, 'client@example.ma')
        self.assertTrue(services.est_supprime(self.co, 'client@example.ma'))
        # Et personne d'autre : le jeton est signé par destinataire.
        self.assertFalse(services.est_supprime(self.co, 'autre@example.ma'))

    def test_destinataire_obligatoire(self):
        resp = self.api.get(
            f'{CAMPAGNES}{self.campagne.id}/lien-desinscription/')
        self.assertEqual(resp.status_code, 400, resp.content)


class ImportListeOppositionTests(TestCase):
    """DRAFT165-22 — la liste d'opposition loi 09-08 entre dans l'ERP."""

    def setUp(self):
        self.co = make_company('audv17-oppo', 'AUDV17 Opposition')
        self.api = auth(make_user(self.co, 'audv17-oppo-user'))

    def test_import_puis_reimport_idempotent(self):
        premier = self.api.post(f'{CAMPAGNES}importer-opposition/', {
            'destinataires': ['a@example.ma', 'b@example.ma'],
        }, format='json')
        self.assertEqual(premier.status_code, 201, premier.content)
        self.assertEqual(premier.data['ajoutes'], 2)
        second = self.api.post(f'{CAMPAGNES}importer-opposition/', {
            'destinataires': ['a@example.ma', 'c@example.ma'],
        }, format='json')
        self.assertEqual(second.data['ajoutes'], 1)
        self.assertEqual(second.data['deja_presents'], 1)
        self.assertEqual(
            SuppressionMarketing.objects.filter(company=self.co).count(), 3)

    def test_un_destinataire_en_opposition_n_est_plus_jamais_cible(self):
        self.api.post(f'{CAMPAGNES}importer-opposition/', {
            'destinataires': ['oppose@example.ma'],
        }, format='json')
        campagne = Campagne.objects.create(
            company=self.co, nom='Promo', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(
            campagne, destinataires=['oppose@example.ma', 'ok@example.ma'])
        campagne.refresh_from_db()
        self.assertEqual(campagne.nb_destinataires, 1)
        self.assertFalse(EnvoiCampagne.objects.filter(
            campagne=campagne, destinataire='oppose@example.ma').exists())

    def test_liste_vide_refusee(self):
        resp = self.api.post(f'{CAMPAGNES}importer-opposition/',
                             {'destinataires': []}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class BorneCheckInEvenementTests(TestCase):
    """DRAFT165-49 (ZMKT18) — émargement libre-service par QR ou recherche."""

    def setUp(self):
        self.co = make_company('audv17-borne', 'AUDV17 Borne')
        self.api = auth(make_user(self.co, 'audv17-borne-user'))
        self.evenement = EvenementMarketing.objects.create(
            company=self.co, nom='Salon solaire',
            date_debut=date(2026, 10, 1))
        # `inscrire_evenement` est le SEUL chemin qui pose un jeton QR :
        # créer l'inscription à la main la laisserait sans badge scannable.
        self.inscription = services.inscrire_evenement(
            self.evenement, nom='Sara Bennani', email='sara@example.ma')

    def test_pointage_par_qr_token(self):
        resp = self.api.post(f'{INSCRIPTIONS}pointer-borne/', {
            'evenement': self.evenement.id,
            'qr_token': self.inscription.qr_token,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.inscription.refresh_from_db()
        self.assertEqual(self.inscription.statut,
                         InscriptionEvenement.Statut.PRESENT)
        self.assertIsNotNone(self.inscription.date_pointage)

    def test_pointage_par_selection_apres_recherche(self):
        resp = self.api.post(f'{INSCRIPTIONS}pointer-borne/', {
            'evenement': self.evenement.id,
            'inscription': self.inscription.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.inscription.refresh_from_db()
        self.assertEqual(self.inscription.statut,
                         InscriptionEvenement.Statut.PRESENT)

    def test_rescanner_le_meme_badge_ne_double_pas_la_presence(self):
        corps = {'evenement': self.evenement.id,
                 'qr_token': self.inscription.qr_token}
        self.api.post(f'{INSCRIPTIONS}pointer-borne/', corps, format='json')
        self.inscription.refresh_from_db()
        premier = self.inscription.date_pointage
        self.api.post(f'{INSCRIPTIONS}pointer-borne/', corps, format='json')
        self.inscription.refresh_from_db()
        self.assertEqual(self.inscription.date_pointage, premier)

    def test_qr_d_un_autre_evenement_refuse(self):
        autre_evenement = EvenementMarketing.objects.create(
            company=self.co, nom='Autre salon', date_debut=date(2026, 11, 1))
        resp = self.api.post(f'{INSCRIPTIONS}pointer-borne/', {
            'evenement': autre_evenement.id,
            'qr_token': self.inscription.qr_token,
        }, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_sans_qr_ni_inscription_refuse(self):
        resp = self.api.post(f'{INSCRIPTIONS}pointer-borne/', {
            'evenement': self.evenement.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_evenement_d_une_autre_societe_refuse(self):
        autre = make_company('audv17-borne-autre', 'AUDV17 Borne Autre')
        evenement_autre = EvenementMarketing.objects.create(
            company=autre, nom='Hors société', date_debut=date(2026, 10, 1))
        resp = self.api.post(f'{INSCRIPTIONS}pointer-borne/', {
            'evenement': evenement_autre.id,
            'inscription': self.inscription.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
