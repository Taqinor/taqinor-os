"""TCH97 — flux de calendrier (`flux/{jeton}.ics`) et grande tuile (`tuile/`) par jeton (reference/regles.md §8,
§10 ; textes.md §8 ; contract_samples/tuile.json ; conception/spec-6b-iphone.md §4, §6).

Sans base (`IcsTests`) : l'écriture du flux (`views.presence.ics_du_flux` → `reporting.calendar.build_ics`) —
CRLF, lignes pliées à 75 octets, échappement, `DESCRIPTION` vide, UID `tache-<id>@taqinor` stables, heure murale
de Casablanca écrite en UTC — relue par le lecteur PUR `moteur.ics.lire_evenements` (aller-retour).

Avec base (`FluxTests`, `TuileTests` : CI) : la tuile sert EXACTEMENT les clés de `tuile.json`, les mêmes chiffres
que l'écran (`aujourdhui/`, `badge/`) ; ni notes, ni check-list, ni nom de projet, ni tâche d'un collègue ou d'une
autre société, ni faite, ni en attente, ni activité ERP titrée, ni rendez-vous externe (le lecteur d'agenda n'est
même pas appelé) ; une confidentielle (par elle-même ou par son projet) est masquée ; titres coupés par
`titres_calendrier` / `titres_tuile`. Société et propriétaire viennent du JETON. Un jeton faux, révoqué, d'un
autre usage ou d'un compte désactivé répond exactement comme un inconnu (404 pour le flux, 401 pour la tuile).
"""
import datetime
import re
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches import agenda_externe as lecteur
from apps.taches.choix import StatutProjet, StatutTache
from apps.taches.models.journee import LignePlanJour
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist
from apps.taches.moteur.flux import EvenementFlux
from apps.taches.moteur.ics import RendezVousPur, lire_evenements
from apps.taches.tests import fabriques
from apps.taches.tests.test_jetons import _neutre
from apps.taches.views.base import exemple_de
from apps.taches.views.presence import ics_du_flux

PREFIXE = '/api/django/taches/'
URL_TUILE = PREFIXE + 'tuile/'
J0 = datetime.date(2026, 11, 17)
FUSEAU = 'Africa/Casablanca'
#: Ce qui ne doit JAMAIS sortir par la tuile ni par le flux (casse ignorée).
MARQUEURS = ('canari', 'note-secrete', 'check-z', 'faite-z', 'attente-z', 'pause-z', 'sous-z', 'loin-z',
             'trier-z', 'collegue-z', 'etranger-z', 'activite-z', 'rdv-z', 'projet-z')
TACHE_CONFIDENTIELLE = 'Tâche confidentielle'


def _depliees(texte):
    """Lignes logiques d'un `.ics` (RFC 5545 §3.1 : CRLF suivi d'une espace = continuation)."""
    return texte.replace('\r\n ', '').split('\r\n')


def _valeurs(texte, nom):
    return [ligne.split(':', 1)[1] for ligne in _depliees(texte) if ligne.split(':', 1)[0] == nom]


