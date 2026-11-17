"""La journée côté serveur (reference/regles.md « La journée » ; donnees.md invariants 2, 3, 10-13, 32).

Avec base (CI). Le jour est toujours injecté (mardi 17/11/2026, repère de regles.md §0) ; les heures
« faites aujourd'hui » sont des instants locaux de ce jour.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.taches.choix import MotifRevoir, SectionJournee as S, StatutProjet, StatutTache
from apps.taches.models.journee import LignePlanJour
from apps.taches.selectors import journee as sel
from apps.taches.tests import fabriques

J = datetime.date(2026, 11, 17)


def a(jour, heure=10, minute=0):
    """Instant aware de l'heure murale `jour` `heure:minute`."""
    return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure, minute)))


def jours(n):
    return J + datetime.timedelta(days=n)


def ligne(plan, tache=None, activite_id=None, **champs):
    champs.setdefault('prevue_au_plan', True)
    return LignePlanJour.objects.create(company=plan.company, plan=plan, tache=tache,
                                        activite_id=activite_id, **champs)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = fabriques.compte(cls.societe, nom='u1')
        cls.projet = fabriques.projet(cls.u, priorite=2)

    def tache(self, **champs):
        champs.setdefault('projet', self.projet)
        return fabriques.tache(self.u, **champs)

    def journee(self):
        return sel.lire_journee(self.u, J)

    def section_de(self, journee, objet, type_='tache'):
        placement = journee.placements.get((type_, objet.pk))
        return placement.section if placement else None


class PrefiltreTests(_Base):
    """Invariants 2 et 10 : le préfiltre unique, et rien d'À trier dans la journée."""

    def test_a_trier_absente_de_toute_section_et_de_propose(self):
        boite = fabriques.tache(self.u)  # sans projet, sans jour : triee_le nul
        self.assertIsNone(boite.triee_le)
        journee = self.journee()
        self.assertNotIn(('tache', boite.pk), journee.items)
        self.assertFalse(sel.taches_de_la_journee(self.u, J).filter(pk=boite.pk).exists())

    def test_sans_projet_triee_presente(self):
        triee = fabriques.tache(self.u, triee_le=a(jours(-3)), jour_prevu=J)
        self.assertEqual(self.section_de(self.journee(), triee), S.JOURNEE)

    def test_sous_tache_bloquee_reserve_pause_absentes(self):
        parent = self.tache(jour_prevu=J)
        enfant = self.tache(jour_prevu=J, parent=parent)
        prerequis = self.tache()
        bloquee = self.tache(jour_prevu=J, bloquee_par=prerequis)
        reserve = self.tache(quelque_jour=True)
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE)
        dans_la_pause = self.tache(projet=en_pause, jour_prevu=J)
        ids = set(sel.taches_de_la_journee(self.u, J).values_list('pk', flat=True))
        self.assertIn(parent.pk, ids)
        for absente in (enfant, bloquee, reserve, dans_la_pause):
            self.assertNotIn(absente.pk, ids, absente.titre)

    def test_prerequis_clos_ne_bloque_plus(self):
        prerequis = self.tache(statut=StatutTache.FAIT, fait_le=a(jours(-2)))
        debloquee = self.tache(jour_prevu=J, bloquee_par=prerequis)
        self.assertEqual(self.section_de(self.journee(), debloquee), S.JOURNEE)

    def test_faite_aujourdhui_presente_faite_hier_absente(self):
        aujourdhui = self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))
        hier = self.tache(jour_prevu=jours(-1), statut=StatutTache.FAIT, fait_le=a(jours(-1), 18))
        journee = self.journee()
        self.assertEqual(self.section_de(journee, aujourdhui), S.FAITES)
        self.assertNotIn(('tache', hier.pk), journee.items)

    def test_autre_compte_et_autre_societe_jamais_lus(self):
        voisin = fabriques.compte(self.societe, nom='u2')
        ailleurs = fabriques.compte(fabriques.societe('b'), nom='u1')
        for autre in (voisin, ailleurs):
            fabriques.tache(autre, projet=fabriques.projet(autre), jour_prevu=J)
        self.assertEqual(sel.taches_de_la_journee(self.u, J).count(), 0)


class ARevoirTests(_Base):
    """Invariant 3 : À revoir ne contient QUE les reportées 3 fois, les retards de plus de 7 jours et
    les activités ERP passées."""

    def test_reportee_3_fois(self):
        t = self.tache(jour_prevu=jours(-4), reports=3)
        journee = self.journee()
        self.assertEqual(journee.placements[('tache', t.pk)].code, MotifRevoir.REPORTEE_3_FOIS)
        self.assertEqual(self.section_de(journee, t), S.A_DECIDER)

    def test_tranchee_ne_revient_que_3_reports_plus_tard(self):
        t = self.tache(jour_prevu=jours(-2), reports=4, reports_tranches=3)
        self.assertEqual(self.section_de(self.journee(), t), S.PROPOSE)

    def test_retard_de_plus_de_7_jours(self):
        par_jour = self.tache(jour_prevu=jours(-8))
        par_echeance = self.tache(echeance=jours(-10))
        journee = self.journee()
        for t in (par_jour, par_echeance):
            self.assertEqual(journee.placements[('tache', t.pk)].code, MotifRevoir.RETARD_ANCIEN)

    def test_retard_de_7_jours_au_plus_en_tete_de_propose(self):
        t = self.tache(jour_prevu=jours(-7))
        self.assertEqual(self.section_de(self.journee(), t), S.PROPOSE)

    def test_activite_passee(self):
        activite = fabriques.activite(self.u, due_date=jours(-2))
        journee = self.journee()
        self.assertEqual(journee.placements[('activite', activite.pk)].code, MotifRevoir.ACTIVITE_PASSEE)

    def test_activites_masquees_si_erp_eteint(self):
        fabriques.reglages(self.u, erp_dans_journee=False)
        activite = fabriques.activite(self.u, due_date=J)
        self.assertNotIn(('activite', activite.pk), self.journee().items)


