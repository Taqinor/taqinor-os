"""RELANCE FOUNDATION — plan de relance structuré (multi-touches).

Covers:
  - ``initialiser_plan_relance`` matérialise UNE cadence du gabarit de la
    société. CKP2 — depuis la CADENCE RÉACTIVE (fondateur 2026-09-10), elle
    n'en matérialise que la PREMIÈRE touche à faire : le gabarit reste la
    partition (annoncée par ``calculer_echeances_cadence`` et l'aperçu MRY30),
    et chaque geste suivant naît de l'ISSUE saisie sur le précédent. Ces tests
    tournent sous ``frozen(DEPART_FIXE)`` — sans quoi « ce qui est déjà échu »
    dépendrait du jour où passe la CI.
    MRY5 : la cadence est désormais NOMMÉE — les 5 barreaux neutres
    historiques (J+2/J+5/J+10/J+20/J+35) vivent sous ``generique``, que ces
    tests demandent EXPLICITEMENT (bug CI #77 : on édite un test épinglé, on
    ne le laisse pas dériver). Les échéances sont en plus recalées sur la
    fenêtre d'appel de la société (MRY8), d'où un départ FIXE ci-dessous
    plutôt qu'un ``today`` qui rendrait les dates attendues dépendantes du
    jour où tourne la CI.
  - Idempotence : un second appel sur un lead déjà initialisé ne duplique
    rien et renvoie le plan existant.
  - ``marquer_etape_relance`` (fait/sautée) journalise dans le chatter et
    fait AVANCER ``Lead.relance_date`` vers la prochaine étape à faire (ou
    la vide si le plan est terminé).
  - Scoping multi-tenant : une étape d'une autre société n'est ni visible
    ni actionnable via l'API (404).
  - File « Relances du jour » (scope overdue/today/all) + filtre owner.
  - Permissions : lecture (list) ouverte à tout rôle, écriture
    (fait/sauter/initialiser) réservée responsable/admin.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.time import frozen

from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    calculer_echeances_cadence, initialiser_plan_relance,
    marquer_etape_relance)
from apps.crm import horaires
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

#: Lundi 7 septembre 2026, minuit heure de Casablanca — départ FIXE : les
#: échéances attendues plus bas sont alors calculables à la main (les touches
#: qui tombent un week-end sont recalées au lundi suivant, MRY8).
DEPART_FIXE = datetime.datetime(2026, 9, 7, tzinfo=horaires.CASABLANCA)


def make_company(slug='relance-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestCadenceRelanceEtapeSeed(TestCase):
    """apps/parametres — le gabarit de cadence par défaut."""

    def test_seed_defaults_cree_les_cinq_barreaux(self):
        company = make_company('relance-param-co')
        created = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(created, 5)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(company=company).count(), 5)
        delais = list(
            CadenceRelanceEtape.objects.filter(company=company)
            .order_by('ordre').values_list('delai_jours', flat=True))
        self.assertEqual(delais, [2, 5, 10, 20, 35])

    def test_seed_defaults_est_idempotent(self):
        company = make_company('relance-param-co2')
        CadenceRelanceEtape.seed_defaults(company)
        # Personnalisation : le founder change un libellé.
        etape = CadenceRelanceEtape.objects.get(company=company, ordre=1)
        etape.libelle = 'Appel personnalisé'
        etape.save(update_fields=['libelle'])
        second = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(second, 0)
        etape.refresh_from_db()
        self.assertEqual(etape.libelle, 'Appel personnalisé')

    def test_cadence_pour_seed_a_la_volee_pour_societe_sans_cadence(self):
        company = make_company('relance-param-co3')
        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=company).count(), 0)
        # MRY4 — `cadence_pour` prend desormais la cadence visee ; les 5
        # barreaux neutres historiques vivent sous `generique`.
        cadence = CadenceRelanceEtape.cadence_pour(company, 'generique')
        self.assertEqual(len(cadence), 5)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(company=company).count(), 5)


@frozen(DEPART_FIXE)
class TestInitialiserPlanRelance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.owner = User.objects.create_user(
            username='relanceowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relanceacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)

    #: Départ lundi 07/09/2026. J+2 = mercredi 09 ; J+5 = SAMEDI 12, recalé
    #: au lundi 14 ; J+10 = jeudi 17 ; J+20 = DIMANCHE 27, recalé au lundi
    #: 28 ; J+35 = lundi 12/10. Les délais du gabarit sont inchangés — seul le
    #: recalage sur les jours ouvrés (MRY8) déplace deux échéances.
    PARTITION = [
        datetime.date(2026, 9, 9),
        datetime.date(2026, 9, 14),
        datetime.date(2026, 9, 17),
        datetime.date(2026, 9, 28),
        datetime.date(2026, 10, 12),
    ]

    def test_ne_materialise_que_la_premiere_touche(self):
        """CKP2 — LA bascule : on ne programme QUE le prochain geste. Les cinq
        touches créées d'avance encombraient la file de rappels que le premier
        appel rendait caducs."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=DEPART_FIXE, cadence='generique')
        self.assertEqual(len(etapes), 1)
        self.assertEqual(etapes[0].due_date, self.PARTITION[0])
        self.assertEqual(etapes[0].statut, RelanceEtape.Statut.A_FAIRE)
        # MRY5 — la touche porte une heure, pas seulement un jour.
        self.assertIsNotNone(etapes[0].due_at)
        self.assertEqual(etapes[0].cadence, 'generique')
        # CKP2 — l'ANCRE est écrite : la J+35 saura se redater dans un mois.
        self.assertEqual(etapes[0].cadence_depart, DEPART_FIXE)

    def test_la_partition_complete_reste_annoncee_sans_rien_ecrire(self):
        """L'aperçu MRY30 continue d'annoncer le PLAN entier — c'est la
        matérialisation qui suit les issues, jamais le calcul."""
        echeances = calculer_echeances_cadence(
            self.lead, 'generique', DEPART_FIXE)
        self.assertEqual(
            [e.astimezone(horaires.CASABLANCA).date() for _g, e in echeances],
            self.PARTITION)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.lead).count(), 0)

    def test_la_suite_nait_de_lissue_une_touche_a_la_fois(self):
        """Le protocole se déroule EN ENTIER — simplement, chaque geste naît
        du précédent : la partition est tenue, touche après touche."""
        initialiser_plan_relance(
            self.lead, self.acteur, depart=DEPART_FIXE, cadence='generique')
        vues = []
        for _ in range(len(self.PARTITION)):
            ouverte = self.lead.relance_etapes.filter(
                cadence='generique',
                statut=RelanceEtape.Statut.A_FAIRE).order_by('ordre').first()
            if ouverte is None:
                break
            vues.append(ouverte.due_date)
            marquer_etape_relance(
                ouverte, self.acteur, RelanceEtape.Statut.FAIT,
                outcome='non_joint')
        self.assertEqual(vues, self.PARTITION)

    def test_pose_relance_date_sur_la_premiere_echeance(self):
        initialiser_plan_relance(
            self.lead, self.acteur, depart=DEPART_FIXE, cadence='generique')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, datetime.date(2026, 9, 9))

    def test_journalise_dans_le_chatter(self):
        initialiser_plan_relance(self.lead, self.acteur, cadence='generique')
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('Plan de relance initialisé' in (n.body or '') for n in notes))

    def test_idempotent_second_appel_ne_duplique_pas(self):
        initialiser_plan_relance(self.lead, self.acteur, cadence='generique')
        second = initialiser_plan_relance(
            self.lead, self.acteur, cadence='generique')
        self.assertEqual(len(second), 1)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.lead).count(), 1)

    def test_aucun_envoi_automatique(self):
        # Garde négative : le service n'importe/n'appelle aucun client
        # WhatsApp/e-mail — seules des lignes RelanceEtape + une note chatter
        # sont créées, jamais un message sortant.
        initialiser_plan_relance(self.lead, self.acteur, cadence='generique')
        for note in LeadActivity.objects.filter(lead=self.lead):
            self.assertNotIn('whatsapp', (note.body or '').lower())
            self.assertNotIn('envoyé', (note.body or '').lower())


