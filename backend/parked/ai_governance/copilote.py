"""NTAI8/NTAI9 — Copilote de fiche : « résume-moi ça » et « et maintenant ? ».

Deux services jumeaux, posés sur la MÊME résolution de cible que le chatter
générique (``records.serializers.resolve_target`` : le type est whitelisté et
l'objet appartient forcément à la société de l'appelant) :

  * :func:`resumer_fiche` (NTAI8) — un résumé FR de la situation, construit à
    partir d'une ALLOWLIST de champs + du fil d'activité ;
  * :func:`prochaines_actions` (NTAI9) — 1 à 3 actions priorisées, produites
    par l'heuristique DÉTERMINISTE existante (``recommend_next_action``), pas
    par le modèle : le LLM ne fait qu'enrichir la RAISON.

INVARIANTS communs :

  * **Aucune écriture.** Les deux services LISENT. Une action proposée porte,
    quand elle existe, la clé d'une action du catalogue ``apps.agent`` — dont
    l'exécution reste un geste explicite (propose → confirme).
  * **Allowlist de champs.** On ne sérialise jamais un objet entier : un champ
    interne ajouté demain au modèle ne peut pas fuiter tout seul.
  * **NO-OP-safe.** Sans clé LLM, le résumé dégrade proprement (503 + « lecture
    manuelle ») et les actions restent entièrement disponibles (l'heuristique
    ne coûte rien et ne dépend d'aucun fournisseur).
"""
from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

from core.ai.registry import is_capability_configured

from .services import (AiCopiloteUnavailable, aplatir_fil, exiger_feature,
                       prompt_effectif)

# ─────────────────────────────────────────────────────────────────────────────
# Cibles et champs autorisés
# ─────────────────────────────────────────────────────────────────────────────

#: Types de fiche sur lesquels le copilote a le droit de travailler. Plus
#: restreint que le chatter (39 cibles) : ce sont les fiches où « résumer » et
#: « prochaine action » ont un sens métier.
RESUME_CONTENT_TYPES = (
    'crm.lead',
    'crm.client',
    'ventes.devis',
    'installations.installation',
    'sav.ticket',
    'contrats.contrat',
)

#: ALLOWLIST de noms de champs lisibles sur une fiche. Un nom absent du modèle
#: est simplement ignoré : la liste est donc partagée par tous les types sans
#: risque. RIEN hors de cette liste n'est lu — c'est ce qui garantit qu'aucune
#: donnée interne (prix d'achat, marge, coût) ne peut atteindre un prompt.
RESUME_CHAMPS = (
    'reference', 'numero', 'nom', 'prenom', 'societe', 'raison_sociale',
    'ville', 'adresse_ville', 'telephone_affiche',
    'statut', 'stage', 'stade', 'etat', 'priorite', 'canal', 'origine',
    'type_installation', 'type_client', 'objet', 'titre', 'sujet',
    'description_courte', 'motif_perte',
    'date_creation', 'date_relance', 'relance_date', 'date_debut', 'date_fin',
    'date_echeance', 'date_signature', 'date_envoi',
    'montant_ttc', 'montant_total_ttc', 'total_ttc', 'montant_mensuel',
    'puissance_kwc', 'surface_m2',
)

#: Termes qui ne doivent JAMAIS apparaître dans les faits transmis (garde de
#: dernier recours, testée : elle rougit si quelqu'un élargit l'allowlist
#: ci-dessus sans y penser).
FAITS_TERMES_INTERDITS = ('prix_achat', 'marge', 'cout_interne', 'coût interne')

#: Libellés FR des types de fiche (pour le contexte donné au modèle).
LABELS_FICHE = {
    'crm.lead': 'lead commercial',
    'crm.client': 'client',
    'ventes.devis': 'devis',
    'installations.installation': 'chantier / installation',
    'sav.ticket': 'ticket SAV',
    'contrats.contrat': 'contrat',
}

RESUME_SYSTEM = (
    "Tu es l'assistant d'un installateur solaire au Maroc. À partir des seuls "
    "faits et du fil ci-dessous, rédige en français un résumé de 3 à 5 phrases "
    "de la SITUATION de cette fiche : où on en est, ce qui s'est passé "
    "récemment, ce qui reste en suspens. N'invente aucun chiffre, aucune date "
    "et aucun engagement qui ne figure pas dans les données fournies."
)


def _valeur_lisible(valeur):
    """Rend un champ lisible pour un prompt (jamais un objet ORM brut)."""
    if valeur is None or valeur == '':
        return ''
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    if isinstance(valeur, datetime):
        return timezone.localtime(valeur).strftime('%Y-%m-%d')
    if isinstance(valeur, date):
        return valeur.strftime('%Y-%m-%d')
    return str(valeur)[:160]