class SectionsEtOrdreTests(_Base):
    """regles.md §4.2 et invariant 32 : section par premier cas vrai, ordre d'affichage."""

    def test_essentiel_ce_soir_prevu_en_attente(self):
        essentielle = self.tache(jour_prevu=J)
        soir = self.tache(jour_prevu=J, moment='soir')
        prevue = self.tache(echeance=J)
        attente = self.tache(jour_prevu=J, statut=StatutTache.EN_ATTENTE, en_attente_de='Lydec')
        ligne(fabriques.plan(self.u, J), tache=essentielle, essentielle=True)
        journee = self.journee()
        self.assertEqual(self.section_de(journee, essentielle), S.ESSENTIEL)
        self.assertEqual(self.section_de(journee, soir), S.CE_SOIR)
        self.assertEqual(self.section_de(journee, prevue), S.JOURNEE)
        self.assertEqual(self.section_de(journee, attente), S.EN_ATTENTE)

    def test_prevu_a_l_heure_d_abord_puis_rang_jour_puis_cle_tri(self):
        sans = self.tache(jour_prevu=J, priorite=3)
        rangee = self.tache(jour_prevu=J, rang_jour=1024)
        a_dix = self.tache(jour_prevu=J, heure_debut=datetime.time(10, 0))
        a_neuf = self.tache(jour_prevu=J, heure_debut=datetime.time(9, 0))
        ordre = [o.pk for o in self.journee().objets_de(S.JOURNEE)]
        self.assertEqual(ordre, [a_neuf.pk, a_dix.pk, rangee.pk, sans.pk])

    def test_a_revoir_dans_l_ordre_de_cle_tri(self):
        # §3.3 : À revoir = 40 (échéance 07/11) puis 50 (reportée 3 fois).
        quarante = self.tache(echeance=datetime.date(2026, 11, 7), priorite=1)
        cinquante = self.tache(jour_prevu=datetime.date(2026, 11, 13), reports=3)
        ordre = [o.pk for o in self.journee().objets_de(S.A_DECIDER)]
        self.assertEqual(ordre, [quarante.pk, cinquante.pk])


class PastilleTests(_Base):
    """Invariant 11 : `compter_journee` = ouverts GARDÉS d'Essentiel, Prévu, Ce soir."""

    def test_compte_les_gardes_ouverts_seulement(self):
        self.tache(jour_prevu=J)
        self.tache(echeance=J)
        self.tache(jour_prevu=J, moment='soir')
        fabriques.activite(self.u, due_date=J)
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))  # faite : jamais
        self.tache(jour_prevu=jours(-1))  # Proposé (retard)
        self.tache()  # Proposé (tour des projets)
        self.tache(jour_prevu=jours(-9))  # À revoir
        self.tache(jour_prevu=J, statut=StatutTache.EN_ATTENTE)  # En attente
        fabriques.tache(self.u)  # À trier
        self.assertEqual(sel.compter_journee(self.u, J), 4)

    def test_peut_valoir_zero(self):
        self.assertEqual(sel.compter_journee(self.u, J), 0)

    def test_plafond_99(self):
        for _ in range(100):
            self.tache(jour_prevu=J)
        self.assertEqual(sel.compter_journee(self.u, J), 99)


class ProgressionTests(_Base):
    """Invariant 13 : `faites` = `compte_du_jour` ; `prevues` = faites + ouverts gardés ; gardées
    faites sur les seules lignes `prevue_au_plan`."""

    def _progression(self):
        journee = self.journee()
        compte, detail = sel.compte_faites(self.u, J)
        return sel.progression_du_jour(journee, faites=compte, detail=detail, capacite=(240, 'defaut'),
                                       rendez_vous_minutes=60)

    def test_faites_et_prevues(self):
        faite = self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9), estimation_minutes=30)
        parent = self.tache(jour_prevu=jours(3))
        self.tache(parent=parent, statut=StatutTache.FAIT, fait_le=a(J, 10))  # sous-tâche : 0
        ouverte = self.tache(jour_prevu=J, estimation_minutes=45)
        self.tache(jour_prevu=J)  # sans estimation
        plan = fabriques.plan(self.u, J, planifie_le=a(J, 8))
        ligne(plan, tache=faite)
        ligne(plan, tache=ouverte, essentielle=True)
        ligne(plan, tache=parent, prevue_au_plan=False)
        p = self._progression()
        self.assertEqual(p['faites'], 1)
        self.assertEqual(p['detail']['etapes'], 1)
        self.assertEqual(p['prevues'], 1 + 2)
        self.assertEqual((p['plan_tenues'], p['plan_lignes']), (1, 2))
        self.assertEqual((p['essentiel_faites'], p['essentiel_prevues']), (0, 1))
        self.assertEqual((p['minutes_prevues'], p['sans_estimation']), (75, 1))
        self.assertEqual((p['capacite_minutes'], p['rendez_vous_minutes'], p['disponible_minutes']),
                         (240, 60, 180))

    def test_faite_d_un_projet_en_pause_compte(self):
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE)
        self.tache(projet=en_pause, statut=StatutTache.FAIT, fait_le=a(J, 11))
        self.assertEqual(self._progression()['faites'], 1)

    def test_forme_complete(self):
        cles = {'faites', 'detail', 'prevues', 'essentiel_faites', 'essentiel_prevues', 'plan_tenues',
                'plan_lignes', 'minutes_prevues', 'sans_estimation', 'capacite_minutes', 'capacite_source',
                'rendez_vous_minutes', 'disponible_minutes', 'activites_closes', 'activites', 'reprise'}
        self.assertEqual(set(self._progression()), cles)


class ObjectifEtCapaciteTests(_Base):
    def test_objectif_par_defaut_sans_reglages(self):
        self.assertEqual(sel.objectif_du_jour(None),
                         {'nb': 5, 'source': 'defaut', 'mode': 'pousser', 'zone': None})

    def test_objectif_libre(self):
        reglages = fabriques.reglages(self.u, mode='libre')
        self.assertIsNone(sel.objectif_du_jour(reglages)['nb'])

    def test_capacite_dite(self):
        from apps.taches.models.rythme import Preference
        Preference.objects.create(company=self.societe, proprietaire=self.u, cle='capacite_jour_min',
                                  valeur=300)
        prefs = sel.preferences_de(self.u)
        self.assertEqual(sel.capacite_du_jour(self.u, J, None, prefs, frozenset()), (300, 'reglage'))

    def test_capacite_par_defaut(self):
        self.assertEqual(sel.capacite_du_jour(self.u, J, None, {}, frozenset()), (240, 'defaut'))


# --- TCH55 : obligations du jour, sur de vraies lignes des apps ERP ------------------------------

