"""Données personnelles de l'app `taches` (reference/donnees.md §5 « effacement 09-08 », §8 ; socle §8).

- `effacer_cibles(company_id, leads=, clients=)` : le cœur des DEUX portes d'effacement 09-08 (le
  récepteur `lead_erased` de `receivers.py`, le fournisseur DSR `dsr.effacer_sujet`) : les tâches
  liées perdent leur libellé (`lien_libelle` vidé, `lien_etat = efface` → « Lead effacé »), les
  suggestions du lead sont supprimées. Le titre tapé par l'utilisateur reste (dit dans Vie privée).
- `exporter(user)` : « Mes données », les 21 modèles du compte (supprimés non purgés compris) ;
  jamais l'empreinte d'un jeton ni l'adresse d'un agenda externe (elle vaut une clé).
- `tout_effacer(user)` : « Tout effacer », suppression DURE des lignes du couple (société,
  utilisateur) ; les jetons disparaissent avec (révoqués).
"""
import datetime
from collections import Counter
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.taches.choix import CibleLiable, LienEtat, StatutTache
from apps.taches.models.agenda import AgendaExterne
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.journee import LignePlanJour, PlanJour
from apps.taches.models.presence import JetonAcces, ReglagesSociete
from apps.taches.models.projets import ModeleProjet, Projet, RevueProjet, Section
from apps.taches.models.rythme import IncitationCoach, Preference, ReglagesRythme
from apps.taches.models.taches import (
    ElementChecklist,
    Etiquette,
    EtiquetteTache,
    Rappel,
    RegleRecurrence,
    Tache,
    VueEnregistree,
)
from apps.taches.serializers.formes import ProjetSerializer, TacheSerializer, charger_taches, contexte

#: Les 21 modèles, sous les clés de `mes_donnees.json`, dans son ordre.
MODELES = {
    'projet': Projet, 'section': Section, 'tache': Tache, 'element_checklist': ElementChecklist,
    'etiquette': Etiquette, 'etiquette_tache': EtiquetteTache, 'regle_recurrence': RegleRecurrence,
    'plan_jour': PlanJour, 'ligne_plan_jour': LignePlanJour, 'reglages_rythme': ReglagesRythme,
    'preference': Preference, 'incitation_coach': IncitationCoach, 'rappel': Rappel,
    'jeton_acces': JetonAcces, 'geste_annulable': GesteAnnulable, 'vue_enregistree': VueEnregistree,
    'modele_projet': ModeleProjet, 'revue_projet': RevueProjet, 'suggestion_tache': SuggestionTache,
    'agenda_externe': AgendaExterne, 'reglages_societe': ReglagesSociete,
}
#: Chemin vers le compte d'un modèle qui ne porte pas `proprietaire` lui-même.
CHEMIN_COMPTE = {
    'section': 'projet__proprietaire',
    'element_checklist': 'tache__proprietaire',
    'etiquette_tache': 'tache__proprietaire',
    'ligne_plan_jour': 'plan__proprietaire',
    'reglages_societe': 'modifie_par',  # réglage de la SOCIÉTÉ : seule la trace du compte est à lui
}
#: Colonnes servies, LISTE BLANCHE, des modèles qui portent un secret (empreinte, adresse-clé).
CHAMPS_PERMIS = {
    'jeton_acces': ('id', 'usage', 'prefixe', 'revoque_le'),
    'agenda_externe': ('id', 'hote', 'libelle'),
}
#: Colonnes jamais servies d'une ligne brute (le compte et la société sont ceux de la requête).
CHAMPS_EXCLUS = frozenset({'company', 'proprietaire'})
#: Ordre de la suppression dure : les feuilles d'abord, les contenants ensuite.
ORDRE_EFFACEMENT = (
    'geste_annulable', 'suggestion_tache', 'rappel', 'etiquette_tache', 'element_checklist',
    'ligne_plan_jour', 'revue_projet', 'modele_projet', 'tache', 'section', 'projet', 'etiquette',
    'regle_recurrence', 'plan_jour', 'reglages_rythme', 'preference', 'incitation_coach', 'jeton_acces',
    'vue_enregistree', 'agenda_externe')
_CLE_DU_MODELE = {modele._meta.label: cle for cle, modele in MODELES.items()}
OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)


# --- Effacement 09-08 ---------------------------------------------------------------------------

def _type_de(cible):
    app_label, modele = cible.split('.', 1)
    return ContentType.objects.get_by_natural_key(app_label, modele)


