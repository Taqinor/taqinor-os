"""TCH169 — `manage.py seed_taches_demo` : la journée de `docs/taches/maquettes/SCENARIO.md`.

Sème, pour le compte `demo_taches` (administrateur de la société de démonstration `demo-taches`, droit
`taches_voir` par un RÔLE DE TEST créé ici), les 5 projets, leurs tâches, la journée du mardi 24 novembre
2026 minute par minute, l'historique « Les jours passés » et le rythme des 10 derniers jours travaillés.
Sert aux acceptations en direct : l'écran réel est comparé aux maquettes.

Garde et méthode
- REFUSE de tourner hors `DEBUG` ou avec un module de réglages de production ; la société doit être
  `est_demo=True` (même garde que `seed_demo`, `authentication.selectors.refus_societe_non_demo`).
- Aucun mot de passe n'est écrit dans le code ni affiché : il vient de la variable d'environnement
  `TACHES_DEMO_PASSWORD` ; sans elle le compte reçoit un mot de passe inutilisable (connexion par
  l'administration seulement).
- IDEMPOTENTE : un compte déjà semé n'est pas retouché (même journée) ; `--reinitialiser` efface les
  données `taches` du compte (`services.donnees.tout_effacer`) puis rejoue le semis.
- Tout passe par les SERVICES de l'app (`creer_taches`, `terminer_tache`, `planifier`, `trancher_tache`,
  `marquer_essentielle`, `planifier_express`, `clore_jour_precedent`, `etapes_nocturnes`…) avec une
  horloge FIGÉE à l'instant de chaque événement du scénario (`timezone.now` remplacé le temps du geste :
  les dates « créée le », « faite le », `PlanJour` des jours passés sont alors celles du scénario).
  Écrits directement, et dits à chaque endroit : `ReglagesRythme.palier/bloc_debut` (objectif 5
  « accepté »), `Projet.planification_le`, les compteurs d'objectif/essentiel des `PlanJour` passés, la
  suggestion ERP acceptée, la clôture de l'activité ERP, l'agenda externe et son cache.
"""
import datetime
import itertools
import os
from collections import defaultdict
from contextlib import contextmanager
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.taches import agenda_externe
from apps.taches.choix import (
    FamilleSuggestion,
    ModeRythme,
    Priorite,
    Source,
    StatutSuggestion,
)
from apps.taches.models.agenda import AgendaExterne
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.journee import PlanJour
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache
from apps.taches.services import donnees as services_donnees
from apps.taches.services import journee, rythme
from apps.taches.services.creation import creer_taches
from apps.taches.services.erp import lier_activite
from apps.taches.services.planification import planifier
from apps.taches.services.projets import creer_projet, modifier_projet
from apps.taches.services.taches import attendre_tache, modifier_tache, terminer_tache

#: Société de démonstration et compte du semis (jamais une société réelle : `est_demo=True` exigé).
SLUG_SOCIETE = 'demo-taches'
NOM_COMPTE = 'demo_taches'
NOM_ROLE = 'Test tâches demo_taches'
VARIABLE_MOT_DE_PASSE = 'TACHES_DEMO_PASSWORD'
#: Le jour du scénario (SCENARIO.md §1) : toutes les dates du scénario s'y rattachent.
JOUR_SCENARIO = datetime.date(2026, 11, 24)
HEURE_DEFAUT = '08:30'
OBJECTIF = 5
PAS_FAIT = 40  # minutes entre deux « faites » d'un même jour sans heure dite

#: Les 8 titres sans projet du réservoir (SCENARIO.md §5) ; « Rappeler le comptable » est celui du lundi 23.
RESERVOIR = ('Répondre au syndic de l\'immeuble', 'Passer à la banque', 'Relancer M. Alaoui pour son avis',
             'Commander des gants de sécurité', 'Mettre à jour le site de Google', 'Payer le parking du dépôt',
             'Envoyer les photos du chantier Salé')
COMPTABLE = 'Rappeler le comptable'
#: Jour (novembre 2026) → tâches faites ce jour-là (SCENARIO.md §5) ; le reste est pris du réservoir.
RYTHME = ((9, 5), (10, 5), (11, 4), (12, 6), (13, 3), (16, 5), (17, 4), (19, 7), (20, 5), (23, 4))
#: Jours de la revue de la semaine du 16 au 20 : (jour, essentiels choisis, essentiels faits) (§5).
ESSENTIELS_PASSES = {16: (1, 1), 17: (1, 0), 19: (1, 1), 20: (1, 1)}
TAILLE_RESERVE = 7  # « En réserve : 7 tâches » (§1)

