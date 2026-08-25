"""T-TRACE (ordres fondateur 25/08/2026) — traçage des visiteurs EXTERNES,
alerte concurrent, direction systématiquement notifiée.

Ce que ce fichier ÉPINGLE, promesse par promesse :

  (a) le modèle et ses deux index company-scopés existent, et la rétention est
      « pas de purge » (aucun mécanisme d'expiration n'est branché) ;
  (b) le traçage est BEST-EFFORT : une exception levée au cœur du service ne
      remonte JAMAIS — ni au beacon, ni à la page proposition, ni au
      questionnaire, ni au webhook lead ;
  (c) les BATTEMENTS du beacon prolongent LA MÊME visite (jamais une ligne
      toutes les 20 s), la durée ne recule jamais, et `fin` clôt la visite ;
  (d) l'ouverture PUBLIQUE d'une proposition trace, l'aperçu par le jeton
      INTERNE ne trace RIEN (règle L-INTPREV, jamais affaiblie) ;
  (e) la notification de création de lead porte l'historique RÉEL de
      l'appareil, et RIEN quand il n'y a pas d'historique (« zéro chiffre
      inventé ») ;
  (f) l'alerte ROUGE part quand un appareil déjà rattaché à un lead redemande
      un devis, et la corrélation « concurrent » part quand un appareil suit
      ≥ 2 prospects ;
  (g) la DIRECTION est destinataire de TOUTES ces notifications ;
  (h) rien ne fuit d'une société à l'autre.

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_visites_externes -v 2
"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.notifications.severity import severity_of
from authentication.models import Company

from . import visites
from .models import Lead, VisiteExterne

User = get_user_model()

SECRET = 'test-secret-t-trace-999'
APPAREIL = '7f2a1c9e-4b52-4a1f-9f0e-2d8c6b3a5e71'
AUTRE_APPAREIL = '00000000-1111-2222-3333-444444444444'


# ── helpers ──────────────────────────────────────────────────────────────────

def make_company(slug):
    """Sociétés VRAIMENT distinctes : le slug (unique) est l'argument, jamais
    une valeur par défaut partagée entre deux appels."""
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_directeur(company, username):
    from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
    role, _ = Role.objects.get_or_create(
        company=company, nom='Directeur',
        defaults={'permissions': DIRECTEUR_PERMISSIONS, 'est_systeme': True})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


def make_commercial(company, username):
    from apps.roles.models import COMMERCIAL_PERMISSIONS, Role
    role, _ = Role.objects.get_or_create(
        company=company, nom='Commercial',
        defaults={'permissions': COMMERCIAL_PERMISSIONS, 'est_systeme': True})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


def payload_site(**extra):
    """Charge utile du site, réduite à ce dont T-TRACE a besoin."""
    base = {
        'fullName': 'Amina Benali',
        'phoneE164': '+212661850410',
        'city': 'Casablanca',
        'consent': True,
        'qualified': True,
        'page': '/',
    }
    base.update(extra)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# (a) Le modèle
# ═══════════════════════════════════════════════════════════════════════════

class TestModeleVisiteExterne(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-modele')

    def test_creation_minimale_et_defauts(self):
        visite = VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.VISITE_SITE)
        self.assertIsNone(visite.lead)
        self.assertEqual(visite.duree_s, 0)
        self.assertFalse(visite.terminee)
        self.assertEqual(visite.appareil_id, '')
        self.assertIsNotNone(visite.created_at)

    def test_les_deux_index_company_scopes_sont_declares(self):
        noms = {index.name for index in VisiteExterne._meta.indexes}
        self.assertIn('crm_visite_comp_app_idx', noms)
        self.assertIn('crm_visite_comp_ip_idx', noms)
        for index in VisiteExterne._meta.indexes:
            # Les deux recherches sont company-scopées : un index qui ne
            # commencerait pas par `company` inviterait un scan cross-tenant.
            self.assertEqual(index.fields[0], 'company')

    def test_aucune_purge_automatique_nest_branchee(self):
        """« keep them stored » : rien dans le modèle ne fait expirer une
        trace (pas de champ d'expiration, pas de TTL)."""
        champs = {f.name for f in VisiteExterne._meta.get_fields()}
        for interdit in ('expires_at', 'expire_le', 'purge_at', 'ttl'):
            self.assertNotIn(interdit, champs)

    def test_le_jeton_nest_jamais_stocke_en_entier(self):
        jeton = 'a' * 40 + 'FINALE'
        visite = visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.PROPOSITION,
            appareil_id=APPAREIL, token=jeton)
        self.assertEqual(visite.token_suffixe, 'FINALE')
        self.assertNotIn(jeton, visite.token_suffixe)


