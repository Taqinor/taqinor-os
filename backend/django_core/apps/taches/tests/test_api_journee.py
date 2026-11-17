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
