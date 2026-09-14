"""QJ-EQUIPE-2 (14/09/2026) — registre SERVEUR des appareils de l'équipe.

Ordre fondateur (14/09/2026) : les appareils du fondateur déclenchaient les
alertes T-TRACE anti-fraude ; le seul mécanisme d'exclusion existant était le
cookie CLIENT ``tq_equipe`` (par navigateur, absent du navigateur intégré
WhatsApp/navigation privée). Ce fichier épingle le registre SERVEUR qui le
complète :

  (a) un appareil marqué équipe ne produit AUCUNE trace T-TRACE ;
  (b) ``detecter_concurrent`` reste muet pour un appareil équipe, y compris
      RÉTROACTIVEMENT (traces écrites AVANT le marquage) ;
  (c) la branche IP ignore aussi les visites d'un appareil équipe ;
  (d) ``historique_appareil`` ne raconte rien d'un appareil équipe ;
  (e) le gate public ``apps.ventes.public_views._stamp_view_si_public``
      n'enregistre rien pour un appareil équipe ;
  (f) l'API (deux ViewSets) est étanche par société, l'agrégat a la forme
      attendue, marquer/démarquer fonctionne, et l'écriture est réservée
      responsable/admin.

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_appareil_equipe -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from authentication.models import Company

from . import visites
from .models import AppareilEquipe, Lead, VisiteExterne

User = get_user_model()

APPAREIL_EQUIPE = 'equipe-0000-1111-2222-3333-444444444444'
AUTRE_APPAREIL = 'client-9999-8888-7777-6666-555555555555'


def make_company(slug):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_directeur(company, username):
    from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
    role, _ = Role.objects.get_or_create(
        company=company, nom='Directeur',
        defaults={'permissions': DIRECTEUR_PERMISSIONS, 'est_systeme': True})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


def make_responsable(company, username):
    from apps.roles.models import Role
    role, _ = Role.objects.get_or_create(
        company=company, nom='Responsable-QJEQ2',
        defaults={'permissions': ['crm_creer', 'crm_modifier']})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


def make_lecture_seule(company, username):
    """Rôle STRICTEMENT lecture (suffixe ``_voir``) — ``is_responsable`` doit
    rester False (ERR4, voir ``authentication.models.CustomUser.is_responsable``)."""
    from apps.roles.models import Role
    role, _ = Role.objects.get_or_create(
        company=company, nom='LectureSeule-QJEQ2',
        defaults={'permissions': ['crm_voir']})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


# ═══════════════════════════════════════════════════════════════════════════
# (a) Aucune trace pour un appareil équipe
# ═══════════════════════════════════════════════════════════════════════════

class TestAucuneTraceAppareilEquipe(TestCase):
    def setUp(self):
        self.company = make_company('qjeq2-notrace')
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE,
            libelle='Téléphone Reda')

    def test_enregistrer_visite_externe_ne_cree_rien(self):
        resultat = visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL_EQUIPE, duree_s=60)
        self.assertIsNone(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 0)

    def test_un_appareil_non_marque_trace_normalement(self):
        resultat = visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=AUTRE_APPAREIL, duree_s=60)
        self.assertIsNotNone(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 1)

    def test_rattacher_visites_au_lead_ne_rattache_rien(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect', appareil_id=APPAREIL_EQUIPE)
        VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL_EQUIPE)
        self.assertEqual(visites.rattacher_visites_au_lead(lead), 0)

    def test_alerter_appareil_partage_ne_fait_rien(self):
        directeur = make_directeur(self.company, 'qjeq2-dir-a')
        Lead.objects.create(
            company=self.company, nom='Premier', appareil_id=APPAREIL_EQUIPE)
        nouveau = Lead.objects.create(
            company=self.company, nom='Second', appareil_id=APPAREIL_EQUIPE)
        visites.alerter_appareil_partage(nouveau)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_appareil_partage', recipient=directeur
        ).exists())


# ═══════════════════════════════════════════════════════════════════════════
# (b)+(c) detecter_concurrent : muet pour l'équipe, y compris RÉTROACTIVEMENT
# ═══════════════════════════════════════════════════════════════════════════

class TestDetecterConcurrentIgnoreEquipe(TestCase):
    def setUp(self):
        self.company = make_company('qjeq2-concurrent')
        self.directeur = make_directeur(self.company, 'qjeq2-dir-b')
        self.lead_a = Lead.objects.create(company=self.company, nom='Client A')
        self.lead_b = Lead.objects.create(company=self.company, nom='Client B')

    def consulter(self, lead, appareil, ip=''):
        return visites.enregistrer_visite_externe(
            self.company, point=VisiteExterne.Point.PROPOSITION, lead=lead,
            appareil_id=appareil, ip=ip, contexte=f'Ouverture devis {lead.pk}')

    def test_deux_prospects_normaux_declenchent_lalerte(self):
        """Témoin — sans marquage, l'alerte part normalement (comportement
        T-TRACE inchangé)."""
        self.consulter(self.lead_a, AUTRE_APPAREIL)
        self.consulter(self.lead_b, AUTRE_APPAREIL)
        visites.detecter_concurrent(self.company, appareil_id=AUTRE_APPAREIL)
        self.assertTrue(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte',
            recipient=self.directeur).exists())

    def test_appareil_marque_apres_les_visites_reste_muet_retroactivement(self):
        """LE CŒUR DE LA RÈGLE — les traces existent AVANT le marquage (« keep
        them stored », elles ne sont jamais supprimées) mais cessent d'être
        LUES par la corrélation dès l'instant du marquage."""
        # Deux traces créées alors que l'appareil n'est PAS encore équipe :
        # (on doit passer directement par le modèle pour simuler un appareil
        # qui n'était pas encore marqué au moment des visites, puisque
        # `enregistrer_visite_externe` refuserait désormais de tracer un
        # appareil déjà marqué.)
        for lead in (self.lead_a, self.lead_b):
            VisiteExterne.objects.create(
                company=self.company, point=VisiteExterne.Point.PROPOSITION,
                lead=lead, appareil_id=APPAREIL_EQUIPE,
                contexte=f'Ouverture devis {lead.pk}')
        self.assertEqual(
            VisiteExterne.objects.filter(appareil_id=APPAREIL_EQUIPE).count(),
            2)

        # Marquage APRÈS coup.
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE)

        visites.detecter_concurrent(self.company, appareil_id=APPAREIL_EQUIPE)
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())
        # Les traces existent toujours (« keep them stored »).
        self.assertEqual(
            VisiteExterne.objects.filter(appareil_id=APPAREIL_EQUIPE).count(),
            2)

    def test_lien_de_lalerte_pointe_vers_lecran_de_revue(self):
        self.consulter(self.lead_a, AUTRE_APPAREIL)
        self.consulter(self.lead_b, AUTRE_APPAREIL)
        visites.detecter_concurrent(self.company, appareil_id=AUTRE_APPAREIL)
        alerte = Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte',
            recipient=self.directeur).first()
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.link, f'/crm/visiteurs?appareil={AUTRE_APPAREIL}')

    def test_branche_ip_ignore_aussi_les_visites_dun_appareil_equipe(self):
        """(c) — un appareil équipe qui partage une IP avec un autre lead ne
        doit pas non plus alimenter la corrélation FAIBLE par IP."""
        ip = '41.77.1.9'
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE)
        # L'appareil ÉQUIPE (identifié, donc normalement suffisant pour
        # rendre la branche IP "identifiée") consulte le lead A ; un appareil
        # anonyme consulte le lead B à la MÊME adresse IP.
        VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.PROPOSITION,
            lead=self.lead_a, appareil_id=APPAREIL_EQUIPE, ip=ip,
            contexte='Ouverture devis A')
        VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.PROPOSITION,
            lead=self.lead_b, appareil_id='', ip=ip,
            contexte='Ouverture devis B')
        visites.detecter_concurrent(self.company, ip=ip)
        # Sans l'exclusion, la visite équipe (identifiée) aurait suffi à
        # déclencher l'alerte FAIBLE par IP ; avec l'exclusion, il ne reste
        # qu'UN lead sur cette IP — aucune corrélation possible.
        self.assertFalse(Notification.objects.filter(
            event_type='visiteur_concurrent_suspecte').exists())