class IcsTests(SimpleTestCase):
    """L'écriture du flux, sans base."""

    TITRE = 'Devis, Settat; lot\\A\nsuite'
    LONG = 'Préparer les câbles du chantier de Settat — ' * 3

    def _ics(self, fuseau=FUSEAU):
        evenements = (
            EvenementFlux('tache-1', self.TITRE, datetime.datetime(2026, 11, 17, 10, 0),
                          datetime.datetime(2026, 11, 17, 10, 45), False),
            EvenementFlux('tache-2', self.LONG, J0, J0 + datetime.timedelta(days=1), True),
            EvenementFlux('taches-autres-20261117', '+ 3 autres tâches', J0, J0 + datetime.timedelta(days=1), True),
        )
        with timezone.override(fuseau):
            return ics_du_flux(evenements)

    def test_crlf_partout_et_lignes_pliees_a_75_octets(self):
        texte = self._ics()
        self.assertTrue(texte.endswith('\r\n'))
        self.assertNotIn('\n', texte.replace('\r\n', ''))
        self.assertNotIn('\r', texte.replace('\r\n', ''))
        physiques = texte.split('\r\n')[:-1]
        for ligne in physiques:
            with self.subTest(ligne=ligne[:30]):
                self.assertLessEqual(len(ligne.encode('utf-8')), 75)
        self.assertTrue(any(ligne.startswith(' ') for ligne in physiques), 'le titre long n\'est pas plié')
        lignes = _depliees(texte)
        self.assertEqual((lignes[0], lignes[-2], lignes[-1]), ('BEGIN:VCALENDAR', 'END:VCALENDAR', ''))
        self.assertIn('VERSION:2.0', lignes)

    def test_calendrier_uid_description_vide_et_echappement(self):
        texte = self._ics()
        self.assertEqual(_valeurs(texte, 'X-WR-CALNAME'), ['Tâches Taqinor'])
        self.assertEqual(_valeurs(texte, 'UID'),
                         ['tache-1@taqinor', 'tache-2@taqinor', 'taches-autres-20261117@taqinor'])
        self.assertEqual(_valeurs(texte, 'DESCRIPTION'), ['', '', ''])
        self.assertEqual(_valeurs(texte, 'SUMMARY')[0], 'Devis\\, Settat\\; lot\\\\A\\nsuite')
        self.assertEqual(_valeurs(texte, 'SUMMARY')[2], '+ 3 autres tâches')
        self.assertEqual(_valeurs(self._ics(), 'UID'), _valeurs(texte, 'UID'), 'UID instables')

    def test_heure_murale_de_la_societe_ecrite_en_utc_et_journee_entiere(self):
        lignes = _depliees(self._ics())
        for nom, heure in (('DTSTART', datetime.time(10, 0)), ('DTEND', datetime.time(10, 45))):
            murale = datetime.datetime.combine(J0, heure, tzinfo=ZoneInfo(FUSEAU))
            self.assertIn(f'{nom}:{murale.astimezone(datetime.timezone.utc):%Y%m%dT%H%M%SZ}', lignes)
        # Un fuseau à décalage non nul prouve la conversion : 10:00 à Paris en novembre = 09:00 UTC.
        self.assertIn('DTSTART:20261117T090000Z', _depliees(self._ics('Europe/Paris')))
        self.assertEqual(lignes.count('DTSTART;VALUE=DATE:20261117'), 2)
        self.assertEqual(lignes.count('DTEND;VALUE=DATE:20261118'), 2)

    def test_aller_retour_par_le_lecteur_pur(self):
        relus = lire_evenements(self._ics(), J0, J0, fuseau=FUSEAU)
        par_titre = {r.titre: r for r in relus}
        self.assertEqual(set(par_titre), {self.TITRE, self.LONG, '+ 3 autres tâches'})
        horodate = par_titre[self.TITRE]
        self.assertEqual((horodate.debut, horodate.fin, horodate.journee_entiere),
                         (datetime.datetime(2026, 11, 17, 10, 0), datetime.datetime(2026, 11, 17, 10, 45), False))
        self.assertTrue(par_titre[self.LONG].journee_entiere)

    def test_calendrier_vide_reste_valide(self):
        with timezone.override(FUSEAU):
            texte = ics_du_flux(())
        self.assertEqual(_depliees(texte)[0], 'BEGIN:VCALENDAR')
        self.assertNotIn('BEGIN:VEVENT', texte)
        self.assertEqual(lire_evenements(texte, J0, J0), ())


