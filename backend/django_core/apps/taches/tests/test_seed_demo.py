"""TCH169 — `manage.py seed_taches_demo` : la journée de `docs/taches/maquettes/SCENARIO.md`.

- Refus hors DEBUG ou sous des réglages de production : SANS base (`SimpleTestCase`), la garde passe avant
  tout accès aux données.
- Le semis (`TestCase`, joué par la CI) : deux lancements = mêmes comptes et mêmes lignes ; `aujourdhui/` du
  24/11 08:30 = « 0 sur 5 · essentiel 0/2 » et 3 proposées ; 15:00 = « 3 sur 5 · essentiel 1/2 » ; le rythme
  des 10 derniers jours travaillés = 5, 5, 4, 6, 3, 5, 4, 7, 5, 4 ; `--vide`, `--reinitialiser`, mot de passe
  jamais écrit dans le code.
"""
import datetime
import os
import secrets
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.choix import StatutTache
from apps.taches.management.commands import seed_taches_demo as commande
from apps.taches.models.journee import PlanJour
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.services import journee
from apps.taches.services.erp import convertir_activites
from testkit.time import frozen

JOUR = datetime.date(2026, 11, 24)


def _instant(heure):
    return timezone.make_aware(datetime.datetime.combine(JOUR, datetime.time.fromisoformat(heure)))


def _semer(*arguments):
    sortie = StringIO()
    with override_settings(DEBUG=True):
        call_command('seed_taches_demo', *arguments, stdout=sortie)
    return sortie.getvalue()


class RefusTests(SimpleTestCase):
    def test_refuse_hors_debug(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('seed_taches_demo', stdout=StringIO())

    def test_refuse_sous_les_reglages_de_production(self):
        with override_settings(DEBUG=True), \
                mock.patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'erp_agentique.settings.prod'}), \
                self.assertRaises(CommandError):
            call_command('seed_taches_demo', stdout=StringIO())


class SemisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _semer()
        cls.user = get_user_model().objects.get(username=commande.NOM_COMPTE)

    def _compter(self):
        return (get_user_model().objects.filter(username=commande.NOM_COMPTE).count(),
                Projet.objects.filter(proprietaire=self.user).count(),
                Tache.all_objects.filter(proprietaire=self.user).count(),
                PlanJour.objects.filter(proprietaire=self.user).count())

    def _aujourdhui(self, heure):
        return journee.aujourdhui(self.user, JOUR, _instant(heure))

    def test_le_compte_est_administrateur_avec_taches_voir_par_un_role_de_test(self):
        self.assertTrue(self.user.company.est_demo)
        self.assertEqual(self.user.role.nom, commande.NOM_ROLE)
        self.assertTrue(self.user.has_erp_permission('taches_voir'))
        self.assertFalse(self.user.has_usable_password())

    def test_deux_lancements_donnent_les_memes_comptes(self):
        avant = self._compter()
        sortie = _semer()
        self.assertIn('déjà semé', sortie)
        self.assertEqual(self._compter(), avant)
        self.assertEqual(avant[1], 5)

    def test_reinitialiser_rejoue_la_meme_journee(self):
        avant = self._compter()
        _semer('--reinitialiser')
        self.user = get_user_model().objects.get(username=commande.NOM_COMPTE)
        self.assertEqual(self._compter(), avant)

    def test_le_matin_0_sur_5_essentiel_0_sur_2_et_3_proposees(self):
        forme = self._aujourdhui('08:30')
        progression = forme['progression']
        self.assertEqual((progression['faites'], progression['essentiel_faites'], progression['essentiel_prevues']),
                         (0, 0, 2))
        self.assertEqual(forme['objectif']['nb'], 5)
        self.assertEqual(len(forme['propose']['pour_objectif']), 3)
        # ERR-PLAN 3 : « Envoyer la facture d'acompte » est un à-faire d'Activités NON converti (le bandeau de
        # TCH136 étape 5 le convertit) : À trier = 4 tâches + 1 à convertir
        self.assertEqual((forme['a_trier']['boite_reception'], forme['a_trier']['a_convertir']), (4, 1))

    def test_une_tache_en_attente_et_des_reserves_aux_vrais_titres(self):
        attente = list(Tache.objects.filter(proprietaire=self.user, statut=StatutTache.EN_ATTENTE))
        self.assertEqual([(t.titre, t.en_attente_de) for t in attente],
                         [('Poser la structure', 'Réceptionner les 16 panneaux')])
        reserve = Tache.objects.filter(proprietaire=self.user, quelque_jour=True)
        self.assertEqual(reserve.count(), commande.TAILLE_RESERVE)
        self.assertFalse(reserve.filter(titre__startswith='Tâche en réserve').exists())

    def test_les_projets_ont_leurs_comptes_du_matin(self):
        ouvertes = {p.nom: Tache.objects.filter(projet=p, statut=StatutTache.A_FAIRE).count()
                    for p in Projet.objects.filter(proprietaire=self.user)}
        self.assertEqual(ouvertes, {commande.BENALI: 5, commande.SALON: 8, commande.RECRUTEMENT: 5,
                                    commande.ADMIN: 3, commande.SITE: 4})

    def test_le_rythme_des_dix_derniers_jours_travailles(self):
        comptes = list(PlanJour.objects.filter(proprietaire=self.user, jour__lt=JOUR, compte_rythme__gt=0)
                       .order_by('jour').values_list('compte_rythme', flat=True))
        self.assertEqual(comptes, [5, 5, 4, 6, 3, 5, 4, 7, 5, 4])

    def test_a_15_heures_3_sur_5_essentiel_1_sur_2(self):
        _semer('--reinitialiser', '--heure', '15:00')
        self.user = get_user_model().objects.get(username=commande.NOM_COMPTE)
        progression = self._aujourdhui('15:00')['progression']
        # regles.md §6.1 : l'activité ERP « Rappeler pour le devis » close à 10:40 porte la tâche du devis
        # (rails, fournisseur, devis = 3 tâches) : portée par une tâche, elle ne compte pas une 2e fois.
        self.assertEqual((progression['faites'], progression['detail']['activites_closes'],
                          progression['essentiel_faites'], progression['essentiel_prevues']), (3, 0, 1, 2))

    def test_vide_ne_laisse_aucune_tache(self):
        _semer('--reinitialiser', '--vide')
        self.assertEqual(Tache.all_objects.filter(proprietaire=self.user).count(), 0)
        self.assertEqual(Projet.all_objects.filter(proprietaire=self.user).count(), 0)

    def test_le_rappel_n_a_aucune_tache_liee_le_matin(self):
        # S5 : « Lier une tâche » du parcours (TCH137 étape 4) doit répondre 201 à 08:30.
        from apps.records.models import Activity
        rappel = Activity.objects.get(company_id=self.user.company_id, summary=commande.ACTIVITE_APPEL)
        self.assertFalse(Tache.all_objects.filter(activite_origine=rappel).exists())
        self.assertFalse(rappel.done)

    def test_le_mot_de_passe_vient_de_l_environnement(self):
        secret = secrets.token_urlsafe(16)
        with mock.patch.dict(os.environ, {commande.VARIABLE_MOT_DE_PASSE: secret}):
            _semer()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(secret))


# --- La preuve du semis : les routes lues horloge FIGÉE à chaque heure-clé de SCENARIO.md -----------------------------
# Chiffres recopiés de `docs/taches/maquettes/SCENARIO.md` ; là où la RÉFÉRENCE les contredit, la valeur de la
# référence est attendue et l'écart est un ERR-SCENARIO du rapport de la lane f2-acc-serveur (dit en commentaire).