# ═══════════════════════════════════════════════════════════════════════════
# (b) Best-effort — le traçage ne casse JAMAIS un point public
# ═══════════════════════════════════════════════════════════════════════════

class TestServiceBestEffort(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-besteffort')

    def test_une_exception_de_tracage_ne_remonte_pas(self):
        with patch.object(VisiteExterne.objects, 'create',
                          side_effect=RuntimeError('base en panne')):
            resultat = visites.enregistrer_visite_externe(
                self.company, point=VisiteExterne.Point.VISITE_SITE,
                appareil_id=APPAREIL)
        self.assertIsNone(resultat)

    def test_societe_absente_ne_leve_pas(self):
        self.assertIsNone(visites.enregistrer_visite_externe(
            None, point=VisiteExterne.Point.VISITE_SITE))

    def test_valeurs_illisibles_sont_ignorees_sans_erreur(self):
        visite = visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL, duree_s='pas un nombre')
        self.assertEqual(visite.duree_s, 0)

    def test_duree_aberrante_est_bornee(self):
        visite = visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL, duree_s=999999)
        self.assertEqual(visite.duree_s, visites.MAX_DUREE_S)

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
    def test_le_beacon_repond_ok_meme_si_lecriture_est_impossible(self):
        """Un beacon ne doit JAMAIS faire apparaître une erreur chez le
        visiteur — même quand la base refuse l'écriture."""
        with patch.object(VisiteExterne.objects, 'create',
                          side_effect=RuntimeError('base en panne')):
            reponse = APIClient().post(
                reverse('public-visite'),
                {'appareil_id': APPAREIL, 'page': '/tarifs'},
                format='json', HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), {'ok': True})
        self.assertEqual(VisiteExterne.objects.count(), 0)