class _Monde(TestCase):
    """Un compte et sa journée ; un collègue et un compte d'une autre société avec leurs tâches."""

    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        demain = cls.jour + datetime.timedelta(days=1)
        a, b = fabriques.societe('ft-a'), fabriques.societe('ft-b')
        cls.moi = fabriques.compte(a, nom='moi')
        cls.collegue = fabriques.compte(a, nom='collegue')
        cls.etranger = fabriques.compte(b, nom='etranger')
        cls.reglages = fabriques.reglages(cls.moi)
        p = fabriques.projet(cls.moi, nom='Projet-Z ventes')
        confidentiel = fabriques.projet(cls.moi, nom='Projet-Z Canari-7Q9', confidentiel=True)
        # Mis en pause la VEILLE : sous C-5 (R2-031) une pause du jour même garderait « Pause-Z » dans la journée.
        veille = timezone.make_aware(datetime.datetime.combine(cls.jour - datetime.timedelta(days=1),
                                                               datetime.time(18)))
        pause = fabriques.projet(cls.moi, nom='Projet-Z pause', statut=StatutProjet.EN_PAUSE, statut_depuis=veille)
        t = fabriques.tache
        cls.heure = t(cls.moi, projet=p, jour_prevu=cls.jour, heure_debut=datetime.time(10, 0), titre='Devis Settat',
                      estimation_minutes=45, priorite=2, echeance=cls.jour + datetime.timedelta(days=2),
                      notes='NOTE-SECRETE du devis')
        ElementChecklist.objects.create(company=a, tache=cls.heure, libelle='Check-Z prix', rang=1024)
        cls.appel = t(cls.moi, projet=p, jour_prevu=cls.jour, titre='Appeler le fournisseur')
        cls.conf = t(cls.moi, projet=p, jour_prevu=cls.jour, titre='Canari-X3K', confidentiel=True)
        cls.par_projet = t(cls.moi, projet=confidentiel, jour_prevu=cls.jour, titre='Canari-PROJ')
        cls.demain = t(cls.moi, projet=p, jour_prevu=demain, titre='Relancer demain')
        t(cls.moi, projet=p, jour_prevu=cls.jour, titre='Faite-Z', statut=StatutTache.FAIT, fait_le=timezone.now())
        t(cls.moi, projet=p, jour_prevu=cls.jour, titre='Attente-Z', statut=StatutTache.EN_ATTENTE)
        t(cls.moi, projet=pause, jour_prevu=cls.jour, titre='Pause-Z')
        t(cls.moi, projet=p, parent=cls.appel, jour_prevu=cls.jour, titre='Sous-Z')
        t(cls.moi, projet=p, jour_prevu=cls.jour + datetime.timedelta(days=15), titre='Loin-Z')
        t(cls.moi, titre='Trier-Z')
        t(cls.collegue, projet=fabriques.projet(cls.collegue), jour_prevu=cls.jour, titre='Collegue-Z')
        t(cls.etranger, projet=fabriques.projet(cls.etranger), jour_prevu=cls.jour, titre='Etranger-Z')
        fabriques.activite(cls.moi, summary='Activite-Z à rappeler')
        fabriques.agenda_externe(cls.moi)
        cls.clair_flux = fabriques.jeton(cls.moi, 'flux')[1]
        cls.clair_tuile = fabriques.jeton(cls.moi, 'tuile')[1]

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        rdv = RendezVousPur('1-rdv', 1, 'Rdv-Z client', datetime.datetime.combine(self.jour, datetime.time(15, 0)),
                            datetime.datetime.combine(self.jour, datetime.time(16, 0)), False)
        remplacement = mock.patch.object(lecteur, 'lire_agenda_externe', return_value=(rdv,))
        self.lecteur = remplacement.start()
        self.addCleanup(remplacement.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.moi)

    def _titres(self, **interrupteurs):
        ReglagesRythme.objects.filter(pk=self.reglages.pk).update(**interrupteurs)

    def _sans_fuite(self, texte):
        bas = texte.lower()
        for marqueur in MARQUEURS:
            with self.subTest(marqueur=marqueur):
                self.assertNotIn(marqueur, bas)