RAILS, FOURNISSEUR, FICHE = commande.RAILS, commande.FOURNISSEUR, commande.FICHE
DEVIS, STAND, CONTRAT = commande.DEVIS, commande.STAND, commande.CONTRAT


def _instant_du(jour, heure):
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time.fromisoformat(heure)))


def _titres(items):
    return [item['titre'] for item in items]


class ScenarioTests(TestCase):
    """Après un semis à chaque heure-clé, `aujourdhui/`, `agenda/`, `projets/`, `revue/projets/` et le bilan
    rendent les chiffres de SCENARIO.md."""

    def semer(self, *arguments):
        _semer('--reinitialiser', *arguments)
        self.user = get_user_model().objects.get(username=commande.NOM_COMPTE)
        self.client_ = APIClient()
        self.client_.force_authenticate(self.user)

    def lire(self, route, instant, **params):
        with frozen(instant):
            reponse = self.client_.get(f'/api/django/taches/{route}', params)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def matin(self):
        self.semer('--heure', '08:30', '--historique', '10')
        return self.lire('aujourdhui/', _instant('08:30'))

    def test_08h30_la_journee_du_matin(self):
        forme = self.matin()
        p = forme['progression']
        self.assertEqual((p['faites'], forme['objectif']['nb'], p['essentiel_faites'], p['essentiel_prevues']),
                         (0, 5, 0, 2))  # « 0 sur 5 · essentiel 0/2 »
        self.assertEqual(_titres(forme['essentiel']), [DEVIS, STAND])
        # Proposé 3 dans l'ordre de la règle (SCENARIO §3 ; ERR-PLAN TCH137 étape 1 sur le 3e titre)
        self.assertEqual(_titres(forme['propose']['pour_objectif']), [RAILS, FOURNISSEUR, FICHE])
        self.assertEqual(_titres(forme['a_decider']), list(commande.A_REVOIR))  # S1 : À revoir 2
        self.assertEqual(_titres(forme['en_attente']), ['Poser la structure'])  # En attente 1
        self.assertEqual(forme['carte_du_moment']['type'], 'garder')  # S2 : « Garder ces 3 »
        self.assertEqual(forme['carte_du_moment']['donnees'], {'n': 3, 'objectif': 5})
        self.assertEqual([i['titre'] for i in forme['journee'] if i['type'] == 'activite'], [commande.ACTIVITE_APPEL])
        # ERR-PLAN 3 / ERR-SCENARIO : la facture d'acompte est l'à-faire d'Activités (échéance ven. 27) que le
        # bandeau convertit (TCH136 étape 5) ; convertie, elle sera PRÉVUE ven. 27 (spec-2 §3.8) : À trier 4 + 1
        self.assertEqual((forme['a_trier']['boite_reception'], forme['a_trier']['a_convertir']), (4, 1))
        self.assertFalse(Tache.all_objects.filter(proprietaire=self.user, titre=commande.ACTIVITE_FACTURE).exists())
        with frozen(_instant('08:31')):
            convertir_activites(self.user, toutes=True)  # « Tout convertir » (P136.5)
        facture = Tache.objects.get(proprietaire=self.user, titre=commande.ACTIVITE_FACTURE)
        self.assertEqual((facture.jour_prevu, facture.echeance), (datetime.date(2026, 11, 27), None))
        self.assertEqual(self.lire('aujourdhui/', _instant('08:31'))['a_trier']['boite_reception'], 4)

    def test_08h30_la_veille_est_close_et_les_a_revoir_reportees_3_fois(self):
        self.matin()
        veille = PlanJour.objects.get(proprietaire=self.user, jour=JOUR - datetime.timedelta(days=1))
        self.assertIsNotNone(veille.cloture_le)  # S2 : bilan du lun. 23 fait
        for titre in commande.A_REVOIR:  # S1 : prévues lun. 23 après 3 vrais reports
            tache = Tache.objects.get(proprietaire=self.user, titre=titre)
            self.assertEqual((tache.jour_prevu, tache.reports, tache.reports_tranches),
                             (datetime.date(2026, 11, 23), 3, 0))

    def test_08h30_les_projets_12_sur_18(self):
        self.semer('--heure', '08:30')
        projets = {p['nom']: p for p in self.lire('projets/', _instant('08:30'))['results']}
        comptes = {nom: (p['compteurs']['faites'], p['compteurs']['faites'] + p['compteurs']['ouvertes'])
                   for nom, p in projets.items()}
        self.assertEqual(comptes, {commande.BENALI: (12, 18), commande.SALON: (3, 11), commande.RECRUTEMENT: (4, 9),
                                   commande.ADMIN: (7, 10), commande.SITE: (0, 4)})
        # ERR-PLAN 5 : « À planifier » ⇔ 0 ouverte (regles.md §5) : Site web, 4 ouvertes, ne l'est pas
        self.assertFalse(projets[commande.SITE]['a_planifier'])

    def test_09h41_la_tuile_et_l_agenda(self):
        self.semer('--heure', '09:41', '--rendez-vous')
        instant = _instant('09:41')
        p = self.lire('aujourdhui/', instant)['progression']
        self.assertEqual((p['faites'], p['essentiel_faites'], p['essentiel_prevues']), (1, 0, 2))  # « 1 sur 5 »
        jour = self.lire('agenda/', instant, du=JOUR.isoformat(), au=JOUR.isoformat(), vue='jour')
        semaine = self.lire('agenda/', instant, du='2026-11-23', au='2026-11-29', vue='semaine')
        # À placer : Aujourd'hui 3 (stand, fiche, contrat) + À revoir 2, LE MÊME dans les deux vues (api.md §4)
        self.assertEqual(sorted(_titres(jour['a_placer'])), sorted([STAND, FICHE, CONTRAT, *commande.A_REVOIR]))
        self.assertEqual(_titres(semaine['a_placer']), _titres(jour['a_placer']))
        # SCENARIO §4 : « À placer · 12 (Jour et Semaine, 09:41) » — le MÊME volet dans les deux vues, « Mes
        # projets » compris (maquettes `agenda-jour.html` et `agenda-semaine.html`) : 5 + 7 = 12.
        self.assertEqual(jour['mes_projets'], semaine['mes_projets'])
        self.assertEqual(len(jour['a_placer']) + sum(len(g['items']) for g in jour['mes_projets']), 12)
        mes_projets = {g['projet']['nom']: _titres(g['items']) for g in semaine['mes_projets']}
        self.assertEqual(sorted(mes_projets[commande.SALON]),
                         sorted(['Préparer la démo onduleur hybride', "Réserver l'hôtel du salon"]))
        self.assertEqual(mes_projets[commande.RECRUTEMENT], ["Préparer les questions d'entretien"])
        self.assertEqual(len(mes_projets[commande.SITE]), 4)
        self.assertEqual(sum(len(titres) for titres in mes_projets.values()), 7, mes_projets)  # « Mes projets 7 » (§4)
        charges = {}
        for j in semaine['jours']:
            taches = [i for i in j['blocs'] + j['sans_heure'] if i.get('type') == 'tache']
            charges[j['jour']] = (len(taches), sum(i['estimation_minutes'] or 0 for i in taches))
        self.assertEqual(charges['2026-11-25'], (3, 150))  # mer. 25 « 3 tâches · 2 h 30 »
        self.assertEqual(charges['2026-11-26'], (2, 120))  # jeu. 26 « 2 tâches · 2 h »
        self.assertEqual(charges['2026-11-27'], (3, 120))  # ven. 27 « 3 tâches · 2 h »
        self.assertEqual(semaine['capacite']['minutes'], 240)

    def test_15h00_3_sur_5_et_objectif_couvert(self):
        self.semer('--heure', '15:00', '--historique', '10')
        forme = self.lire('aujourdhui/', _instant('15:00'))
        p = forme['progression']
        self.assertEqual((p['faites'], p['detail']['activites_closes'], p['essentiel_faites'],
                          p['essentiel_prevues']), (3, 0, 1, 2))
        self.assertEqual(forme['propose']['pour_objectif'], [])  # « Objectif couvert par ce que tu as gardé. »
        self.assertEqual(self.lire('badge/', _instant('15:02'))['n'], 2)  # cockpit « 2 à faire » (stand, contrat)
        self.assertNotIn(FICHE, _titres(forme['journee']))  # partie jeu. 26 à 14:10
        self.assertEqual(_titres(forme['ce_soir']), [CONTRAT])
        # Essentiel : le devis (fait 10:50, ★) et le stand ; la faite est servie dans `faites`, ★ portée
        essentielles = [i['titre'] for i in forme['essentiel'] + forme['faites'] if i['essentielle']]
        self.assertEqual(sorted(essentielles), sorted([DEVIS, STAND]))

    def test_18h20_le_bilan(self):
        self.semer('--heure', '18:20', '--historique', '10')
        cloture = self.lire('journee/cloture/', _instant('18:20'), jour=JOUR.isoformat())
        bilan = cloture['bilan']
        self.assertEqual(bilan['texte'], '4 sur 5 · essentiel 2 sur 2')
        # SCENARIO §3, 18:20 : « 4 des 5 gardées » — devis, stand, rails, fournisseur tenues ; la fiche, passée à
        # jeu. 26, garde sa ligne (non tenue). L'activité ERP « Rappeler pour le devis », gardée le matin puis LIÉE
        # à une tâche à 10:30, n'est pas une gardée de plus : sa tâche la représente (`sel.ligne_gardee`).
        self.assertEqual((bilan['plan_tenues'], bilan['plan_lignes']), (4, 5))
        self.assertEqual(bilan['texte_gardees'], '4 des 5 gardées')
        self.assertEqual(_titres(cloture['restes']), [CONTRAT])
        self.assertEqual(sorted(_titres(cloture['faites'])), sorted([DEVIS, FOURNISSEUR, RAILS, STAND]))
        self.assertEqual(cloture['prochain_jour_ouvre'], '2026-11-25')

    def test_vide_aucune_tache_aucun_projet(self):
        self.semer('--vide')
        forme = self.lire('aujourdhui/', _instant('08:30'))
        self.assertEqual((forme['essentiel'], forme['journee'], forme['propose']['pour_objectif']), ([], [], []))
        self.assertEqual(self.lire('projets/', _instant('08:30'))['count'], 0)

    def test_absence_10_jours_la_carte_de_retour(self):
        self.semer('--jour', '2026-12-07', '--absence', '10')
        retour = datetime.date(2026, 12, 7)
        instant = _instant_du(retour, '08:30')
        with frozen(instant):
            journee.vu(self.user, retour, instant)  # l'écran fait `POST vu/` à l'ouverture
        forme = self.lire('aujourdhui/', instant)
        carte = forme['carte_du_moment']
        self.assertEqual(carte['type'], 'retour')
        self.assertTrue(carte['proposition']['texte'].startswith('Tu reviens après 10 jours'))
        self.assertTrue(forme['progression']['reprise'])

    def test_revue_du_vendredi_20_sur_le_semis_par_defaut(self):
        # ERR-PLAN 6 : la revue se lit sur le semis PAR DÉFAUT, horloge au ven. 20 17:40 (`--jour 2026-11-20`
        # décale tout le scénario de −4 jours).
        self.semer()
        revue = self.lire('revue/projets/', _instant_du(datetime.date(2026, 11, 20), '17:40'))
        self.assertEqual(revue['bilan_semaine']['texte'],
                         'Du lun. 16 au ven. 20 : 21 tâches en 4 jours (précédente : 23). '
                         'Objectif atteint 3 jours sur 4 · essentiel 3 sur 4.')