# ═══════════════════════════════════════════════════════════════════════════
# (c) Le beacon public et ses battements
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TestBeaconPublic(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-beacon')
        self.url = reverse('public-visite')

    def battre(self, **corps):
        donnees = {'appareil_id': APPAREIL, 'page': '/tarifs'}
        donnees.update(corps)
        return APIClient().post(self.url, donnees, format='json',
                                HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_url_conforme_au_contrat(self):
        self.assertEqual(self.url, '/api/django/crm/public/visite/')

    def test_lauth_est_LITTERALEMENT_celle_du_webhook_lead(self):
        """Décision d'orchestration du 25/08/2026 : le beacon exige le MÊME
        secret que le webhook lead. On épingle l'IDENTITÉ des fonctions (pas
        une simple ressemblance) pour qu'un futur refactor ne puisse pas
        forker silencieusement les deux mécanismes d'authentification."""
        from . import public_visite_views, webhooks
        self.assertIs(public_visite_views._secret_ok, webhooks._secret_ok)
        self.assertIs(public_visite_views._freshness_ok, webhooks._freshness_ok)
        self.assertIs(
            public_visite_views._resolve_company, webhooks._resolve_company)

    def test_sans_secret_401_et_aucune_trace(self):
        reponse = APIClient().post(
            self.url, {'appareil_id': APPAREIL}, format='json')
        self.assertEqual(reponse.status_code, 401)
        self.assertEqual(VisiteExterne.objects.count(), 0)

    def test_mauvais_secret_401(self):
        reponse = APIClient().post(
            self.url, {'appareil_id': APPAREIL}, format='json',
            HTTP_X_WEBHOOK_SECRET='faux')
        self.assertEqual(reponse.status_code, 401)
        self.assertEqual(VisiteExterne.objects.count(), 0)

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='')
    def test_secret_non_configure_ferme_lendpoint(self):
        reponse = APIClient().post(
            self.url, {'appareil_id': APPAREIL}, format='json',
            HTTP_X_WEBHOOK_SECRET='')
        self.assertEqual(reponse.status_code, 401)

    def test_horodatage_hors_tolerance_401(self):
        vieux = (timezone.now() - timedelta(hours=3)).isoformat()
        reponse = APIClient().post(
            self.url, {'appareil_id': APPAREIL}, format='json',
            HTTP_X_WEBHOOK_SECRET=SECRET, HTTP_X_WEBHOOK_TIMESTAMP=vieux)
        self.assertEqual(reponse.status_code, 401)
        self.assertEqual(VisiteExterne.objects.count(), 0)

    def test_premier_battement_cree_une_visite(self):
        reponse = self.battre(duree_s=20, langue='fr')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), {'ok': True})
        visite = VisiteExterne.objects.get()
        self.assertEqual(visite.company, self.company)
        self.assertEqual(visite.appareil_id, APPAREIL)
        self.assertEqual(visite.contexte, '/tarifs')
        self.assertEqual(visite.duree_s, 20)
        self.assertEqual(visite.langue, 'fr')
        self.assertEqual(visite.point, VisiteExterne.Point.VISITE_SITE)
        self.assertFalse(visite.terminee)

    def test_battements_successifs_mettent_a_jour_la_meme_visite(self):
        for duree in (20, 40, 60):
            self.battre(duree_s=duree)
        self.assertEqual(VisiteExterne.objects.count(), 1)
        self.assertEqual(VisiteExterne.objects.get().duree_s, 60)

    def test_un_battement_en_retard_ne_fait_pas_reculer_la_duree(self):
        self.battre(duree_s=120)
        self.battre(duree_s=40)
        self.assertEqual(VisiteExterne.objects.get().duree_s, 120)

    def test_fin_cloture_la_visite_et_la_suivante_est_neuve(self):
        self.battre(duree_s=30, fin=True)
        visite = VisiteExterne.objects.get()
        self.assertTrue(visite.terminee)
        self.battre(duree_s=5)
        self.assertEqual(VisiteExterne.objects.count(), 2)

    def test_deux_pages_donnent_deux_visites(self):
        self.battre(page='/tarifs')
        self.battre(page='/references')
        self.assertEqual(VisiteExterne.objects.count(), 2)

    def test_ip_et_navigateur_sont_lus_cote_serveur(self):
        APIClient().post(
            self.url, {'appareil_id': APPAREIL, 'page': '/tarifs',
                       'ip': '9.9.9.9', 'user_agent': 'MENTEUR'},
            format='json', HTTP_X_WEBHOOK_SECRET=SECRET,
            HTTP_X_FORWARDED_FOR='41.77.1.5, 10.0.0.1',
            HTTP_USER_AGENT='Mozilla/5.0 (Android)')
        visite = VisiteExterne.objects.get()
        # L'IP du corps est IGNORÉE : seule celle des en-têtes compte.
        self.assertEqual(visite.ip, '41.77.1.5')
        self.assertNotEqual(visite.ip, '9.9.9.9')
        self.assertIn('Mozilla', visite.user_agent)
        self.assertNotEqual(visite.user_agent, 'MENTEUR')

    def test_sans_appareil_les_battements_se_regroupent_sur_ip_et_navigateur(self):
        """Repli anti-explosion de lignes : tant que le site n'a pas posé
        d'``appareil_id``, deux battements du même visiteur sur la même page
        doivent tout de même prolonger LA MÊME visite — sinon une proposition
        lue 10 minutes produirait des dizaines de lignes."""
        for duree in (20, 40):
            APIClient().post(
                self.url, {'page': '/tarifs', 'duree_s': duree},
                format='json', HTTP_X_WEBHOOK_SECRET=SECRET,
                HTTP_X_FORWARDED_FOR='41.77.1.5',
                HTTP_USER_AGENT='Mozilla/5.0 (Android)')
        self.assertEqual(VisiteExterne.objects.count(), 1)
        visite = VisiteExterne.objects.get()
        self.assertEqual(visite.duree_s, 40)
        self.assertEqual(visite.appareil_id, '')

    def test_deux_navigateurs_derriere_la_meme_ip_restent_distincts(self):
        """Le repli ne doit JAMAIS fusionner deux visiteurs : au Maroc une IP
        est massivement partagée, donc le navigateur fait partie de la clé."""
        for agent in ('Mozilla/5.0 (Android)', 'Mozilla/5.0 (iPhone)'):
            APIClient().post(
                self.url, {'page': '/tarifs', 'duree_s': 20},
                format='json', HTTP_X_WEBHOOK_SECRET=SECRET,
                HTTP_X_FORWARDED_FOR='41.77.1.5', HTTP_USER_AGENT=agent)
        self.assertEqual(VisiteExterne.objects.count(), 2)

    def test_reponse_muette_ne_fuit_aucun_etat_interne(self):
        self.battre(duree_s=10)
        corps = self.battre(duree_s=30).json()
        self.assertEqual(set(corps), {'ok'})