class FluxTests(_Monde):
    def _flux(self, clair=None):
        return APIClient().get(f'{PREFIXE}flux/{clair or self.clair_flux}.ics')

    def test_taches_a_faire_de_j_a_j14_et_rien_d_autre(self):
        self.lecteur.reset_mock()
        reponse = self._flux()
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse['Content-Type'].startswith('text/calendar'))
        self.assertEqual(reponse['Cache-Control'], 'no-store')
        texte = reponse.content.decode('utf-8')
        attendus = {self.heure, self.appel, self.conf, self.par_projet, self.demain}
        self.assertEqual(sorted(_valeurs(texte, 'UID')), sorted(f'tache-{t.pk}@taqinor' for t in attendus))
        self.assertEqual(_valeurs(texte, 'DESCRIPTION'), [''] * len(attendus))
        self.assertEqual(sorted(_valeurs(texte, 'SUMMARY')),
                         sorted(['Devis Settat', 'Appeler le fournisseur', 'Relancer demain',
                                 TACHE_CONFIDENTIELLE, TACHE_CONFIDENTIELLE]))
        self._sans_fuite(''.join(_depliees(texte)))
        self.lecteur.assert_not_called()

    def test_heure_et_duree_relues_a_l_heure_de_la_societe(self):
        texte = self._flux().content.decode('utf-8')
        relus = {r.titre: r for r in lire_evenements(texte, self.jour, self.jour + datetime.timedelta(days=14))}
        bloc = relus['Devis Settat']
        debut = datetime.datetime.combine(self.jour, datetime.time(10, 0))
        self.assertEqual((bloc.debut, bloc.fin, bloc.journee_entiere),
                         (debut, debut + datetime.timedelta(minutes=45), False))
        self.assertTrue(relus['Appeler le fournisseur'].journee_entiere)

    def test_titres_coupes_par_le_reglage(self):
        self._titres(titres_calendrier=False)
        texte = self._flux().content.decode('utf-8')
        self.assertEqual(sorted(_valeurs(texte, 'SUMMARY')),
                         sorted(['Tâche'] * 3 + [TACHE_CONFIDENTIELLE] * 2))
        self.assertNotIn('Devis Settat', texte)

    def test_uid_stables_d_un_appel_a_l_autre(self):
        premier = _valeurs(self._flux().content.decode('utf-8'), 'UID')
        self.assertEqual(_valeurs(self._flux().content.decode('utf-8'), 'UID'), premier)

    def test_le_proprietaire_et_la_societe_sont_ceux_du_jeton(self):
        for compte, sien in ((self.collegue, 'Collegue-Z'), (self.etranger, 'Etranger-Z')):
            with self.subTest(compte=compte.username):
                texte = self._flux(fabriques.jeton(compte, 'flux')[1]).content.decode('utf-8')
                self.assertEqual(_valeurs(texte, 'SUMMARY'), [sien])

    def test_refus_neutres_comme_un_inconnu(self):
        revoque, clair_revoque = fabriques.jeton(self.collegue, 'flux')
        revoque.revoque_le = timezone.now()
        revoque.save()
        inactif = fabriques.compte(self.moi.company, nom='inactif')
        clair_inactif = fabriques.jeton(inactif, 'flux')[1]
        inactif.is_active = False
        inactif.save()
        reference = self._flux('tqf_' + 'x' * 43)
        self.assertEqual(reference.status_code, 404)
        capture = fabriques.jeton(self.moi, 'capture')[1]
        for nom, clair in (('jeton tuile', self.clair_tuile), ('jeton capture', capture),
                           ('révoqué', clair_revoque), ('compte désactivé', clair_inactif)):
            with self.subTest(cas=nom):
                reponse = self._flux(clair)
                self.assertEqual(_neutre(reponse), _neutre(reference))
                self.assertEqual(reponse['Cache-Control'], 'no-store')
                self.assertNotIn(clair, reponse.content.decode('utf-8'))

    def test_un_accept_text_calendar_n_est_pas_refuse(self):
        reponse = APIClient().get(f'{PREFIXE}flux/{self.clair_flux}.ics', HTTP_ACCEPT='text/calendar')
        self.assertEqual(reponse.status_code, 200)


