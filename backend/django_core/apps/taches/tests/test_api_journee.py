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
from apps.taches.tests.test_api_saisie import champs

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
        # en pause depuis HIER : rien de ce projet n'est plus dans la journée, même prévu aujourd'hui (C-5)
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE, statut_depuis=a(jours(-1), 18))
        dans_la_pause = self.tache(projet=en_pause, jour_prevu=J)
        ids = set(sel.taches_de_la_journee(self.u, J).values_list('pk', flat=True))
        self.assertIn(parent.pk, ids)
        for absente in (enfant, bloquee, reserve, dans_la_pause):
            self.assertNotIn(absente.pk, ids, absente.titre)

    def test_pause_du_jour_garde_ce_qui_est_pose_ce_jour(self):
        """R2-031 (choix C-5) — mis en pause aujourd'hui à 15:00 : la tâche posée aujourd'hui à 16:00 reste
        dans la journée (Prévu) ; ses tâches sans jour, pour plus tard ou prévues un autre jour n'y sont pas ;
        le lendemain, plus rien du projet."""
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE, statut_depuis=a(J, 15))
        a_16h = self.tache(projet=en_pause, jour_prevu=J, heure_debut=datetime.time(16, 0))
        sans_jour = self.tache(projet=en_pause)
        demain = self.tache(projet=en_pause, jour_prevu=jours(1))
        reservee = self.tache(projet=en_pause, quelque_jour=True)
        ids = set(sel.taches_de_la_journee(self.u, J).values_list('pk', flat=True))
        self.assertIn(a_16h.pk, ids)
        for absente in (sans_jour, demain, reservee):
            self.assertNotIn(absente.pk, ids, absente.titre)
        self.assertEqual(self.section_de(self.journee(), a_16h), S.JOURNEE)
        self.assertNotIn(demain.pk, set(sel.taches_de_la_journee(self.u, jours(1)).values_list('pk', flat=True)))

    def test_pause_du_jour_absente_de_propose(self):
        """R2-031 — la pause retire toujours de Proposé : une tâche sans jour du projet en pause n'est jamais
        proposée, celle posée aujourd'hui est dans Prévu (gardée), pas dans Proposé."""
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE, statut_depuis=a(J, 15))
        posee = self.tache(projet=en_pause, jour_prevu=J)
        sans_jour = self.tache(projet=en_pause)
        journee = self.journee()
        self.assertEqual(self.section_de(journee, posee), S.JOURNEE)
        self.assertIsNone(self.section_de(journee, sans_jour))
        self.assertNotIn(('tache', sans_jour.pk), journee.items)

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

    def test_essentielle_faite_reste_dans_essentiel_et_dans_faites(self):
        """D-V1 (passe visuelle) — regles.md §4.1 ligne 3 (« ouvertes ou faites aujourd'hui ») et §4.2-1 (« et reste
        dans essentiel si sa ligne y est ») : barrée à sa place dans Essentiel ET repliée dans Faites ; une faite sans
        ★ n'est que dans Faites ; la pastille et la progression la comptent une seule fois."""
        faite = self.tache(jour_prevu=J, heure_debut=datetime.time(9, 0), statut=StatutTache.FAIT, fait_le=a(J, 10))
        ouverte = self.tache(jour_prevu=J)
        simple = self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 11))
        plan = fabriques.plan(self.u, J)
        ligne(plan, tache=faite, essentielle=True)
        ligne(plan, tache=ouverte, essentielle=True)
        ligne(plan, tache=simple)
        journee = self.journee()
        self.assertEqual([o.pk for o in journee.objets_de(S.ESSENTIEL)], [faite.pk, ouverte.pk])
        self.assertEqual(sorted(o.pk for o in journee.objets_de(S.FAITES)), sorted([faite.pk, simple.pk]))
        self.assertEqual(sel.compter_journee(self.u, J, journee), 1)
        reponse = client_de(self.u).get('/api/django/taches/aujourdhui/', {'jour': J.isoformat()}).json()
        self.assertEqual([(i['id'], i['statut']) for i in reponse['essentiel']],
                         [(faite.pk, 'fait'), (ouverte.pk, 'a_faire')])
        self.assertEqual(sorted(i['id'] for i in reponse['faites']), sorted([faite.pk, simple.pk]))
        self.assertEqual((reponse['progression']['faites'], reponse['progression']['essentiel_faites'],
                          reponse['progression']['essentiel_prevues']), (2, 1, 2))

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
        # R4-01 : la charge = ce qui RESTE (la faite de 30 min ne compte plus) : 45 min, 1 sans durée, 2 tâches
        self.assertEqual(p['charge'], {'taches': 2, 'restantes_minutes': 45, 'sans_duree': 1, 'capacite_minutes': 240,
                                       'rendez_vous_minutes': 60, 'disponible_minutes': 180, 'deborde_minutes': 0})
        self.assertEqual(sel.minutes_prevues_du_jour(self.journee()), 75)  # la statistique de la nuit, jamais montrée
        self.assertEqual((p['capacite_minutes'], p['rendez_vous_minutes'], p['disponible_minutes']),
                         (240, 60, 180))

    def test_faite_d_un_projet_en_pause_compte(self):
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE)
        self.tache(projet=en_pause, statut=StatutTache.FAIT, fait_le=a(J, 11))
        self.assertEqual(self._progression()['faites'], 1)

    def test_forme_complete(self):
        cles = {'faites', 'detail', 'prevues', 'essentiel_faites', 'essentiel_prevues', 'plan_tenues',
                'plan_lignes', 'charge', 'capacite_minutes', 'capacite_source',
                'rendez_vous_minutes', 'disponible_minutes', 'activites_closes', 'activites', 'reprise'}
        self.assertEqual(set(self._progression()), cles)


