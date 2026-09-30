"""COCKPIT-CONTRÔLE (30/09/2026) — LE SCÉNARIO VÉCU : le contrôle du suivi DIT-IL VRAI ?

Ordre fondateur (Reda, 30/09/2026) : « … make reading the data and if the commercial did
everything as she should … and test at the end ». Les tests de ``tests_cockpit_controle.py``
posent chaque règle une à une ; celui-ci fait VIVRE trois semaines de dossiers par l'API
réelle (création du lead, « Fait » avec sa réponse, « Sauter », « Reporter », « Arrêter la
cadence », devis envoyé puis accepté, visite planifiée, congé déclaré, jour férié), puis
confronte ce que sert ``GET relance-etapes/controle/`` à un ORACLE écrit à part
(``cockpit_oracle_outils.Oracle`` : les règles du contrat recalculées sur les lignes de la
base, sans une ligne du module mesuré).

Les dossiers (chacun son cas de la vie réelle) : des réguliers traités le jour même ; une
étape rattrapée le lendemain ; une étape sautée ; une étape reportée deux fois ; des retards
de plusieurs jours ; une tâche « préparer le devis » laissée en attente (et une autre posée
la veille, pas encore « en attente ») ; une cadence arrêtée à la main (dossier sans prochaine
étape) ; un lead jamais contacté ; un devis envoyé puis accepté ; une visite planifiée ; une
deuxième commerciale en congé déclaré (une étape rattrapée au retour : excusée ; une autre
laissée ouverte : en retard à partir du retour seulement).

COMMENT LE RELANCER. La CI le joue à chaque merge (job ``backend-tests``). En local :
``manage.py test apps.crm.tests_cockpit_scenario --keepdb`` (base de test migrée). Un échec
imprime chaque écart « attendu — servi » ; le journal des gestes joués suit.

Horloge gelée (``ParcoursBase``) : départ mercredi 30/09/2026 10 h à Casablanca, lecture
mercredi 21/10/2026 14 h ; lundi 12/10/2026 est férié pour la société du test.
"""
import datetime

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import horaires
from apps.crm.cockpit_oracle_outils import Oracle, ecarts
from apps.crm.models import Lead, PeriodeAbsence, RelanceEtape
from apps.crm.parcours_suivi_outils import (
    GEL, ParcoursBase, etapes_de_la_table, reponse_de, type_de)
from apps.notifications.calendar_utils import ajouter_jours_ouvres, is_jour_ouvre
from apps.notifications.models import Holiday

User = get_user_model()

A_FAIRE = RelanceEtape.Statut.A_FAIRE
JOURS_JOUES = 21
FERIE = datetime.date(2026, 10, 12)