class TuileTests(_Monde):
    def _tuile(self, clair=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {clair or self.clair_tuile}')
        return api.get(URL_TUILE)

    def _corps(self):
        reponse = self._tuile()
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse

    def test_tuile_json_exactement(self):
        reponse = self._corps()
        self.assertEqual(reponse['Cache-Control'], 'no-store')
        corps, echantillon = reponse.json(), exemple_de('tuile')
        self.assertEqual(set(corps), set(echantillon))
        self.assertEqual(set(corps['essentiel']), set(echantillon['essentiel']))
        self.assertEqual(set(corps['prochaine_echeance']), set(echantillon['prochaine_echeance']))
        for ligne in corps['top']:
            self.assertEqual(set(ligne), set(echantillon['top'][0]))
        self.assertEqual(corps['jour'], self.jour.isoformat())
        self.assertTrue(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$', corps['maj']), corps['maj'])
        self.assertEqual(corps['lien'], 'http://testserver/taches/aujourdhui')

    def test_memes_chiffres_que_l_ecran(self):
        corps = self._corps().json()
        ecran = self.api.get(PREFIXE + 'aujourdhui/').json()
        progression = ecran['progression']
        self.assertEqual((corps['faites'], corps['prevues'], corps['objectif']),
                         (progression['faites'], progression['prevues'], ecran['objectif']['nb']))
        self.assertEqual(corps['essentiel'], {'faites': progression['essentiel_faites'],
                                              'prevues': progression['essentiel_prevues']})
        pastille = self.api.get(PREFIXE + 'badge/').json()['n']
        self.assertEqual(corps['reste'], pastille - len(corps['top']))

    def test_top_gardees_ouvertes_confidentielles_masquees_activite_jamais_titree(self):
        self.lecteur.reset_mock()
        reponse = self._corps()
        corps = reponse.json()
        self.assertEqual(corps['top'][0],
                         {'id': self.heure.pk, 'titre': 'Devis Settat', 'heure': '10:00', 'priorite': 2})
        self.assertEqual({ligne['id'] for ligne in corps['top']},
                         {self.heure.pk, self.appel.pk, self.conf.pk, self.par_projet.pk})
        titres = {ligne['id']: ligne['titre'] for ligne in corps['top']}
        self.assertEqual((titres[self.conf.pk], titres[self.par_projet.pk]), (TACHE_CONFIDENTIELLE,) * 2)
        self.assertGreaterEqual(corps['reste'], 1, "l'activité ERP du jour ne compte pas dans le reste")
        self.assertEqual(corps['prochaine_echeance'], {
            'titre': 'Devis Settat', 'jour': (self.jour + datetime.timedelta(days=2)).isoformat(), 'heure': None})
        self._sans_fuite(reponse.content.decode('utf-8'))
        self.lecteur.assert_not_called()

    def test_titres_coupes_par_le_reglage(self):
        self._titres(titres_tuile=False)
        corps = self._corps().json()
        self.assertEqual(sorted(ligne['titre'] for ligne in corps['top']),
                         sorted(['Tâche', 'Tâche', TACHE_CONFIDENTIELLE, TACHE_CONFIDENTIELLE]))
        self.assertEqual(corps['prochaine_echeance']['titre'], 'Tâche')

    def test_essentiel_du_plan_en_tete(self):
        plan = fabriques.plan(self.moi, self.jour)
        LignePlanJour.objects.create(company=self.moi.company, plan=plan, tache=self.appel, prevue_au_plan=True,
                                     essentielle=True)
        corps = self._corps().json()
        self.assertEqual(corps['essentiel'], {'faites': 0, 'prevues': 1})
        self.assertEqual(corps['top'][0]['id'], self.appel.pk)

    def test_le_proprietaire_et_la_societe_sont_ceux_du_jeton(self):
        for compte, sien in ((self.collegue, 'Collegue-Z'), (self.etranger, 'Etranger-Z')):
            with self.subTest(compte=compte.username):
                corps = self._tuile(fabriques.jeton(compte, 'tuile')[1]).json()
                self.assertEqual([ligne['titre'] for ligne in corps['top']], [sien])

    def test_refus_neutres_comme_un_inconnu(self):
        revoque, clair_revoque = fabriques.jeton(self.collegue, 'tuile')
        revoque.revoque_le = timezone.now()
        revoque.save()
        inactif = fabriques.compte(self.moi.company, nom='inactif')
        clair_inactif = fabriques.jeton(inactif, 'tuile')[1]
        inactif.is_active = False
        inactif.save()
        reference = self._tuile('tqt_' + 'x' * 43)
        self.assertEqual(reference.status_code, 401)
        for nom, clair in (('jeton flux', self.clair_flux), ('révoqué', clair_revoque),
                           ('compte désactivé', clair_inactif)):
            with self.subTest(cas=nom):
                reponse = self._tuile(clair)
                self.assertEqual(_neutre(reponse), _neutre(reference))
                self.assertNotIn(clair, reponse.content.decode('utf-8'))
