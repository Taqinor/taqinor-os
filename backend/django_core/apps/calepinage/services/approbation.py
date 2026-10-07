"""CALX347 — la décision d'APPROBATION d'un calepinage (second regard interne).

LE CONSTAT
----------
Le module n'avait que deux codes (``calepinage_voir``/``calepinage_gerer``) :
« qui peut écrire » valait « qui peut valider », et ``services/feu_vert.py``
ne vérifiait qu'une visite technique — jamais une relecture interne de la
conception. Ce module porte la décision, et RIEN d'autre.

OÙ VIT LA DÉCISION
------------------
Dans le champ DÉDIÉ ``Calepinage.approbation`` (migration ``0013``), forme
``{etat, decide_par_id, decide_le, motif}`` — jamais dans
``Calepinage.resultat``, qui appartient au moteur et qu'une simulation réécrit.
``None`` = personne n'a encore décidé : c'est l'état de tout calepinage
existant, et la lecture le publie tel quel (``etat: null``), jamais comme un
refus ni comme un accord.

LA REVUE HUMAINE D'ABORD (Aurora l'impose avant la pièce d'exécution)
---------------------------------------------------------------------
Une conception qui porte ENCORE une valeur d'origine AUTOMATIQUE restée à
l'état de suggestion — pente LiDAR IGN (``zones[].pitchSuggestion``, CAL237 /
CALX29), hauteur OpenStreetMap (``buildings[].hauteurSuggestion``, CALX106) —
ne s'approuve PAS : le refus liste, champ par champ, ce qui attend une
acceptation humaine. Une suggestion VALIDÉE (la valeur a été reprise) ou
REFUSÉE (la saisie a été maintenue) est une décision humaine : elle ne bloque
plus. Toute autre clé ``…Suggestion`` d'un pan ou d'un bâtiment suit la même
règle — une source automatique future n'a rien à déclarer ici pour être
tenue.

La SOCIÉTÉ et l'AUTEUR viennent toujours du serveur (``calepinage`` borné par
le queryset du viewset, ``user`` de la requête) — jamais d'un corps.
"""
from __future__ import annotations

#: Les deux décisions possibles, et leur libellé français.
APPROUVE, REFUSE = 'approuve', 'refuse'
DECISIONS = {APPROUVE: 'approuvé', REFUSE: 'refusé'}

#: Clé, DANS la section ``presets`` des réglages société (CAL197), qui rend
#: l'approbation OBLIGATOIRE avant PUBLICATION (devis / pièces d'exécution ;
#: décision fondateur 07/10/2026 : plus à la retenue, ex-CALX348). Absente
#: ou différente de ``True`` ⇒ ``exigee: false`` : comportement d'aujourd'hui.
CLE_EXIGEE = 'approbation_exigee'

#: Les statuts d'une suggestion qui valent DÉCISION HUMAINE (patron
#: ``services/lidar_ign.py`` : ``validee``/``refusee``). Tout autre statut —
#: ``suggeree``, ou aucun — est une suggestion EN ATTENTE.
STATUTS_DECIDES = ('validee', 'refusee')

#: Suffixe des emplacements de suggestion dans le document ``roof_layout``.
SUFFIXE_SUGGESTION = 'Suggestion'

#: Les collections du document où une valeur automatique peut être suggérée.
COLLECTIONS = ('zones', 'buildings')

#: Les emplacements CONNUS : ``(collection, clé) -> (champ de valeur, libellé,
#: source, message)``. Une clé ``…Suggestion`` inconnue est tenue quand même
#: (règle générique) et nommée par sa propre clé. Les messages sont ceux du
#: contrat CALX334 (``refus_suggestions_en_attente``).
EMPLACEMENTS = {
    ('buildings', 'hauteurSuggestion'): (
        'hauteurM', 'Hauteur du bâtiment', 'OpenStreetMap',
        "Hauteur proposée par OpenStreetMap, jamais acceptée : acceptez-la "
        "ou saisissez-la avant d'approuver."),
}