# --- Les projets (§1) : nom, couleur, priorité, échéance, étapes dans l'ordre -----------------------------------
PROJETS = (
    ('Chantier Benali 9 kWc', 'ambre', Priorite.HAUTE, (12, 4), True),
    ('Salon Solaire Expo', 'indigo', Priorite.HAUTE, (11, 27), True),
    ('Recrutement technicien', 'vert', Priorite.MOYENNE, (1, 15, 2027), True),
    ('Administratif', 'prune', Priorite.BASSE, None, True),
    ('Site web', 'ciel', Priorite.MOYENNE, None, False),  # « À planifier » : jamais planifié
)
BENALI, SALON, RECRUTEMENT, ADMIN, SITE = (p[0] for p in PROJETS)

# --- Les tâches des projets (§2) ---------------------------------------------------------------------------------
# (projet, étape, titre, fait, extras). `fait` = (jour_de_novembre, 'HH:MM' | None) ou None si ouverte.
# extras : est (minutes), prevu ((mois, jour), 'HH:MM' | None), priorite, echeance, moment, jalon, reserve,
# cree ((mois, jour), 'HH:MM').
D = 'Démarches'
TACHES = (
    (BENALI, 'Études', 'Visiter le site', (9, None), {}),
    (BENALI, 'Études', 'Relever les factures du client', (10, None), {}),
    (BENALI, 'Études', 'Valider le dimensionnement', (12, None), {}),
    (BENALI, 'Études', 'Préparer le devis', (13, None), {}),
    (BENALI, 'Études', 'Faire signer le devis', (16, None), {}),
    (BENALI, 'Études', "Encaisser l'acompte", (17, None), {}),
    (BENALI, 'Études', "Valider l'étude de toiture", (19, None), {}),
    (BENALI, 'Études', 'Envoyer le devis révisé', None,
     {'est': 120, 'prevu': ((11, 24), '09:00'), 'priorite': 3, 'echeance': (11, 25), 'cree': ((11, 20), '08:00')}),
    (BENALI, D, 'Déposer la demande de raccordement', (16, None), {}),
    (BENALI, D, 'Prévenir le syndic', (19, None), {}),
    (BENALI, D, "Obtenir l'accord du bureau de contrôle", (20, None), {}),
    (BENALI, 'Matériel', 'Commander les onduleurs', (23, '10:00'), {'est': 60, 'prevu': ((11, 23), '09:00')}),
    (BENALI, 'Matériel', 'Commander les 16 panneaux', (23, '11:30'), {'est': 30, 'prevu': ((11, 23), '11:00')}),
    (BENALI, 'Matériel', 'Commander les rails de fixation', None, {'est': 30}),
    (BENALI, 'Matériel', 'Valider le plan de calepinage', None,
     {'est': 60, 'prevu': ((11, 25), '09:00'), 'echeance': (11, 26)}),
    (BENALI, 'Matériel', 'Réceptionner les 16 panneaux', None, {'est': 60, 'prevu': ((11, 26), '09:00')}),
    (BENALI, 'Pose', 'Poser la structure', None, {'est': 480, 'prevu': ((11, 23), None)}),
    (BENALI, 'Pose', 'Mise en service', None, {'jalon': True, 'echeance': (12, 3)}),
    (SALON, 'Stand', 'Réserver le stand', (3, None), {}),
    (SALON, 'Stand', 'Confirmer la réservation du stand', None,
     {'est': 30, 'prevu': ((11, 24), None), 'echeance': (11, 24)}),
    (SALON, 'Stand', 'Préparer le matériel du stand', None, {'est': 60, 'prevu': ((11, 26), '14:00')}),
    (SALON, 'Stand', "Imprimer les badges de l'équipe", None, {'est': 30, 'prevu': ((11, 27), '11:30')}),
    (SALON, 'Supports', "Envoyer le visuel à l'imprimeur", (19, None), {}),
    (SALON, 'Supports', 'Valider le texte des brochures', (23, '15:00'), {'est': 60, 'prevu': ((11, 23), '14:00')}),
    (SALON, 'Supports', 'Imprimer les kakémonos', None, {'est': 30, 'prevu': ((11, 25), '11:00')}),
    (SALON, 'Supports', "Comparer deux devis d'impression", None, {'est': 30, 'reserve': True}),
    (SALON, 'Démo', 'Appeler le fournisseur', None, {'est': 30, 'priorite': 3}),
    (SALON, 'Démo', "Préparer la démo onduleur hybride", None, {'est': 120}),
    (SALON, 'Logistique', "Réserver l'hôtel du salon", None, {'est': 30}),
    (RECRUTEMENT, None, 'Valider le budget du poste', (10, None), {}),
    (RECRUTEMENT, None, "Choisir les sites d'annonce", (12, None), {}),
    (RECRUTEMENT, None, 'Définir le profil recherché', (16, None), {}),
    (RECRUTEMENT, None, "Publier l'annonce", (19, None), {}),
    (RECRUTEMENT, None, 'Trier les CV reçus', None, {'est': 60, 'prevu': ((11, 25), '14:00')}),
    (RECRUTEMENT, None, 'Rédiger la fiche de poste', None, {'est': 60}),
    (RECRUTEMENT, None, 'Planifier les entretiens', None, {'est': 30}),
    (RECRUTEMENT, None, "Préparer les questions d'entretien", None, {'est': 45}),
    (RECRUTEMENT, None, 'Appeler les candidats retenus', None, {'est': 30}),
    (ADMIN, None, "Payer la CNSS d'octobre", (2, None), {}),
    (ADMIN, None, "Envoyer les factures d'octobre", (3, None), {}),
    (ADMIN, None, 'Payer le loyer du dépôt', (9, None), {}),
    (ADMIN, None, "Renouveler l'abonnement téléphonique", (11, None), {}),
    (ADMIN, None, 'Archiver les relevés bancaires', (13, None), {}),
    (ADMIN, None, 'Payer la CNSS de novembre', (17, None), {}),
    (ADMIN, None, 'Classer les factures fournisseurs', (20, None), {}),
    # Existe dès le matin (§7 : 3 ouvertes à 08:30) ; « Reda l'ajoute à la main pour ce soir » à 09:10.
    (ADMIN, None, 'Relire le contrat de maintenance', None, {'est': 45}),
    (ADMIN, None, 'Préparer la déclaration de TVA', None, {'est': 60, 'prevu': ((11, 27), '10:00')}),
    (ADMIN, None, "Payer l'assurance du camion", None, {'est': 30, 'prevu': ((11, 27), '15:00')}),
    (SITE, None, 'Lister les pages du site', None, {'est': 60}),
    (SITE, None, "Choisir l'hébergeur", None, {'est': 60}),
    (SITE, None, "Rédiger la page d'accueil", None, {'est': 120}),
    (SITE, None, 'Photographier trois chantiers', None, {'est': 60}),
)
#: (tâche bloquée, prérequis) : la puce « attend : {titre} », dans le même projet (§2).
ATTENTES = (('Planifier les entretiens', 'Trier les CV reçus'),
            ('Appeler les candidats retenus', 'Planifier les entretiens'))