class ObjectifEtCapaciteTests(_Base):
    def test_objectif_par_defaut_sans_reglages(self):
        from apps.taches.services.journee import objectif_du_jour
        self.assertEqual(objectif_du_jour(None, J, {}),
                         {'nb': 5, 'source': 'defaut', 'mode': 'pousser', 'zone': None})

    def test_objectif_libre(self):
        from apps.taches.services.journee import objectif_du_jour
        reglages = fabriques.reglages(self.u, mode='libre')
        self.assertIsNone(objectif_du_jour(reglages, J, {'jours_courts': [J.weekday()]})['nb'])

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
        fabriques.reglages(self.u, palier=5, palier_source='accepte')
        self.tache(jour_prevu=J)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.assertEqual(self.carte(15, 30), {'type': 'alleger', 'proposition': None,
                                              'donnees': {'faites': 0, 'prevues': 1}})

    # --- R4-02 / R4-04 : la carte du moment selon l'heure (regles.md §4.10), horloge figée ----------------------------

    def journee_en_retard(self):
        """Objectif DIT 5, plan gardé à 8 h, 1 faite, 3 prévues ouvertes aujourd'hui (rien qui déborde : 0 min)."""
        fabriques.reglages(self.u, palier=5, palier_source='dit')
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        for _ in range(3):
            self.tache(jour_prevu=J)
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))

    def test_le_matin_pas_d_alleger(self):
        self.journee_en_retard()
        self.assertIsNone(self.carte(9, 12))

    def test_a_15_h_alleger(self):
        self.journee_en_retard()
        self.assertEqual(self.carte(15, 0)['type'], 'alleger')

    def test_le_soir_en_retard_le_bilan_gagne(self):
        """R4-02 — 18:30, 1 faite sur 5 : « Faire le bilan », jamais « Alléger » (qui n'avait pas de fin)."""
        self.journee_en_retard()
        self.assertEqual(self.carte(18, 30)['type'], 'faire_bilan')

    def test_le_soir_le_bilan_passe_avant_garder(self):
        """R4-02 — rien gardé, une faite, une candidate à proposer : à 18:30 le bilan, pas « Garder ces N »."""
        fabriques.reglages(self.u, palier=5, palier_source='dit')
        self.tache()
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))
        self.assertEqual(self.carte(10, 0)['type'], 'garder')
        self.assertEqual(self.carte(18, 30)['type'], 'faire_bilan')

    def test_premier_jour_jamais_alleger(self):
        """R4-04 — compte neuf (objectif par défaut, jamais dit) : une tâche à 17 h ne fait pas lire « 0 sur 5 ·
        Alléger »."""
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.tache(jour_prevu=J, estimation_minutes=600)  # même une journée qui déborde
        self.assertIsNone(self.carte(17, 0))

    def test_apres_le_bilan_plus_d_alleger(self):
        """R4-04 — « Bilan enregistré » (`cloture_le`) : ni Alléger, ni Faire le bilan, rechargé ou non."""
        self.journee_en_retard()
        from apps.taches.models.journee import PlanJour
        PlanJour.objects.filter(proprietaire=self.u, jour=J).update(cloture_le=a(J, 16, 30))
        self.assertIsNone(self.carte(17, 0))
        self.assertIsNone(self.carte(18, 30))

    def test_rien_a_alleger_pas_de_carte(self):
        """R4-04 — la seule tâche ouverte est due aujourd'hui (Alléger la garderait) : rien à alléger, pas de carte."""
        fabriques.reglages(self.u, palier=5, palier_source='dit')
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.tache(jour_prevu=J, echeance=J)
        self.assertIsNone(self.carte(15, 30))

    def test_une_journee_qui_deborde_s_allege_meme_a_moitie_faite(self):
        """R4-04 — 3 faites sur 5 (plus de la moitié) mais 6 h restent pour 4 h : la charge déborde, « Alléger »."""
        fabriques.reglages(self.u, palier=5, palier_source='dit')
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        for _ in range(3):
            self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))
        self.tache(jour_prevu=J, estimation_minutes=360)
        self.assertEqual(self.carte(15, 30)['type'], 'alleger')

    def test_revelation_en_dernier_rendue_par_ses_textes(self):
        from apps.taches.models.rythme import IncitationCoach
        fabriques.reglages(self.u)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=J, type='revelation',
                                       cle='ranger_copilote', canal='ecran', donnees={'n': 7}, expire_le=jours(7))
        a_trier = [fabriques.tache(self.u) for _ in range(5)]  # le nombre est lu à l'affichage (#10)
        carte = self.carte()
        self.assertEqual(carte['type'], 'revelation')
        self.assertEqual(carte['proposition']['texte'],
                         '5 tâches à trier : le Copilote peut les ranger dans tes projets.')
        self.assertEqual(carte['proposition']['boutons'], [{'reponse': 'ok', 'libelle': 'OK'}])
        a_trier[0].statut = StatutTache.FAIT  # 4 à trier : la révélation n'a plus rien à dire
        a_trier[0].save(update_fields=['statut'])
        self.assertIsNone((self.carte() or {}).get('proposition'))
        # Une seule carte du moment : une proposition du rythme passe devant la révélation.
        IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=J, type='proposition_palier',
                                       cle='monter', canal='ecran', donnees={'N': 5, 'N1': 6, 'tenus': 7},
                                       expire_le=jours(7))
        self.assertEqual(self.carte()['type'], 'rythme')

    def incitation(self, type_, cle='', jour=J, **champs):
        from apps.taches.models.rythme import IncitationCoach
        champs.setdefault('donnees', {})
        return IncitationCoach.objects.create(company=self.societe, proprietaire=self.u, jour=jour, type=type_,
                                              cle=cle, canal='ecran', expire_le=jours(7), **champs)

    def test_un_constat_sans_question_n_est_jamais_la_carte_du_matin(self):
        """R3-005 (choix C-17) — C5 (« 57 % de tes tâches… », une information sans geste) ouvert : aucune carte le
        matin ; il reste au bilan du soir (et dans Mon rythme). C7, qui pose une question, peut l'être."""
        fabriques.reglages(self.u)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.incitation('constat', 'C5', donnees={'p': 57, 'n': 51, 'h1': 10, 'h2': 12})
        self.assertIsNone(self.carte())
        self.incitation('constat', 'C7', donnees={'n': 2})
        carte = self.carte()
        self.assertEqual((carte['type'], carte['proposition']['cle']), ('rythme', 'C7'))

    def test_une_carte_de_conseil_par_jour(self):
        """R3-005 — C7 répondu ce matin : ni la pause ni la révélation ouvertes ne prennent sa place, rechargé autant
        de fois qu'on veut ; le lendemain, la révélation vient ; les cartes liées à l'heure restent (bilan du soir)."""
        fabriques.reglages(self.u)
        fabriques.plan(self.u, J, planifie_le=a(J, 8))
        self.incitation('constat', 'C7', donnees={'n': 2}, reponse='pas_maintenant', repondu_le=a(J, 9, 10))
        self.incitation('pause', 'plan_matin', donnees={'type_pause': 'plan_matin', 'ignorees': 3})
        self.incitation('revelation', 'mon_iphone')
        for _ in range(3):
            self.assertIsNone(self.carte(9, 30))
        # R4-10 (T3-F n° 9) — le serveur le DIT : un autre appareil n'y ajoute pas son astuce
        from apps.taches.services import journee as services_
        self.assertIs(services_.aujourdhui(self.u, J, maintenant_a(9, 30))['conseil_donne'], True)
        self.assertIs(services_.aujourdhui(self.u, jours(1), timezone.localtime(a(jours(1), 9, 12)))['conseil_donne'],
                      False)
        self.assertEqual(self.carte(18, 30)['type'], 'faire_bilan')
        from apps.taches.services import journee as services
        demain = services.aujourdhui(self.u, jours(1), timezone.localtime(a(jours(1), 9, 12)))['carte_du_moment']
        self.assertEqual(demain['type'], 'pause')