#: ACAL65 (D-ACAL-19) — emplacements qui ne bloquent JAMAIS l'approbation :
#: la pente IGN est la pente du TERRAIN, jamais celle du pan.
EMPLACEMENTS_NON_BLOQUANTS = (('zones', 'pitchSuggestion'),)

__all__ = [
    'APPROUVE', 'REFUSE', 'DECISIONS', 'CLE_EXIGEE', 'ApprobationRefusee',
    'approbation_exigee', 'etat_approbation', 'decider', 'est_approuve',
]


class ApprobationRefusee(ValueError):
    """Refus métier — message français, champ fautif NOMMÉ.

    ``en_attente`` porte, quand le refus vient de suggestions non acceptées,
    la liste ``[{champ, libelle, source}]`` de ce qui attend un humain.
    """

    def __init__(self, message, *, champ='', en_attente=None):
        super().__init__(message)
        self.champ = champ
        self.en_attente = list(en_attente or [])

    def corps(self):
        """Le corps 400 du contrat CALX334 : UN message par champ fautif —
        chaque suggestion en attente sous SON chemin (``buildings[0].hauteurM``),
        sinon le champ refusé (``decision``, ``motif``)."""
        if self.en_attente:
            return {ligne['champ']: ligne['message']
                    for ligne in self.en_attente}
        return {self.champ or 'approbation': str(self)}


def _libelle_objet(objet, collection):
    nom = str(objet.get('label') or objet.get('id') or '').strip()
    genre = 'pan' if collection == 'zones' else 'bâtiment'
    return f'{genre} « {nom} »' if nom else f'{genre} sans nom'


def _suggestions_en_attente(roof_layout):
    """Les valeurs d'origine AUTOMATIQUE encore en attente d'un humain.

    Lecture PURE du document. Returns ``[{champ, libelle, source, cle,
    message}]`` — ``champ`` écrit ``<collection>[<rang>].<champ de valeur>``
    (rang dans la liste du document, forme du contrat CALX334) pour que
    l'écran désigne LE champ à accepter (règle fondateur du 08/09/2026).
    Liste vide = rien n'attend : la conception peut être approuvée.
    """
    document = roof_layout if isinstance(roof_layout, dict) else {}
    en_attente = []
    for collection in COLLECTIONS:
        objets = document.get(collection)
        if not isinstance(objets, list):
            continue
        for rang, objet in enumerate(objets):
            if not isinstance(objet, dict):
                continue
            for cle in sorted(objet):
                if not (isinstance(cle, str)
                        and cle.endswith(SUFFIXE_SUGGESTION)):
                    continue
                if (collection, cle) in EMPLACEMENTS_NON_BLOQUANTS:
                    continue
                suggestion = objet[cle]
                if not isinstance(suggestion, dict):
                    continue
                if suggestion.get('status') in STATUTS_DECIDES:
                    continue
                champ_valeur, libelle, source, message = EMPLACEMENTS.get(
                    (collection, cle), (
                        cle, cle, '',
                        f"Valeur « {cle} » d'origine automatique, jamais "
                        "acceptée : acceptez-la ou saisissez-la avant "
                        "d'approuver."))
                source = str(suggestion.get('source') or source or '').strip()
                en_attente.append({
                    'champ': f'{collection}[{rang}].{champ_valeur}',
                    'libelle': (f'{libelle} — '
                                f'{_libelle_objet(objet, collection)}'),
                    'source': source,
                    'cle': cle,
                    'message': message,
                })
    return en_attente


def approbation_exigee(company):
    """``True`` si la société exige l'approbation avant de publier (devis,
    pièces d'exécution — décision fondateur 07/10/2026 ; plus à la retenue). Lecture pure ; ``False`` par défaut (D12)."""
    from ..selectors import parametres_de_societe

    presets = parametres_de_societe(company).get('presets') or {}
    return presets.get(CLE_EXIGEE) is True


