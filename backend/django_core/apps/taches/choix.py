"""Énumérations fermées de l'app `taches` (reference/donnees.md §1).

Source unique des valeurs techniques : modèles, sérialiseurs, moteur et front
(marqueur `source-choix:`) y puisent, jamais une liste recopiée.
"""
from django.db import models


class Priorite(models.IntegerChoices):
    AUCUNE = 0, 'Aucune'
    BASSE = 1, 'Basse'
    MOYENNE = 2, 'Moyenne'
    HAUTE = 3, 'Haute'


class StatutTache(models.TextChoices):
    A_FAIRE = 'a_faire', 'À faire'
    EN_ATTENTE = 'en_attente', 'En attente de…'
    FAIT = 'fait', 'Fait'
    ANNULE = 'annule', 'Abandonnée'


class StatutProjet(models.TextChoices):
    ACTIF = 'actif', 'Actif'
    EN_PAUSE = 'en_pause', 'En pause'
    TERMINE = 'termine', 'Terminé'
    ARCHIVE = 'archive', 'Archivé'


class IssueProjet(models.TextChoices):
    AUCUNE = '', 'Aucune'
    ATTEINT = 'atteint', 'Atteint'
    ABANDONNE = 'abandonne', 'Abandonné'


class Moment(models.TextChoices):
    AUCUN = '', 'Aucun'
    MATIN = 'matin', 'Matin'
    APRES_MIDI = 'apres_midi', 'Après-midi'
    SOIR = 'soir', 'Ce soir'


class Creneau(models.TextChoices):
    AUCUN = '', 'Aucun'
    MATIN = 'matin', 'Matin'  # avant 12 h
    APRES_MIDI = 'apres_midi', 'Après-midi'  # 12-16 h
    FIN_JOURNEE = 'fin_journee', 'Fin de journée'  # dès 16 h


class Source(models.TextChoices):
    MANUEL = 'manuel', 'Manuel'
    RAPIDE = 'rapide', 'Saisie rapide'
    ASSISTANT = 'assistant', 'Assistant'
    CAPTURE = 'capture', 'Capture'
    ACTIVITE = 'activite', 'Activité'
    RECURRENCE = 'recurrence', 'Récurrence'
    MODELE = 'modele', 'Modèle'
    SUGGESTION = 'suggestion', 'Suggestion'


class Couleur(models.TextChoices):
    TERRE = 'terre', 'Terre'
    AMBRE = 'ambre', 'Ambre'
    OLIVE = 'olive', 'Olive'
    VERT = 'vert', 'Vert'
    MENTHE = 'menthe', 'Menthe'
    CIEL = 'ciel', 'Ciel'
    BLEU = 'bleu', 'Bleu'
    INDIGO = 'indigo', 'Indigo'
    PRUNE = 'prune', 'Prune'
    ROSE = 'rose', 'Rose'


class Visibilite(models.TextChoices):
    PRIVE = 'prive', 'Privé'


class LienEtat(models.TextChoices):
    AUCUN = '', 'Aucun'
    OK = 'ok', 'Disponible'
    ARCHIVE = 'archive', 'Archivé'
    INTROUVABLE = 'introuvable', 'Introuvable'
    INACCESSIBLE = 'inaccessible', 'Inaccessible'
    EFFACE = 'efface', 'Effacé'


class CibleLiable(models.TextChoices):
    LEAD = 'crm.lead', 'Lead'
    CLIENT = 'crm.client', 'Client'
    DEVIS = 'ventes.devis', 'Devis'


class Frequence(models.TextChoices):
    QUOTIDIEN = 'quotidien', 'Tous les jours'
    JOURS_OUVRES = 'jours_ouvres', 'Les jours ouvrés'
    HEBDO = 'hebdo', 'Toutes les semaines'
    MENSUEL = 'mensuel', 'Tous les mois'
    ANNUEL = 'annuel', 'Tous les ans'


class ModeRecurrence(models.TextChoices):
    CALENDRIER = 'calendrier', 'Selon le calendrier'
    APRES_FAIT = 'apres_fait', 'Après avoir fait'


class ModeRythme(models.TextChoices):
    POUSSER = 'pousser', 'En faire plus'
    TENIR = 'tenir', 'Garder ce rythme'
    LIBRE = 'libre', 'Sans objectif'


class SourceObjectif(models.TextChoices):
    DEFAUT = 'defaut', 'Par défaut'
    CALCULE = 'calcule', 'Calculé'
    ACCEPTE = 'accepte', 'Accepté'
    DIT = 'dit', 'Dit'
    LIBRE = 'libre', 'Libre'


class CapaciteSource(models.TextChoices):
    DEFAUT = 'defaut', 'Par défaut'
    HISTORIQUE = 'historique', 'Historique'
    REGLAGE = 'reglage', 'Réglage'


class StatutJour(models.TextChoices):
    CONGE = 'conge', 'Congé'
    NON_OUVRE = 'non_ouvre', 'Non ouvré'
    SANS_DONNEES = 'sans_donnees', 'Sans données'
    EVALUE = 'evalue', 'Évalué'


