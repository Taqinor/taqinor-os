"""CAD178 (audit CAD86, 24/09/2026) — les gestes clés de la cadence, par
famille d'appareil.

Constat : les 4 écrans de cadence n'avaient AUCUNE trace d'usage mobile ; la
mesure CAD87/CAD100 était 100 % desktop. Ce fichier verrouille :

  * ``famille_appareil`` classe un User-Agent en mobile/tablette/ordinateur/
    inconnu, sans inventer une famille pour une requête sans User-Agent ;
  * ``enregistrer_geste_appareil`` incrémente un compteur JOURNALIER (jamais
    un événement par clic conservé indéfiniment), BEST-EFFORT (une erreur
    interne ne fait jamais échouer le geste métier qu'elle mesure) ;
  * les 4 endpoints existants (``fait``, ``reporter``, ``whatsapp``) et le
    nouveau (``appel-compose``, CAD80 : « Appeler » ne touchait jamais le
    serveur) comptent chacun leur geste, jamais un autre ;
  * ``gestes_par_appareil`` (servie par ``mesure_cadence``) agrège sur la
    fenêtre, multi-tenant, et le contrat ``mesure_cadence.json`` (PACT10)
    porte la même forme que ce que le serveur sert réellement.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, mesure_cadence, stages
from apps.crm.models import GesteRelanceAppareil, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 28, 12, 0, tzinfo=horaires.CASABLANCA)

UA_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 '
             'Mobile/15E148 Safari/604.1')
UA_ANDROID_PHONE = ('Mozilla/5.0 (Linux; Android 14; Pixel 8) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 '
                    'Mobile Safari/537.36')
UA_IPAD = ('Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) '
           'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 '
           'Mobile/15E148 Safari/604.1')
UA_DESKTOP = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class FamilleAppareilTests(SimpleTestCase):
    """Classification pure — aucune base de données."""

    def test_iphone_est_mobile(self):
        self.assertEqual(mesure_cadence.famille_appareil(UA_IPHONE),
                         GesteRelanceAppareil.FamilleAppareil.MOBILE)

    def test_android_telephone_est_mobile(self):
        self.assertEqual(mesure_cadence.famille_appareil(UA_ANDROID_PHONE),
                         GesteRelanceAppareil.FamilleAppareil.MOBILE)

    def test_ipad_est_tablette_jamais_mobile(self):
        """iPadOS porte « iPad » mais AUCUN jeton « Mobi » : sans la garde
        tablette AVANT le motif mobile générique, il tomberait à tort en
        mobile — l'ordre des deux motifs est ce qui compte ici."""
        self.assertEqual(mesure_cadence.famille_appareil(UA_IPAD),
                         GesteRelanceAppareil.FamilleAppareil.TABLETTE)

    def test_desktop_est_ordinateur(self):
        self.assertEqual(mesure_cadence.famille_appareil(UA_DESKTOP),
                         GesteRelanceAppareil.FamilleAppareil.ORDINATEUR)

    def test_user_agent_absent_est_inconnu_jamais_ordinateur_par_defaut(self):
        self.assertEqual(mesure_cadence.famille_appareil(''),
                         GesteRelanceAppareil.FamilleAppareil.INCONNU)
        self.assertEqual(mesure_cadence.famille_appareil(None),
                         GesteRelanceAppareil.FamilleAppareil.INCONNU)


class EnregistrerGesteAppareilTests(TestCase):
    slug = 'cad178-compteur'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)

    def test_premier_geste_cree_la_ligne_a_un(self):
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'fait', UA_IPHONE)
        ligne = GesteRelanceAppareil.objects.get(
            company=self.company, geste='fait', famille_appareil='mobile')
        self.assertEqual(ligne.total, 1)
        self.assertEqual(ligne.jour, MAINTENANT.date())

    def test_gestes_repetes_incrementent_la_meme_ligne(self):
        for _ in range(3):
            mesure_cadence.enregistrer_geste_appareil(
                self.company, 'whatsapp', UA_ANDROID_PHONE)
        self.assertEqual(GesteRelanceAppareil.objects.filter(
            company=self.company, geste='whatsapp',
            famille_appareil='mobile').count(), 1)
        ligne = GesteRelanceAppareil.objects.get(
            company=self.company, geste='whatsapp', famille_appareil='mobile')
        self.assertEqual(ligne.total, 3)

    def test_gestes_et_familles_distincts_ne_se_melangent_jamais(self):
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'appeler', UA_IPHONE)
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'appeler', UA_DESKTOP)
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'reporter', UA_IPHONE)
        self.assertEqual(GesteRelanceAppareil.objects.filter(
            company=self.company).count(), 3)

    def test_best_effort_ne_leve_jamais(self):
        """Une société ``None`` (donnée invalide) ne fait jamais planter
        l'appelant — c'est tout le sens du « best-effort »."""
        try:
            mesure_cadence.enregistrer_geste_appareil(None, 'fait', UA_IPHONE)
        except Exception as exc:  # noqa: BLE001 — l'assertion EST le test
            self.fail(f'enregistrer_geste_appareil a levé : {exc!r}')