class BadgeEtVuTests(_Base):
    def test_badge(self):
        self.tache(jour_prevu=timezone.localdate())
        rendu = client_de(self.u).get('/api/django/taches/badge/').json()
        self.assertEqual(set(rendu), set(exemple('badge')))
        self.assertEqual(rendu, {'n': 1, 'jour': timezone.localdate().isoformat(), 'a_trier': 0})

    def test_badge_porte_le_compte_a_trier_de_aujourdhui(self):
        self.tache(jour_prevu=timezone.localdate())
        self.tache(projet=None)
        self.tache(projet=None)
        client = client_de(self.u)
        rendu = client.get('/api/django/taches/badge/').json()
        journee = client.get('/api/django/taches/aujourdhui/').json()
        self.assertEqual(rendu['a_trier'], journee['a_trier']['boite_reception'])
        self.assertEqual(rendu['a_trier'], 2)

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
        self.assertEqual(champs(rendu), {'essentielles': ['3 au plus.']})

    def test_mode_inconnu_400(self):
        corps = self.corps(self.tache())
        corps['mode'] = 'complet'
        self.assertEqual(champs(self.poster(corps, statut=400)), {'mode': ['Valeur inconnue.']})

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

    def test_annuler_le_plan_garde_ce_que_les_gestes_suivants_ont_pose(self):
        """Revue F2 #3 : plan gardé (G1) → ★ sur une 4e tâche (G2) → bilan (G3) → annuler G1 : le plan,
        la ligne de G2 et le bilan restent ; la réponse dit le conflit sur le plan."""
        from apps.taches.models.journee import PlanJour
        from apps.taches.services import journee as services
        from apps.taches.services.gestes import annuler_geste
        gardee, quatrieme = self.tache(), self.tache(jour_prevu=J)
        g1 = services.planifier_express(self.u, J, maintenant_a(9), lignes=[{'type': 'tache', 'id': gardee.pk}])
        services.marquer_essentielle(self.u, quatrieme.pk, True, maintenant_a(11))
        services.cloturer(self.u, J, maintenant_a(18), reflexion='Bonne journée')
        plan = PlanJour.objects.get(proprietaire=self.u, jour=J)
        lignes_avant = set(plan.ligneplanjour_set.values_list('tache_id', 'essentielle'))
        rendu = annuler_geste(self.u, g1['geste_id'])
        self.assertIn({'objet': 'plan_jour', 'id': plan.pk, 'raison': 'modifiee_depuis'}, rendu['conflits'])
        plan.refresh_from_db()
        self.assertIsNotNone(plan.planifie_le)
        self.assertIsNotNone(plan.cloture_le)
        self.assertEqual(plan.reflexion, 'Bonne journée')
        self.assertEqual(set(plan.ligneplanjour_set.values_list('tache_id', 'essentielle')), lignes_avant)
        self.assertIn((quatrieme.pk, True), lignes_avant)

    def test_annuler_le_plan_garde_les_compteurs_de_la_nuit(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services.gestes import annuler_geste
        geste_id = self.poster(self.corps(self.tache()))['geste_id']
        PlanJour.objects.filter(proprietaire=self.u, jour=J).update(statut_jour='evalue', compte_rythme=4)
        rendu = annuler_geste(self.u, geste_id)
        plan = PlanJour.objects.get(proprietaire=self.u, jour=J)
        self.assertEqual((plan.statut_jour, plan.compte_rythme), ('evalue', 4))
        self.assertEqual([c['objet'] for c in rendu['conflits']], ['plan_jour'])
        self.assertEqual(plan.ligneplanjour_set.count(), 1)


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

    def test_4e_etoile_409(self):
        """Trois ★ DÉJÀ posées : refus d'état, 409 au même corps (api-fuzz r2)."""
        for _ in range(3):
            self.etoile(self.tache(jour_prevu=self.jour))
        rendu = self.etoile(self.tache(jour_prevu=self.jour), statut=409)
        self.assertEqual(rendu['essentielle'], ['3 au plus.'])

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
        self.assertEqual(rendu['bilan']['texte_gardees'], '')  # R3-001 : plus de « x des y gardées »
        self.assertFalse(rendu['bilan']['objectif_atteint'])
        from apps.taches.services.journee import _possible_jusqua
        self.assertEqual(rendu['possible_jusqua'], _possible_jusqua(J).isoformat())

    def test_constat_c5_d_information_n_offre_que_ok(self):
        """Passe visuelle n° 25 — textes.md §4.2 : un constat d'information (C5) n'a qu'un bouton [OK] ; le bilan
        servait [Oui] [Pas maintenant], que `repondre/` refuse (400) pour C5."""
        from apps.taches.choix import CanalIncitation, TypeIncitationEcran
        from apps.taches.models.rythme import IncitationCoach
        self.scenario()
        IncitationCoach.objects.create(
            company=self.u.company, proprietaire=self.u, type=TypeIncitationEcran.CONSTAT, cle='C5',
            canal=CanalIncitation.ECRAN, donnees={'p': 57, 'n': 51, 'h1': 10, 'h2': 12},
            jour=J, expire_le=J + datetime.timedelta(days=7))
        constat = self.cloture()['constat']
        self.assertEqual(constat['texte'], '57 % de tes 51 tâches finies entre 10 h et 12 h.')
        self.assertEqual(constat['boutons'], [{'reponse': 'ok', 'libelle': 'OK'}])

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
        self.assertEqual(trop_vieux.status_code, 409)  # bilan fermé : refus d'ÉTAT, même corps (api-fuzz r2)


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


# --- TCH161 : routes déterministes du Copilote (regles.md §12, A18-M3) -----------------------------

URL_PRIORITES = '/api/django/taches/journee/priorites/'
URL_POINT = '/api/django/taches/journee/point/'


#: Plafonds de requêtes mesurés horloge figée sur J (le Maroc est à UTC+0) : (moment -> plafond).
MATIN_J, APRES_MIDI_J = '2026-11-17 09:00:00', '2026-11-17 15:00:00'
#: `priorites/` : 16 + 1 (R3-006) — `selectors.journee._minutes_historiques`, l'historique de la capacité (les
#: `PlanJour.minutes_faites` des 28 jours) qui donne `disponible_minutes`, donc `deborde_minutes` ; aucune autre
#: lecture ne le porte (le plan du jour seul est lu). Le même +1 que `test_plafonds.PLAFONDS_FIGES` (22 → 23).
PLAFONDS_PRIORITES = {MATIN_J: 17, APRES_MIDI_J: 17}
PLAFONDS_POINT = {MATIN_J: 20, APRES_MIDI_J: 18}


def requetes_de(client, url, params=None):
    """Nombre de requêtes d'un GET, une fois les caches du processus chauds (agendas, calendrier)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    client.get(url, params or {})
    with CaptureQueriesContext(connection) as capture:
        reponse = client.get(url, params or {})
    assert reponse.status_code == 200, reponse.content[:300]
    return len(capture)


def canari(compte, jour):
    """Un projet confidentiel et ses tâches portant « Canari » partout (regles.md §8) : une prévue au
    jour (Prévu), une essentielle, une sans jour (tour des projets), une à échéance proche."""
    secret = fabriques.projet(compte, nom='Canari-projet', objectif='Canari-objectif', domaine='Canari-dom',
                              confidentiel=True)
    etape = fabriques.section(secret, nom='Canari-étape')
    communs = {'projet': secret, 'section': etape, 'notes': 'Canari-notes', 'en_attente_de': 'Canari-attente'}
    prevue = fabriques.tache(compte, titre='Canari-titre', jour_prevu=jour, **communs)
    essentielle = fabriques.tache(compte, titre='Canari-titre-essentiel', jour_prevu=jour, **communs)
    fabriques.tache(compte, titre='Canari-titre-tour', **communs)
    fabriques.tache(compte, titre='Canari-titre-echeance', echeance=jour + datetime.timedelta(days=1), **communs)
    ligne(fabriques.plan(compte, jour), tache=essentielle, essentielle=True)
    return prevue


class PrioritesTests(_Base):
    """GET journee/priorites/ : toutes les ouvertes non gardées, classées, chacune avec sa raison."""

    def scenario(self):
        self.presse = self.tache(echeance=jours(1))  # ce qui presse : échéance proche
        self.premiere = self.tache()  # tour des projets : prochaine action
        self.suivante = self.tache()  # tour des projets : action suivante
        self.gardee = self.tache(jour_prevu=J)  # gardée aujourd'hui : absente
        self.revoir = self.tache(jour_prevu=jours(-4), reports=3)  # À revoir, en dernier
        autre = fabriques.compte(self.societe, nom='u2')
        self.etrangere = fabriques.tache(autre, projet=fabriques.projet(autre))

    def get(self, **params):
        params.setdefault('jour', J.isoformat())
        reponse = client_de(self.u).get(URL_PRIORITES, params)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def test_une_journee_qui_deborde_sert_les_gardees_a_alleger(self):
        """R3-006 — objectif 9, 1 faite, 10 gardées pour 8 h 45 sur une capacité de 4 h (défaut, aucun rendez-vous).
        Calcul à la main : minutes restantes = 9 × 50 + 75 = 525 ; débordement = 525 − 240 = 285 (4 h 45). La carte ne
        pousse pas à en ajouter : les lignes sont les 10 GARDÉES (jamais la candidate), `geste_propose` « alleger » ;
        `faites` 1 ≠ objectif 9 (garder_n 0 n'est pas « objectif atteint »). « Où j'en suis ? » dit le même temps."""
        from apps.taches.views import journee as vues
        fabriques.reglages(self.u, palier=9, palier_source='dit')
        gardees = [self.tache(jour_prevu=J, estimation_minutes=50) for _ in range(9)]
        gardees.append(self.tache(jour_prevu=J, estimation_minutes=75))
        candidate = self.tache()
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9), estimation_minutes=30)
        rendu = self.get()
        self.assertEqual((rendu['faites'], rendu['objectif']['nb'], rendu['charge']['restantes_minutes'],
                          rendu['charge']['deborde_minutes'], rendu['geste_propose']), (1, 9, 525, 285, 'alleger'))
        ids = [ligne_['item']['id'] for ligne_ in rendu['lignes']]
        self.assertEqual(sorted(ids), sorted(t.pk for t in gardees))
        self.assertNotIn(candidate.pk, ids)
        self.assertTrue(all(ligne_['item']['raison'] is None for ligne_ in rendu['lignes']))
        point = vues.point(self.u, maintenant_a(15))
        charge = point['progression']['charge']
        self.assertEqual((point['faites'], charge['restantes_minutes'], charge['deborde_minutes']), (1, 525, 285))
        self.assertEqual(point['progression']['disponible_minutes'], 240)

    def test_sans_debordement_rien_ne_change(self):
        self.scenario()
        rendu = self.get()
        self.assertEqual((rendu['charge']['deborde_minutes'], rendu['geste_propose']), (0, None))
        self.assertIn(self.premiere.pk, [ligne_['item']['id'] for ligne_ in rendu['lignes']])

    def test_forme_de_l_echantillon(self):
        self.scenario()
        modele, rendu = exemple('priorites'), self.get()
        self.assertEqual(list(rendu), list(modele))
        self.assertEqual(set(rendu['objectif']), set(modele['objectif']))
        for ligne_ in rendu['lignes']:
            self.assertEqual(set(ligne_), set(modele['lignes'][0]))
            self.assertEqual(set(ligne_['item']), CLES_ITEM)
        self.assertFalse(rendu['tronque'])

    def test_ordre_raisons_et_motif(self):
        self.scenario()
        rendu = self.get()
        ids = [ligne_['item']['id'] for ligne_ in rendu['lignes']]
        self.assertEqual(ids, [self.presse.pk, self.premiere.pk, self.suivante.pk, self.revoir.pk])
        self.assertEqual([ligne_['rang'] for ligne_ in rendu['lignes']], [1, 2, 3, 4])
        raisons = [ligne_['item']['raison'] for ligne_ in rendu['lignes']]
        self.assertEqual([r['code'] for r in raisons[:3]], ['echeance_proche', 'prochaine_action', 'action_suivante'])
        self.assertEqual(raisons[1]['texte'], f'prochaine action de {self.projet.nom}')
        self.assertTrue(all(r['texte'] for r in raisons[:3]))
        dernier = rendu['lignes'][-1]['item']
        self.assertIsNone(dernier['raison'])
        self.assertEqual(dernier['motif'], 'reportee_3_fois')
        self.assertEqual(dernier['explication'], 'reportée 3 fois')
        self.assertNotIn(self.gardee.pk, ids)
        self.assertNotIn(self.etrangere.pk, ids)

    def test_garder_n_et_plus_tard(self):
        from apps.taches.moteur import classement
        self.scenario()
        rendu = self.get()
        # N = 5 − 0 faite − 1 gardée ouverte = 4 ; Proposé n'a que 3 candidates (presse + tour).
        self.assertEqual(rendu['garder_n'], 3)
        attendu = classement.plus_tard(J, sel.travailles_autour(self.u, J))
        self.assertEqual(rendu['plus_tard'], attendu.isoformat())
        self.assertEqual(rendu['jour'], J.isoformat())
        self.assertEqual(rendu['objectif']['nb'], 5)

    def test_jour_illisible_400_au_champ(self):
        reponse = client_de(self.u).get(URL_PRIORITES, {'jour': '17/11/2026'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('jour', reponse.json())

    def test_plafond_de_requetes(self):
        """Horloge FIGÉE sur J (mardi) aux deux moments — le matin, la journée relit aussi le plan de la
        veille et ses restes — chacun à son plafond mesuré (cible api.md §10 : 20) ; ne grandit pas."""
        from testkit.time import frozen
        self.scenario()
        params = {'jour': J.isoformat()}
        peu = {}
        for moment, plafond in PLAFONDS_PRIORITES.items():
            with self.subTest(moment=moment), frozen(moment):
                peu[moment] = requetes_de(client_de(self.u), URL_PRIORITES, params)
                self.assertLessEqual(peu[moment], plafond)
        for _ in range(10):
            self.tache()
            self.tache(echeance=jours(1), estimation_minutes=30)
        for moment in PLAFONDS_PRIORITES:
            with self.subTest(moment=moment), frozen(moment):
                self.assertEqual(requetes_de(client_de(self.u), URL_PRIORITES, params), peu[moment])

    def test_canari_jamais_servi_a_l_assistant(self):
        canari(self.u, J)
        params = {'jour': J.isoformat()}
        assistant = client_de(self.u).get(URL_PRIORITES, params, HTTP_X_TAQINOR_ASSISTANT='1')
        self.assertEqual(assistant.status_code, 200, assistant.content[:300])
        self.assertNotIn('canari', assistant.content.decode('utf-8').lower())
        ecran = client_de(self.u).get(URL_PRIORITES, params).content.decode('utf-8')
        self.assertIn('Canari-titre-tour', ecran)  # le canari est vivant


class UneChargeTests(_Base):
    """R4-01 (M1, « un chiffre, une source » — la garde `UneSourceTests` étendue à la charge) : la charge du jour est
    LA MÊME dans toutes les lectures qui la disent : Aujourd'hui (`progression.charge`), toute écriture, l'Agenda du
    jour, la Semaine (donc Planifier ma semaine), « Aide-moi à prioriser » et « Où j'en suis ? ». Avant : Aujourd'hui
    comptait la faite (« 6 h prévues »), le Copilote non (« déborde de 1 h 30 ») et l'Agenda Ce soir en plus
    (« 6 h 15 ») — quatre chiffres à la même minute (T3-F n° 1)."""

    def jeu(self):
        """Mardi 17/11, 15:00, capacité par défaut 240 min, aucun rendez-vous. Calcul à la main :
        restent 120 + 90 + 60 (prévues) + 30 (prévue demain, échéance aujourd'hui) = 300 min ; 1 sans durée ; 5 tâches ;
        la faite (30 min) et Ce soir (20 min) ne comptent pas ; disponible 240 ; déborde 300 − 240 = 60 min.
        Demain : la même tâche à échéance aujourd'hui, prévue demain : 30 min."""
        for minutes in (120, 90, 60):
            self.tache(jour_prevu=J, estimation_minutes=minutes)
        self.tache(jour_prevu=J)
        self.tache(jour_prevu=jours(1), echeance=J, estimation_minutes=30)
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9), estimation_minutes=30)
        self.tache(jour_prevu=J, moment='soir', estimation_minutes=20)

    def test_les_cinq_lectures_disent_la_meme_charge(self):
        from apps.taches.services import journee as services
        from apps.taches.views import agenda as vues_agenda
        from apps.taches.views import journee as vues
        self.jeu()
        attendu = {'taches': 5, 'restantes_minutes': 300, 'sans_duree': 1, 'capacite_minutes': 240,
                   'rendez_vous_minutes': 0, 'disponible_minutes': 240, 'deborde_minutes': 60}
        heure = maintenant_a(15)
        aujourdhui = services.aujourdhui(self.u, J, heure)
        jour = vues_agenda.lire_agenda(self.u, J, J, 'jour', heure)['jours'][0]
        lue = vues_agenda.lire_agenda(self.u, jours(-1), jours(5), 'semaine', heure)
        semaine = {j['jour']: j for j in lue['jours']}
        lectures = {
            'aujourdhui': aujourdhui['progression']['charge'],
            'ecriture': sel.progression_courante(self.u, J)['charge'],  # toute TACHE_ECRITE recale la page avec elle
            'agenda_jour': jour['charge'],
            'semaine': semaine[J.isoformat()]['charge'],
            'priorites': vues.priorites(self.u, J)['charge'],
            'point': vues.point(self.u, heure)['progression']['charge'],
        }
        for lecture, charge in lectures.items():
            with self.subTest(lecture=lecture):
                self.assertEqual(charge, attendu)
        self.assertEqual(semaine[jours(1).isoformat()]['charge']['restantes_minutes'], 30)
        self.assertIsNone(semaine[jours(-1).isoformat()]['charge'])  # un jour passé dit ses faites, pas une charge
        # la charge de « Garder ces N » part de la même base (aucune proposée ici)
        self.assertEqual(aujourdhui['propose']['charge']['minutes_estimees'], 300)


class PointTests(_Base):
    """GET journee/point/ (« Où j'en suis ? ») à 15 h : essentielles restantes, prochaine ligne, restes."""

    def scenario(self):
        self.essentielle = self.tache(jour_prevu=J, heure_debut=datetime.time(10, 0))
        self.passee = self.tache(jour_prevu=J, heure_debut=datetime.time(11, 0))
        self.sans_heure = self.tache(jour_prevu=J)
        self.a_venir = self.tache(jour_prevu=J, heure_debut=datetime.time(16, 0))
        self.soir = self.tache(jour_prevu=J, moment='soir')
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))
        ligne(fabriques.plan(self.u, J, planifie_le=a(J, 8)), tache=self.essentielle, essentielle=True)

    def point(self, heure=15, minute=0):
        from apps.taches.views import journee as vues
        return vues.point(self.u, maintenant_a(heure, minute))

    def test_forme_de_l_echantillon(self):
        self.scenario()
        modele, rendu = exemple('point'), self.point()
        self.assertEqual(list(rendu), list(modele))
        self.assertEqual(set(rendu['objectif']), set(modele['objectif']))
        self.assertEqual(set(rendu['progression']), set(modele['progression']))
        self.assertEqual(set(rendu['progression']['detail']), set(modele['progression']['detail']))
        self.assertEqual(set(rendu['prochaine']), CLES_ITEM)
        for item in rendu['essentiel_restant']:
            self.assertEqual(set(item), CLES_ITEM)
        self.assertEqual(set(rendu['carte_du_moment']), set(modele['carte_du_moment']))
        self.assertEqual(rendu['jour'], J.isoformat())
        self.assertEqual(rendu['maintenant'], maintenant_a(15).isoformat())

    def test_essentielles_restantes_et_restes(self):
        self.scenario()
        rendu = self.point()
        self.assertEqual([item['id'] for item in rendu['essentiel_restant']], [self.essentielle.pk])
        self.assertEqual(rendu['restes_nb'], 5)
        self.assertEqual(rendu['progression']['faites'], 1)
        self.assertEqual(rendu['rendez_vous_restants'], [])

    def test_prochaine_bloc_a_venir_puis_sans_heure_puis_ce_soir(self):
        from apps.taches.models.taches import Tache
        self.scenario()
        self.assertEqual(self.point()['prochaine']['id'], self.a_venir.pk)
        Tache.objects.filter(pk=self.a_venir.pk).update(statut=StatutTache.FAIT, fait_le=a(J, 15))
        self.assertEqual(self.point()['prochaine']['id'], self.sans_heure.pk)
        Tache.objects.filter(pk__in=[self.sans_heure.pk, self.passee.pk]).update(
            statut=StatutTache.FAIT, fait_le=a(J, 15))
        self.assertEqual(self.point()['prochaine']['id'], self.soir.pk)
        Tache.objects.filter(pk=self.soir.pk).update(statut=StatutTache.FAIT, fait_le=a(J, 15))
        self.assertIsNone(self.point()['prochaine'])

    def test_le_matin_le_bloc_passe_n_existe_pas_encore(self):
        self.scenario()
        self.assertEqual(self.point(10, 30)['prochaine']['id'], self.passee.pk)

    def test_route_et_plafond_de_requetes(self):
        """Horloge FIGÉE sur J (mardi) aux deux moments — le matin, la journée relit aussi le plan de la
        veille et ses restes — chacun à son plafond mesuré (cible api.md §10 : 18) ; ne grandit pas."""
        from testkit.time import frozen
        self.tache(jour_prevu=J, estimation_minutes=30)
        with frozen(APRES_MIDI_J):
            rendu = client_de(self.u).get(URL_POINT).json()
        self.assertEqual(list(rendu), list(exemple('point')))
        peu = {}
        for moment, plafond in PLAFONDS_POINT.items():
            with self.subTest(moment=moment), frozen(moment):
                peu[moment] = requetes_de(client_de(self.u), URL_POINT)
                self.assertLessEqual(peu[moment], plafond)
        for _ in range(10):
            self.tache(jour_prevu=J)
        for moment in PLAFONDS_POINT:
            with self.subTest(moment=moment), frozen(moment):
                self.assertEqual(requetes_de(client_de(self.u), URL_POINT), peu[moment])

    def test_canari_jamais_servi_a_l_assistant(self):
        canari(self.u, timezone.localdate())
        assistant = client_de(self.u).get(URL_POINT, HTTP_X_TAQINOR_ASSISTANT='1')
        self.assertEqual(assistant.status_code, 200, assistant.content[:300])
        self.assertNotIn('canari', assistant.content.decode('utf-8').lower())
        ecran = client_de(self.u).get(URL_POINT).content.decode('utf-8')
        self.assertIn('Canari-titre-essentiel', ecran)  # le canari est vivant


