"""Formes partagées de l'app `taches`, sérialisées UNE seule fois (reference/api.md §1).

ITEM, TACHE, TACHE_ECRITE, PROJET, PROPOSITION, LIEN, RENDEZ_VOUS : chaque vue de F2-F4 rend ces
classes, jamais une copie ; leurs champs déclarés sont aussi le schéma OpenAPI des réponses.

Ce qu'une forme ne calcule pas seule est CALCULÉ par l'appelant et passé dans le contexte
(`contexte(calculs={(type, id): {...}})`) : explication, motif, raison, rang du contexte,
essentielle, prevue_au_plan, peut_cloturer d'un ITEM ; a_planifier, compteurs, sante,
focus_semaine d'un PROJET ; texte et boutons d'une PROPOSITION ; libellé du lien d'une activité.
La forme ne lit jamais la base pour eux. Les objets sont chargés par `charger_items(qs)` /
`charger_taches(qs)` : aucune requête par ligne.

Requête « assistant » (`contexte(assistant=True)`) : titres et noms par `nom_pour(…, 'assistant')`,
`notes` jamais servies, rendez-vous titrés « Rendez-vous » (api.md §0) ; d'une tâche ou d'un projet
confidentiel, aucun contenu (`_masque`, regles.md §8).
"""
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.taches.choix import Frequence, LienEtat, StatutRappel, StatutTache
from apps.taches.confidentialite import ASSISTANT, ECRAN, est_confidentielle, nom_pour
from apps.taches.entrees import HeureServie
from apps.taches.models.taches import Tache
from apps.taches.moteur.recurrence import libelle_regle
from apps.taches.selectors.liens import url_de_cible

TACHE = 'tache'
ACTIVITE = 'activite'
PROJET = 'projet'
PROPOSITION = 'proposition'
FORMAT_HEURE = '%H:%M'
TITRE_RENDEZ_VOUS_ASSISTANT = 'Rendez-vous'
LIBELLE_LEAD_EFFACE = 'Lead effacé'
#: Une routine (puce « routine », comptée 0 au rythme) : quotidienne ou jours ouvrés, intervalle 1.
FREQUENCES_ROUTINE = frozenset({Frequence.QUOTIDIEN, Frequence.JOURS_OUVRES})
#: Statuts d'une tâche qui ne bloquent plus une autre (invariant 6).
STATUTS_CLOS = frozenset({StatutTache.FAIT, StatutTache.ANNULE})
#: États d'un lien dont le libellé est servi (invariant 23 ; « Lead effacé » si `efface`).
ETATS_LIBELLE_SERVI = frozenset({LienEtat.OK, LienEtat.EFFACE})

CHARGEMENT_LIGNE = (
    'projet', 'section', 'parent', 'parent__projet', 'recurrence', 'content_type',
    'bloquee_par', 'bloquee_par__projet', 'bloquee_par__parent', 'bloquee_par__parent__projet')


def contexte(*, assistant=False, reglages=None, calculs=None, agendas=None):
    """Contexte des formes. `calculs` : `{(type, id): {champ: valeur}}` ; `agendas` :
    `{agenda_id: libellé}` des RENDEZ_VOUS ; `reglages` : la `ReglagesRythme` déjà lue."""
    return {'assistant': bool(assistant), 'reglages': reglages,
            'calculs': dict(calculs or {}), 'agendas': dict(agendas or {})}


def _enfants_charges():
    return Prefetch('enfants', queryset=Tache.objects.select_related(*CHARGEMENT_LIGNE).prefetch_related(
        'rappel_set', 'elementchecklist_set', 'enfants'))


def charger_items(qs):
    """Tout ce qu'un ITEM lit, en une poignée de requêtes (jamais une par ligne)."""
    return qs.select_related(*CHARGEMENT_LIGNE).prefetch_related(
        'rappel_set', 'elementchecklist_set', _enfants_charges())


def charger_taches(qs):
    """Tout ce qu'une TACHE (fiche) lit, en une poignée de requêtes."""
    return charger_items(qs).prefetch_related('etiquettetache_set__etiquette')


def _heure(valeur):
    return valeur.strftime(FORMAT_HEURE) if valeur is not None else None


def _date(valeur):
    return valeur.isoformat() if valeur is not None else None


def _cible_de(content_type):
    return f'{content_type.app_label}.{content_type.model}' if content_type is not None else None