def effacer_cibles(company_id, *, leads=(), clients=()):
    """Efface ce que `taches` garde de ces leads et clients, pour TOUS les comptes de la société :
    libellé des tâches liées vidé et état `efface`, suggestions des leads supprimées (dur).
    Idempotent ; rend le nombre de lignes touchées."""
    leads, clients = [int(pk) for pk in leads or ()], [int(pk) for pk in clients or ()]
    if not (leads or clients):
        return 0
    liees = (Q(content_type=_type_de(CibleLiable.LEAD), object_id__in=leads)
             | Q(content_type=_type_de(CibleLiable.CLIENT), object_id__in=clients))
    taches = (Tache.all_objects.filter(company_id=company_id).filter(liees)
              .update(lien_libelle='', lien_etat=LienEtat.EFFACE))
    suggestions = 0
    if leads:
        suggestions, _ = SuggestionTache.objects.filter(company_id=company_id, lead_ref__in=leads).delete()
    return taches + suggestions


# --- Mes données --------------------------------------------------------------------------------

def lignes_du_compte(cle, user):
    """Toutes les lignes du modèle `cle` appartenant à `user` dans sa société (supprimées comprises)."""
    modele = MODELES[cle]
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return modele._base_manager.none()
    chemin = CHEMIN_COMPTE.get(cle, 'proprietaire')
    return modele._base_manager.filter(company_id=user.company_id, **{chemin: user})


def _valeur(valeur):
    if isinstance(valeur, datetime.datetime):
        return timezone.localtime(valeur).isoformat() if timezone.is_aware(valeur) else valeur.isoformat()
    if isinstance(valeur, (datetime.date, datetime.time)):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    return valeur


def _ligne(cle, instance):
    """Une ligne brute : colonnes du modèle (clé étrangère = `<nom>_id`), liste blanche si secret."""
    noms = CHAMPS_PERMIS.get(cle) or [
        field.name for field in instance._meta.concrete_fields if field.name not in CHAMPS_EXCLUS]
    ligne = {}
    for nom in noms:
        field = instance._meta.get_field(nom)
        ligne[field.attname] = _valeur(getattr(instance, field.attname))
    return ligne


def _projets(user):
    """Forme PROJET de chaque projet (compteurs calculés sur ses tâches vivantes)."""
    projets = list(lignes_du_compte('projet', user).order_by('pk'))
    comptes = (Tache.objects.filter(company_id=user.company_id, proprietaire=user, projet__in=projets)
               .values('projet_id')
               .annotate(ouvertes=Count('pk', filter=Q(statut__in=OUVERTES)),
                         faites=Count('pk', filter=Q(statut=StatutTache.FAIT))))
    calculs = {('projet', ligne['projet_id']): {'compteurs': {'ouvertes': ligne['ouvertes'],
                                                              'faites': ligne['faites']}}
               for ligne in comptes}
    return ProjetSerializer(projets, many=True, context=contexte(calculs=calculs)).data


def _taches(user):
    taches = charger_taches(lignes_du_compte('tache', user).order_by('pk'))
    return TacheSerializer(taches, many=True, context=contexte()).data


def exporter(user, *, maintenant=None):
    """« Mes données » de `user` (`mes_donnees.json`) : une liste par modèle, sous sa clé."""
    instant = timezone.localtime(maintenant or timezone.now())
    donnees = {'exporte_le': instant.isoformat(timespec='seconds')}
    for cle in MODELES:
        if cle == 'projet':
            donnees[cle] = _projets(user)
        elif cle == 'tache':
            donnees[cle] = _taches(user)
        else:
            donnees[cle] = [_ligne(cle, instance) for instance in lignes_du_compte(cle, user).order_by('pk')]
    return donnees


# --- Tout effacer -------------------------------------------------------------------------------

def tout_effacer(user):
    """Suppression DURE de toutes les lignes `taches` de `user` dans sa société (une transaction) →
    `{"effacees": {clé: nombre}}` (`tout_effacer.json`, clés à zéro omises). Le réglage de la
    société garde sa valeur ; seule la trace « modifié par » de `user` est retirée."""
    effacees = Counter()
    with transaction.atomic():
        for cle in ORDRE_EFFACEMENT:
            _total, par_modele = lignes_du_compte(cle, user).delete()
            for label, nombre in par_modele.items():
                if nombre and label in _CLE_DU_MODELE:
                    effacees[_CLE_DU_MODELE[label]] += nombre
        traces = lignes_du_compte('reglages_societe', user).update(modifie_par=None)
        if traces:
            effacees['reglages_societe'] += traces
    return {'effacees': dict(effacees)}