def _decideur(calepinage, decide_par_id):
    """``{id, nom_complet}`` du décideur, borné société, ou ``None``."""
    if not decide_par_id:
        return None
    from django.contrib.auth import get_user_model

    user = (get_user_model().objects
            .filter(pk=decide_par_id,
                    company_id=getattr(calepinage, 'company_id', None))
            .first())
    if user is None:
        return None
    nom = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return {'id': user.pk,
            'nom_complet': nom or getattr(user, 'username', '')}


def _decision(calepinage):
    decision = getattr(calepinage, 'approbation', None)
    return decision if isinstance(decision, dict) else {}


def _empreinte_approuvee(calepinage):
    """ACAL114 (D-ACAL-11) — l'empreinte IMPRIMÉE approuvée, ou ``''``."""
    valeur = _decision(calepinage).get('empreinte_approuvee')
    return valeur if isinstance(valeur, str) else ''


def approbation_perimee(calepinage):
    """ACAL114 — un ACCORD dont l'empreinte imprimée a changé depuis (ou
    donné avant le suivi d'empreinte : « à redécider ») est PÉRIMÉ."""
    if _decision(calepinage).get('etat') != APPROUVE:
        return False
    approuvee = _empreinte_approuvee(calepinage)
    return not approuvee or approuvee != (
        getattr(calepinage, 'layout_hash', '') or '')


def etat_approbation(calepinage):
    """``{etat, decide_par, decide_le, motif, exigee, perimee,
    empreinte_approuvee}`` — le contrat CALX334 (+ ACAL6/ACAL114).

    ``etat`` vaut ``None`` tant que personne n'a décidé ; ``exigee`` reflète
    le réglage société (jamais supposé) ; ``perimee`` dit qu'un accord ne
    couvre plus la conception imprimée d'aujourd'hui.
    """
    decision = _decision(calepinage)
    etat = decision.get('etat')
    etat = etat if etat in DECISIONS else None
    return {
        'etat': etat,
        'decide_par': (_decideur(calepinage, decision.get('decide_par_id'))
                       if etat else None),
        'decide_le': decision.get('decide_le') if etat else None,
        'motif': (decision.get('motif') or '') if etat else None,
        'exigee': approbation_exigee(getattr(calepinage, 'company', None)),
        'perimee': approbation_perimee(calepinage),
        'empreinte_approuvee': _empreinte_approuvee(calepinage) if etat else '',
    }


def est_approuve(calepinage, *, empreinte=None):
    """``True`` si la dernière décision est un ACCORD NON PÉRIMÉ.

    ACAL114 — ``empreinte`` (imprimée) : l'accord doit porter sur CETTE
    conception (ex. la variante qu'on retient, D-ACAL-2) ; absente, sur la
    conception courante du calepinage.
    """
    if _decision(calepinage).get('etat') != APPROUVE:
        return False
    approuvee = _empreinte_approuvee(calepinage)
    attendue = (empreinte if empreinte is not None
                else (getattr(calepinage, 'layout_hash', '') or ''))
    return bool(approuvee) and approuvee == attendue


#: ACAL114 (D-ACAL-19) — le statut DÉRIVÉ (lecture seule) et ses libellés.
STATUT_BROUILLON, STATUT_VALIDE, STATUT_PERIME = (
    'brouillon', 'valide', 'perime')
LIBELLES_STATUT = {STATUT_BROUILLON: 'Brouillon', STATUT_VALIDE: 'Validé',
                   STATUT_PERIME: 'Périmé'}


def statut_derive(calepinage):
    """``brouillon`` | ``valide`` (approuvé non périmé) | ``perime``
    (approuvé puis empreinte imprimée changée) — jamais stocké."""
    if est_approuve(calepinage):
        return STATUT_VALIDE
    if _decision(calepinage).get('etat') == APPROUVE:
        return STATUT_PERIME
    return STATUT_BROUILLON