#: (tâche, attendu) : « En attente 1 » (§1) par `attendre_tache` (le texte « attend : … » est `en_attente_de`) ; la
#: tâche est datée (lun. 23) : une tâche en attente n'entre dans la section qu'avec un jour prévu ou une échéance ≤ J.
EN_ATTENTE = (('Poser la structure', 'Réceptionner les 16 panneaux'),)
#: Titres, jour et heure du jour du scénario dont l'heure d'étape est dite en §3.
DEVIS, STAND, RAILS = 'Envoyer le devis révisé', 'Confirmer la réservation du stand', 'Commander les rails de fixation'
FOURNISSEUR, FICHE = 'Appeler le fournisseur', 'Rédiger la fiche de poste'
CONTRAT = 'Relire le contrat de maintenance'
A_REVOIR = ('Mettre à jour le planning des poses', 'Rappeler le bureau de contrôle')
#: S1 (acceptation F2) : « À revoir » = reportée 3 fois (regles.md §4.2 cas 3, textes.md « À revoir ») ; prévues
#: lun. 23 (§1) APRÈS trois reports faits par le vrai geste « Reporter » (`planifier`), le soir de chaque jour prévu.
#: Les trois premiers jours ne sont pas dans SCENARIO.md (ERR-SCENARIO au rapport) : 17 → 19 (18 férié) → 20 → 23.
JOURS_A_REVOIR = ((11, 17), (11, 19), (11, 20), (11, 23))
CREATION_A_REVOIR = ((11, 16), '08:30')
HEURE_DU_REPORT = '18:00'
#: La journée du 24 (§3), dans l'ordre : (heure, geste). Un geste n'est semé que si son heure est PASSÉE (`--heure`).
#: « Lier une tâche » sur « Rappeler pour le devis » (parcours TCH137 étape 4) n'a pas d'heure dans SCENARIO.md
#: (ERR-SCENARIO) : 10:30, l'heure de l'activité, avant sa clôture de 10:40 — sans ce lien la clôture compterait 1
#: (regles.md §6.1) et 15:00 dirait « 4 sur 5 ».
GESTES_DU_JOUR = (
    ('08:20', 'essentielles'), ('08:31', 'garder'), ('08:52', 'rails'), ('09:10', 'contrat'),
    ('10:20', 'fournisseur'), ('10:30', 'lier_rappel'), ('10:40', 'fermer_rappel'), ('10:50', 'devis'),
    ('14:10', 'fiche'), ('16:30', 'stand'))