# ═══════════════════════════════════════════════════════════════════════════
# (d) Proposition — le PUBLIC trace, l'aperçu INTERNE ne trace RIEN
# ═══════════════════════════════════════════════════════════════════════════

class TestAccrocheProposition(TestCase):
    """L-INTPREV ne doit JAMAIS être affaiblie par T-TRACE : l'aperçu du
    commercial reste totalement muet, traçage anti-fraude compris.

    On appelle l'accroche elle-même (``_stamp_view_si_public``) avec une
    requête fabriquée plutôt que l'endpoint complet : c'est EXACTEMENT le
    point modifié, et le test ne dépend alors ni du moteur de devis ni du
    rendu PDF."""

    def setUp(self):
        from decimal import Decimal

        from apps.ventes.models import Devis, ShareLink

        from .models import Client as CrmClient

        self.company = make_company('ttrace-proposition')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect Proposition')
        client_obj = CrmClient.objects.create(
            company=self.company, nom='Proposition', prenom='Test')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-TTRACE-1',
            client=client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    def _requete(self, jeton_appareil=APPAREIL):
        from django.test import RequestFactory
        return RequestFactory().get(
            f'/api/django/public/proposition/{self.link.token}/',
            {'appareil_id': jeton_appareil},
            HTTP_X_FORWARDED_FOR='41.77.1.5',
            HTTP_USER_AGENT='Mozilla/5.0 (Android)')

    def test_ouverture_publique_trace_la_visite(self):
        from apps.ventes.public_views import _stamp_view_si_public

        _stamp_view_si_public(self.link, False, self._requete())
        visite = VisiteExterne.objects.get()
        self.assertEqual(visite.point, VisiteExterne.Point.PROPOSITION)
        self.assertEqual(visite.company, self.company)
        self.assertEqual(visite.lead_id, self.lead.pk)
        self.assertEqual(visite.appareil_id, APPAREIL)
        self.assertEqual(visite.ip, '41.77.1.5')
        self.assertIn('DEV-TTRACE-1', visite.contexte)
        # Le jeton n'est jamais stocké en entier.
        self.assertEqual(visite.token_suffixe, self.link.token[-6:])

    def test_apercu_par_le_jeton_interne_ne_trace_rien(self):
        from apps.ventes.public_views import _stamp_view_si_public

        _stamp_view_si_public(self.link, True, self._requete())
        self.assertEqual(VisiteExterne.objects.count(), 0)

    def test_sans_requete_le_comportement_dorigine_est_inchange(self):
        """Un appelant qui ne passe pas ``request`` (chemin historique) ne
        crée aucune trace — l'ajout est strictement additif."""
        from apps.ventes.public_views import _stamp_view_si_public

        _stamp_view_si_public(self.link, False)
        self.assertEqual(VisiteExterne.objects.count(), 0)


# ═══════════════════════════════════════════════════════════════════════════
# (d bis) Questionnaire — le CLIENT trace, l'aperçu INTERNE ne trace RIEN
# ═══════════════════════════════════════════════════════════════════════════