def faits_fiche(cible) -> dict:
    """Faits transmissibles d'une fiche — ALLOWLIST stricte.

    Ne lit QUE :data:`RESUME_CHAMPS`, et seulement des valeurs scalaires. Un
    champ relationnel est rendu par son ``str()`` (jamais par ses propres
    champs), ce qui interdit la descente en cascade dans des données internes.
    """
    faits = {}
    for champ in RESUME_CHAMPS:
        if not hasattr(cible, champ):
            continue
        try:
            valeur = getattr(cible, champ)
        except Exception:  # noqa: BLE001 — une propriété en erreur n'est pas un fait
            continue
        if callable(valeur):
            continue
        lisible = _valeur_lisible(valeur)
        if lisible:
            faits[champ] = lisible
    return faits


def faits_en_texte(faits: dict) -> str:
    """Met les faits à plat, et REFUSE d'émettre un terme interdit.

    Lève ``ValueError`` — garde de dernier recours contre une régression qui
    élargirait l'allowlist (même patron que la garde `prix_achat` de NTAI13)."""
    texte = '\n'.join(f'{cle} : {valeur}' for cle, valeur in faits.items())
    minuscules = texte.lower()
    fuite = [t for t in FAITS_TERMES_INTERDITS if t in minuscules]
    if fuite:
        raise ValueError(
            f'Donnée interne interdite dans les faits de fiche : {sorted(fuite)}')
    return texte


def resoudre_fiche(company, content_type, object_id):
    """``(ct, objet, label)`` ou :class:`AiCopiloteUnavailable` (400).

    Double barrière : le type doit être dans :data:`RESUME_CONTENT_TYPES` ET
    passer ``resolve_target`` (qui vérifie l'appartenance à la société)."""
    from apps.records.serializers import resolve_target

    label = str(content_type or '').strip().lower()
    if label not in RESUME_CONTENT_TYPES:
        raise AiCopiloteUnavailable(
            'Type de fiche non pris en charge par le copilote — attendu : '
            + ', '.join(RESUME_CONTENT_TYPES) + '.')
    try:
        ct, cible = resolve_target(label, object_id, company)
    except ValueError as exc:
        raise AiCopiloteUnavailable(str(exc))
    return ct, cible, label


# ─────────────────────────────────────────────────────────────────────────────
# NTAI8 — Résumer cette fiche
# ─────────────────────────────────────────────────────────────────────────────