def lien(cible, id, libelle, etat):
    """Une forme LIEN (dict) ; l'adresse vient des gabarits, servie seulement si `etat` = ok."""
    servi = etat in ETATS_LIBELLE_SERVI
    return {'cible': cible, 'id': id, 'libelle': (libelle or '') if servi else '',
            'url': url_de_cible(cible, id) if etat == LienEtat.OK else None, 'etat': etat}


def lien_de_tache(tache):
    """LIEN d'une tâche (`None` sans lien) depuis son état STOCKÉ (la fiche le revérifie avant)."""
    if tache.content_type_id is None or tache.object_id is None:
        return None
    libelle = LIBELLE_LEAD_EFFACE if tache.lien_etat == LienEtat.EFFACE else tache.lien_libelle
    return lien(_cible_de(tache.content_type), tache.object_id, libelle, tache.lien_etat)


class _FormeSerializer(serializers.Serializer):
    """Base : usage du contexte et calculs de l'appelant."""

    def _usage(self):
        return ASSISTANT if self.context.get('assistant') else ECRAN

    def _calcul(self, type_, pk, champ, defaut):
        return self.context.get('calculs', {}).get((type_, pk), {}).get(champ, defaut)

    def _masque(self, obj):
        """Vrai sous l'en-tête assistant pour une tâche ou un projet confidentiel : aucun contenu
        (check-list, `en_attente_de`, lien ERP, étape, étiquettes, texte du projet) ne part
        (reference/regles.md §8). Les champs restent déclarés : seules les valeurs sont vidées."""
        return bool(self.context.get('assistant')) and est_confidentielle(obj)


# --- Petites formes imbriquées (schéma ; les valeurs sont des dict) ----------------------------

class ProjetCourtSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nom = serializers.CharField(allow_null=True)
    couleur = serializers.CharField()
    priorite = serializers.IntegerField()


class SectionCourteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nom = serializers.CharField()


class RaisonSerializer(serializers.Serializer):
    code = serializers.CharField()
    texte = serializers.CharField()


class RappelCourtSerializer(serializers.Serializer):
    jour = serializers.DateField()
    heure = serializers.CharField()


class LienSerializer(serializers.Serializer):
    """Forme LIEN (api.md §1)."""
    cible = serializers.CharField()
    id = serializers.IntegerField()
    libelle = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_null=True)
    etat = serializers.CharField(allow_blank=True)  # une valeur de LienEtat


class CompteChecklistSerializer(serializers.Serializer):
    faits = serializers.IntegerField()
    total = serializers.IntegerField()


class CompteSousTachesSerializer(serializers.Serializer):
    faites = serializers.IntegerField()
    total = serializers.IntegerField()


class TacheCourteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    titre = serializers.CharField(allow_null=True)


class EtiquetteCourteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nom = serializers.CharField()
    couleur = serializers.CharField()


class ElementChecklistFormeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    libelle = serializers.CharField()
    fait = serializers.BooleanField()
    rang = serializers.IntegerField()


class RappelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    jour = serializers.DateField()
    heure = HeureServie(format=FORMAT_HEURE)
    ancre = serializers.CharField(allow_blank=True)
    decalage_jours = serializers.IntegerField()
    statut = serializers.CharField()


class RappelEcritSerializer(RappelSerializer):
    """Le rappel posé par une écriture (`rappels/`, `repeter/`) : + `hors_fenetre`."""
    hors_fenetre = serializers.BooleanField(default=False)


class RecurrenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    frequence = serializers.CharField()
    intervalle = serializers.IntegerField()
    jours_semaine = serializers.CharField()
    jour_du_mois = serializers.IntegerField(allow_null=True)
    rang_dans_mois = serializers.IntegerField(allow_null=True)
    mode = serializers.CharField()
    date_debut = serializers.DateField()
    date_fin = serializers.DateField(allow_null=True)
    actif = serializers.BooleanField()
    libelle = serializers.CharField(allow_blank=True)


class AvertissementSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


# --- ITEM ---------------------------------------------------------------------------------------