#: Les 6 autres tâches « En réserve » : le scénario n'en dit que le nombre (§1) ; titres plausibles, sans nom propre.
RESERVE_ANONYME = (
    'Étudier une assurance pour la flotte de véhicules', "Tester un logiciel de devis concurrent",
    "Rédiger un guide d'entretien pour les clients", "Visiter le showroom d'un fournisseur d'onduleurs",
    'Imaginer une offre de maintenance annuelle', "Écrire un article sur l'autoconsommation")
assert len(RESERVE_ANONYME) == TAILLE_RESERVE - 1
ACTIVITE_APPEL = 'Rappeler pour le devis'
ACTIVITE_FACTURE = "Envoyer la facture d'acompte"
TITRE_ICS = 'tests/donnees/agenda.ics'


def _heure(texte):
    return datetime.time.fromisoformat(texte) if texte else None


@contextmanager
def horloge(instant):
    """Fige `django.utils.timezone.now` (et donc `localdate`, `auto_now*`) le temps d'un geste."""
    with mock.patch('django.utils.timezone.now', return_value=instant):
        yield


def _production():
    """Vrai si les réglages courants sont ceux d'une production (DEBUG faux, ou module `prod`)."""
    module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    return (not settings.DEBUG) or module.rsplit('.', 1)[-1] in ('prod', 'production')