@frozen(DEPART_FIXE)
class TestMarquerEtapeRelance(TestCase):
    def _ouverte(self):
        """CKP2 — la SEULE touche encore ouverte du plan à cet instant."""
        return self.lead.relance_etapes.filter(
            cadence='generique',
            statut=RelanceEtape.Statut.A_FAIRE).order_by('ordre').first()

    def setUp(self):
        self.company = make_company('relance-mark-co')
        self.owner = User.objects.create_user(
            username='relmarkowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relmarkacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=DEPART_FIXE, cadence='generique')

    def test_marquer_fait_journalise_et_avance_relance_date(self):
        premiere = self.etapes[0]
        marquer_etape_relance(premiere, self.acteur, RelanceEtape.Statut.FAIT,
                              note='Client injoignable, rappel demain',
                              outcome='non_joint')
        premiere.refresh_from_db()
        self.assertEqual(premiere.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(premiere.traite_par, self.acteur)
        self.assertIsNotNone(premiere.traite_le)

        # CKP2 — la touche SUIVANTE vient de naître de l'issue, et la file
        # pointe dessus.
        suivante = self._ouverte()
        self.assertIsNotNone(suivante)
        self.assertGreater(suivante.ordre, premiere.ordre)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, suivante.due_date)

        # MRY10 — la ligne de chatter d'une touche FAIT est désormais TYPÉE
        # selon le canal de l'étape (ici APPEL pour l'étape 1, « Premier
        # rappel »), jamais une note libre EN PLUS d'une activité typée :
        # cette suite pinnait le comportement PRÉ-MRY10 (kind=NOTE toujours).
        # Voir tests_mry10_journal_rappel.ToucheTypeeTests, qui verrouille
        # explicitement ce nouveau typage.
        notes = LeadActivity.objects.filter(lead=self.lead)
        self.assertTrue(any('faite' in (n.body or '') for n in notes))
        self.assertTrue(any('injoignable' in (n.body or '') for n in notes))

    def test_marquer_sautee_avance_aussi(self):
        """CKP2 — sauter n'éteint pas la cadence : le geste suivant naît quand
        même, sinon sauter la première touche supprimait tout le reste."""
        premiere = self.etapes[0]
        marquer_etape_relance(premiere, self.acteur, RelanceEtape.Statut.SAUTEE)
        premiere.refresh_from_db()
        self.assertEqual(premiere.statut, RelanceEtape.Statut.SAUTEE)
        suivante = self._ouverte()
        self.assertIsNotNone(suivante)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, suivante.due_date)

    def test_derniere_etape_traitee_pose_le_filet_et_garde_relance_date(self):
        """QJ-INVARIANT (fondateur 07/09/2026) — épuiser la cadence ne vide
        plus la relance : le filet pose la prochaine étape (la liste d'un
        lead actif ne se termine que par Froid ou Signé) et ``relance_date``
        la suit — jamais None sur un lead encore dans le funnel."""
        # CKP2 — on déroule le protocole geste par geste (« pas de réponse »
        # à chaque fois) jusqu'à ce que le gabarit n'ait plus rien à faire
        # naître : c'est LÀ, et seulement là, que la cadence s'épuise.
        for _ in range(20):
            ouverte = self._ouverte()
            if ouverte is None:
                break
            marquer_etape_relance(ouverte, self.acteur,
                                  RelanceEtape.Statut.FAIT,
                                  outcome='non_joint')
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.relance_date)
        self.assertTrue(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists())

    def test_statut_invalide_leve(self):
        with self.assertRaises(ValueError):
            marquer_etape_relance(
                self.etapes[0], self.acteur, RelanceEtape.Statut.A_FAIRE)