class TestAccrocheQuestionnaire(TestCase):
    """La garde L-QUEST (« un aperçu ne déclenche rien ») doit rester vraie
    après T-TRACE : le jeton INTERNE ne peut pas écrire, donc il ne peut pas
    non plus laisser de trace de visite."""

    def setUp(self):
        from .models import QuestionnaireLien

        self.company = make_company('ttrace-questionnaire')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect Questionnaire')
        self.lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead)

    def _url(self, token):
        return reverse('public-questionnaire', args=[token])

    def test_reponse_client_trace_la_visite(self):
        reponse = APIClient().post(
            self._url(self.lien.token),
            {'section': 'contact', 'reponses': {'ville': 'Casablanca'},
             'appareil_id': APPAREIL},
            format='json')
        self.assertEqual(reponse.status_code, 200)
        visite = VisiteExterne.objects.get()
        self.assertEqual(visite.point, VisiteExterne.Point.QUESTIONNAIRE)
        self.assertEqual(visite.lead_id, self.lead.pk)
        self.assertEqual(visite.appareil_id, APPAREIL)
        self.assertEqual(visite.token_suffixe, self.lien.token[-6:])

    def test_le_GET_ne_trace_rien(self):
        """``_detail`` promet « aucune écriture, aucune trace » — c'est cette
        promesse qui rend l'aperçu interne muet ; T-TRACE ne l'entame pas."""
        reponse = APIClient().get(self._url(self.lien.token))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(VisiteExterne.objects.count(), 0)

    def test_le_jeton_interne_ne_trace_rien(self):
        reponse = APIClient().post(
            self._url(self.lien.token_interne),
            {'section': 'contact', 'reponses': {'ville': 'Casablanca'},
             'appareil_id': APPAREIL},
            format='json')
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(VisiteExterne.objects.count(), 0)