class Scenario:
    """Une exécution du semis : dates décalées de `delta` jours, `heure` jusqu'où on rejoue le 24."""

    def __init__(self, user, jour, heure, historique):
        self.user = user
        self.delta = jour - JOUR_SCENARIO
        self.jour = jour
        self.heure = heure
        self.historique = historique
        self.taches = {}
        self.projets = {}
        self.sections_vues = set()
        self.faites_du_jour = defaultdict(int)

    # --- Dates et instants -----------------------------------------------------------------------------------
    def date(self, mois, jour, annee=2026):
        return datetime.date(annee, mois, jour) + self.delta

    def instant(self, jour, heure):
        return timezone.make_aware(datetime.datetime.combine(jour, _heure(heure) if isinstance(heure, str) else heure))

    # --- Projets ---------------------------------------------------------------------------------------------
    def creer_projets(self):
        ouverture = self.instant(self.date(11, 2), '08:30')
        for nom, couleur, priorite, echeance, planifie in PROJETS:
            with horloge(ouverture):
                projet = creer_projet(self.user, nom=nom, priorite=priorite, couleur=couleur).projet
                donnees = {'echeance': self.date(*echeance)} if echeance else {}
                if donnees:
                    projet = modifier_projet(self.user, projet.pk, donnees, version=projet.lock_version)
                if planifie:
                    # Écrit directement : seul `planifier_projet` le pose, et il créerait des tâches.
                    Projet.objects.filter(pk=projet.pk).update(planification_le=ouverture)
            self.projets[nom] = projet

    # --- Tâches ----------------------------------------------------------------------------------------------
    def _creer(self, instant, ligne, *, source=Source.MANUEL, porte='ecran', **options):
        with horloge(instant):
            resultat = creer_taches(self.user, [ligne], source=source, porte=porte, **options)
        return resultat.creees[0]

    def _terminer(self, tache, instant):
        with horloge(instant):
            terminer_tache(self.user, tache.pk, maintenant=instant, aujourdhui=timezone.localtime(instant).date())

    def _instant_fait(self, jour, heure):
        if heure:
            return self.instant(jour, heure)
        rang = self.faites_du_jour[jour]
        self.faites_du_jour[jour] += 1
        base = datetime.datetime.combine(jour, datetime.time(9, 30)) + datetime.timedelta(minutes=PAS_FAIT * rang)
        return timezone.make_aware(base)

    def _ligne(self, projet, etape, titre, extras):
        ligne = {'titre': titre, 'projet_id': self.projets[projet].pk if projet else None}
        if etape:
            ligne['nouvelle_section'] = {'nom': etape}
        if 'est' in extras:
            ligne['estimation_minutes'] = extras['est']
        if 'priorite' in extras:
            ligne['priorite'] = extras['priorite']
        if 'echeance' in extras:
            ligne['echeance'] = self.date(*extras['echeance'])
        if extras.get('jalon'):
            ligne['jalon'] = True
        if extras.get('reserve'):
            ligne['quelque_jour'] = True
        if 'prevu' in extras:
            (mois, jour), heure = extras['prevu']
            ligne['jour_prevu'] = self.date(mois, jour)
            if heure:
                ligne['heure_debut'] = heure
        if 'moment' in extras:
            ligne['moment'] = extras['moment']
        return {c: v for c, v in ligne.items() if v is not None}

    def taches_des_projets(self):
        """Les tâches des 5 projets dans l'ordre du scénario ; les faites sont créées PUIS cochées à leur jour."""
        for projet, etape, titre, fait, extras in TACHES:
            if fait is not None:
                jour = self.date(11, fait[0])
                creee = self.instant(jour, '08:00')
                tache = self._creer(creee, self._ligne(projet, etape, titre, extras))
                self._terminer(tache, self._instant_fait(jour, fait[1]))
                self.taches[titre] = tache
                continue
            (mois, jour), heure = extras.get('cree', ((11, 2), '09:00'))
            self.taches[titre] = self._creer(self.instant(self.date(mois, jour), heure),
                                             self._ligne(projet, etape, titre, extras))
        for titre, prerequis in ATTENTES:
            tache = Tache.objects.get(pk=self.taches[titre].pk)
            with horloge(self.instant(self.date(11, 2), '09:30')):
                modifier_tache(self.user, tache.pk, {'bloquee_par_id': self.taches[prerequis].pk},
                               version=tache.lock_version)
        for titre, attendu in EN_ATTENTE:
            with horloge(self.instant(self.date(11, 2), '09:45')):
                attendre_tache(self.user, self.taches[titre].pk, attendu)

    def reservoir(self):
        """Les tâches sans projet faites chaque jour : le total du scénario moins celles des projets."""
        titres = itertools.cycle(RESERVOIR)
        for jour_n, total in RYTHME:
            jour = self.date(11, jour_n)
            des_projets = sum(1 for _p, _e, _t, fait, _x in TACHES if fait and fait[0] == jour_n)
            noms = [COMPTABLE] if jour_n == 23 else [next(titres) for _ in range(total - des_projets)]
            for nom in noms:
                tache = self._creer(self.instant(jour, '08:00'), {'titre': nom})
                heure = '16:30' if nom == COMPTABLE else None
                self._terminer(tache, self._instant_fait(jour, heure))

    # --- À trier, à revoir, en réserve (§1) -----------------------------------------------------------------------
    def a_trier(self):
        """5 tâches À TRIER, nées par leur porte réelle (suggestion, activité, capture, saisie)."""
        soir_23 = self.instant(self.date(11, 23), '17:30')
        suggeree = self._creer(self.instant(self.date(11, 23), '18:00'),
                               {'titre': 'Préparer le chantier du devis accepté'},
                               source=Source.SUGGESTION, porte='suggestion')
        # Écrit directement : aucun service ne crée une `SuggestionTache` (TCH71-TCH72 la lisent).
        SuggestionTache.objects.create(
            company_id=self.user.company_id, proprietaire=self.user, famille=FamilleSuggestion.DEVIS_ACCEPTE,
            cle='demo-devis-accepte', titre_propose=suggeree.titre, statut=StatutSuggestion.ACCEPTEE,
            tache=suggeree, decidee_le=suggeree.created_at)
        self._facture_d_acompte(soir_23)
        self._creer(self.instant(self.date(11, 23), '17:00'), {'titre': 'Acheter des cartouches pour l\'imprimante'},
                    source=Source.CAPTURE, porte='capture')
        self._creer(self.instant(self.date(11, 23), '12:00'),
                    {'titre': "Demander le devis d'assurance décennale"}, source=Source.RAPIDE, porte='saisie')
        self._creer(self.instant(self.date(11, 22), '10:00'), {'titre': 'Filmer le chantier pour Instagram'},
                    source=Source.RAPIDE, porte='saisie')

    def _activite(self, **champs):
        """Activité ERP (`records`, app de fondation) : type « À faire » de la société, créée telle quelle."""
        from apps.records.models import Activity, ActivityType
        type_ = ActivityType.objects.filter(company_id=self.user.company_id, nom='À faire').first()
        if type_ is None:
            type_ = ActivityType.objects.create(
                company_id=self.user.company_id, nom='À faire', icone='✔️', ordre=50, est_systeme=True)
        return Activity.objects.create(company_id=self.user.company_id, activity_type=type_, assigned_to=self.user,
                                       created_by=self.user, done=False, **champs)

    def _facture_d_acompte(self, instant):
        """« À-faire d'Activités » converti comme `services.erp._convertir_une` : échéance ven. 27, À trier."""
        from apps.records.services import cloturer_a_faire_personnel
        with horloge(instant):
            activite = self._activite(summary=ACTIVITE_FACTURE, personnelle=True, due_date=self.date(11, 27))
            creer_taches(self.user, [{'titre': ACTIVITE_FACTURE, 'echeance': self.date(11, 27)}],
                         source=Source.ACTIVITE, porte='conversion', activite=activite)
            cloturer_a_faire_personnel(activite, self.user)

    def a_revoir(self):
        """S1 : prévues lun. 23 après trois reports (`JOURS_A_REVOIR`), chacun par `planifier` le soir du
        jour prévu (ancien jour ≤ aujourd'hui : le service compte le report, invariant 4)."""
        (mois, jour), heure = CREATION_A_REVOIR
        premier, *suivants = JOURS_A_REVOIR
        for titre in A_REVOIR:
            tache = self._creer(self.instant(self.date(mois, jour), heure),
                                {'titre': titre, 'jour_prevu': self.date(*premier), 'estimation_minutes': 30})
            prevu = premier
            for suivant in suivants:
                with horloge(self.instant(self.date(*prevu), HEURE_DU_REPORT)):
                    planifier(tache, acteur=self.user, jour_prevu=self.date(*suivant))
                prevu = suivant

    def reserve(self):
        for titre in RESERVE_ANONYME:
            self._creer(self.instant(self.date(11, 2), '10:00'), {'titre': titre, 'quelque_jour': True})

    # --- Réglages du rythme (§1) ---------------------------------------------------------------------------------
    def reglages(self):
        """Objectif 5 « accepté », mode En faire plus, bloc commencé le lun. 9 ; écrit directement : seule la
        réponse à une carte pose `accepte`, et le bloc est celui des 10 jours évalués du scénario."""
        reglages = ReglagesRythme.objects.get(company_id=self.user.company_id, proprietaire=self.user)
        reglages.mode, reglages.palier, reglages.palier_source = ModeRythme.POUSSER, OBJECTIF, 'accepte'
        reglages.bloc_debut = self.date(11, 9)
        reglages.save(update_fields=['mode', 'palier', 'palier_source', 'bloc_debut', 'updated_at'])

    def jours_passes(self):
        """Clôture les jours passés par la VRAIE étape de nuit (`clore_jour_precedent`, qui pose aussi
        l'objectif du jour : revue F2 tour 2 #4), puis complète directement, pour la revue de la semaine,
        les essentiels du plan clos (§5)."""
        retenus = RYTHME[len(RYTHME) - self.historique:] if self.historique else ()
        for jour_n, _total in retenus:
            jour = self.date(11, jour_n)
            with horloge(self.instant(jour + datetime.timedelta(days=1), '03:00')):
                journee.clore_jour_precedent(self.user.company_id, jour + datetime.timedelta(days=1))
            plan = PlanJour.objects.get(company_id=self.user.company_id, proprietaire=self.user, jour=jour)
            choisis, faits = ESSENTIELS_PASSES.get(jour_n, (0, 0))
            plan.essentiels_choisis, plan.essentiels_faits = choisis, faits
            plan.save(update_fields=['essentiels_choisis', 'essentiels_faits', 'updated_at'])

    def nuit_du_jour(self):
        """La nuit qui ouvre le 24 : clôt le 23 et pose les cartes du rythme (« Monter à 6 »)."""
        avant = self.instant(self.jour, '03:00')
        with horloge(avant):
            if self.historique:
                journee.clore_jour_precedent(self.user.company_id, self.jour)
            rythme.etapes_nocturnes(self.user.company_id, self.jour)

    # --- La journée du mardi 24, minute par minute (§3) : la table `GESTES_DU_JOUR` -------------------------------
    #: Heure des « faites » du 24 (§3).
    FAIT_A = {RAILS: '08:52', FOURNISSEUR: '10:20', DEVIS: '10:50', STAND: '16:30'}

    def _geste_essentielles(self, instant):
        for titre in (DEVIS, STAND):
            journee.marquer_essentielle(self.user, self.taches[titre].pk, True, instant)

    def _geste_garder(self, instant):
        T = self.taches
        lignes = [{'type': 'tache', 'id': T[t].pk} for t in (RAILS, FOURNISSEUR, FICHE)]
        journee.planifier_express(self.user, self.jour, instant, lignes=lignes,
                                  essentielles=[T[DEVIS].pk, T[STAND].pk])
        planifier(T[RAILS], acteur=self.user, jour_prevu=self.jour, heure_debut=datetime.time(8, 30))
        planifier(T[FOURNISSEUR], acteur=self.user, jour_prevu=self.jour, heure_debut=datetime.time(10, 0))

    def _geste_contrat(self, instant):
        planifier(self.taches[CONTRAT], acteur=self.user, jour_prevu=self.jour, moment='soir')

    def _geste_rails(self, instant):
        self._terminer(self.taches[RAILS], instant)

    def _geste_fournisseur(self, instant):
        self._terminer(self.taches[FOURNISSEUR], instant)

    def _geste_devis(self, instant):
        self._terminer(self.taches[DEVIS], instant)

    def _geste_stand(self, instant):
        self._terminer(self.taches[STAND], instant)

    def _geste_lier_rappel(self, instant):
        """S5 : « Lier une tâche » par la VRAIE route (`services.erp.lier_activite`, `jour_prevu` nul comme
        l'écran) ; avant 10:30 l'activité n'a aucune tâche et le geste du parcours répond 201."""
        lier_activite(self.user, activite_id=self.rappel.pk)

    def _geste_fermer_rappel(self, instant):
        """L'activité ERP « Rappeler pour le devis » est close à 10:40 ; écrit directement : seule la route
        `records` des activités clôt une activité planifiée (aucun service sans HTTP)."""
        from apps.records.models import Activity
        Activity.objects.filter(pk=self.rappel.pk).update(done=True, done_at=instant, done_by=self.user)

    def _geste_fiche(self, instant):
        """« Choisir un jour » (§3 14:10) : la route `taches/{id}/planifier/`, donc `planifier` — pas
        `trancher`, la décision d'À revoir (acceptation F2 défaut 6)."""
        planifier(self.taches[FICHE], acteur=self.user, jour_prevu=self.date(11, 26))

    def activite_du_jour(self):
        """L'activité ERP du 24 « Rappeler pour le devis » (§1), sans tâche liée d'avance (S5)."""
        with horloge(self.instant(self.jour, '08:00')):
            self.rappel = self._activite(summary=ACTIVITE_APPEL, personnelle=False, due_date=self.jour)

    def jour_du_scenario(self):
        """Rejoue `GESTES_DU_JOUR` jusqu'à `--heure` incluse, horloge figée à l'heure de chaque geste."""
        self.activite_du_jour()
        limite = _heure(self.heure)
        for heure, nom in GESTES_DU_JOUR:
            if _heure(heure) <= limite:
                instant = self.instant(self.jour, heure)
                with horloge(instant):
                    getattr(self, f'_geste_{nom}')(instant)

    def rendez_vous(self, utilisateur):
        """Agenda externe rempli depuis `tests/donnees/agenda.ics` : le texte va directement dans le cache
        d'une adresse jamais jointe (aucun réseau)."""
        chemin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              *TITRE_ICS.split('/'))
        with open(chemin, encoding='utf-8') as fichier:
            texte = fichier.read()
        agenda = AgendaExterne.objects.create(
            company_id=utilisateur.company_id, proprietaire=utilisateur, libelle='Agenda de démonstration',
            url='https://agenda-demo.example.invalid/taches.ics')
        cache.set(agenda_externe.cle_cache(agenda), texte, agenda_externe.CACHE_SECONDES)
        agenda_externe.oublier_index(utilisateur)