class TestRelanceEtapesDuesSelector(TestCase):
    def setUp(self):
        from apps.crm.selectors import relance_etapes_dues
        self.selector = relance_etapes_dues
        self.company = make_company('relance-sel-co')
        self.owner = User.objects.create_user(
            username='relselowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relselacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        today = datetime.date.today()
        self.en_retard = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date=today - datetime.timedelta(days=3), canal='appel')
        self.aujourdhui = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=2,
            due_date=today, canal='whatsapp')
        self.futur = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=3,
            due_date=today + datetime.timedelta(days=5), canal='email')

    def test_scope_today_ne_montre_que_aujourdhui(self):
        qs = self.selector(self.company, self.acteur, scope='today')
        self.assertEqual(list(qs), [self.aujourdhui])

    def test_scope_overdue_ne_montre_que_le_retard(self):
        qs = self.selector(self.company, self.acteur, scope='overdue')
        self.assertEqual(list(qs), [self.en_retard])

    def test_scope_all_montre_aujourdhui_et_retard_pas_le_futur(self):
        qs = self.selector(self.company, self.acteur, scope='all')
        self.assertEqual(set(qs), {self.en_retard, self.aujourdhui})

    def test_etape_traitee_disparait_de_la_file(self):
        marquer_etape_relance(self.aujourdhui, self.acteur, RelanceEtape.Statut.FAIT)
        qs = self.selector(self.company, self.acteur, scope='today')
        self.assertEqual(list(qs), [])

    def test_filtre_owner(self):
        autre_owner = User.objects.create_user(
            username='relselautre', password='x', company=self.company)
        autre_lead = Lead.objects.create(
            company=self.company, nom='Autre', owner=autre_owner)
        RelanceEtape.objects.create(
            company=self.company, lead=autre_lead, ordre=1,
            due_date=datetime.date.today(), canal='appel')
        qs = self.selector(
            self.company, self.acteur, scope='today', owner=self.owner.id)
        self.assertEqual(list(qs), [self.aujourdhui])