class ControleDuSuiviScenarioTests(ParcoursBase):
    """Trois semaines vécues, puis le contrôle confronté à l'oracle."""

    slug = 'cockpit-scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.com = cls.acteur
        cls.com2 = User.objects.create_user(
            username=f'{cls.slug}-com2', password='x', role_legacy='responsable',
            company=cls.company)
        cls.chef = User.objects.create_user(
            username=f'{cls.slug}-chef', password='x', role_legacy='admin',
            company=cls.company)
        Holiday.objects.create(company=cls.company, date=FERIE, nom='Férié du scénario')

    # ── l'identité de l'appelant (le jeton suit l'horloge ET la personne) ──

    def _jeton(self):
        qui = getattr(self, '_qui', None) or self.acteur
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(qui)}')

    def en_tant_que(self, user):
        self._qui = user
        self._jeton()

    # ── le calendrier du scénario ──

    def _preparer_calendrier(self):
        self.depart = GEL.date()
        self.lecture = self.depart + datetime.timedelta(days=JOURS_JOUES)
        self.jours_joues = [self.depart + datetime.timedelta(days=n)
                            for n in range(JOURS_JOUES)]
        self.ouvres = [jour for jour in self.jours_joues
                       if is_jour_ouvre(jour, self.company)]
        self._minutes = 0
        self.jour = self.depart

    def J(self, k):
        """Le k-ième jour ouvré AVANT le jour de lecture (``J(1)`` = la veille ouvrée)."""
        return self.ouvres[-k]

    def _a(self, heure):
        """Avance l'horloge au prochain instant du jour joué (une minute par geste)."""
        self._minutes += 1
        self.avancer_a(datetime.datetime.combine(
            self.jour, datetime.time(heure, 0), tzinfo=horaires.CASABLANCA)
            + datetime.timedelta(minutes=self._minutes))

    # ── les gestes ──

    def creer(self, code, owner):
        self._a(10)
        self.en_tant_que(owner)
        numero = len(self.dossiers) + 1
        resp = self.appel('post', '/api/django/crm/leads/', {
            'nom': f'Scénario {code}', 'telephone': f'+2126100{numero:05d}',
            'owner': owner.pk})
        lead = Lead.objects.get(pk=resp.data['id'])
        self.assertEqual(lead.owner_id, owner.pk, self.msg('responsable du lead', lead))
        self.dossiers[code] = lead
        self._journal(f'[{self.jour:%d/%m}] {code} : lead #{lead.pk} créé ({owner.username})')
        return lead

    def dues(self, lead):
        return [etape for etape in self.ouvertes(lead) if etape.due_date <= self.jour]

    def est_tache(self, etape):
        return type_de(etape) in self.types_tache

    def closes(self, lead):
        return lead.relance_etapes.filter(
            statut__in=(RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE)).count()

    def repondre_modele(self, lead, etape, *modeles):
        """La première réponse de ``modeles`` que la table propose sur le type de l'étape."""
        type_id = type_de(etape)
        for modele in modeles:
            try:
                reponse = reponse_de(type_id, modele)
            except KeyError:
                continue
            self._a(11)
            self.en_tant_que(lead.owner)
            self.repondre(etape, reponse)
            return
        self.fail(self.msg(f'aucune des réponses {modeles} sur le type {type_id}', lead))

    def sauter(self, lead, etape):
        self._a(11)
        self.en_tant_que(lead.owner)
        self.appel('post', f'/api/django/crm/relance-etapes/{etape.pk}/sauter/',
                   {'note': 'Scénario — étape sautée'})
        self._journal(f'[{self.jour:%d/%m}] #{lead.pk} {type_de(etape)} SAUTÉE')

    def reporter(self, lead, etape, jour):
        self._a(11)
        self.en_tant_que(lead.owner)
        self.appel('post', f'/api/django/crm/relance-etapes/{etape.pk}/reporter/',
                   {'rappel_le': jour.isoformat(), 'rappel_heure': '10:30'})
        self._journal(f'[{self.jour:%d/%m}] #{lead.pk} {type_de(etape)} REPORTÉE au {jour:%d/%m}')

    def arreter(self, lead):
        self._a(11)
        self.en_tant_que(lead.owner)
        self.appel('post', f'/api/django/crm/leads/{lead.pk}/relance/arreter/',
                   {'motif': 'Scénario — le client temporise'})
        self._journal(f'[{self.jour:%d/%m}] #{lead.pk} cadence ARRÊTÉE à la main')

    def traiter_dues(self, lead, decision=None):
        """Traite, le jour même, les étapes dues (les tâches restent). ``decision(etape,
        rang)`` rend ``'pdr'`` (pas de réponse — défaut), ``'laisser'``, ``'sauter'`` ou
        ``('reporter', jour)`` ; ``rang`` = nombre d'étapes déjà closes sur le dossier."""
        for _tour in range(12):
            agi = False
            for etape in self.dues(lead):
                if self.est_tache(etape):
                    continue
                choix = decision(etape, self.closes(lead)) if decision else 'pdr'
                if choix == 'laisser':
                    continue
                if choix == 'pdr':
                    self.repondre_modele(lead, etape, 'pas_de_reponse', 'sans_reponse', 'fait')
                elif choix == 'sauter':
                    self.sauter(lead, etape)
                else:
                    self.reporter(lead, etape, choix[1])
                agi = True
                break
            if not agi:
                return

    # ── les politiques (une par dossier) ──

    def regulier(self, lead):
        self.traiter_dues(lead)

    def rattrape(self, lead):
        self.traiter_dues(lead, lambda etape, rang: (
            'laisser' if rang == 1 and etape.due_date == self.jour else 'pdr'))

    def sautee(self, lead):
        self.traiter_dues(lead, lambda etape, rang: 'sauter' if rang == 1 else 'pdr')

    def reportee(self, lead):
        def decision(etape, rang):
            if rang != 1:
                return 'pdr'
            if etape.nb_reports == 0:
                return ('reporter', ajouter_jours_ouvres(self.jour, 1, self.company))
            if etape.nb_reports == 1:
                return ('reporter', ajouter_jours_ouvres(self.lecture, 1, self.company))
            return 'laisser'
        self.traiter_dues(lead, decision)

    def arret_depuis(self, k):
        def politique(lead):
            if self.jour < self.J(k):
                self.traiter_dues(lead)
        return politique

    def joint_depuis(self, k):
        """« Client joint » à partir de ``J(k)`` : la tâche « préparer le devis » est posée,
        puis laissée en attente."""
        def politique(lead):
            if any(self.est_tache(etape) for etape in self.ouvertes(lead)):
                return
            if self.jour >= self.J(k):
                dues = self.dues(lead)
                if dues:
                    self.repondre_modele(lead, dues[0], 'joint', 'a_repondu')
                return
            self.traiter_dues(lead)
        return politique

    def sans_etape(self, lead):
        if self.jour == self.J(2):
            if self.ouvertes(lead):
                self.arreter(lead)
        elif self.jour < self.J(2):
            self.traiter_dues(lead)

    def jamais(self, lead):
        return

    def _joint_puis_devis(self, lead):
        """Les deux premiers temps de ``resultats`` et ``signe`` ; rend l'état atteint."""
        etat = self.etats.get(lead.pk, 0)
        if etat == 0:
            dues = self.dues(lead)
            if dues:
                self.repondre_modele(lead, dues[0], 'joint', 'a_repondu')
                self.etats[lead.pk] = 1
            return None
        if etat == 1:
            self._a(12)
            self.en_tant_que(lead.owner)
            self.devis[lead.pk] = self.envoyer_devis(lead)
            self.etats[lead.pk] = 2
            return None
        return etat

    def resultats(self, lead):
        """Joint → devis envoyé → visite planifiée."""
        if self._joint_puis_devis(lead) != 2:
            return
        if self.jour >= self.J(4):
            suivis = [etape for etape in self.dues(lead)
                      if type_de(etape) in ('suivi_appel', 'suivi_message')]
            if suivis:
                self.repondre_modele(lead, suivis[0], 'visite')
                self.etats[lead.pk] = 3
            return
        self.traiter_dues(lead)

    def signe(self, lead):
        """Joint → devis envoyé → devis ACCEPTÉ à ``J(2)``."""
        if self._joint_puis_devis(lead) != 2:
            return
        if self.jour == self.J(2):
            self._a(15)
            self.en_tant_que(lead.owner)
            devis = self.devis[lead.pk]
            self.appel('post', f'/api/django/ventes/devis/{devis.pk}/accepter/', {
                'nom': 'Client scénario', 'date': self.jour.isoformat(),
                'option': 'sans_batterie'})
            self._journal(f'[{self.jour:%d/%m}] #{lead.pk} devis {devis.reference} ACCEPTÉ')
            self.etats[lead.pk] = 3
            return
        self.traiter_dues(lead)

    def absente_puis_rattrape(self, lead):
        if self.absence[0] <= self.jour <= self.absence[1]:
            return
        self.traiter_dues(lead)

    # ── le scénario ──

    def jouer_le_scenario(self):
        self._preparer_calendrier()
        self.dossiers, self.etats, self.devis = {}, {}, {}
        self.types_tache = {type_id for type_id, etape in etapes_de_la_table().items()
                            if etape.get('tache')}
        self.absence = (self.J(4), self.J(2))
        PeriodeAbsence.objects.create(
            company=self.company, utilisateur=self.com2,
            date_debut=self.absence[0], date_fin=self.absence[1],
            motif=PeriodeAbsence.Motif.CONGE)
        com, com2 = self.com, self.com2
        # code, responsable, jour de création (k → J(k)), politique
        plan = [
            ('ancien1', com, 14, self.regulier),
            ('ancien2', com, 13, self.rattrape),
            ('reg1', com, 8, self.regulier),
            ('reg2', com, 7, self.regulier),
            ('reg3', com, 6, self.regulier),
            ('reg4', com, 5, self.regulier),
            ('rattrape', com, 6, self.rattrape),
            ('sautee', com, 5, self.sautee),
            ('reportee', com, 5, self.reportee),
            ('retard3', com, 7, self.arret_depuis(3)),
            ('retard1', com, 5, self.arret_depuis(1)),
            ('tache', com, 5, self.joint_depuis(3)),
            ('tache_recente', com, 3, self.joint_depuis(1)),
            ('sans_etape', com, 6, self.sans_etape),
            ('premier', com, 4, self.jamais),
            ('resultats', com, 8, self.resultats),
            ('signe', com, 7, self.signe),
            ('abs_excusee', com2, 7, self.absente_puis_rattrape),
            ('abs_ouverte', com2, 7, self.arret_depuis(4)),
            ('reg_com2', com2, 1, self.regulier),
        ]
        for jour in self.jours_joues:
            self.jour = jour
            self._minutes = 0
            for code, owner, k, _politique in plan:
                if self.J(k) == jour:
                    self.creer(code, owner)
            for code, _owner, k, politique in plan:
                if self.J(k) <= jour:
                    politique(self.dossiers[code])
        self.jour = self.lecture
        self._minutes = 0
        self.lire_a(self.lecture, 14)

    def lire_a(self, jour, heure):
        self.avancer_a(datetime.datetime.combine(
            jour, datetime.time(heure, 0), tzinfo=horaires.CASABLANCA))
        self.en_tant_que(self.chef)

    def servi(self, jours=14, owner=None):
        url = f'/api/django/crm/relance-etapes/controle/?jours={jours}'
        if owner is not None:
            url += f'&owner={owner}'
        return self.appel('get', url).data

    def confronter(self, jours=14, owner=None):
        """Les écarts oracle ↔ API pour (``jours``, ``owner``), à l'instant gelé."""
        from django.utils import timezone

        oracle = Oracle(self.company, self.chef, maintenant=timezone.now())
        return ecarts(oracle.attendu(jours=jours, owner=owner),
                      self.servi(jours=jours, owner=owner))

    def lignes(self, servi, liste):
        return {ligne['lead']: ligne for ligne in servi['exceptions'][liste]['lignes']}

    # ── LE test ──

    def test_le_controle_dit_vrai_sur_trois_semaines_vecues(self):
        self.jouer_le_scenario()
        d = self.dossiers

        # 1. L'API et l'oracle disent la même chose — toutes périodes, toute l'équipe et
        #    chaque commerciale.
        for jours in (7, 14, 30):
            for owner in (None, self.com.pk, self.com2.pk):
                with self.subTest(jours=jours, owner=owner):
                    self.assertEqual(self.confronter(jours, owner), [], self.msg(
                        f'écarts oracle ↔ API (jours={jours}, owner={owner})'))

        # 2. Les faits du scénario, dits un à un (pas seulement « l'oracle est d'accord »).
        servi = self.servi(14)
        verdict = servi['verdict']
        with self.subTest('niveau'):
            self.assertEqual(verdict['niveau'], 'alerte')
        with self.subTest('une étape sautée, une rattrapée en retard'):
            self.assertEqual(verdict['sautees'], 1)
            self.assertGreaterEqual(verdict['en_retard'], 1)
        with self.subTest('reportée deux fois'):
            reports = self.lignes(servi, 'reports')
            self.assertEqual(set(reports), {d['reportee'].pk})
            self.assertEqual(servi['exceptions']['reports']['plusieurs_fois'], 1)
            ligne = reports[d['reportee'].pk]
            self.assertEqual(ligne['nb_reports'], 2)
            self.assertEqual(ligne['due_initial'], self.J(5).isoformat())
            self.assertEqual(
                ligne['due_date'],
                ajouter_jours_ouvres(self.lecture, 1, self.company).isoformat())
        with self.subTest('tâche en attente : 3 jours ouvrés, pas celle de la veille'):
            taches = self.lignes(servi, 'taches_en_attente')
            self.assertEqual(set(taches), {d['tache'].pk})
            self.assertEqual(taches[d['tache'].pk]['ouverte_depuis_jours'], 3)
            self.assertTrue(taches[d['tache'].pk]['est_tache'])
        with self.subTest('dossier sans prochaine étape'):
            self.assertEqual(set(self.lignes(servi, 'sans_prochaine_etape')),
                             {d['sans_etape'].pk})
        with self.subTest('premier contact hors délai'):
            self.assertEqual(set(self.lignes(servi, 'premier_contact_hors_delai')),
                             {d['premier'].pk})
        with self.subTest('en retard : le congé déclaré ne compte pas'):
            en_retard = self.lignes(servi, 'en_retard')
            self.assertIn(d['abs_ouverte'].pk, en_retard)
            self.assertEqual(en_retard[d['abs_ouverte'].pk]['jours_de_retard'], 2)
            self.assertIn(d['retard3'].pk, en_retard)
            self.assertIn(d['premier'].pk, en_retard)
            self.assertNotIn(d['abs_excusee'].pk, en_retard)
            self.assertNotIn(d['reportee'].pk, en_retard)
        with self.subTest('résultats'):
            self.assertEqual(servi['resultats'], {
                'visites_planifiees': 1, 'devis_envoyes': 2, 'devis_acceptes': 1})
        with self.subTest('par commerciale'):
            seule = self.servi(14, owner=self.com2.pk)
            self.assertEqual(set(self.lignes(seule, 'en_retard')), {d['abs_ouverte'].pk})
            self.assertEqual({c['id'] for c in seule['commerciaux']},
                             {self.com.pk, self.com2.pk})
        with self.subTest('la frise : une case par jour, le férié non ouvré et vide'):
            jours = {jour['date']: jour for jour in servi['jours']}
            self.assertEqual(len(jours), 14)
            self.assertFalse(jours[FERIE.isoformat()]['ouvre'])
            self.assertTrue(jours[self.lecture.isoformat()]['aujourdhui'])

        # 3. Le week-end : rien ne devient « en retard » un jour non ouvré, et le lundi
        #    compte pour un jour — l'API et l'oracle suivent ensemble.
        samedi = self.lecture + datetime.timedelta(days=3)
        for jour in (samedi, samedi + datetime.timedelta(days=1),
                     samedi + datetime.timedelta(days=2)):
            with self.subTest(lecture=jour.isoformat()):
                self.lire_a(jour, 12)
                self.assertEqual(self.confronter(14), [], self.msg(
                    f'écarts oracle ↔ API à la lecture du {jour:%d/%m/%Y}'))