class ChiffresDuJourTests(_Base):
    """Revue F2 tour 2 : un nombre montré est calculé des données, le même partout (Aujourd'hui, bilan
    du soir, nuit) pour la même chose."""

    def garder_et_faire(self, n=3, essentielles=1):
        from apps.taches.services import journee as services
        from apps.taches.services.taches import terminer_tache
        fabriques.reglages(self.u)
        self.pr = fabriques.projet(self.u)
        taches = [fabriques.tache(self.u, projet=self.pr, jour_prevu=J) for _ in range(n)]
        services.planifier_express(self.u, J, maintenant_a(9), lignes=[],
                                   essentielles=[t.pk for t in taches[:essentielles]])
        for t in taches:
            terminer_tache(self.u, t.pk, maintenant=a(J, 11), aujourdhui=J)
        return taches

    def chiffres(self):
        from apps.taches.services import journee as services
        rendu = services.aujourdhui(self.u, J, maintenant_a(18, 30))
        p = rendu['progression']
        bilan = services.cloture(self.u, J, maintenant_a(18, 30))['bilan']
        return (len(rendu['faites']), p['faites'], p['plan_tenues'], p['plan_lignes'], p['essentiel_faites'],
                p['essentiel_prevues']), (bilan['texte'], bilan['texte_gardees'])

    def nuit(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services.journee import clore_jour_precedent
        clore_jour_precedent(self.societe.pk, jours(1))
        plan = PlanJour.objects.get(proprietaire=self.u, jour=J)
        return plan.compte_rythme, plan.plan_faites, plan.plan_prevues, plan.essentiels_faits, plan.essentiels_choisis

    def test_1_faites_d_un_projet_termine_le_jour_meme(self):
        from apps.taches.services.projets import terminer_projet
        self.garder_et_faire()
        avant = self.chiffres()
        self.assertEqual(avant, ((3, 3, 3, 3, 1, 1), ('3 sur 5 · essentiel 1 sur 1', '')))
        terminer_projet(self.u, self.pr.pk, issue='atteint')
        self.assertEqual(self.chiffres(), avant)
        self.assertEqual(self.nuit(), (3, 3, 3, 1, 1))

    def test_1_faites_d_un_projet_mis_en_pause_le_jour_meme(self):
        from apps.taches.services.projets import modifier_projet
        self.garder_et_faire(n=2, essentielles=0)
        avant = self.chiffres()
        self.assertEqual(avant, ((2, 2, 2, 2, 0, 0), ('2 sur 5', '')))
        self.pr.refresh_from_db()
        modifier_projet(self.u, self.pr.pk, {'statut': StatutProjet.EN_PAUSE}, version=self.pr.lock_version)
        self.assertEqual(self.chiffres(), avant)
        self.assertEqual(self.nuit(), (2, 2, 2, 0, 0))

    def test_2_activite_gardee_puis_close_compte_dans_les_gardees_faites(self):
        from apps.taches.services import journee as services
        from apps.taches.services.taches import terminer_tache
        fabriques.reglages(self.u)
        self.pr = fabriques.projet(self.u)
        t = fabriques.tache(self.u, projet=self.pr, jour_prevu=J)
        activite = fabriques.activite(self.u, due_date=J)
        services.planifier_express(self.u, J, maintenant_a(9), lignes=[])
        self.assertEqual(set(LignePlanJour.objects.filter(plan__proprietaire=self.u)
                             .values_list('tache_id', 'activite_id', 'prevue_au_plan')),
                         {(t.pk, None, True), (None, activite.pk, True)})
        terminer_tache(self.u, t.pk, maintenant=a(J, 11), aujourdhui=J)
        activite.done, activite.done_by, activite.done_at = True, self.u, a(J, 12)
        activite.save(update_fields=['done', 'done_by', 'done_at'])
        self.assertEqual(self.chiffres(), ((1, 2, 2, 2, 0, 0), ('2 sur 5', '')))
        self.assertEqual(sel.progression_courante(self.u, J)['plan_tenues'], 2)
        self.assertEqual(self.nuit(), (2, 2, 2, 0, 0))

    def test_2_une_activite_gardee_qui_porte_une_tache_n_est_pas_une_ligne_de_plus(self):
        """Une activité ERP gardée à laquelle une tâche est liée (ou qui a été convertie) n'est pas une gardée
        de plus : sa tâche la représente, comme dans le compte (regles.md §6.1, « jamais deux fois »). Sans
        cela, l'activité liée puis close restait une gardée NON tenue (« 4 des 6 » au lieu de « 4 des 5 »,
        SCENARIO §3, 18:20). Une activité gardée SANS tâche reste une ligne, tenue quand elle est close."""
        from apps.taches.services import journee as services
        from apps.taches.services.erp import lier_activite
        from apps.taches.services.taches import terminer_tache
        fabriques.reglages(self.u)
        self.pr = fabriques.projet(self.u)
        t = fabriques.tache(self.u, projet=self.pr, jour_prevu=J)
        liee, seule = fabriques.activite(self.u, due_date=J), fabriques.activite(self.u, due_date=J)
        services.planifier_express(self.u, J, maintenant_a(9), lignes=[])
        self.assertEqual(sel.progression_courante(self.u, J)['plan_lignes'], 3)
        lier_activite(self.u, activite_id=liee.pk)
        self.assertEqual(sel.progression_courante(self.u, J)['plan_lignes'], 2)
        terminer_tache(self.u, t.pk, maintenant=a(J, 11), aujourdhui=J)
        for activite in (liee, seule):
            activite.done, activite.done_by, activite.done_at = True, self.u, a(J, 12)
            activite.save(update_fields=['done', 'done_by', 'done_at'])
        progression = sel.progression_courante(self.u, J)
        self.assertEqual((progression['plan_tenues'], progression['plan_lignes']), (2, 2))
        self.assertEqual(self.nuit()[1:3], (2, 2))

    def test_3_jour_court_le_meme_objectif_partout(self):
        """regles.md §6.3 : un jour court vaut `max(1, N − 1)` sur Aujourd'hui, l'en-tête du Copilote, le
        plan gardé et le bilan (qui le dit, textes.md §4.3), avant et après un « + » puis « − »."""
        from apps.taches.models.journee import PlanJour
        from apps.taches.services import journee as services
        from apps.taches.services import rythme
        vendredi = datetime.date(2026, 11, 20)
        fabriques.reglages(self.u)
        rythme.poser_preference(self.u, 'jours_courts', [vendredi.weekday()], 'ecran')

        def a_heure(heure):
            return timezone.localtime(a(vendredi, heure))

        def partout():
            rendu = services.aujourdhui(self.u, vendredi, a_heure(18))
            entete = rythme.entete_coach(self.u, vendredi)[0]
            bilan = services.cloture(self.u, vendredi, a_heure(18))['bilan']
            plan = PlanJour.objects.get(proprietaire=self.u, jour=vendredi)
            return (rendu['objectif']['nb'], entete.rsplit(' sur ', 1)[1], plan.objectif_du_jour, bilan['objectif'],
                    bilan['texte'])

        t = fabriques.tache(self.u, projet=fabriques.projet(self.u), jour_prevu=vendredi)
        self.assertEqual(services.proposition_du_jour(self.u, vendredi, a_heure(8))['objectif']['nb'], 4)
        services.planifier_express(self.u, vendredi, a_heure(9), lignes=[{'type': 'tache', 'id': t.pk}])
        attendu = (4, '4', 4, 4, '0 sur 4 (jour court : objectif 4)')
        self.assertEqual(partout(), attendu)
        rythme.regler_rythme(self.u, {'mode': 'pousser', 'sens': 'plus'}, vendredi)
        rythme.regler_rythme(self.u, {'mode': 'pousser', 'sens': 'moins'}, vendredi)
        self.assertEqual(partout(), attendu)

    def test_3_jour_ordinaire_sans_mention(self):
        from apps.taches.services import journee as services
        from apps.taches.services import rythme
        fabriques.reglages(self.u)
        rythme.poser_preference(self.u, 'jours_courts', [4], 'ecran')  # vendredi ; J est un mardi
        self.assertEqual(services.aujourdhui(self.u, J, maintenant_a(18))['objectif']['nb'], 5)
        self.assertEqual(services.cloture(self.u, J, maintenant_a(18))['bilan']['texte'], '0 sur 5')

    def test_4_la_nuit_pose_l_objectif_du_jour_juge_s_il_manque(self):
        from apps.taches.models.journee import PlanJour
        from apps.taches.services import rythme
        from apps.taches.services.journee import clore_jour_precedent
        vendredi, lundi = datetime.date(2026, 11, 20), datetime.date(2026, 11, 23)
        fabriques.reglages(self.u)
        rythme.poser_preference(self.u, 'jours_courts', [vendredi.weekday()], 'ecran')
        for jour in (J, vendredi):
            fabriques.tache(self.u, jour_prevu=jour, statut=StatutTache.FAIT, fait_le=a(jour, 10))
        fabriques.plan(self.u, J, planifie_le=a(J, 8), objectif_du_jour=6)  # gardé : jamais réécrit
        clore_jour_precedent(self.societe.pk, jours(1))
        clore_jour_precedent(self.societe.pk, vendredi + datetime.timedelta(days=1))
        clore_jour_precedent(self.societe.pk, lundi)  # dimanche : non travaillé, rien à juger
        objectifs = dict(PlanJour.objects.filter(proprietaire=self.u).values_list('jour', 'objectif_du_jour'))
        self.assertEqual(objectifs, {J: 6, vendredi: 4, datetime.date(2026, 11, 22): None})

    def test_11_etoile_d_une_tache_supprimee_ou_abandonnee_ne_compte_plus(self):
        from apps.taches.services import journee as services
        from apps.taches.services.taches import supprimer_tache, trancher_tache
        fabriques.reglages(self.u)
        projet = fabriques.projet(self.u)
        supprimee, abandonnee, *autres = [fabriques.tache(self.u, projet=projet, jour_prevu=J) for _ in range(5)]
        for t in (supprimee, abandonnee):
            services.marquer_essentielle(self.u, t.pk, True, maintenant_a(8))
        supprimer_tache(self.u, supprimee.pk)
        trancher_tache(self.u, abandonnee.pk, 'abandonner', maintenant=a(J, 9), aujourdhui=J)
        rendu = services.aujourdhui(self.u, J, maintenant_a(10))
        p = rendu['progression']
        self.assertEqual((p['essentiel_faites'], p['essentiel_prevues'], len(rendu['essentiel'])), (0, 0, 0))
        for t in autres:  # trois ★ visibles : permises
            services.marquer_essentielle(self.u, t.pk, True, maintenant_a(11))
        self.assertEqual(sel.progression_courante(self.u, J)['essentiel_prevues'], 3)
        self.assertEqual(self.nuit()[3:], (0, 3))

    def test_1_ouverte_d_un_projet_en_pause_reste_absente(self):
        # mis en pause AVANT ce jour (R2-031, choix C-5 : seule la pause du jour même garde ce qui y était posé)
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE, statut_depuis=a(jours(-1), 18))
        ouverte = self.tache(projet=en_pause, jour_prevu=J)
        faite = self.tache(projet=en_pause, jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 9))
        ids = set(sel.taches_de_la_journee(self.u, J).values_list('pk', flat=True))
        self.assertNotIn(ouverte.pk, ids)
        self.assertIn(faite.pk, ids)