# ═══════════════════════════════════════════════════════════════════════════
# (d) historique_appareil ne raconte rien d'un appareil équipe
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoriqueAppareilIgnoreEquipe(TestCase):
    def setUp(self):
        self.company = make_company('qjeq2-historique')

    def test_historique_none_pour_un_appareil_equipe(self):
        VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL_EQUIPE, duree_s=120)
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE)
        self.assertIsNone(
            visites.historique_appareil(self.company, APPAREIL_EQUIPE))

    def test_historique_normal_pour_un_appareil_non_marque(self):
        VisiteExterne.objects.create(
            company=self.company, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=AUTRE_APPAREIL, duree_s=120)
        self.assertIsNotNone(
            visites.historique_appareil(self.company, AUTRE_APPAREIL))


# ═══════════════════════════════════════════════════════════════════════════
# (e) Le gate public ventes n'enregistre rien pour un appareil équipe
# ═══════════════════════════════════════════════════════════════════════════

class TestGatePublicVentesIgnoreEquipe(TestCase):
    def setUp(self):
        from decimal import Decimal

        from apps.ventes.models import Devis, ShareLink

        from .models import Client as CrmClient

        self.company = make_company('qjeq2-ventes')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect QJEQ2')
        client_obj = CrmClient.objects.create(
            company=self.company, nom='QJEQ2', prenom='Test')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJEQ2-1',
            client=client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE)

    def _requete(self, appareil_id):
        from django.test import RequestFactory
        return RequestFactory().get(
            f'/api/django/public/proposition/{self.link.token}/',
            {'appareil_id': appareil_id},
            HTTP_X_FORWARDED_FOR='41.77.1.5',
            HTTP_USER_AGENT='Mozilla/5.0 (Android)')

    def test_appareil_equipe_ne_stampe_ni_ne_trace(self):
        from apps.ventes.public_views import _stamp_view_si_public

        resultat = _stamp_view_si_public(
            self.link, False, self._requete(APPAREIL_EQUIPE))
        self.assertFalse(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 0)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.first_viewed_at)

    def test_appareil_non_equipe_stampe_normalement(self):
        from apps.ventes.public_views import _stamp_view_si_public

        resultat = _stamp_view_si_public(
            self.link, False, self._requete(AUTRE_APPAREIL))
        self.assertTrue(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# (f) API — isolation, forme de l'agrégat, marquer/démarquer, rôles
# ═══════════════════════════════════════════════════════════════════════════

class TestApiVisitesExternesEtAppareilEquipe(TestCase):
    def setUp(self):
        self.co1 = make_company('qjeq2-api-un')
        self.co2 = make_company('qjeq2-api-deux')
        self.resp1 = make_responsable(self.co1, 'qjeq2-resp-1')
        self.lecture1 = make_lecture_seule(self.co1, 'qjeq2-lect-1')
        self.resp2 = make_responsable(self.co2, 'qjeq2-resp-2')
        self.api1 = APIClient()
        self.api1.force_authenticate(self.resp1)
        self.api2 = APIClient()
        self.api2.force_authenticate(self.resp2)

    def test_isolation_visites_externes(self):
        VisiteExterne.objects.create(
            company=self.co1, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=AUTRE_APPAREIL)
        VisiteExterne.objects.create(
            company=self.co2, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=AUTRE_APPAREIL)
        resp = self.api1.get('/api/django/crm/visites-externes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 1)

    def test_isolation_appareils_equipe(self):
        AppareilEquipe.objects.create(company=self.co1, appareil_id='a1')
        AppareilEquipe.objects.create(company=self.co2, appareil_id='a2')
        resp = self.api1.get('/api/django/crm/appareils-equipe/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['appareil_id'], 'a1')

    def test_agregat_appareils_a_la_forme_attendue(self):
        lead = Lead.objects.create(company=self.co1, nom='Client agrégat')
        VisiteExterne.objects.create(
            company=self.co1, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=AUTRE_APPAREIL, duree_s=30)
        VisiteExterne.objects.create(
            company=self.co1, point=VisiteExterne.Point.PROPOSITION,
            appareil_id=AUTRE_APPAREIL, duree_s=90, lead=lead)
        resp = self.api1.get('/api/django/crm/visites-externes/appareils/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = next(
            r for r in resp.data if r['appareil_id'] == AUTRE_APPAREIL)
        self.assertEqual(ligne['nb_visites'], 2)
        self.assertEqual(ligne['duree_totale_s'], 120)
        self.assertEqual(ligne['nb_propositions'], 1)
        self.assertEqual(ligne['leads_touches'], [{'id': lead.pk, 'nom': lead.nom}])
        self.assertFalse(ligne['equipe'])
        self.assertIn('premiere', ligne)
        self.assertIn('derniere', ligne)

    def test_agregat_marque_equipe_quand_enregistre(self):
        AppareilEquipe.objects.create(
            company=self.co1, appareil_id=APPAREIL_EQUIPE)
        VisiteExterne.objects.create(
            company=self.co1, point=VisiteExterne.Point.VISITE_SITE,
            appareil_id=APPAREIL_EQUIPE)
        resp = self.api1.get(
            '/api/django/crm/visites-externes/appareils/',
            {'appareil_id': APPAREIL_EQUIPE})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertTrue(resp.data[0]['equipe'])

    def test_marquer_puis_demarquer_un_appareil(self):
        creation = self.api1.post('/api/django/crm/appareils-equipe/', {
            'appareil_id': APPAREIL_EQUIPE, 'libelle': 'Téléphone test',
        })
        self.assertEqual(creation.status_code, 201, creation.data)
        self.assertTrue(AppareilEquipe.objects.filter(
            company=self.co1, appareil_id=APPAREIL_EQUIPE).exists())
        self.assertEqual(creation.data['cree_par'], self.resp1.pk)

        pk = creation.data['id']
        suppression = self.api1.delete(
            f'/api/django/crm/appareils-equipe/{pk}/')
        self.assertEqual(suppression.status_code, 204)
        self.assertFalse(AppareilEquipe.objects.filter(
            company=self.co1, appareil_id=APPAREIL_EQUIPE).exists())

    def test_marquage_est_idempotent_pas_derreur_400(self):
        premier = self.api1.post('/api/django/crm/appareils-equipe/', {
            'appareil_id': APPAREIL_EQUIPE, 'libelle': 'Première fois',
        })
        self.assertEqual(premier.status_code, 201, premier.data)
        second = self.api1.post('/api/django/crm/appareils-equipe/', {
            'appareil_id': APPAREIL_EQUIPE, 'libelle': 'Deuxième fois',
        })
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            AppareilEquipe.objects.filter(
                company=self.co1, appareil_id=APPAREIL_EQUIPE).count(), 1)
        self.assertEqual(
            AppareilEquipe.objects.get(
                company=self.co1, appareil_id=APPAREIL_EQUIPE).libelle,
            'Deuxième fois')

    def test_ecriture_refusee_a_un_role_lecture_seule(self):
        api_lecture = APIClient()
        api_lecture.force_authenticate(self.lecture1)
        resp = api_lecture.post('/api/django/crm/appareils-equipe/', {
            'appareil_id': APPAREIL_EQUIPE,
        })
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(AppareilEquipe.objects.filter(
            company=self.co1, appareil_id=APPAREIL_EQUIPE).exists())

    def test_lecture_ouverte_au_role_lecture_seule(self):
        api_lecture = APIClient()
        api_lecture.force_authenticate(self.lecture1)
        resp = api_lecture.get('/api/django/crm/appareils-equipe/')
        self.assertEqual(resp.status_code, 200)

    def test_une_societe_ne_peut_pas_demarquer_lappareil_dune_autre(self):
        marque = AppareilEquipe.objects.create(
            company=self.co2, appareil_id=APPAREIL_EQUIPE)
        resp = self.api1.delete(
            f'/api/django/crm/appareils-equipe/{marque.pk}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(
            AppareilEquipe.objects.filter(pk=marque.pk).exists())