class TestRelanceEtapeAPI(TestCase):
    def setUp(self):
        self.company = make_company('relance-api-co')
        self.other_company = make_company('relance-api-co-b')
        self.owner = User.objects.create_user(
            username='relapiowner', password='x', company=self.company)
        self.responsable = User.objects.create_user(
            username='relapiresp', password='x', role_legacy='responsable',
            company=self.company)
        self.normal = User.objects.create_user(
            username='relapinormal', password='x', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        self.etapes = initialiser_plan_relance(
            self.lead, self.responsable, cadence='generique')

        self.api_resp = APIClient()
        self.api_resp.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.responsable)}')
        self.api_normal = APIClient()
        self.api_normal.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')

    def test_initialiser_endpoint_idempotent(self):
        lead2 = Lead.objects.create(company=self.company, nom='Lead2', owner=self.owner)
        # MRY5 — l'endpoint prend une cadence (défaut `contact`) ; ce test
        # vérifie l'IDEMPOTENCE, pas le nombre de touches du protocole : il
        # demande donc explicitement l'échelle neutre historique.
        resp = self.api_resp.post(
            f'/api/django/crm/leads/{lead2.id}/relance/initialiser/',
            {'cadence': 'generique'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # CKP2 — une SEULE touche matérialisée (cadence réactive) ; c'est
        # l'idempotence qui est testée ici, pas la longueur du protocole.
        self.assertEqual(len(resp.data), 1)
        resp2 = self.api_resp.post(
            f'/api/django/crm/leads/{lead2.id}/relance/initialiser/',
            {'cadence': 'generique'}, format='json')
        self.assertEqual(len(resp2.data), 1)
        self.assertEqual(RelanceEtape.objects.filter(lead=lead2).count(), 1)

    def test_liste_dues_lecture_ouverte_a_tout_role(self):
        resp = self.api_normal.get('/api/django/crm/relance-etapes/?scope=all')
        self.assertEqual(resp.status_code, 200, resp.content)
        # aujourd'hui + retard uniquement -> ici la 1ere echeance est J+2, donc
        # rien n'est encore du (scope=all == aujourd'hui+retard).
        self.assertEqual(resp.data['count'], 0)

    def test_fait_reserve_responsable_admin(self):
        etape = self.etapes[0]
        resp = self.api_normal.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/')
        self.assertEqual(resp.status_code, 403)

    def test_fait_ok_pour_responsable(self):
        etape = self.etapes[0]
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/',
            {'note': 'Rappelé, intéressé', 'outcome': 'non_joint'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'fait')
        self.assertEqual(resp.data['note'], 'Rappelé, intéressé')

    def test_un_appel_fait_SANS_issue_est_refuse_en_nommant_le_champ(self):
        """CKP2 — l'issue programme le geste suivant : la clore sans elle
        laissait le dossier sans suite. L'erreur NOMME le champ (règle
        fondateur 08/09/2026), jamais un « non enregistré » générique."""
        etape = self.etapes[0]
        self.assertEqual(etape.canal, RelanceEtape.Canal.APPEL)
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/',
            {'note': 'Ça a sonné'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('outcome', resp.data['erreurs'])
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_un_message_fait_sans_issue_reste_accepte(self):
        """Envoyer un WhatsApp n'a pas d'issue tant que personne n'a
        répondu : l'obligation ne vaut QUE pour l'appel."""
        etape = self.etapes[0]
        etape.canal = RelanceEtape.Canal.WHATSAPP
        etape.save(update_fields=['canal'])
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'fait')

    def test_sauter_ok_pour_responsable(self):
        etape = self.etapes[0]
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/sauter/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'sautee')

    def test_etape_autre_societe_404(self):
        other_owner = User.objects.create_user(
            username='relapiotherowner', password='x',
            company=self.other_company)
        other_resp_user = User.objects.create_user(
            username='relapiotherresp', password='x',
            role_legacy='responsable', company=self.other_company)
        other_lead = Lead.objects.create(
            company=self.other_company, nom='Autre societe', owner=other_owner)
        other_etapes = initialiser_plan_relance(other_lead, other_resp_user)

        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{other_etapes[0].id}/fait/')
        self.assertEqual(resp.status_code, 404)

    def test_initialiser_autre_societe_404(self):
        other_owner = User.objects.create_user(
            username='relapiotherowner2', password='x',
            company=self.other_company)
        other_lead = Lead.objects.create(
            company=self.other_company, nom='Autre societe 2', owner=other_owner)
        resp = self.api_resp.post(
            f'/api/django/crm/leads/{other_lead.id}/relance/initialiser/')
        self.assertEqual(resp.status_code, 404)


@frozen(DEPART_FIXE)
class TestMaterialiserToucheSuivante(TestCase):
    """CKP2 — les DEUX régimes d'ancrage de la touche qui naît d'une issue.

    C'est là que tout se joue : ancrer une touche du JOUR MÊME sur le départ
    de cadence la placerait dans le passé (un appel d'ouverture passé à 15 h
    ne se rappelle pas « 2 h 30 après 08 h 30 »), et ancrer une touche J+N sur
    l'instant de clôture décalerait tout le plan que l'aperçu MRY30 annonce.
    """

    def setUp(self):
        from apps.crm.services import materialiser_touche_suivante
        self.materialiser = materialiser_touche_suivante
        self.company = make_company('relance-ckp2')
        self.acteur = User.objects.create_user(
            username='relckp2', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)

    def _premiere(self, cadence):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=DEPART_FIXE, cadence=cadence)
        self.assertEqual(len(etapes), 1)
        return etapes[0]

    def test_une_touche_du_jour_meme_est_ancree_sur_la_cloture(self):
        """Cadence `contact` : les touches 1-3 sont des touches J0."""
        premiere = self._premiere('contact')
        cloture = premiere.due_at + datetime.timedelta(hours=6)
        premiere.statut = RelanceEtape.Statut.FAIT
        premiere.traite_le = cloture
        premiere.save(update_fields=['statut', 'traite_le'])
        suivante = self.materialiser(premiere, self.acteur)
        self.assertIsNotNone(suivante)
        # Née APRÈS la clôture — jamais dans le passé, ce qu'un ancrage sur le
        # départ aurait produit ici.
        self.assertGreaterEqual(suivante.due_at, cloture)
        self.assertGreater(suivante.ordre, premiere.ordre)
        self.assertEqual(suivante.cadence_depart, premiere.cadence_depart)

    def test_une_touche_a_j_plus_n_reste_ancree_sur_le_depart(self):
        """Cadence `generique` : J+2 puis J+5 — le J+5 se compte depuis
        l'arrivée du lead, pas depuis le dernier geste, sinon un dossier
        repris tardivement décalerait tout son plan."""
        premiere = self._premiere('generique')
        attendue = calculer_echeances_cadence(
            self.lead, 'generique', DEPART_FIXE)[1][1]
        premiere.statut = RelanceEtape.Statut.FAIT
        premiere.traite_le = premiere.due_at + datetime.timedelta(days=3)
        premiere.save(update_fields=['statut', 'traite_le'])
        suivante = self.materialiser(premiere, self.acteur)
        self.assertIsNotNone(suivante)
        self.assertEqual(suivante.due_at, attendue)

    def test_elle_est_idempotente(self):
        premiere = self._premiere('generique')
        premiere.statut = RelanceEtape.Statut.FAIT
        premiere.traite_le = premiere.due_at
        premiere.save(update_fields=['statut', 'traite_le'])
        une = self.materialiser(premiere, self.acteur)
        deux = self.materialiser(premiere, self.acteur)
        self.assertIsNotNone(une)
        self.assertIsNone(deux)
        self.assertEqual(self.lead.relance_etapes.filter(
            cadence='generique').count(), 2)

    def test_un_lead_quon_ne_relance_plus_ne_recoit_rien(self):
        premiere = self._premiere('generique')
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        premiere.lead.refresh_from_db()
        self.assertIsNone(self.materialiser(premiere, self.acteur))