class GestesParAppareilAgregationTests(TestCase):
    slug = 'cad178-agregat'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)

    def test_agrege_sur_la_fenetre_multi_tenant(self):
        autre = _company('cad178-agregat-autre')
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'fait', UA_IPHONE)
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'fait', UA_IPHONE)
        mesure_cadence.enregistrer_geste_appareil(
            autre, 'fait', UA_IPHONE)
        lignes = mesure_cadence.gestes_par_appareil(self.company)
        self.assertEqual(lignes, [
            {'geste': 'fait', 'famille_appareil': 'mobile', 'total': 2}])

    def test_hors_fenetre_ignore(self):
        GesteRelanceAppareil.objects.create(
            company=self.company, geste='whatsapp',
            famille_appareil='mobile',
            jour=MAINTENANT.date() - datetime.timedelta(days=120), total=9)
        self.assertEqual(
            mesure_cadence.gestes_par_appareil(self.company, jours=90), [])

    def test_aucun_geste_rend_une_liste_vide_jamais_une_ligne_a_zero(self):
        self.assertEqual(mesure_cadence.gestes_par_appareil(self.company), [])

    def test_mesure_cadence_porte_gestes_par_appareil(self):
        mesure_cadence.enregistrer_geste_appareil(
            self.company, 'reporter', UA_DESKTOP)
        resultat = mesure_cadence.mesure_cadence(self.company)
        self.assertIn('gestes_par_appareil', resultat)
        self.assertEqual(resultat['gestes_par_appareil'], [
            {'geste': 'reporter', 'famille_appareil': 'ordinateur',
             'total': 1}])


class EndpointsComptentLeGesteTests(TestCase):
    """Les endpoints RÉELS (``fait``/``reporter``/``whatsapp``/
    ``appel-compose``) comptent chacun leur propre geste — jamais un autre,
    jamais sur un refus 400."""

    slug = 'cad178-endpoints'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Fassi', owner=self.acteur,
            stage=stages.CONTACTED, telephone='+212661000178')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, canal=RelanceEtape.Canal.WHATSAPP):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=1, canal=canal, libelle='Touche', statut='a_faire',
            due_at=MAINTENANT, due_date=MAINTENANT.date())

    def _compte(self, geste, famille):
        return GesteRelanceAppareil.objects.filter(
            company=self.company, geste=geste,
            famille_appareil=famille).count()

    def test_fait_compte_le_geste_fait(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', {},
            HTTP_USER_AGENT=UA_IPHONE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._compte('fait', 'mobile'), 1)
        self.assertEqual(self._compte('whatsapp', 'mobile'), 0)

    def test_un_refus_400_ne_compte_jamais(self):
        """Une langue inconnue refuse AVANT le geste : rien n'est compté."""
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'langue': 'xx'}, HTTP_USER_AGENT=UA_IPHONE)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(GesteRelanceAppareil.objects.filter(
            company=self.company).count(), 0)

    def test_reporter_compte_le_geste_reporter(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/reporter/',
            {'rappel_le': (MAINTENANT.date()
                           + datetime.timedelta(days=2)).isoformat(),
             'rappel_heure': '10:00'},
            HTTP_USER_AGENT=UA_DESKTOP)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._compte('reporter', 'ordinateur'), 1)

    def test_whatsapp_compte_le_geste_whatsapp(self):
        self.lead.whatsapp = '+212661000178'
        self.lead.save(update_fields=['whatsapp'])
        etape = self._touche(canal=RelanceEtape.Canal.WHATSAPP)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/whatsapp/', {},
            HTTP_USER_AGENT=UA_ANDROID_PHONE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._compte('whatsapp', 'mobile'), 1)

    def test_appel_compose_compte_le_geste_appeler_sans_rien_ecrire(self):
        """CAD80/CAD178 — jusqu'ici ce geste ne touchait JAMAIS le serveur :
        l'action n'écrit rien sur la touche (statut inchangé)."""
        etape = self._touche(canal=RelanceEtape.Canal.APPEL)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/appel-compose/',
            HTTP_USER_AGENT=UA_IPHONE)
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertEqual(self._compte('appeler', 'mobile'), 1)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_endpoint_mesure_cadence_reflete_les_gestes_comptes(self):
        etape = self._touche(canal=RelanceEtape.Canal.APPEL)
        self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/appel-compose/',
            HTTP_USER_AGENT=UA_IPHONE)
        resp = self.api.get('/api/django/crm/leads/mesure-cadence/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(
            {'geste': 'appeler', 'famille_appareil': 'mobile', 'total': 1},
            resp.data['gestes_par_appareil'])


class ContratMesureCadenceTests(SimpleTestCase):
    """PACT10 — le contrat committé porte la même forme que le serveur."""

    def test_gestes_par_appareil_dans_lechantillon(self):
        import json
        from pathlib import Path
        echantillon = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'mesure_cadence.json').read_text(encoding='utf-8'))
        self.assertIn('gestes_par_appareil', echantillon['exemple'])
        self.assertIn('gestes_par_appareil', echantillon['exemple_vide'])
        self.assertEqual(echantillon['exemple_vide']['gestes_par_appareil'], [])
        for ligne in echantillon['exemple']['gestes_par_appareil']:
            self.assertEqual(
                set(ligne), {'geste', 'famille_appareil', 'total'})