def resumer_fiche(*, company, content_type, object_id, max_tokens=400) -> dict:
    """NTAI8 — Résumé FR de la situation d'une fiche. LECTURE SEULE.

    Sans clé LLM : lève ``AiCopiloteUnavailable(configured=False)`` → 503 douce
    « résumé indisponible, lecture manuelle », sans aucun appel réseau.
    """
    exiger_feature(company, 'ai.resume_fiche')

    from core.ai.services import summarize_thread

    ct, cible, label = resoudre_fiche(company, content_type, object_id)
    faits = faits_fiche(cible)
    texte_faits = faits_en_texte(faits)

    if not is_capability_configured('llm'):
        raise AiCopiloteUnavailable(
            'Résumé indisponible (aucun fournisseur LLM configuré) — '
            'lecture manuelle de la fiche.', configured=False)

    fil = aplatir_fil(company=company, content_type=ct, object_id=cible.pk)
    consigne = prompt_effectif(company, 'ai.resume_fiche.system', RESUME_SYSTEM)
    contexte = (f'{consigne}\n\n'
                f'{LABELS_FICHE.get(label, label)} « {str(cible)[:120]} »\n'
                f'{texte_faits}')
    # Un fil VIDE n'est pas une fiche vide : les faits suffisent à résumer.
    messages = fil or [{'texte': texte_faits or str(cible)[:120]}]

    synthese = summarize_thread(
        messages, context=contexte, max_tokens=max_tokens)
    if not synthese.configured:
        raise AiCopiloteUnavailable(
            'Résumé indisponible (aucun fournisseur LLM configuré) — '
            'lecture manuelle de la fiche.', configured=False)
    if not synthese.available:
        raise AiCopiloteUnavailable(
            "Le fournisseur n'a pas produit de résumé exploitable.")

    return {
        'content_type': f'{ct.app_label}.{ct.model}',
        'object_id': cible.pk,
        'libelle': str(cible)[:160],
        'resume': synthese.summary,
        'faits': faits,
        'entrees_fil': len(fil),
        'source': synthese.source,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI9 — Les 3 prochaines actions
# ─────────────────────────────────────────────────────────────────────────────
#
# L'ACTION vient de l'heuristique DÉTERMINISTE de la fondation
# (``core.ai.services.recommend_next_action``) — jamais du modèle : une action
# inventée hors catalogue serait inexécutable. Le LLM, quand il est là, ne
# réécrit que la RAISON de l'action de tête.

#: Statuts de devis (rule #4 du dépôt : chaîne brouillon → envoyé → accepté →
#: refusé → expiré, préservée à l'identique — ce ne sont PAS des étapes de
#: pipeline, qui elles viennent de STAGES.py).
DEVIS_STATUT_ENVOYE = 'envoye'
DEVIS_STATUT_ACCEPTE = 'accepte'

#: Correspondance action → clé du catalogue ``apps.agent``, PAR TYPE DE FICHE.
#: Une clé absente du registre au moment de l'appel n'est pas proposée : mieux
#: vaut une action sans bouton qu'un bouton mort.
ACTIONS_CATALOGUE = {
    ('crm.lead', 'relancer'): 'crm.lead.whatsapp_prepare',
    ('crm.lead', 'qualifier'): 'crm.lead.update',
    ('crm.lead', 'envoyer_devis'): 'ventes.devis.creer_auto',
    ('ventes.devis', 'facturer'): 'ventes.devis.generer_facture',
    ('ventes.devis', 'planifier'): 'installations.intervention.planifier_visite',
    ('installations.installation', 'planifier'):
        'installations.intervention.planifier_visite',
    ('sav.ticket', 'cloturer'): 'sav.ticket.update',
}

#: Nombre d'actions renvoyées au maximum (le plan en demande 1 à 3).
ACTIONS_MAX = 3


def _jours_depuis(valeur, *, today=None) -> int | None:
    """Nombre de jours écoulés depuis une date/datetime (ou ``None``)."""
    if valeur is None:
        return None
    today = today or timezone.localdate()
    if isinstance(valeur, datetime):
        valeur = timezone.localtime(valeur).date()
    if not isinstance(valeur, date):
        return None
    return (today - valeur).days


def _derniere_date_fil(fil) -> date | None:
    """Date de l'entrée de fil la plus récente (le fil est ordonné ancien→neuf)."""
    for entree in reversed(fil or []):
        brut = str(entree.get('date') or '')[:10]
        try:
            return date.fromisoformat(brut)
        except ValueError:
            continue
    return None


def faits_decision(cible, label, *, fil=None, today=None) -> dict:
    """FAITS normalisés attendus par ``recommend_next_action``.

    Construits depuis les champs PROPRES à la fiche (aucune lecture d'une autre
    app) : l'étape de pipeline vient de ``STAGES.py`` via ``apps.crm.stages``
    (jamais une chaîne codée en dur), les statuts de devis de la chaîne
    documentaire du dépôt.
    """
    today = today or timezone.localdate()
    facts = {'kind': label.split('.', 1)[-1]}

    jours = _jours_depuis(_derniere_date_fil(fil), today=today)
    if jours is None:
        jours = _jours_depuis(
            getattr(cible, 'updated_at', None) or getattr(
                cible, 'created_at', None), today=today)

    if label == 'crm.lead':
        from apps.crm.stages import (CONTACTED, FOLLOW_UP, QUOTE_SENT, SIGNED)

        stage = getattr(cible, 'stage', '') or ''
        facts['kind'] = 'lead'
        facts['stage'] = stage
        facts['has_open_quote'] = stage in (QUOTE_SENT, FOLLOW_UP)
        facts['quote_accepted'] = stage == SIGNED
        facts['qualified'] = stage in (CONTACTED, FOLLOW_UP, QUOTE_SENT)
        # Une relance DÉPASSÉE compte comme un contact en retard d'autant.
        retard = _jours_depuis(getattr(cible, 'relance_date', None),
                               today=today)
        if retard is not None and retard > 0:
            jours = max(jours or 0, retard)
    elif label == 'ventes.devis':
        statut = getattr(cible, 'statut', '') or ''
        facts['has_open_quote'] = statut == DEVIS_STATUT_ENVOYE
        facts['quote_accepted'] = statut == DEVIS_STATUT_ACCEPTE
    elif label == 'sav.ticket':
        statut = str(getattr(cible, 'statut', '') or '').lower()
        facts['ticket_resolu'] = statut in ('resolu', 'résolu', 'termine',
                                            'terminé')

    if jours is not None:
        facts['days_since_contact'] = jours
    return facts


def _candidats(facts: dict) -> list:
    """Toutes les actions DÉFENDABLES au vu des faits, priorité décroissante.

    Même table de décision que l'heuristique de la fondation (qui, elle, ne
    rend que la PREMIÈRE) : c'est ce qui permet d'en proposer 3 sans jamais en
    inventer une."""
    jours = facts.get('days_since_contact')
    jours_txt = int(jours) if isinstance(jours, (int, float)) else 0
    regles = [
        (facts.get('invoice_unpaid'), 'relancer', 'Relancer le paiement', 90,
         'Facture impayée'),
        (facts.get('work_done') and not facts.get('invoiced'), 'facturer',
         'Émettre la facture', 85, 'Travaux terminés, à facturer'),
        (facts.get('quote_accepted'), 'planifier',
         'Planifier une intervention', 80, 'Devis accepté'),
        (facts.get('has_open_quote') and jours_txt >= 3, 'relancer',
         'Relancer le client', 70, f'Devis en attente depuis {jours_txt} j'),
        (facts.get('kind') == 'lead' and facts.get('qualified')
         and not facts.get('has_open_quote'), 'envoyer_devis',
         'Envoyer le devis', 60, 'Lead qualifié sans devis'),
        (facts.get('kind') == 'lead' and not facts.get('qualified'),
         'qualifier', 'Qualifier le lead', 50, 'Lead à qualifier'),
        (facts.get('ticket_resolu'), 'cloturer', 'Clôturer', 45,
         'Ticket résolu, à clôturer'),
        (jours_txt >= 14, 'relancer', 'Relancer le client', 40,
         f'Sans contact depuis {jours_txt} j'),
    ]
    retenues = {}
    for actif, action, libelle, priorite, raison in regles:
        if not actif or action in retenues:
            continue
        retenues[action] = {
            'action': action, 'label': libelle, 'priorite': priorite,
            'raison': raison, 'source': 'heuristique',
        }
    return sorted(retenues.values(), key=lambda a: -a['priorite'])


def action_key_pour(label, action, user=None):
    """Clé du catalogue ``apps.agent`` pour ``(type de fiche, action)``.

    ``None`` si aucune correspondance, si l'action a disparu du catalogue, ou
    si l'utilisateur n'a pas le droit de l'exécuter — l'écran n'affiche alors
    pas de bouton, plutôt qu'un bouton qui échouerait."""
    cle = ACTIONS_CATALOGUE.get((label, action))
    if not cle:
        return None
    try:
        from apps.agent.registry import all_actions, for_user

        disponibles = for_user(user) if user is not None else all_actions()
        return cle if any(a.key == cle for a in disponibles) else None
    except Exception:  # noqa: BLE001 — un catalogue indisponible = pas de bouton
        return None


def prochaines_actions(*, company, content_type, object_id, user=None,
                       limit=ACTIONS_MAX, max_tokens=150) -> dict:
    """NTAI9 — 1 à 3 actions priorisées pour une fiche. LECTURE SEULE.

    Contrairement au résumé, ce service reste ENTIÈREMENT disponible sans clé
    LLM : l'heuristique est déterministe et gratuite. Le LLM, s'il est
    configuré, ne fait qu'enrichir la raison de l'action de tête.
    """
    exiger_feature(company, 'ai.prochaines_actions')

    from core.ai.services import recommend_next_action_ai

    ct, cible, label = resoudre_fiche(company, content_type, object_id)
    fil = aplatir_fil(company=company, content_type=ct, object_id=cible.pk)
    facts = faits_decision(cible, label, fil=fil)

    tete = recommend_next_action_ai(
        facts, context=f'{LABELS_FICHE.get(label, label)} '
                       f'« {str(cible)[:120]} »')
    actions = [{
        'action': tete.action, 'label': tete.label, 'priorite': tete.priority,
        'raison': tete.reason, 'source': tete.source,
    }]
    for candidat in _candidats(facts):
        if len(actions) >= max(1, int(limit or ACTIONS_MAX)):
            break
        if candidat['action'] == tete.action:
            continue
        actions.append(candidat)

    for entree in actions:
        entree['action_key'] = action_key_pour(label, entree['action'], user)

    return {
        'content_type': f'{ct.app_label}.{ct.model}',
        'object_id': cible.pk,
        'libelle': str(cible)[:160],
        'actions': actions,
        'faits': facts,
        # Contrat explicite : proposer n'est pas exécuter.
        'execute': False,
    }