class ItemSerializer(_FormeSerializer):
    """Forme ITEM : une tâche (`Tache`) OU une activité ERP (`records.Activity`, `type:"activite"`,
    champs sans objet nuls ou faux, `lock_version:null`)."""

    type = serializers.SerializerMethodField()
    id = serializers.IntegerField()
    titre = serializers.SerializerMethodField()
    statut = serializers.CharField()
    projet = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(allow_null=True)
    priorite = serializers.IntegerField()
    jour_prevu = serializers.DateField(allow_null=True)
    moment = serializers.CharField(allow_blank=True)
    heure_debut = HeureServie(format=FORMAT_HEURE, allow_null=True)
    echeance = serializers.DateField(allow_null=True)
    echeance_heure = HeureServie(format=FORMAT_HEURE, allow_null=True)
    quelque_jour = serializers.BooleanField()
    estimation_minutes = serializers.IntegerField(allow_null=True)
    reports = serializers.IntegerField()
    rang = serializers.SerializerMethodField()
    motif = serializers.SerializerMethodField()
    raison = serializers.SerializerMethodField()
    explication = serializers.SerializerMethodField()
    rappel = serializers.SerializerMethodField()
    lien = serializers.SerializerMethodField()
    checklist = serializers.SerializerMethodField()
    sous_taches = serializers.SerializerMethodField()
    recurrente = serializers.SerializerMethodField()
    routine = serializers.SerializerMethodField()
    jalon = serializers.BooleanField()
    bloquee_par = serializers.SerializerMethodField()
    en_attente_de = serializers.CharField(allow_blank=True)
    essentielle = serializers.SerializerMethodField()
    prevue_au_plan = serializers.SerializerMethodField()
    confidentiel = serializers.BooleanField()
    confidentielle = serializers.SerializerMethodField()
    source = serializers.CharField(allow_null=True)
    peut_cloturer = serializers.SerializerMethodField()
    a_notes = serializers.SerializerMethodField()
    fait_le = serializers.DateTimeField(allow_null=True)
    lock_version = serializers.IntegerField(allow_null=True)

    def to_representation(self, instance):
        if not isinstance(instance, Tache):
            return self._activite(instance)
        donnees = super().to_representation(instance)
        if self._masque(instance):
            donnees['en_attente_de'] = ''
        return donnees

    def _du_contexte(self, obj, champ, defaut):
        return self._calcul(TACHE, obj.pk, champ, defaut)

    @extend_schema_field(serializers.CharField())  # 'tache' ici, 'activite' pour une activité
    def get_type(self, obj):
        return TACHE

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_titre(self, obj):
        return nom_pour(obj, self._usage(), self.context.get('reglages'))

    @extend_schema_field(ProjetCourtSerializer(allow_null=True))
    def get_projet(self, obj):
        if obj.projet_id is None:
            return None
        projet = obj.projet
        return {'id': projet.pk, 'nom': nom_pour(projet, self._usage(), self.context.get('reglages')),
                'couleur': projet.couleur, 'priorite': projet.priorite}

    @extend_schema_field(SectionCourteSerializer(allow_null=True))
    def get_section(self, obj):
        if not obj.section_id:
            return None
        return {'id': obj.section.pk, 'nom': '' if self._masque(obj) else obj.section.nom}

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_rang(self, obj):
        return self._du_contexte(obj, 'rang', obj.rang_projet)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_motif(self, obj):
        return self._du_contexte(obj, 'motif', None)

    @extend_schema_field(RaisonSerializer(allow_null=True))
    def get_raison(self, obj):
        return self._du_contexte(obj, 'raison', None)

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_explication(self, obj):
        return self._du_contexte(obj, 'explication', '')

    @extend_schema_field(RappelCourtSerializer(allow_null=True))
    def get_rappel(self, obj):
        attente = [r for r in obj.rappel_set.all() if r.statut == StatutRappel.EN_ATTENTE]
        if not attente:
            return None
        prochain = min(attente, key=lambda r: (r.jour, r.heure))
        return {'jour': _date(prochain.jour), 'heure': _heure(prochain.heure)}

    @extend_schema_field(LienSerializer(allow_null=True))
    def get_lien(self, obj):
        return None if self._masque(obj) else lien_de_tache(obj)

    @extend_schema_field(CompteChecklistSerializer(allow_null=True))
    def get_checklist(self, obj):
        elements = list(obj.elementchecklist_set.all())
        if not elements:
            return None
        return {'faits': sum(1 for e in elements if e.fait), 'total': len(elements)}

    @extend_schema_field(CompteSousTachesSerializer(allow_null=True))
    def get_sous_taches(self, obj):
        enfants = [e for e in obj.enfants.all() if not e.is_deleted]
        if not enfants:
            return None
        return {'faites': sum(1 for e in enfants if e.statut == StatutTache.FAIT), 'total': len(enfants)}

    @extend_schema_field(serializers.BooleanField())
    def get_recurrente(self, obj):
        return obj.recurrence_id is not None

    @extend_schema_field(serializers.BooleanField())
    def get_routine(self, obj):
        regle = obj.recurrence if obj.recurrence_id else None
        return bool(regle and regle.frequence in FREQUENCES_ROUTINE and regle.intervalle == 1)

    @extend_schema_field(TacheCourteSerializer(allow_null=True))
    def get_bloquee_par(self, obj):
        prerequis = obj.bloquee_par if obj.bloquee_par_id else None
        if prerequis is None or prerequis.is_deleted or prerequis.statut in STATUTS_CLOS:
            return None
        return {'id': prerequis.pk,
                'titre': nom_pour(prerequis, self._usage(), self.context.get('reglages'))}

    @extend_schema_field(serializers.BooleanField())
    def get_essentielle(self, obj):
        return bool(self._du_contexte(obj, 'essentielle', False))

    @extend_schema_field(serializers.BooleanField())
    def get_prevue_au_plan(self, obj):
        return bool(self._du_contexte(obj, 'prevue_au_plan', False))

    @extend_schema_field(serializers.BooleanField())
    def get_confidentielle(self, obj):
        return est_confidentielle(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_peut_cloturer(self, obj):
        return bool(self._du_contexte(obj, 'peut_cloturer', True))

    @extend_schema_field(serializers.BooleanField())
    def get_a_notes(self, obj):
        """L'indice « note » de la ligne, lu de la colonne déjà chargée ; jamais vrai sous l'en-tête
        assistant : les notes ne lui sont jamais servies, leur présence non plus (regles.md §8)."""
        return not self.context.get('assistant') and bool(obj.notes)

    def _lien_activite(self, activite):
        cible = _cible_de(getattr(activite, 'content_type', None))
        if cible is None or activite.object_id is None:
            return None
        libelle = self._calcul(ACTIVITE, activite.pk, 'lien_libelle', '')
        return lien(cible, activite.object_id, libelle, LienEtat.OK)

    def _activite(self, activite):
        """ITEM d'une activité ERP : mêmes clés, champs sans objet nuls ou faux."""
        calcul = self.context.get('calculs', {}).get((ACTIVITE, activite.pk), {})
        return {
            'type': ACTIVITE, 'id': activite.pk, 'titre': activite.summary,
            'statut': StatutTache.FAIT if activite.done else StatutTache.A_FAIRE,
            'projet': None, 'section': None, 'parent_id': None, 'priorite': 0,
            'jour_prevu': _date(activite.due_date), 'moment': '', 'heure_debut': None,
            'echeance': None, 'echeance_heure': None, 'quelque_jour': False,
            'estimation_minutes': None, 'reports': 0, 'rang': calcul.get('rang'),
            'motif': calcul.get('motif'), 'raison': calcul.get('raison'),
            'explication': calcul.get('explication', ''), 'rappel': None,
            'lien': self._lien_activite(activite), 'checklist': None, 'sous_taches': None,
            'recurrente': False, 'routine': False, 'jalon': False, 'bloquee_par': None,
            'en_attente_de': '', 'essentielle': bool(calcul.get('essentielle', False)),
            'prevue_au_plan': bool(calcul.get('prevue_au_plan', False)),
            'confidentiel': False, 'confidentielle': False, 'source': None,
            'peut_cloturer': bool(calcul.get('peut_cloturer', False)), 'a_notes': False,
            'fait_le': self.fields['fait_le'].to_representation(activite.done_at) if activite.done_at else None,
            'lock_version': None,
        }


# --- TACHE (fiche) ------------------------------------------------------------------------------

class TacheSerializer(ItemSerializer):
    """Forme TACHE = ITEM + champs de fiche (`updated_at` sert le bandeau de conflit)."""

    notes = serializers.SerializerMethodField()
    etiquettes = serializers.SerializerMethodField()
    elements_checklist = serializers.SerializerMethodField()
    enfants = serializers.SerializerMethodField()
    recurrence = serializers.SerializerMethodField()
    rappels = serializers.SerializerMethodField()
    triee_le = serializers.DateTimeField(allow_null=True)
    premier_jour_prevu = serializers.DateField(allow_null=True)
    reports_tranches = serializers.IntegerField()
    duree_reelle_minutes = serializers.IntegerField(allow_null=True)
    annule_le = serializers.DateTimeField(allow_null=True)
    occurrence_du = serializers.DateField(allow_null=True)
    activite_origine_id = serializers.IntegerField(allow_null=True)
    lien_verifie_le = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_notes(self, obj):
        return '' if self.context.get('assistant') else obj.notes

    @extend_schema_field(EtiquetteCourteSerializer(many=True))
    def get_etiquettes(self, obj):
        if self._masque(obj):
            return []
        etiquettes = sorted((lien_.etiquette for lien_ in obj.etiquettetache_set.all()), key=lambda e: e.nom_cle)
        return [{'id': e.pk, 'nom': e.nom, 'couleur': e.couleur} for e in etiquettes]

    @extend_schema_field(ElementChecklistFormeSerializer(many=True))
    def get_elements_checklist(self, obj):
        if self._masque(obj):
            return []  # le compte `checklist` reste servi
        elements = sorted(obj.elementchecklist_set.all(), key=lambda e: (e.rang, e.pk))
        return [{'id': e.pk, 'libelle': e.libelle, 'fait': e.fait, 'rang': e.rang} for e in elements]

    @extend_schema_field(ItemSerializer(many=True))
    def get_enfants(self, obj):
        enfants = sorted((e for e in obj.enfants.all() if not e.is_deleted),
                         key=lambda e: (e.rang_projet is None, e.rang_projet, e.pk))
        return ItemSerializer(enfants, many=True, context=self.context).data

    @extend_schema_field(RecurrenceSerializer(allow_null=True))
    def get_recurrence(self, obj):
        if obj.recurrence_id is None:
            return None
        regle = obj.recurrence
        return {'id': regle.pk, 'frequence': regle.frequence, 'intervalle': regle.intervalle,
                'jours_semaine': regle.jours_semaine, 'jour_du_mois': regle.jour_du_mois,
                'rang_dans_mois': regle.rang_dans_mois, 'mode': regle.mode,
                'date_debut': _date(regle.date_debut), 'date_fin': _date(regle.date_fin),
                'actif': regle.actif, 'libelle': libelle_regle(regle)}

    @extend_schema_field(RappelSerializer(many=True))
    def get_rappels(self, obj):
        rappels = sorted((r for r in obj.rappel_set.all() if r.statut != StatutRappel.ANNULE),
                         key=lambda r: (r.jour, r.heure, r.pk))
        return RappelSerializer(rappels, many=True).data


# --- TACHE_ECRITE, PROGRESSION ------------------------------------------------------------------

class DetailProgressionSerializer(serializers.Serializer):
    etapes = serializers.IntegerField()
    routines = serializers.IntegerField()
    micro_non_comptees = serializers.IntegerField()
    activites_closes = serializers.IntegerField()


class ProgressionSerializer(serializers.Serializer):
    """Forme PROGRESSION (api.md §1) : un dict calculé par le service du jour."""
    faites = serializers.IntegerField()
    detail = DetailProgressionSerializer()
    prevues = serializers.IntegerField()
    essentiel_faites = serializers.IntegerField()
    essentiel_prevues = serializers.IntegerField()
    plan_tenues = serializers.IntegerField()
    plan_lignes = serializers.IntegerField()
    minutes_prevues = serializers.IntegerField()
    sans_estimation = serializers.IntegerField()
    capacite_minutes = serializers.IntegerField()
    capacite_source = serializers.CharField()
    rendez_vous_minutes = serializers.IntegerField()
    disponible_minutes = serializers.IntegerField()
    activites_closes = serializers.IntegerField()
    activites = serializers.IntegerField()
    reprise = serializers.BooleanField()


class TacheEcriteSerializer(_FormeSerializer):
    """Forme TACHE_ECRITE, rendue par toute écriture d'une tâche. Instance = dict :
    `tache` (Tache), `suivante` (Tache|None, occurrence née), `projet_cree` (Projet|None),
    `rappel` (Rappel ou dict avec `hors_fenetre`, ou None), `question_titres`,
    `avertissements` ([{code, message}]), `progression` (dict|None), `geste_id`."""

    tache = TacheSerializer()
    suivante = TacheSerializer(allow_null=True)
    projet_cree = serializers.SerializerMethodField()
    rappel = RappelEcritSerializer(allow_null=True)
    question_titres = serializers.BooleanField()
    avertissements = AvertissementSerializer(many=True)
    progression = ProgressionSerializer(allow_null=True)
    geste_id = serializers.IntegerField(allow_null=True)

    @extend_schema_field(ProjetCourtSerializer(allow_null=True))
    def get_projet_cree(self, obj):
        projet = obj.get('projet_cree')
        if projet is None:
            return None
        return {'id': projet.pk, 'nom': nom_pour(projet, self._usage(), self.context.get('reglages')),
                'couleur': projet.couleur, 'priorite': projet.priorite}


def tache_ecrite(tache, *, suivante=None, projet_cree=None, rappel=None, question_titres=False,
                 avertissements=(), progression=None, geste_id=None):
    """L'instance (dict) d'une TACHE_ECRITE, toutes clés présentes."""
    return {'tache': tache, 'suivante': suivante, 'projet_cree': projet_cree, 'rappel': rappel,
            'question_titres': bool(question_titres), 'avertissements': list(avertissements),
            'progression': progression, 'geste_id': geste_id}


# --- PROJET -------------------------------------------------------------------------------------

#: Valeurs d'`affichage` tant que l'utilisateur n'a rien mémorisé (clés fermées, api.md §1).
AFFICHAGE_DEFAUT = {'vue': 'liste', 'tri': 'manuel', 'groupe': 'section', 'montrer_faites': False}
#: Textes d'un projet confidentiel jamais servis à l'assistant (reference/regles.md §8).
TEXTES_PROJET = ('objectif', 'domaine', 'issue', 'bilan')


class AffichageSerializer(serializers.Serializer):
    vue = serializers.CharField()  # liste, tableau ou chronologie
    tri = serializers.CharField()
    groupe = serializers.CharField()
    montrer_faites = serializers.BooleanField()


class ComptesProjetSerializer(serializers.Serializer):
    ouvertes = serializers.IntegerField()
    faites = serializers.IntegerField()


class SanteSerializer(serializers.Serializer):
    code = serializers.CharField()
    phrase = serializers.CharField()
    donnees = serializers.DictField()


class ProjetSerializer(_FormeSerializer):
    """Forme PROJET (api.md §1) ; `a_planifier`, `compteurs`, `sante`, `focus_semaine` calculés
    par l'appelant (`calculs[('projet', id)]`)."""

    id = serializers.IntegerField()
    nom = serializers.SerializerMethodField()
    objectif = serializers.CharField(allow_blank=True)
    icone = serializers.CharField(allow_blank=True)
    couleur = serializers.CharField()
    priorite = serializers.IntegerField()
    statut = serializers.CharField()
    statut_depuis = serializers.DateTimeField()
    domaine = serializers.CharField(allow_blank=True)
    date_debut = serializers.DateField(allow_null=True)
    echeance = serializers.DateField(allow_null=True)
    termine_le = serializers.DateTimeField(allow_null=True)
    issue = serializers.CharField(allow_blank=True)
    bilan = serializers.CharField(allow_blank=True)
    planification_le = serializers.DateTimeField(allow_null=True)
    rang = serializers.IntegerField()
    confidentiel = serializers.BooleanField()
    affichage = serializers.SerializerMethodField()
    a_planifier = serializers.SerializerMethodField()
    compteurs = serializers.SerializerMethodField()
    sante = serializers.SerializerMethodField()
    focus_semaine = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField()
    lock_version = serializers.IntegerField()

    def to_representation(self, instance):
        donnees = super().to_representation(instance)
        if self._masque(instance):
            for champ in TEXTES_PROJET:
                donnees[champ] = ''
        return donnees

    def _du_contexte(self, obj, champ, defaut):
        return self._calcul(PROJET, obj.pk, champ, defaut)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_nom(self, obj):
        return nom_pour(obj, self._usage(), self.context.get('reglages'))

    @extend_schema_field(AffichageSerializer())
    def get_affichage(self, obj):
        memorise = obj.affichage if isinstance(obj.affichage, dict) else {}
        return {cle: memorise.get(cle, defaut) for cle, defaut in AFFICHAGE_DEFAUT.items()}

    @extend_schema_field(serializers.BooleanField())
    def get_a_planifier(self, obj):
        return bool(self._du_contexte(obj, 'a_planifier', False))

    @extend_schema_field(ComptesProjetSerializer())
    def get_compteurs(self, obj):
        return self._du_contexte(obj, 'compteurs', {'ouvertes': 0, 'faites': 0})

    @extend_schema_field(SanteSerializer(many=True))
    def get_sante(self, obj):
        return list(self._du_contexte(obj, 'sante', []))

    @extend_schema_field(serializers.BooleanField())
    def get_focus_semaine(self, obj):
        return bool(self._du_contexte(obj, 'focus_semaine', False))


def projet_court(projet, *, assistant=False, reglages=None):
    """`{id, nom, couleur, priorite}` d'un projet (référence dans une liste, `projets_crees`)."""
    if projet is None:
        return None
    usage = ASSISTANT if assistant else ECRAN
    return {'id': projet.pk, 'nom': nom_pour(projet, usage, reglages),
            'couleur': projet.couleur, 'priorite': projet.priorite}


# --- PROPOSITION --------------------------------------------------------------------------------

class BoutonSerializer(serializers.Serializer):
    reponse = serializers.CharField()
    libelle = serializers.CharField()


class PropositionSerializer(_FormeSerializer):
    """Forme PROPOSITION : une carte à réponse (`IncitationCoach`) ; `texte` et `boutons`
    (`[(libellé, réponse)]` de `moteur.gabarits.boutons`) calculés par l'appelant."""

    id = serializers.IntegerField()
    type = serializers.CharField()
    cle = serializers.CharField(allow_blank=True)
    texte = serializers.SerializerMethodField()
    donnees = serializers.DictField()
    boutons = serializers.SerializerMethodField()
    expire_le = serializers.DateField(allow_null=True)

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_texte(self, obj):
        return self._calcul(PROPOSITION, obj.pk, 'texte', '')

    @extend_schema_field(BoutonSerializer(many=True))
    def get_boutons(self, obj):
        boutons = self._calcul(PROPOSITION, obj.pk, 'boutons', ())
        return [{'reponse': reponse, 'libelle': libelle} for libelle, reponse in boutons]


# --- RENDEZ_VOUS --------------------------------------------------------------------------------

class RendezVousSerializer(_FormeSerializer):
    """Forme RENDEZ_VOUS : un événement d'agenda externe (`moteur.ics.RendezVousPur`), lecture
    seule, jamais une tâche ; libellé de l'agenda par `contexte(agendas={id: libellé})`."""

    cle = serializers.CharField()
    agenda_id = serializers.IntegerField()
    agenda = serializers.SerializerMethodField()
    titre = serializers.SerializerMethodField()
    debut = serializers.DateTimeField()
    fin = serializers.DateTimeField()
    journee_entiere = serializers.BooleanField()

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_agenda(self, obj):
        return self.context.get('agendas', {}).get(obj.agenda_id, '')

    @extend_schema_field(serializers.CharField())
    def get_titre(self, obj):
        return TITRE_RENDEZ_VOUS_ASSISTANT if self.context.get('assistant') else obj.titre


def _prefixer_les_composants(espace):
    """Nom de composant OpenAPI `Taches<Nom>` pour chaque sérialiseur de ce module (`Meta.ref_name`,
    posé sur CHAQUE classe : un `Meta` hérité donnerait deux composants du même nom) — sinon
    « Projet », « Lien », « Rappel »… entreraient en collision avec ceux des autres apps."""
    for nom, objet in list(espace.items()):
        if isinstance(objet, type) and issubclass(objet, serializers.Serializer) \
                and objet.__module__ == __name__:
            objet.Meta = type('Meta', (), {'ref_name': 'Taches' + nom.removesuffix('Serializer')})


_prefixer_les_composants(globals())

#: Les formes, par nom de forme de reference/api.md §1 (lu par les schémas des vues et les tests).
FORMES = {
    'ITEM': ItemSerializer,
    'TACHE': TacheSerializer,
    'TACHE_ECRITE': TacheEcriteSerializer,
    'PROJET': ProjetSerializer,
    'PROPOSITION': PropositionSerializer,
    'LIEN': LienSerializer,
    'RENDEZ_VOUS': RendezVousSerializer,
    'PROGRESSION': ProgressionSerializer,
}