# ═══════════════════════════════════════════════════════════════════════════
# (e)+(f)+(g) Webhook lead : historique, alerte rouge, direction
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TestAccrocheWebhookLead(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-webhook')
        self.directeur = make_directeur(self.company, 'ttrace-dir')
        self.url = reverse('website-lead-webhook')

    def poster(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def visiter(self, appareil=APPAREIL, page='/tarifs', duree=60):
        return visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=appareil, contexte=page, duree_s=duree, fin=True)

    def test_appareil_id_du_payload_est_range_sur_le_lead(self):
        reponse = self.poster(payload_site(appareil_id=APPAREIL))
        self.assertEqual(reponse.status_code, 201)
        lead = Lead.objects.get(pk=reponse.json()['lead_id'])
        self.assertEqual(lead.appareil_id, APPAREIL)

    def test_alias_camelcase_accepte(self):
        reponse = self.poster(payload_site(appareilId=APPAREIL))
        lead = Lead.objects.get(pk=reponse.json()['lead_id'])
        self.assertEqual(lead.appareil_id, APPAREIL)

    def test_sans_appareil_id_le_champ_reste_null(self):
        reponse = self.poster(payload_site())
        lead = Lead.objects.get(pk=reponse.json()['lead_id'])
        self.assertIsNone(lead.appareil_id)

    def test_la_demande_est_tracee_comme_visite_tunnel(self):
        reponse = self.poster(payload_site(appareil_id=APPAREIL))
        lead_id = reponse.json()['lead_id']
        trace = VisiteExterne.objects.get(
            point=VisiteExterne.Point.TUNNEL_LEAD)
        self.assertEqual(trace.lead_id, lead_id)
        self.assertEqual(trace.appareil_id, APPAREIL)

    def test_les_visites_anonymes_sont_rattachees_retroactivement(self):
        anonyme = self.visiter()
        self.assertIsNone(anonyme.lead_id)
        reponse = self.poster(payload_site(appareil_id=APPAREIL))
        anonyme.refresh_from_db()
        self.assertEqual(anonyme.lead_id, reponse.json()['lead_id'])

    def test_notification_de_creation_porte_lhistorique_reel(self):
        self.visiter(duree=180)
        self.visiter(page='/references', duree=120)
        self.poster(payload_site(appareil_id=APPAREIL))
        notif = Notification.objects.filter(
            event_type='lead_new', recipient=self.directeur).first()
        self.assertIsNotNone(notif)
        self.assertIn('A visité le site 2 fois avant sa demande', notif.body)
        self.assertIn('durée totale 5 min', notif.body)

    def test_sans_historique_la_notification_ne_dit_rien(self):
        """« zéro chiffre inventé » : jamais « 0 visite », jamais une durée
        estimée — la phrase est simplement absente."""
        self.poster(payload_site(appareil_id=AUTRE_APPAREIL))
        notif = Notification.objects.filter(
            event_type='lead_new', recipient=self.directeur).first()
        self.assertIsNotNone(notif)
        self.assertNotIn('A visité le site', notif.body)
        self.assertNotIn('0 fois', notif.body)

    def test_la_direction_recoit_la_notification_de_creation(self):
        self.poster(payload_site(appareil_id=APPAREIL))
        self.assertTrue(Notification.objects.filter(
            event_type='lead_new', recipient=self.directeur).exists())

    def test_alerte_rouge_quand_lappareil_sert_deja_un_autre_lead(self):
        premier = self.poster(payload_site(appareil_id=APPAREIL))
        self.assertEqual(premier.status_code, 201)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_appareil_partage').exists())

        second = self.poster(payload_site(
            appareil_id=APPAREIL, fullName='Karim Autre',
            phoneE164='+212600000002'))
        self.assertEqual(second.status_code, 201)
        alertes = Notification.objects.filter(
            event_type='visiteur_appareil_partage')
        self.assertTrue(alertes.exists())
        alerte = alertes.first()
        # « with red » — la sévérité EST le rouge du système.
        self.assertEqual(severity_of('visiteur_appareil_partage'), 'critique')
        self.assertIn('🔴', alerte.title)
        self.assertIn(str(premier.json()['lead_id']), alerte.body)
        # « and director as well »
        self.assertTrue(alertes.filter(recipient=self.directeur).exists())

    def test_pas_dalerte_pour_deux_appareils_differents(self):
        self.poster(payload_site(appareil_id=APPAREIL))
        self.poster(payload_site(appareil_id=AUTRE_APPAREIL,
                                 phoneE164='+212600000003'))
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_appareil_partage').exists())


# ═══════════════════════════════════════════════════════════════════════════
# (f) Corrélation « concurrent »
# ═══════════════════════════════════════════════════════════════════════════

class TestAlerteConcurrent(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-concurrent')
        self.directeur = make_directeur(self.company, 'ttrace-dir-conc')
        self.lead_a = Lead.objects.create(company=self.company, nom='Client A')
        self.lead_b = Lead.objects.create(company=self.company, nom='Client B')

    def consulter(self, lead, appareil=APPAREIL, ip=''):
        return visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.PROPOSITION, lead=lead,
            appareil_id=appareil, ip=ip, contexte=f'Ouverture devis {lead.pk}')

    def test_un_seul_prospect_ne_declenche_rien(self):
        self.consulter(self.lead_a)
        visites.detecter_concurrent(self.company, appareil_id=APPAREIL)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())

    def test_deux_prospects_sur_le_meme_appareil_declenchent_lalerte(self):
        self.consulter(self.lead_a)
        self.consulter(self.lead_b)
        visites.detecter_concurrent(self.company, appareil_id=APPAREIL)
        alerte = Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte',
            recipient=self.directeur).first()
        self.assertIsNotNone(alerte)
        self.assertEqual(
            severity_of('visiteur_concurrent_suspecte'), 'critique')
        self.assertIn('🔴', alerte.title)
        self.assertIn('appareil', alerte.title.lower())
        self.assertIn('FORT', alerte.body)

    def test_lalerte_ne_se_repete_pas_pour_le_meme_couple(self):
        self.consulter(self.lead_a)
        self.consulter(self.lead_b)
        for _ in range(3):
            visites.detecter_concurrent(self.company, appareil_id=APPAREIL)
        self.assertEqual(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte',
            recipient=self.directeur).count(), 1)

    def test_signal_ip_est_libelle_prudemment(self):
        self.consulter(self.lead_a, appareil='', ip='41.77.1.5')
        self.consulter(self.lead_b, appareil='', ip='41.77.1.5')
        visites.detecter_concurrent(self.company, ip='41.77.1.5')
        alerte = Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte',
            recipient=self.directeur).first()
        self.assertIsNotNone(alerte)
        self.assertIn('FAIBLE', alerte.body)
        self.assertIn('partagée', alerte.body)
        # L'IP ne doit JAMAIS être présentée comme une preuve.
        self.assertIn('jamais comme une preuve', alerte.body)

    def test_les_visites_anonymes_du_site_ne_comptent_pas(self):
        """Deux visiteurs anonymes du même cybercafé ne sont pas un
        concurrent : seuls les points qui désignent un prospect NOMMÉ
        alimentent la corrélation."""
        for lead in (self.lead_a, self.lead_b):
            visites.enregistrer_visite_externe(
                self.company, point=VisiteExterne.Point.VISITE_SITE,
                lead=lead, appareil_id=APPAREIL, contexte='/tarifs')
        visites.detecter_concurrent(self.company, appareil_id=APPAREIL)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())

    def test_hors_fenetre_de_30_jours_aucune_correlation(self):
        v1 = self.consulter(self.lead_a)
        self.consulter(self.lead_b)
        vieux = timezone.now() - timedelta(
            days=visites.FENETRE_CORRELATION_JOURS + 5)
        VisiteExterne.objects.filter(pk=v1.pk).update(created_at=vieux)
        visites.detecter_concurrent(self.company, appareil_id=APPAREIL)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())