class SectionJournee(models.TextChoices):
    ESSENTIEL = 'essentiel', 'Essentiel'
    JOURNEE = 'journee', 'Prévu'
    CE_SOIR = 'ce_soir', 'Ce soir'
    PROPOSE = 'propose', 'Proposé pour aujourd\'hui'
    A_DECIDER = 'a_decider', 'À revoir'
    EN_ATTENTE = 'en_attente', 'En attente'
    FAITES = 'faites', 'Faites'


class MotifRevoir(models.TextChoices):
    REPORTEE_3_FOIS = 'reportee_3_fois', 'Reportée 3 fois'
    RETARD_ANCIEN = 'retard_ancien', 'En retard depuis plus de 7 jours'
    ACTIVITE_PASSEE = 'activite_passee', 'Activité passée'


class RaisonPropose(models.TextChoices):
    """Raison de chaque ligne de « Proposé », dans cet ordre."""
    RETARD = 'retard', 'Prévue hier'
    ECHEANCE_PASSEE = 'echeance_passee', 'Échéance passée'
    ECHEANCE_PROCHE = 'echeance_proche', 'Échéance proche'
    PROCHAINE_ACTION = 'prochaine_action', 'Prochaine action du projet'
    ACTION_SUIVANTE = 'action_suivante', 'Action suivante du projet'


class Decision(models.TextChoices):
    AUJOURDHUI = 'aujourdhui', 'Aujourd\'hui'
    GARDER = 'garder', 'Garder'
    PROCHAIN_JOUR_OUVRE = 'prochain_jour_ouvre', 'Reporter au prochain jour ouvré'
    JOUR = 'jour', 'Un jour précis'
    UN_JOUR = 'un_jour', 'En réserve'
    ABANDONNER = 'abandonner', 'Abandonner'


class FamilleObligation(models.TextChoices):
    VISITE = 'visite', 'Visite'
    POSE = 'pose', 'Pose'
    INTERVENTION = 'intervention', 'Intervention'
    TOUCHES = 'touches', 'Suivi des relances'


class CarteDuMoment(models.TextChoices):
    """Ordre de priorité des cartes."""
    RETOUR = 'retour', 'Retour'
    BILAN_HIER = 'bilan_hier', 'Bilan d\'hier'
    GARDER = 'garder', 'Garder'
    ALLEGER = 'alleger', 'Alléger'
    FAIRE_BILAN = 'faire_bilan', 'Faire le bilan'
    RYTHME = 'rythme', 'Rythme'
    PAUSE = 'pause', 'Pause'
    REVELATION = 'revelation', 'Révélation'


class CodeSante(models.TextChoices):
    SANS_PROCHAINE_ACTION = 'sans_prochaine_action', 'Sans prochaine action'
    A_L_ARRET = 'a_l_arret', 'À l\'arrêt'
    ECHEANCE_MENACEE = 'echeance_menacee', 'Échéance menacée'
    NEGLIGE = 'neglige', 'Négligé'
    TOUT_FAIT = 'tout_fait', 'Tout est fait'


class TypeJeton(models.TextChoices):
    JOUR = 'jour', 'Jour'
    HEURE = 'heure', 'Heure'
    MOMENT = 'moment', 'Moment'
    ECHEANCE = 'echeance', 'Échéance'
    QUELQUE_JOUR = 'quelque_jour', 'Quelque jour'
    PROJET = 'projet', 'Projet'
    SECTION = 'section', 'Étape'
    PRIORITE = 'priorite', 'Priorité'
    ETIQUETTE = 'etiquette', 'Étiquette'
    DUREE = 'duree', 'Durée'
    RECURRENCE = 'recurrence', 'Récurrence'
    RAPPEL = 'rappel', 'Rappel'


class AlerteSaisie(models.TextChoices):
    # `deux_<type>` (un type de jeton lu deux fois) : voir `alerte_deux`.
    DATE_PASSEE = 'date_passee', 'Date passée'
    HEURE_PASSEE = 'heure_passee', 'Heure passée'
    PLUSIEURS_PROJETS = 'plusieurs_projets', 'Plusieurs projets'
    PROJET_ARCHIVE = 'projet_archive', 'Projet archivé'
    DATE_INVALIDE = 'date_invalide', 'Date invalide'
    DUREE_HORS_BORNES = 'duree_hors_bornes', 'Durée hors bornes'


PREFIXE_ALERTE_DEUX = 'deux_'


def alerte_deux(type_jeton):
    """Code d'alerte `deux_<type>` pour un `TypeJeton` lu deux fois."""
    return PREFIXE_ALERTE_DEUX + str(type_jeton)


class StatutRappel(models.TextChoices):
    EN_ATTENTE = 'en_attente', 'En attente'
    ENVOYE = 'envoye', 'Envoyé'
    MANQUE = 'manque', 'Manqué'
    ANNULE = 'annule', 'Annulé'


class SourceRappel(models.TextChoices):
    MANUEL = 'manuel', 'Manuel'
    REPETITION = 'repetition', 'Répétition'
    BLOC = 'bloc', 'Bloc'