def compte_erp(societe, nom, permissions):
    """Fabrique locale : un compte interne dont le rôle de test porte `permissions` (+ taches_voir)."""
    from django.contrib.auth import get_user_model

    from apps.roles.models import Role
    role = Role.objects.create(company=societe, nom=f'Test ERP {nom}', permissions=['taches_voir', *permissions])
    return get_user_model().objects.create_user(
        username=f'{nom}@{societe.slug}', password=None, company=societe, role=role, first_name=nom)


def lead(societe, owner, nom='Benali', prenom='Karim'):
    from apps.crm.models import Lead
    return Lead.objects.create(company=societe, nom=nom, prenom=prenom, owner=owner)


def touche(societe, lead_, jour):
    from apps.crm.models import RelanceEtape
    return RelanceEtape.objects.create(company=societe, lead=lead_, cadence='contact', ordre=1,
                                       canal=RelanceEtape.Canal.APPEL, libelle='Appeler', due_date=jour)


class ObligationsTests(TestCase):
    """donnees.md §5 `obligations_du_jour` : visites, interventions, touches ; famille en échec =
    absente ; `peut_cloturer` fourni à ITEM."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.admin = compte_erp(cls.societe, 'admin', ['crm_voir', 'visites_voir', 'roles_gerer'])
        cls.collegue = compte_erp(cls.societe, 'collegue', ['crm_voir'])

    def familles(self, obligations):
        return [ligne['famille'] for ligne in obligations.lignes]

    def test_admin_a_4_touches_dont_1_a_lui(self):
        for owner in (self.admin, self.collegue, self.collegue, self.collegue):
            touche(self.societe, lead(self.societe, owner), J)
        obligations = sel.obligations_du_jour(self.admin, J)
        touches = [ligne for ligne in obligations.lignes if ligne['famille'] == 'touches']
        self.assertEqual(len(touches), 1)
        self.assertEqual(touches[0]['nb'], 1)
        self.assertEqual(touches[0]['url'], '/crm/relances')
        self.assertEqual(touches[0]['titre'], 'Suivi des relances')

    def test_aucune_touche_aucune_ligne(self):
        self.assertNotIn('touches', self.familles(sel.obligations_du_jour(self.admin, J)))

    def test_touches_sans_crm_voir_absentes(self):
        seul = compte_erp(self.societe, 'seul', [])
        touche(self.societe, lead(self.societe, seul), J)
        self.assertEqual(sel.obligations_du_jour(seul, J).lignes, ())

    def test_visite_du_jour_seulement(self):
        from apps.visites.models import VisiteTerrain
        du_jour = VisiteTerrain.objects.create(company=self.societe, lead=lead(self.societe, self.admin),
                                               commercial=self.admin, date_prevue=J)
        VisiteTerrain.objects.create(company=self.societe, lead=lead(self.societe, self.admin, nom='Alaoui'),
                                     commercial=self.admin, date_prevue=jours(3))
        visites = [ligne for ligne in sel.obligations_du_jour(self.admin, J).lignes if ligne['famille'] == 'visite']
        self.assertEqual(visites, [{'famille': 'visite', 'id': du_jour.pk, 'titre': 'Visite — Karim Benali',
                                    'jour': J.isoformat(), 'url': '/visites'}])

    def test_visite_d_un_collegue_absente(self):
        from apps.visites.models import VisiteTerrain
        VisiteTerrain.objects.create(company=self.societe, lead=lead(self.societe, self.collegue),
                                     commercial=self.collegue, date_prevue=J)
        self.assertNotIn('visite', self.familles(sel.obligations_du_jour(self.admin, J)))

    def test_intervention_du_jour(self):
        from apps.installations.models import Installation, Intervention
        chantier = Installation.objects.create(company=self.societe, reference='INS-T-0042')
        Intervention.objects.create(company=self.societe, installation=chantier, type_intervention='pose',
                                    technicien=self.admin, date_prevue=timezone.localdate())
        interventions = [ligne for ligne in sel.obligations_du_jour(self.admin, J).lignes
                         if ligne['famille'] == 'intervention']
        self.assertEqual(len(interventions), 1)
        self.assertEqual(interventions[0]['url'], f'/chantiers?id={chantier.pk}')

    def test_famille_en_echec_absente_les_autres_servies(self):
        from unittest import mock
        touche(self.societe, lead(self.societe, self.admin), J)
        with mock.patch('apps.crm.selectors.relance_etapes_dues', side_effect=RuntimeError('panne')):
            obligations = sel.obligations_du_jour(self.admin, J)
        self.assertEqual(obligations.echecs, ('touches',))
        self.assertNotIn('touches', self.familles(obligations))

    def test_peut_cloturer_est_la_regle_de_records(self):
        from apps.records.selectors import peut_cloturer_activites
        self.assertEqual(sel.obligations_du_jour(self.admin, J).peut_cloturer, peut_cloturer_activites(self.admin))

    def test_compte_sans_societe_rien(self):
        from types import SimpleNamespace
        self.assertEqual(sel.obligations_du_jour(SimpleNamespace(company_id=None, pk=1), J), sel.Obligations())


# --- TCH56 : aujourdhui/, badge/, aujourdhui/ailleurs/, vu/ --------------------------------------

def exemple(nom):
    import json
    from pathlib import Path
    chemin = Path(__file__).resolve().parents[1] / 'contract_samples' / f'{nom}.json'
    return json.loads(chemin.read_text(encoding='utf-8'))['exemple']


CLES_ITEM = set(exemple('item'))


def client_de(compte, **entetes):
    from rest_framework.test import APIClient
    client = APIClient(**entetes)
    client.force_authenticate(compte)
    return client


def maintenant_a(heure, minute=0):
    return timezone.localtime(a(J, heure, minute))


class AujourdhuiTests(_Base):
    """GET aujourdhui/ : la forme d'`aujourdhui.json`, la carte du moment, Proposé replié, 200 lignes."""

    def scenario(self):
        essentielle = self.tache(jour_prevu=J, estimation_minutes=60)
        self.tache(jour_prevu=J)
        self.tache(jour_prevu=J, moment='soir')
        self.tache(jour_prevu=jours(-1))  # Proposé : retard
        self.tache()  # Proposé : prochaine action
        self.tache(jour_prevu=jours(-4), reports=3)  # À revoir
        self.tache(jour_prevu=J, statut=StatutTache.EN_ATTENTE, en_attente_de='Lydec')
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 8))
        ligne(fabriques.plan(self.u, J, planifie_le=a(J, 8, 40)), tache=essentielle, essentielle=True)

    def get(self, **params):
        params.setdefault('jour', J.isoformat())
        reponse = client_de(self.u).get('/api/django/taches/aujourdhui/', params)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def test_reponse_a_la_forme_de_l_echantillon(self):
        self.scenario()
        modele, rendu = exemple('aujourdhui'), self.get(tout='1')
        self.assertEqual(list(rendu), list(modele))
        for cle in ('objectif', 'progression', 'plan', 'propose', 'a_trier'):
            self.assertEqual(set(rendu[cle]), set(modele[cle]), cle)
        self.assertEqual(set(rendu['progression']['detail']), set(modele['progression']['detail']))
        self.assertEqual(set(rendu['propose']['charge']), set(modele['propose']['charge']))
        for section in ('essentiel', 'journee', 'ce_soir', 'a_decider', 'en_attente', 'faites'):
            self.assertTrue(rendu[section], section)
            for item in rendu[section]:
                self.assertEqual(set(item), CLES_ITEM, section)
        for item in rendu['propose']['pour_objectif']:
            self.assertEqual(set(item), CLES_ITEM)
            self.assertEqual(set(item['raison']), {'code', 'texte'})
        groupe = rendu['propose']['suite_par_projet'][0]
        self.assertEqual(set(groupe), set(modele['propose']['suite_par_projet'][0]))

    def test_sections_et_mots(self):
        self.scenario()
        rendu = self.get()
        self.assertTrue(rendu['essentiel'][0]['essentielle'])
        self.assertTrue(rendu['essentiel'][0]['prevue_au_plan'])
        self.assertEqual(rendu['a_decider'][0]['motif'], 'reportee_3_fois')
        # N = 5 − 1 faite − 3 gardées ouvertes = 1 : ce qui presse (le retard) prend la place ;
        # la prochaine action du projet attend dans la suite dépliée.
        pour_objectif = rendu['propose']['pour_objectif']
        self.assertEqual([item['raison'] for item in pour_objectif], [{'code': 'retard', 'texte': 'prévue hier'}])
        self.assertIsNone(rendu['propose']['suite_par_projet'])
        suite = self.get(tout='1')['propose']['suite_par_projet']
        self.assertEqual(suite[0]['projet']['id'], self.projet.pk)
        self.assertEqual(suite[0]['items'][0]['raison'],
                         {'code': 'prochaine_action', 'texte': f'prochaine action de {self.projet.nom}'})
        self.assertEqual(rendu['progression']['faites'], 1)
        self.assertEqual(rendu['plan']['planifie_le'], timezone.localtime(a(J, 8, 40)).isoformat())

    def test_jour_illisible_400_au_champ(self):
        reponse = client_de(self.u).get('/api/django/taches/aujourdhui/', {'jour': '17/11/2026'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('jour', reponse.json())

    def test_propose_replie_apres_alleger(self):
        self.tache()
        fabriques.plan(self.u, J, planifie_le=a(J, 8), allege_le=a(J, 15))
        propose = self.get()['propose']
        self.assertTrue(propose['replie'])
        self.assertEqual(propose['pour_objectif'], [])

    def test_rendez_vous_vides_avant_les_agendas(self):
        self.assertEqual(self.get()['rendez_vous'], [])

    def test_200_lignes_au_plus(self):
        for _ in range(205):
            self.tache(jour_prevu=J)
        rendu = self.get()
        self.assertTrue(rendu['tronque'])
        self.assertEqual(len(rendu['journee']), 200)

    def test_requetes_constantes_en_nombre_de_taches(self):
        """Une forme servie depuis des objets préchargés : pas une requête de plus par ligne."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.tache(jour_prevu=J)
        self.get()  # chauffe l'index des agendas externes (en cache, TCH122)
        with CaptureQueriesContext(connection) as peu:
            self.get()
        for _ in range(12):
            self.tache(jour_prevu=J, estimation_minutes=30)
            self.tache()
        with CaptureQueriesContext(connection) as beaucoup:
            self.get()
        self.assertEqual(len(beaucoup), len(peu))

    def test_assistant_ne_lit_aucun_nom_confidentiel(self):
        secret = fabriques.projet(self.u, nom='Rachat Dupont', confidentiel=True)
        self.tache(projet=secret, jour_prevu=J, titre='Signer la promesse')
        reponse = client_de(self.u).get('/api/django/taches/aujourdhui/', {'jour': J.isoformat()},
                                        HTTP_X_TAQINOR_ASSISTANT='1')
        corps = reponse.content.decode('utf-8')
        self.assertNotIn('Rachat Dupont', corps)
        self.assertNotIn('Signer la promesse', corps)


class CarteDuMomentTests(_Base):
    """regles.md « La carte du moment » : une carte, la première vraie dans l'ordre."""

    def carte(self, heure=9, minute=12):
        from apps.taches.services import journee as services
        return services.aujourdhui(self.u, J, maintenant_a(heure, minute))['carte_du_moment']

    def test_garder_tant_que_rien_n_est_garde(self):
        self.tache()
        self.assertEqual(self.carte(), {'type': 'garder', 'proposition': None, 'donnees': {'n': 1, 'objectif': 5}})

    def test_rythme_a_la_forme_de_l_echantillon(self):
        from apps.taches.models.rythme import IncitationCoach
        fabriques.reglages(self.u)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=J, type='proposition_palier',
                                       cle='monter', canal='ecran', donnees={'N': 5, 'N1': 6, 'tenus': 7},
                                       expire_le=jours(7))
        carte, modele = self.carte(), exemple('carte_du_moment')
        self.assertEqual(set(carte), set(modele))
        self.assertEqual(set(carte['proposition']), set(modele['proposition']))
        self.assertEqual(carte['proposition']['texte'], modele['proposition']['texte'])
        self.assertEqual(carte['proposition']['boutons'], modele['proposition']['boutons'])

    def test_faire_bilan_le_soir(self):
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.assertEqual(self.carte(18, 30)['type'], 'faire_bilan')

    def test_bilan_d_hier_avant_midi_seulement(self):
        self.tache(jour_prevu=jours(-1))
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.assertEqual(self.carte(9)['donnees'], {'jour': jours(-1).isoformat()})
        self.assertIsNone(self.carte(12, 5))

    def test_alleger_l_apres_midi(self):
        self.tache(jour_prevu=J)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.assertEqual(self.carte(15, 30), {'type': 'alleger', 'proposition': None,
                                              'donnees': {'faites': 0, 'prevues': 1}})

    def test_revelation_en_dernier_rendue_par_ses_textes(self):
        from apps.taches.models.rythme import IncitationCoach
        fabriques.reglages(self.u)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=J, type='revelation',
                                       cle='ranger_copilote', canal='ecran', donnees={'n': 5}, expire_le=jours(7))
        carte = self.carte()
        self.assertEqual(carte['type'], 'revelation')
        self.assertEqual(carte['proposition']['texte'],
                         '5 tâches à trier : le Copilote peut les ranger dans tes projets.')
        self.assertEqual(carte['proposition']['boutons'], [{'reponse': 'ok', 'libelle': 'OK'}])
        # Une seule carte du moment : une proposition du rythme passe devant la révélation.
        IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=J, type='proposition_palier',
                                       cle='monter', canal='ecran', donnees={'N': 5, 'N1': 6, 'tenus': 7},
                                       expire_le=jours(7))
        self.assertEqual(self.carte()['type'], 'rythme')