def annoter_statut_derive(queryset):
    """ACAL114 — annote ``statut_derive`` (même règle que
    :func:`statut_derive`, en SQL) pour filtrer ``?statut=`` et ordonner."""
    from django.db.models import Case, CharField, F, Q, Value, When
    from django.db.models.fields.json import KeyTextTransform

    if 'statut_derive' in queryset.query.annotations:
        return queryset
    return (queryset
            .annotate(_appr_etat=KeyTextTransform('etat', 'approbation'),
                      _appr_empreinte=KeyTextTransform(
                          'empreinte_approuvee', 'approbation'))
            .annotate(statut_derive=Case(
                When(Q(_appr_etat=APPROUVE)
                     & Q(_appr_empreinte=F('layout_hash'))
                     & ~Q(_appr_empreinte=''),
                     then=Value(STATUT_VALIDE)),
                When(_appr_etat=APPROUVE, then=Value(STATUT_PERIME)),
                default=Value(STATUT_BROUILLON),
                output_field=CharField())))


def _valider(decision, motif, roof_layout):
    """Les trois refus, dans l'ordre où un relecteur les corrigerait."""
    if decision not in DECISIONS:
        raise ApprobationRefusee(
            "Décision inconnue : "
            f"« {decision if decision is not None else ''} ». Décisions "
            f"admises : {', '.join(DECISIONS)}.", champ='decision')
    motif = motif.strip() if isinstance(motif, str) else ''
    if decision == REFUSE and not motif:
        raise ApprobationRefusee(
            "Un refus d'approbation exige un motif : dites ce qui est à "
            "reprendre.", champ='motif')
    if decision == APPROUVE:
        en_attente = _suggestions_en_attente(roof_layout)
        if en_attente:
            champs = ', '.join(
                f"{ligne['champ']} ({ligne['libelle']}"
                + (f", source {ligne['source']}" if ligne['source'] else '')
                + ')' for ligne in en_attente)
            raise ApprobationRefusee(
                "Cette conception ne peut pas être approuvée : des valeurs "
                "d'origine automatique attendent encore une acceptation "
                f"humaine — {champs}. Acceptez-les ou refusez-les dans "
                "l'atelier, puis décidez.",
                champ=en_attente[0]['champ'], en_attente=en_attente)
        # ACAL114 — une conception VIDE (aucun pan, aucun contour) ne
        # s'approuve pas : il n'y a rien à relire.
        from .layout import layout_decrit_une_geometrie

        if not layout_decrit_une_geometrie(roof_layout):
            raise ApprobationRefusee(
                'Rien à approuver : dessinez la toiture',
                champ='roof_layout')
    return motif