class AncreRappel(models.TextChoices):
    AUCUNE = '', 'Aucune'
    JOUR_PREVU = 'jour_prevu', 'Jour prévu'
    ECHEANCE = 'echeance', 'Échéance'


class UsageJeton(models.TextChoices):
    CAPTURE = 'capture', 'Capture'  # préfixe tqc_
    FLUX = 'flux', 'Flux'  # préfixe tqf_
    TUILE = 'tuile', 'Tuile'  # préfixe tqt_


class TypeIncitationPush(models.TextChoices):
    PLAN_MATIN = 'plan_matin', 'Aujourd\'hui'
    BILAN_SOIR = 'bilan_soir', 'Bilan du soir'
    REVUE_SEMAINE = 'revue_semaine', 'Revue de la semaine'
    RELANCE = 'relance', 'Message de {heure}'


class TypeIncitationEcran(models.TextChoices):
    PROPOSITION_PALIER = 'proposition_palier', 'Proposition de palier'
    DERIVE_TENIR = 'derive_tenir', 'Dérive du rythme tenu'
    GARDE_TAILLE = 'garde_taille', 'Garde de taille'
    CONSTAT = 'constat', 'Constat'
    PAUSE = 'pause', 'Pause'
    RETOUR = 'retour', 'Retour'
    REVELATION = 'revelation', 'Révélation'


class CanalIncitation(models.TextChoices):
    PUSH = 'push', 'Notification'
    ECRAN = 'ecran', 'Écran'


class ReponseIncitation(models.TextChoices):
    AUCUNE = '', 'Aucune'
    OUI = 'oui', 'Oui'
    PAS_MAINTENANT = 'pas_maintenant', 'Pas maintenant'
    GARDER = 'garder', 'Garder'
    GARDER_CE_RYTHME = 'garder_ce_rythme', 'Garder ce rythme'
    PASSER = 'passer', 'Passer'
    TACHES_CHANGEES = 'taches_changees', 'Tâches changées'
    REACTIVER = 'reactiver', 'Réactiver'
    REMETTRE_DANS_PROPOSE = 'remettre_dans_propose', 'Remettre dans Proposé'
    UNE_PAR_UNE = 'une_par_une', 'Une par une'
    OK = 'ok', 'OK'
    IGNOREE = 'ignoree', 'Ignorée'  # posée par la tâche nocturne seule
    EXPIREE = 'expiree', 'Expirée'  # posée par la tâche nocturne seule


class FamilleSuggestion(models.TextChoices):
    DEVIS_ACCEPTE = 'devis_accepte', 'Devis accepté'
    CHANTIER_RECEPTIONNE = 'chantier_receptionne', 'Chantier réceptionné'
    CHANTIER_ANNULE = 'chantier_annule', 'Chantier annulé'
    VISITE_VALIDEE = 'visite_validee', 'Visite validée'  # éteinte


class StatutSuggestion(models.TextChoices):
    PROPOSEE = 'proposee', 'Proposée'
    ACCEPTEE = 'acceptee', 'Acceptée'
    REFUSEE = 'refusee', 'Refusée'
    RETIREE = 'retiree', 'Retirée'


class DecisionRevue(models.TextChoices):
    AUCUNE = '', 'Aucune'
    GARDER = 'garder', 'Garder'
    PAUSE = 'pause', 'Mettre en pause'
    TERMINER = 'terminer', 'Terminer'
    PASSE = 'passe', 'Suivant'


class SourcePreference(models.TextChoices):
    ECRAN = 'ecran', 'Écran'
    COPILOTE = 'copilote', 'Copilote'
    CARTE = 'carte', 'Carte'


class ClePreference(models.TextChoices):
    CAPACITE_JOUR_MIN = 'capacite_jour_min', 'Capacité du jour (minutes)'
    JOURS_TRAVAILLES = 'jours_travailles', 'Jours travaillés'
    JOURS_COURTS = 'jours_courts', 'Jours courts'
    CONGES = 'conges', 'Congés'
    HEURE_MATIN = 'heure_matin', 'Heure du plan du matin'
    RELANCE_JOUR = 'relance_jour', 'Heure de la relance'
    HEURE_SOIR = 'heure_soir', 'Heure du bilan du soir'
    HEURE_LIMITE = 'heure_limite', 'Heure limite'
    REVUE_SEMAINE = 'revue_semaine', 'Jour de la revue de semaine'
    ESSENTIEL_LE_MATIN = 'essentiel_le_matin', 'Choisir l\'essentiel le matin'
    NOTE_LIBRE = 'note_libre', 'Notes libres'


class EtatAgendaExterne(models.TextChoices):
    AUCUN = '', 'Aucun'
    OK = 'ok', 'Connecté'
    PAS_HTTPS = 'pas_https', 'Adresse non sécurisée'
    ADRESSE_PRIVEE = 'adresse_privee', 'Adresse non publique'
    INJOIGNABLE = 'injoignable', 'Injoignable'
    TROP_GRANDE = 'trop_grande', 'Agenda trop volumineux'
    DELAI = 'delai', 'Délai dépassé'
    ILLISIBLE = 'illisible', 'Illisible'