class UneSourceTests(_Base):
    """M1 (vague 3) — un chiffre, UNE source, et toutes ses lectures rendent le même nombre sur le même jeu."""

    def trois_etoiles(self):
        """3 ★ du jour ; une REPORTÉE à demain sans échéance, une COCHÉE à 11:00 (R3-001)."""
        from apps.taches.services import journee as services
        from apps.taches.services.planification import planifier
        from apps.taches.services.taches import terminer_tache
        fabriques.reglages(self.u)
        faite, reportee, ouverte = (self.tache(jour_prevu=J, titre=f'Étoile {n}') for n in range(3))
        for t in (faite, reportee, ouverte):
            services.marquer_essentielle(self.u, t.pk, True, maintenant_a(8))
        planifier(reportee, acteur=self.u, jour_prevu=jours(1))
        terminer_tache(self.u, faite.pk, maintenant=a(J, 11), aujourdhui=J)
        return faite, reportee, ouverte

    def test_essentiel_le_meme_couple_sur_la_page_le_bilan_l_ecriture_et_la_nuit(self):
        """Calcul à la main : 3 ★ posées ; la reportée sans échéance quitte la section Essentiel (prévues 3 → 2) ;
        la cochée y reste, barrée (faites 1) : « essentiel 1/2 » partout — page (`aujourdhui/`), bilan du soir
        (`journee/cloture/`), toute TACHE_ECRITE (`progression_courante`, ce que Mon rythme et la page
        recalent), et la nuit (`PlanJour.essentiels_*`, lue par la revue)."""
        from apps.taches.models.journee import PlanJour
        from apps.taches.services import journee as services
        from apps.taches.services.journee import clore_jour_precedent
        faite, reportee, ouverte = self.trois_etoiles()
        page = services.aujourdhui(self.u, J, maintenant_a(18, 30))
        self.assertEqual([i['id'] for i in page['essentiel']], [faite.pk, ouverte.pk])
        bilan = services.cloture(self.u, J, maintenant_a(18, 30))['bilan']
        ecriture = sel.progression_courante(self.u, J)
        lectures = {
            'page': (page['progression']['essentiel_faites'], page['progression']['essentiel_prevues']),
            'bilan': (bilan['essentiel_faites'], bilan['essentiel_prevues']),
            'ecriture': (ecriture['essentiel_faites'], ecriture['essentiel_prevues']),
        }
        self.assertEqual(lectures, {nom: (1, 2) for nom in lectures})
        self.assertEqual(bilan['texte'], '1 sur 5 · essentiel 1 sur 2')
        self.assertEqual(bilan['texte_gardees'], '')
        clore_jour_precedent(self.societe.pk, jours(1))
        nuit = PlanJour.objects.get(proprietaire=self.u, jour=J)
        self.assertEqual((nuit.essentiels_faits, nuit.essentiels_choisis), (1, 2))

    def test_faites_du_jour_le_meme_nombre_sur_la_page_le_bilan_et_la_nuit(self):
        """Calcul à la main : 1 ★ cochée + 2 tâches faites (dont une sous-tâche = 0, `compte_du_jour`) + 1 tâche
        faite d'un projet mis en pause = 3 ; page, bilan, écriture et nuit disent 3."""
        from apps.taches.models.journee import PlanJour
        from apps.taches.services import journee as services
        from apps.taches.services.journee import clore_jour_precedent
        faite, _reportee, _ouverte = self.trois_etoiles()
        self.tache(jour_prevu=J, statut=StatutTache.FAIT, fait_le=a(J, 12))
        self.tache(parent=faite, statut=StatutTache.FAIT, fait_le=a(J, 12))
        en_pause = fabriques.projet(self.u, statut=StatutProjet.EN_PAUSE)
        self.tache(projet=en_pause, statut=StatutTache.FAIT, fait_le=a(J, 13))
        page = services.aujourdhui(self.u, J, maintenant_a(18, 30))['progression']['faites']
        bilan = services.cloture(self.u, J, maintenant_a(18, 30))['bilan']['faites']
        ecriture = sel.progression_courante(self.u, J)['faites']
        clore_jour_precedent(self.societe.pk, jours(1))
        nuit = PlanJour.objects.get(proprietaire=self.u, jour=J).compte_rythme
        self.assertEqual((page, bilan, ecriture, nuit), (3, 3, 3, 3))

    #: La semaine lue le jeudi 19/11/2026 à 15 h (lundi 16).
    JEUDI = datetime.date(2026, 11, 19)
    MAINTENANT = '2026-11-19 15:00:00'

    def semaine_faite(self):
        """Lun. 16 : 2 tâches + 1 routine (0) ; mar. 17 : 1 tâche, 1 tâche et sa sous-tâche (0), 1 activité ERP close ;
        jeu. 19 (aujourd'hui) : 1 tâche ; ven. 13 : 2 tâches ; sam. 14 (non travaillé) : 3 tâches. Rien le mer. 18
        (férié ou non selon le calendrier de la société : le test n'en dépend pas)."""
        from apps.taches.models.taches import RegleRecurrence
        regle = RegleRecurrence.objects.create(company=self.societe, proprietaire=self.u, frequence='quotidien',
                                               date_debut=datetime.date(2026, 11, 1))
        for jour, n in ((16, 2), (17, 1), (19, 1), (13, 2), (14, 3)):
            for rang in range(n):
                self.tache(statut=StatutTache.FAIT, fait_le=a(datetime.date(2026, 11, jour), 9 + rang))
        self.tache(statut=StatutTache.FAIT, fait_le=a(datetime.date(2026, 11, 16), 12), recurrence=regle)
        parent = self.tache(statut=StatutTache.FAIT, fait_le=a(datetime.date(2026, 11, 17), 15))
        self.tache(parent=parent, statut=StatutTache.FAIT, fait_le=a(datetime.date(2026, 11, 17), 14))
        activite = fabriques.activite(self.u, due_date=datetime.date(2026, 11, 17))
        activite.done, activite.done_by, activite.done_at = True, self.u, a(datetime.date(2026, 11, 17), 12)
        activite.save(update_fields=['done', 'done_by', 'done_at'])

    def test_la_semaine_le_meme_total_dans_la_revue_la_recherche_et_l_agenda(self):
        """C-16 — calcul à la main : cette semaine = lun. 2 (la routine vaut 0) + mar. 3 (2 tâches, la sous-tâche
        vaut 0, + l'activité close) + jeu. 1 = 6 ; la semaine d'avant = ven. 13 : 2 + sam. 14 : 3 = 5 (week-end
        compris) ; jours = 3 (lun., mar., jeu.). Revue (tête), Recherche (`total` de « Faites cette semaine »)
        et Agenda (Σ `faites_nb` du lun. 16 au dim. 22) disent 6."""
        from testkit.time import frozen
        self.semaine_faite()
        client = client_de(self.u)
        with frozen(self.MAINTENANT):
            revue = client.get('/api/django/taches/revue/projets/').json()['bilan_semaine']
            recherche = client.get('/api/django/taches/taches/', {'periode': 'faites_semaine'}).json()
            agenda = client.get('/api/django/taches/agenda/', {'du': '2026-11-16', 'au': '2026-11-22',
                                                               'vue': 'semaine'}).json()
        lectures = {'revue': revue['donnees']['faites'], 'recherche': recherche['total'],
                    'agenda': sum(j['faites_nb'] for j in agenda['jours'])}
        self.assertEqual(lectures, {nom: 6 for nom in lectures})
        self.assertEqual((revue['donnees']['prec'], revue['donnees']['jours']), (5, 3))
        self.assertEqual(revue['texte'], 'Cette semaine : 6 faites (5 la précédente).')
        self.assertEqual(len(recherche['results']) + len(recherche['activites_closes']), recherche['total'])

    def test_mon_rythme_et_l_agenda_disent_le_meme_nombre_chaque_jour(self):
        """C-21 — la nuit clôt du ven. 13 au mer. 18 ; la série de Mon rythme (ven. 13 : 2, sam. 14 HORS OBJECTIF : 3,
        lun. 16 : 2, mar. 17 : 3) et l'Agenda (`faites_nb`) disent le même nombre, jour par jour ; le samedi ne compte
        jamais contre l'objectif."""
        from apps.taches.services.journee import clore_jour_precedent
        from testkit.time import frozen
        fabriques.reglages(self.u)
        self.semaine_faite()
        client = client_de(self.u)
        with frozen(self.MAINTENANT):
            for jour in range(14, 20):
                clore_jour_precedent(self.societe.pk, datetime.date(2026, 11, jour))
            serie = client.get('/api/django/taches/rythme/').json()['serie']
            agenda = client.get('/api/django/taches/agenda/', {'du': '2026-11-13', 'au': '2026-11-18',
                                                               'vue': 'semaine'}).json()
        rythme = {barre['jour']: (barre['faites'], barre['hors_objectif']) for barre in serie if barre['faites']}
        self.assertEqual(rythme, {'2026-11-13': (2, False), '2026-11-14': (3, True), '2026-11-16': (2, False),
                                  '2026-11-17': (3, False)})
        faites_agenda = {j['jour']: j['faites_nb'] for j in agenda['jours'] if j['jour'] in rythme}
        self.assertEqual({jour: faites for jour, (faites, _hors) in rythme.items()}, faites_agenda)