class Command(BaseCommand):
    help = "Sème la journée de docs/taches/maquettes/SCENARIO.md pour le compte demo_taches (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--jour', default=JOUR_SCENARIO.isoformat(), help='Jour du scénario (AAAA-MM-JJ).')
        parser.add_argument('--heure', default=HEURE_DEFAUT, help='Heure du jour rejouée jusqu\'à (HH:MM).')
        parser.add_argument('--historique', type=int, default=len(RYTHME),
                            help='Nombre de jours de rythme clos (0 à 10, les plus récents).')
        parser.add_argument('--vide', action='store_true', help='Compte sans aucune tâche.')
        parser.add_argument('--absence', type=int, default=0,
                            help="Jours d'absence : le scénario s'arrête N jours avant --jour.")
        parser.add_argument('--rendez-vous', action='store_true', dest='rendez_vous',
                            help='Agenda externe rempli depuis tests/donnees/agenda.ics (sans réseau).')
        parser.add_argument('--reinitialiser', action='store_true',
                            help='Efface les données tâches du compte avant de semer.')

    def _lire(self, options):
        try:
            jour = datetime.date.fromisoformat(options['jour'])
            heure_ok = datetime.time.fromisoformat(options['heure'])
        except ValueError as exc:
            raise CommandError(f'--jour (AAAA-MM-JJ) ou --heure (HH:MM) illisible : {exc}')
        if not 0 <= options['historique'] <= len(RYTHME) or options['absence'] < 0:
            raise CommandError('--historique entre 0 et 10 ; --absence positive.')
        return jour, heure_ok.strftime('%H:%M')

    def _compte(self):
        from apps.roles.models import Role
        from authentication.models import Company, CustomUser
        from authentication.selectors import refus_societe_non_demo
        refus = refus_societe_non_demo(SLUG_SOCIETE)
        if refus:
            raise CommandError(refus)
        societe, _cree = Company.objects.get_or_create(
            slug=SLUG_SOCIETE, defaults={'nom': 'Société de démonstration', 'est_demo': True})
        # Rôle de TEST : `taches_voir` n'est accordé à aucun rôle système avant l'activation du module.
        role, _cree = Role.objects.get_or_create(company=societe, nom=NOM_ROLE)
        role.permissions = ['taches_voir', 'roles_gerer']
        role.save(update_fields=['permissions'])
        utilisateur = CustomUser.objects.filter(username=NOM_COMPTE).first()
        cree = utilisateur is None
        if cree:
            utilisateur = CustomUser.objects.create(
                username=NOM_COMPTE, email=f'{NOM_COMPTE}@demo.local', company=societe,
                role_legacy=CustomUser.ROLE_ADMIN, role=role)
        if not cree and (utilisateur.company_id != societe.pk or utilisateur.role_id != role.pk):
            utilisateur.company, utilisateur.role = societe, role
            utilisateur.save(update_fields=['company', 'role'])
        mot_de_passe = os.environ.get(VARIABLE_MOT_DE_PASSE)
        if mot_de_passe:
            utilisateur.set_password(mot_de_passe)
            utilisateur.save(update_fields=['password'])
        elif cree:
            utilisateur.set_unusable_password()
            utilisateur.save(update_fields=['password'])
            self.stdout.write(f'Mot de passe non posé : définir {VARIABLE_MOT_DE_PASSE} puis relancer.')
        return utilisateur

    def _deja_seme(self, utilisateur):
        return (Projet.all_objects.filter(company_id=utilisateur.company_id, proprietaire=utilisateur).exists()
                or Tache.all_objects.filter(company_id=utilisateur.company_id, proprietaire=utilisateur).exists())

    def _effacer(self, utilisateur):
        from apps.records.models import Activity
        services_donnees.tout_effacer(utilisateur)
        Activity.objects.filter(company_id=utilisateur.company_id, created_by=utilisateur).delete()

    def handle(self, *args, **options):
        # La garde AVANT tout accès base (aucune transaction ouverte, aucune requête).
        if _production():
            raise CommandError("seed_taches_demo est refusé en production (DEBUG faux ou réglages de production).")
        with transaction.atomic():
            self._semer(options)

    def _semer(self, options):
        jour, heure = self._lire(options)
        utilisateur = self._compte()
        if self._deja_seme(utilisateur):
            if not options['reinitialiser']:
                self.stdout.write(self.style.WARNING(
                    f'{NOM_COMPTE} est déjà semé : rien à faire (--reinitialiser pour rejouer).'))
                return
            self._effacer(utilisateur)
        if options['vide']:
            self.stdout.write(self.style.SUCCESS(f'{NOM_COMPTE} : compte sans tâche.'))
            return
        scenario = Scenario(utilisateur, jour - datetime.timedelta(days=options['absence']), heure,
                            options['historique'])
        scenario.creer_projets()
        scenario.taches_des_projets()
        scenario.reservoir()
        scenario.a_revoir()
        scenario.reserve()
        scenario.a_trier()
        scenario.reglages()
        scenario.jours_passes()
        scenario.nuit_du_jour()
        scenario.jour_du_scenario()
        if options['rendez_vous']:
            scenario.rendez_vous(utilisateur)
        # Les gestes « Annuler » du semis n'appartiennent pas à la démonstration (la pile démarre vide).
        GesteAnnulable.objects.filter(company_id=utilisateur.company_id, proprietaire=utilisateur).delete()
        self.stdout.write(self.style.SUCCESS(f'{NOM_COMPTE} : journée du {scenario.jour.isoformat()} semée.'))