class BadgeEtVuTests(_Base):
    def test_badge(self):
        self.tache(jour_prevu=timezone.localdate())
        rendu = client_de(self.u).get('/api/django/taches/badge/').json()
        self.assertEqual(set(rendu), set(exemple('badge')))
        self.assertEqual(rendu, {'n': 1, 'jour': timezone.localdate().isoformat()})

    def test_vu_sans_reglages_n_ecrit_rien(self):
        from apps.taches.models.journee import PlanJour
        reponse = client_de(self.u).post('/api/django/taches/vu/', {'ecran': 'aujourdhui'}, format='json')
        self.assertEqual(reponse.json(), {'carte_du_moment': None})
        self.assertFalse(PlanJour.objects.filter(proprietaire=self.u).exists())

    def test_vu_pose_l_ouverture(self):
        from apps.taches.models.journee import PlanJour
        fabriques.reglages(self.u)
        client_de(self.u).post('/api/django/taches/vu/', {'ecran': 'aujourdhui'}, format='json')
        plan = PlanJour.objects.get(proprietaire=self.u, jour=timezone.localdate())
        self.assertIsNotNone(plan.app_ouverte_le)

    def test_carte_de_retour(self):
        from apps.taches.services import journee as services
        fabriques.reglages(self.u)
        fabriques.plan(self.u, jours(-10), app_ouverte_le=a(jours(-10), 9))
        self.tache(jour_prevu=jours(-5))
        self.tache(jour_prevu=jours(-2))
        carte = services.vu(self.u, J, maintenant_a(9))['carte_du_moment']
        modele = exemple('vu')['carte_du_moment']
        self.assertEqual(set(carte), set(modele))
        self.assertEqual(set(carte['proposition']), set(modele['proposition']))
        self.assertEqual(carte['proposition']['texte'], 'Tu reviens après 10 jours : 2 tâches attendaient.')
        self.assertEqual(carte['proposition']['boutons'], modele['proposition']['boutons'])
        # une fois par retour : rejouer vu/ ne crée rien de plus
        services.vu(self.u, J, maintenant_a(10))
        from apps.taches.models.rythme import IncitationCoach
        self.assertEqual(IncitationCoach.objects.filter(proprietaire=self.u, type='retour').count(), 1)
        self.assertTrue(services.aujourdhui(self.u, J, maintenant_a(10))['progression']['reprise'])

    def test_remettre_dans_propose_lit_les_ids_de_la_carte(self):
        from apps.taches.models.rythme import IncitationCoach
        from apps.taches.models.taches import Tache
        from apps.taches.services import journee as services
        from apps.taches.services.rythme import repondre_carte
        fabriques.reglages(self.u)
        fabriques.plan(self.u, jours(-10), app_ouverte_le=a(jours(-10), 9))
        une, deux = self.tache(jour_prevu=jours(-5)), self.tache(jour_prevu=jours(-2))
        services.vu(self.u, J, maintenant_a(9))
        carte = IncitationCoach.objects.get(proprietaire=self.u, type='retour')
        self.assertEqual(carte.donnees['ids'], sorted([une.pk, deux.pk]))
        repondre_carte(self.u, carte.pk, 'remettre_dans_propose', J)
        remises = Tache.objects.filter(pk__in=[une.pk, deux.pk])
        self.assertEqual(set(remises.values_list('jour_prevu', flat=True)), {None})
        self.assertEqual(set(remises.values_list('reports', flat=True)), {0})

    def test_pas_de_retour_apres_un_jour(self):
        from apps.taches.services import journee as services
        fabriques.reglages(self.u)
        fabriques.plan(self.u, jours(-1), app_ouverte_le=a(jours(-1), 9))
        self.tache(jour_prevu=jours(-1))
        self.assertIsNone(services.vu(self.u, J, maintenant_a(9))['carte_du_moment'])


class AilleursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = compte_erp(cls.societe, 'tech', [])

    def test_forme_et_chantier_assigne(self):
        from apps.installations.models import Installation
        Installation.objects.create(company=self.societe, reference='INS-T-0001', technicien_responsable=self.u)
        rendu = client_de(self.u).get('/api/django/taches/aujourdhui/ailleurs/').json()
        self.assertEqual(set(rendu), set(exemple('ailleurs')))
        self.assertEqual(rendu['chantiers'], 1)
        self.assertEqual(rendu['lien'], '/activites')


# --- TCH57 : proposition, « Garder ces N », ★ ------------------------------------------------------

J24 = datetime.date(2026, 11, 24)  # SCENARIO.md : mardi 24 novembre 2026


class PropositionTests(TestCase):
    """GET journee/proposition/ (invariant 34) sur la matinée du 24/11 de SCENARIO.md (08:30)."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = fabriques.compte(cls.societe, nom='u1')
        u = cls.u
        benali = fabriques.projet(u, nom='Chantier Benali 9 kWc', priorite=3, rang=1024)
        salon = fabriques.projet(u, nom='Salon Solaire Expo', priorite=3, rang=2048)
        recrutement = fabriques.projet(u, nom='Recrutement technicien', priorite=2, rang=3072)
        admin = fabriques.projet(u, nom='Administratif', priorite=1, rang=4096)
        site = fabriques.projet(u, nom='Site web', priorite=2, rang=5120)
        cls.devis = fabriques.tache(u, projet=benali, titre='Envoyer le devis révisé', priorite=3, jour_prevu=J24,
                                    echeance=J24 + datetime.timedelta(days=1))
        cls.rails = fabriques.tache(u, projet=benali, titre='Commander les rails de fixation')
        cls.stand = fabriques.tache(u, projet=salon, titre='Confirmer la réservation du stand', echeance=J24)
        cls.fournisseur = fabriques.tache(u, projet=salon, titre='Appeler le fournisseur', priorite=3)
        fabriques.tache(u, projet=recrutement, titre='Trier les CV reçus', jour_prevu=J24 + datetime.timedelta(days=1))
        cls.fiche = fabriques.tache(u, projet=recrutement, titre='Rédiger la fiche de poste')
        cls.contrat = fabriques.tache(u, projet=admin, titre='Relire le contrat de maintenance')
        fabriques.tache(u, projet=site, titre='Lister les pages du site')
        plan = fabriques.plan(u, J24)
        for essentielle in (cls.devis, cls.stand):
            ligne(plan, tache=essentielle, essentielle=True, prevue_au_plan=False)

    def get(self, **params):
        params.setdefault('jour', J24.isoformat())
        reponse = client_de(self.u).get('/api/django/taches/journee/proposition/', params)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def test_les_3_proposees_du_matin(self):
        # objectif 5 − 0 faite − 2 gardées ouvertes = 3 : prochaine action de chaque projet.
        rendu = self.get()
        ids = [ligne['item']['id'] for ligne in rendu['proposition']]
        self.assertEqual(ids, [self.rails.pk, self.fournisseur.pk, self.fiche.pk])
        self.assertNotIn(self.contrat.pk, ids)
        self.assertEqual([ligne['item']['raison']['code'] for ligne in rendu['proposition']],
                         ['prochaine_action'] * 3)
        self.assertEqual(rendu['proposition'][0]['item']['raison']['texte'],
                         'prochaine action de Chantier Benali 9 kWc')
        self.assertTrue(all(ligne['cochee'] and not ligne['deja_prevue'] for ligne in rendu['proposition']))

    def test_forme_de_l_echantillon(self):
        modele, rendu = exemple('journee_proposition'), self.get(tout='1')
        self.assertEqual(set(rendu), set(modele))
        self.assertEqual(set(rendu['capacite']), set(modele['capacite']))
        self.assertEqual(set(rendu['charge']), set(modele['charge']))
        self.assertEqual(set(rendu['proposition'][0]), set(modele['proposition'][0]))
        self.assertEqual(set(rendu['proposition'][0]['item']), CLES_ITEM)
        self.assertEqual(set(rendu['suite_par_projet'][0]), set(modele['suite_par_projet'][0]))

    def test_exclure_inclure(self):
        ids = [ligne['item']['id'] for ligne in self.get(exclure=str(self.rails.pk))['proposition']]
        self.assertNotIn(self.rails.pk, ids)
        ids = [ligne['item']['id'] for ligne in self.get(inclure=str(self.contrat.pk))['proposition']]
        self.assertEqual(ids[0], self.contrat.pk)

    def test_ids_etrangers_ignores(self):
        autre = fabriques.compte(self.societe, nom='u2')
        etrangere = fabriques.tache(autre, projet=fabriques.projet(autre))
        sans = self.get()
        avec = self.get(exclure=f'{etrangere.pk},x', inclure=str(etrangere.pk))
        self.assertEqual(avec['proposition'], sans['proposition'])


class PlanifierJourneeTests(_Base):
    """POST journee/planifier/ (« Garder ces N », mode express) — invariants 9, 18."""

    URL = '/api/django/taches/journee/planifier/'

    def poster(self, corps, statut=200):
        reponse = client_de(self.u).post(self.URL, corps, format='json')
        self.assertEqual(reponse.status_code, statut, reponse.content[:300])
        return reponse.json()

    def corps(self, *taches, essentielles=()):
        return {'jour': J.isoformat(), 'mode': 'express',
                'lignes': [{'type': 'tache', 'id': t.pk} for t in taches], 'essentielles': [t.pk for t in essentielles]}

    def test_garder_ces_n(self):
        from apps.taches.models.journee import PlanJour
        du_jour = self.tache(jour_prevu=J)
        a, b = self.tache(), self.tache()
        rendu = self.poster(self.corps(a, b, essentielles=[du_jour]))
        self.assertEqual(set(rendu), set(exemple('journee_ecrite')))
        self.assertIsNotNone(rendu['geste_id'])
        for t in (a, b):
            t.refresh_from_db()
            self.assertEqual((t.jour_prevu, t.reports), (J, 0))
        plan = PlanJour.objects.get(proprietaire=self.u, jour=J)
        self.assertIsNotNone(plan.planifie_le)
        self.assertEqual(plan.objectif_du_jour, 5)
        lignes = {lig.tache_id: lig for lig in plan.ligneplanjour_set.all()}
        self.assertEqual(set(lignes), {du_jour.pk, a.pk, b.pk})
        self.assertTrue(all(lig.prevue_au_plan for lig in lignes.values()))
        self.assertTrue(lignes[du_jour.pk].essentielle)

    def test_revalider_n_ajoute_que_des_lignes(self):
        from apps.taches.models.journee import PlanJour
        a, b = self.tache(), self.tache()
        self.poster(self.corps(a))
        premier = PlanJour.objects.get(proprietaire=self.u, jour=J).planifie_le
        self.poster(self.corps(b))
        plan = PlanJour.objects.get(proprietaire=self.u, jour=J)
        self.assertEqual(plan.planifie_le, premier)
        self.assertEqual(plan.ligneplanjour_set.count(), 2)

    def test_4e_essentielle_400(self):
        taches = [self.tache(jour_prevu=J) for _ in range(4)]
        rendu = self.poster(self.corps(essentielles=taches), statut=400)
        self.assertEqual(rendu, {'essentielles': ['3 au plus.']})

    def test_mode_inconnu_400(self):
        corps = self.corps(self.tache())
        corps['mode'] = 'complet'
        self.assertEqual(self.poster(corps, statut=400), {'mode': ['Valeur inconnue.']})

    def test_id_etranger_404_rien_ecrit(self):
        from apps.taches.models.journee import PlanJour
        autre = fabriques.compte(self.societe, nom='u2')
        etrangere = fabriques.tache(autre, projet=fabriques.projet(autre))
        self.poster(self.corps(self.tache(), etrangere), statut=404)
        self.assertFalse(PlanJour.objects.filter(proprietaire=self.u).exists())

    def test_annuler_defait_le_geste(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services.gestes import annuler_geste
        a = self.tache()
        geste_id = self.poster(self.corps(a))['geste_id']
        annuler_geste(self.u, geste_id)
        a.refresh_from_db()
        self.assertIsNone(a.jour_prevu)
        self.assertFalse(PlanJour.objects.filter(proprietaire=self.u, jour=J).exists())


class EssentielTests(_Base):
    """POST journee/essentiel/ (★) : ligne essentielle du plan du jour, 3 au plus."""

    URL = '/api/django/taches/journee/essentiel/'

    def setUp(self):
        self.jour = timezone.localdate()

    def etoile(self, tache, essentielle=True, statut=200):
        reponse = client_de(self.u).post(self.URL, {'tache_id': tache.pk, 'essentielle': essentielle}, format='json')
        self.assertEqual(reponse.status_code, statut, reponse.content[:300])
        return reponse.json()

    def ligne_de(self, tache):
        from apps.taches.models.journee import LignePlanJour as Ligne
        return Ligne.objects.filter(plan__proprietaire=self.u, plan__jour=self.jour, tache=tache).first()

    def test_etoile_sur_plan_non_valide(self):
        t = self.tache(jour_prevu=self.jour)
        rendu = self.etoile(t)
        self.assertEqual(set(rendu), set(exemple('tache_ecrite')))
        self.assertIsNotNone(rendu['geste_id'])
        lig = self.ligne_de(t)
        self.assertTrue(lig.essentielle)
        self.assertTrue(lig.prevue_au_plan)

    def test_etoile_sur_plan_valide_n_est_pas_au_plan(self):
        fabriques.plan(self.u, self.jour, planifie_le=timezone.now())
        t = self.tache(jour_prevu=self.jour)
        self.etoile(t)
        self.assertFalse(self.ligne_de(t).prevue_au_plan)

    def test_retirer_l_etoile(self):
        t = self.tache(jour_prevu=self.jour)
        self.etoile(t)
        self.etoile(t, essentielle=False)
        self.assertFalse(self.ligne_de(t).essentielle)

    def test_4e_etoile_400(self):
        for _ in range(3):
            self.etoile(self.tache(jour_prevu=self.jour))
        rendu = self.etoile(self.tache(jour_prevu=self.jour), statut=400)
        self.assertEqual(rendu, {'essentielle': ['3 au plus.']})

    def test_tache_d_un_autre_404(self):
        autre = fabriques.compte(self.societe, nom='u2')
        self.etoile(fabriques.tache(autre, projet=fabriques.projet(autre)), statut=404)


# --- TCH58 : Alléger, bilan du soir, passage à minuit ---------------------------------------------

class AllegerTests(_Base):
    """POST journee/alleger/ (regles.md « Alléger ma journée ») : sans report, Proposé replié."""

    def scenario(self):
        self.garde = self.tache(jour_prevu=J)
        self.renvoyee = self.tache(jour_prevu=J, reports=2)
        self.essentielle = self.tache(jour_prevu=J)
        self.a_echeance = self.tache(jour_prevu=J, echeance=J)
        self.tache()  # de quoi remplir Proposé s'il n'était pas replié
        self.plan = fabriques.plan(self.u, J, planifie_le=a(J, 8))
        for t in (self.garde, self.renvoyee, self.a_echeance):
            ligne(self.plan, tache=t)
        ligne(self.plan, tache=self.essentielle, essentielle=True)

    def alleger(self):
        from apps.taches.services import journee as services
        return services.alleger(self.u, J, maintenant_a(15, 30), garder=[self.garde.pk])

    def test_le_reste_retourne_aux_projets_sans_report(self):
        self.scenario()
        rendu = self.alleger()
        self.assertEqual(set(rendu), set(exemple('journee_ecrite')))
        self.assertEqual(rendu['renvoyees'], sorted([self.renvoyee.pk, self.essentielle.pk]))
        for t in (self.renvoyee, self.essentielle):
            t.refresh_from_db()
            self.assertIsNone(t.jour_prevu)
        self.renvoyee.refresh_from_db()
        self.assertEqual(self.renvoyee.reports, 2)
        self.a_echeance.refresh_from_db()
        self.assertEqual(self.a_echeance.jour_prevu, J)
        restantes = set(self.plan.ligneplanjour_set.values_list('tache_id', flat=True))
        self.assertEqual(restantes, {self.garde.pk, self.a_echeance.pk})
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.allege_le)
        self.assertTrue(rendu['aujourdhui']['propose']['replie'])
        self.assertEqual(rendu['aujourdhui']['propose']['pour_objectif'], [])

    def test_annuler_remet_tout(self):
        from apps.taches.services.gestes import annuler_geste
        self.scenario()
        annuler_geste(self.u, self.alleger()['geste_id'])
        self.renvoyee.refresh_from_db()
        self.assertEqual(self.renvoyee.jour_prevu, J)
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.allege_le)
        self.assertTrue(self.plan.ligneplanjour_set.filter(tache=self.essentielle, essentielle=True).exists())

    def test_tache_d_un_autre_404(self):
        autre = fabriques.compte(self.societe, nom='u2')
        etrangere = fabriques.tache(autre, projet=fabriques.projet(autre), jour_prevu=timezone.localdate())
        reponse = client_de(self.u).post('/api/django/taches/journee/alleger/',
                                         {'jour': timezone.localdate().isoformat(), 'garder': [etrangere.pk]},
                                         format='json')
        self.assertEqual(reponse.status_code, 404)


class BilanTests(_Base):
    """GET journee/cloture/ et POST journee/cloturer/ (regles.md « Bilan du soir »)."""

    def scenario(self):
        self.faite = self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 10))
        self.reste = self.tache(jour_prevu=J)
        self.reste2 = self.tache(jour_prevu=J, moment='soir')
        self.a_trancher = self.tache(jour_prevu=J, reports=3)
        self.activite = fabriques.activite(self.u, due_date=J)
        self.plan = fabriques.plan(self.u, J, planifie_le=a(J, 8))
        ligne(self.plan, tache=self.faite)
        ligne(self.plan, tache=self.reste, essentielle=True)

    def cloture(self, jour=J, heure=18, minute=20, jour_heure=J):
        from apps.taches.services import journee as services
        return services.cloture(self.u, jour, timezone.localtime(a(jour_heure, heure, minute)))

    def cloturer(self, **corps):
        from apps.taches.services import journee as services
        return services.cloturer(self.u, J, maintenant_a(18, 20), **corps)

    def test_contenu_du_bilan(self):
        self.scenario()
        rendu, modele = self.cloture(), exemple('journee_cloture')
        self.assertEqual(set(rendu), set(modele))
        self.assertEqual(set(rendu['bilan']), set(modele['bilan']))
        self.assertEqual([i['id'] for i in rendu['faites']], [self.faite.pk])
        self.assertEqual({i['id'] for i in rendu['restes']}, {self.reste.pk, self.reste2.pk})
        self.assertEqual([i['id'] for i in rendu['a_trancher']], [self.a_trancher.pk])
        self.assertEqual([i['id'] for i in rendu['activites_a_clore']], [self.activite.pk])
        self.assertEqual(rendu['bilan']['texte'], '1 sur 5 · essentiel 0 sur 1')
        self.assertEqual(rendu['bilan']['texte_gardees'], '1 des 2 gardées')
        self.assertFalse(rendu['bilan']['objectif_atteint'])
        from apps.taches.services.journee import possible_jusqua
        self.assertEqual(rendu['possible_jusqua'], possible_jusqua(J).isoformat())

    def test_bilan_d_hier_jusqu_a_midi(self):
        from apps.taches.services.journee import Refus
        self.cloture(jour=jours(-1), heure=11, jour_heure=J)
        with self.assertRaises(Refus) as refus:
            self.cloture(jour=jours(-1), heure=12, minute=30, jour_heure=J)
        self.assertEqual(refus.exception.erreurs, {'jour': ["Le bilan d'hier n'est plus modifiable après midi."]})

    def test_tout_reporter(self):
        from apps.taches.selectors.base import prochain_jour_travaille
        self.scenario()
        rendu = self.cloturer(le_reste=True, reflexion='Bonne journée')
        self.assertEqual(set(rendu), set(exemple('journee_cloturee')))
        self.assertEqual(set(rendu['plan']), set(exemple('journee_cloturee')['plan']))
        prochain = prochain_jour_travaille(self.u, J)
        for t in (self.reste, self.reste2):
            t.refresh_from_db()
            self.assertEqual((t.jour_prevu, t.reports), (prochain, 1))
        self.a_trancher.refresh_from_db()
        self.assertEqual((self.a_trancher.jour_prevu, self.a_trancher.reports), (J, 3))
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.cloture_le)
        self.assertEqual(self.plan.reflexion, 'Bonne journée')
        self.assertTrue(self.plan.ligneplanjour_set.get(tache=self.reste).reportee)

    def test_choix_par_reste(self):
        self.scenario()
        lundi = datetime.date(2026, 11, 23)
        self.cloturer(choix=[{'id': self.reste.pk, 'choix': 'jour', 'jour': lundi},
                             {'id': self.reste2.pk, 'choix': 'un_jour'},
                             {'id': self.a_trancher.pk, 'choix': 'abandonner'}])
        for t in (self.reste, self.reste2, self.a_trancher):
            t.refresh_from_db()
        self.assertEqual(self.reste.jour_prevu, lundi)
        self.assertTrue(self.reste2.quelque_jour)
        self.assertEqual(self.a_trancher.statut, StatutTache.ANNULE)
        self.assertIsNotNone(self.a_trancher.annule_le)

    def test_choix_inconnu_400(self):
        from apps.taches.services.journee import Refus
        self.scenario()
        with self.assertRaises(Refus) as refus:
            self.cloturer(choix=[{'id': self.reste.pk, 'choix': 'demain'}])
        self.assertEqual(refus.exception.erreurs, {'choix': ['Valeur inconnue.']})

    def test_route_du_jour(self):
        aujourdhui = timezone.localdate()
        self.tache(jour_prevu=aujourdhui)
        client = client_de(self.u)
        lu = client.get('/api/django/taches/journee/cloture/', {'jour': aujourdhui.isoformat()})
        self.assertEqual(lu.status_code, 200, lu.content[:300])
        ecrit = client.post('/api/django/taches/journee/cloturer/',
                            {'jour': aujourdhui.isoformat(), 'le_reste': True}, format='json')
        self.assertEqual(ecrit.status_code, 200, ecrit.content[:300])
        self.assertIsNotNone(ecrit.json()['geste_id'])
        trop_vieux = client.get('/api/django/taches/journee/cloture/',
                                {'jour': (aujourdhui - datetime.timedelta(days=3)).isoformat()})
        self.assertEqual(trop_vieux.status_code, 400)


class PassageAMinuitTests(_Base):
    """`clore_jour_precedent` : la nuit clôt le PlanJour d'hier, tâches intactes, rejouable."""

    def test_clot_la_veille_sans_toucher_aux_taches(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services.journee import clore_jour_precedent
        fabriques.reglages(self.u)
        sans_reglages = fabriques.compte(self.societe, nom='u2')
        self.tache(jour_prevu=jours(-1), statut=StatutTache.FAIT, fait_le=a(jours(-1), 10), estimation_minutes=30)
        ouverte = self.tache(jour_prevu=jours(-1))
        clore_jour_precedent(self.societe.pk, J)
        plan = PlanJour.objects.get(proprietaire=self.u, jour=jours(-1))
        self.assertEqual((plan.compte_rythme, plan.minutes_faites), (1, 30))
        self.assertIn(plan.statut_jour, ('evalue', 'non_ouvre'))
        ouverte.refresh_from_db()
        self.assertEqual((ouverte.jour_prevu, ouverte.reports), (jours(-1), 0))
        clore_jour_precedent(self.societe.pk, J)
        self.assertEqual(PlanJour.objects.filter(proprietaire=self.u).count(), 1)
        self.assertFalse(PlanJour.objects.filter(proprietaire=sans_reglages).exists())