# ═══════════════════════════════════════════════════════════════════════════
# (g) La direction, toujours
# ═══════════════════════════════════════════════════════════════════════════

class TestDirectionToujoursDestinataire(TestCase):
    def setUp(self):
        self.company = make_company('ttrace-direction')
        self.directeur = make_directeur(self.company, 'ttrace-dir-d')
        self.commercial = make_commercial(self.company, 'ttrace-com-d')

    def test_utilisateurs_direction_retourne_le_directeur(self):
        trouves = visites.utilisateurs_direction(self.company)
        self.assertIn(self.directeur, trouves)
        self.assertNotIn(self.commercial, trouves)

    def test_avec_direction_ajoute_sans_dupliquer_ni_reordonner(self):
        combines = visites.avec_direction([self.commercial], self.company)
        self.assertEqual(combines[0], self.commercial)
        self.assertIn(self.directeur, combines)
        self.assertEqual(len(combines), len(set(u.pk for u in combines)))

    def test_direction_deja_presente_nest_pas_dupliquee(self):
        combines = visites.avec_direction(
            [self.directeur, self.commercial], self.company)
        self.assertEqual(
            [u.pk for u in combines].count(self.directeur.pk), 1)

    def test_societe_sans_direction_ne_fabrique_aucun_destinataire(self):
        autre = make_company('ttrace-direction-vide')
        self.assertEqual(visites.utilisateurs_direction(autre), [])

    def test_un_directeur_inactif_nest_pas_notifie(self):
        self.directeur.is_active = False
        self.directeur.save(update_fields=['is_active'])
        self.assertNotIn(
            self.directeur, visites.utilisateurs_direction(self.company))


# ═══════════════════════════════════════════════════════════════════════════
# (h) Étanchéité multi-société
# ═══════════════════════════════════════════════════════════════════════════

class TestIsolationMultiSociete(TestCase):
    def setUp(self):
        self.co1 = make_company('ttrace-tenant-un')
        self.co2 = make_company('ttrace-tenant-deux')
        self.dir1 = make_directeur(self.co1, 'ttrace-dir-1')
        self.dir2 = make_directeur(self.co2, 'ttrace-dir-2')

    def test_lhistorique_dun_appareil_ne_traverse_pas_les_societes(self):
        visites.enregistrer_visite_externe(
            self.co1, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL, duree_s=60)
        self.assertEqual(
            visites.historique_appareil(self.co1, APPAREIL)['visites'], 1)
        self.assertIsNone(visites.historique_appareil(self.co2, APPAREIL))

    def test_la_direction_dune_societe_nest_pas_celle_de_lautre(self):
        self.assertEqual(
            visites.utilisateurs_direction(self.co1), [self.dir1])
        self.assertEqual(
            visites.utilisateurs_direction(self.co2), [self.dir2])

    def test_le_meme_appareil_chez_deux_societes_ne_correle_pas(self):
        lead1 = Lead.objects.create(company=self.co1, nom='Chez un')
        lead2 = Lead.objects.create(company=self.co2, nom='Chez deux')
        for company, lead in ((self.co1, lead1), (self.co2, lead2)):
            visites.enregistrer_visite_externe(
                company, point=VisiteExterne.Point.PROPOSITION, lead=lead,
                appareil_id=APPAREIL, contexte='Ouverture devis')
        visites.detecter_concurrent(self.co1, appareil_id=APPAREIL)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())

    def test_lalerte_doublon_ne_regarde_que_sa_propre_societe(self):
        Lead.objects.create(
            company=self.co2, nom='Homonyme ailleurs', appareil_id=APPAREIL)
        lead = Lead.objects.create(
            company=self.co1, nom='Nouveau ici', appareil_id=APPAREIL)
        visites.alerter_appareil_partage(lead)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_appareil_partage').exists())