def decider(calepinage, *, decision, motif='', user=None, maintenant=None):
    """Enregistre la décision d'approbation et la note au chatter.

    Args:
        calepinage: le calepinage, déjà borné société par l'appelant.
        decision: ``'approuve'`` ou ``'refuse'``.
        motif: obligatoire pour un refus, facultatif pour un accord.
        user: le décideur — posé côté serveur.
        maintenant: horodatage injectable (aware) ; ``timezone.now()`` sinon.

    Returns:
        ``etat_approbation(calepinage)`` après écriture.

    Raises:
        ApprobationRefusee: décision inconnue (``decision``), refus sans
            motif (``motif``), ou suggestions automatiques en attente (le
            champ du premier en attente, la liste complète dans
            ``en_attente``). RIEN n'est écrit dans ces trois cas.
    """
    from django.utils import timezone

    from .verrou import verifier_ecriture_autorisee

    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture.
    verifier_ecriture_autorisee(calepinage, champ='approbation')
    motif = _valider(decision, motif,
                     getattr(calepinage, 'roof_layout', None))
    if decision == APPROUVE:
        # ACAL303 (D-ACAL-11) — SÉPARATION DES TÂCHES : qui a conçu ou porte
        # la conception ne l'approuve pas (un REFUS reste admis). RIEN n'est
        # écrit.
        _refuser_auto_approbation(calepinage, user)
    # ACAL172 (D-ACAL-9) — un ACCORD lit le verdict électrique : bloquant ⇒
    # refus nommé, rien n'est écrit ; indéterminé ⇒ accord AVEC avertissement.
    avertissement = (_verdict_electrique_avant_accord(calepinage)
                     if decision == APPROUVE else '')
    horodatage = maintenant or timezone.now()
    calepinage.approbation = {
        'etat': decision,
        'decide_par_id': getattr(user, 'pk', None),
        'decide_le': horodatage.isoformat(),
        'motif': motif,
        # ACAL114 (D-ACAL-11) — l'accord porte sur l'empreinte IMPRIMÉE
        # d'aujourd'hui : qu'elle change, et l'accord est périmé.
        'empreinte_approuvee': getattr(calepinage, 'layout_hash', '') or '',
    }
    calepinage.save(update_fields=['approbation', 'updated_at'])

    from .journal import noter

    texte = f"Conception {DECISIONS[decision]} (approbation)"
    if motif:
        texte += f" — motif : {motif}"
    if avertissement:
        texte += f" — {avertissement}"
    noter(calepinage, texte, user=user)
    return etat_approbation(calepinage)


#: ACAL303 — le refus d'une auto-approbation (champ ``decision``).
MESSAGE_AUTO_APPROBATION = (
    "Vous avez conçu ou portez cette conception : l'approbation revient à "
    "un autre relecteur.")


def _concepteurs(calepinage):
    """Les comptes qui ONT CONÇU ou PORTENT la conception : l'auteur du
    calepinage, son responsable, l'auteur de sa DERNIÈRE version."""
    from ..models import CalepinageVersion

    ids = {getattr(calepinage, 'cree_par_id', None),
           getattr(calepinage, 'responsable_id', None)}
    if getattr(calepinage, 'pk', None):
        derniere = (CalepinageVersion.objects
                    .filter(calepinage_id=calepinage.pk)
                    .order_by('-created_at', '-id')
                    .values_list('cree_par_id', flat=True).first())
        ids.add(derniere)
    ids.discard(None)
    return ids


def _refuser_auto_approbation(calepinage, user):
    """ACAL303 — ``ApprobationRefusee`` (``decision``) quand ``user`` a conçu
    ou porte la conception."""
    if getattr(user, 'pk', None) in _concepteurs(calepinage):
        raise ApprobationRefusee(MESSAGE_AUTO_APPROBATION, champ='decision')


def _verdict_electrique_avant_accord(calepinage):
    """ACAL172 — refuse d'approuver une conception électriquement BLOQUÉE.

    Lit ``electrique.verdict_de_conception`` (la lecture unique des
    bloquants). Rend l'avertissement à consigner quand le verdict est
    indéterminé, ``''`` sinon.

    Raises:
        ApprobationRefusee: au moins un bloquant (champ ``electrique``).
    """
    from .electrique import TemperaturesInvalides, verdict_de_conception

    try:
        verdict = verdict_de_conception(calepinage)
    except TemperaturesInvalides as refus:
        # Lot 2 critique #19 — une saisie de températures incohérente est un
        # refus NOMMÉ (400), jamais un 500.
        raise ApprobationRefusee(
            "Cette conception ne peut pas être approuvée : " + str(refus),
            champ=getattr(refus, 'champ', '') or 'temperatures') from refus
    if verdict['bloquants']:
        raise ApprobationRefusee(
            "Cette conception ne peut pas être approuvée : verdict "
            "électrique bloquant — "
            + ' ; '.join(b['libelle'] for b in verdict['bloquants']),
            champ='electrique')
    if verdict['verdict'] == 'indetermine':
        return ("verdict électrique indéterminé : "
                + ' ; '.join(verdict['manquantes']))
    return ''
