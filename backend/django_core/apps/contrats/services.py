"""Services d'écriture / d'orchestration de la Gestion des contrats.

Point d'entrée ÉCRITURE de l'app `contrats` (pendant lecture de
``selectors.py``). Conformément à la frontière cross-app (CLAUDE.md), toute
orchestration interne au contrat passe ici ; aucun import direct des
``models``/``views`` d'une autre app de domaine n'est fait depuis ce module.

Contenu :

- CONTRAT10 — **Génération du contrat par fusion (merge tokens)** :
  ``contexte_fusion`` / ``rendre_contrat`` construisent le texte final d'un
  contrat en fusionnant des jetons ``{{ jeton }}`` dans un gabarit (le corps du
  ``ModeleContrat`` ou un corps fourni). La fusion est volontairement
  DÉPENDANCE-LÉGÈRE : un simple remplacement de jetons par expression
  régulière (``re``) de la bibliothèque standard — aucun moteur de gabarit
  tiers, aucune exécution de code, pas d'injection possible.

- CONTRAT12 — **Machine d'états du cycle de vie + transitions gardées** :
  ``TRANSITIONS_AUTORISEES`` décrit le graphe d'états du ``Contrat.statut`` et
  ``changer_statut`` applique une transition en la gardant (transition permise,
  parties suffisantes pour finaliser). Voir ``machine_etats.py`` — réexporté
  ici pour garder un point d'entrée unique côté services.

- CONTRAT14 — **Workflow d'approbation interne** : ``lancer_workflow_approbation``
  instancie les ``EtapeApprobation`` d'un contrat à partir de la
  ``RegleApprobation`` la plus spécifique (CONTRAT13, via le sélecteur
  ``resoudre_regle_approbation``), et ``approuver_etape`` / ``rejeter_etape``
  font avancer le workflow étape après étape. Ces opérations gèrent uniquement
  les statuts LOCAUX des étapes (``en_attente`` / ``approuve`` / ``rejete``) et
  ne touchent JAMAIS au ``Contrat.statut`` (préservation des statuts).

- SCA35 — **Pilote « Contrat » du kit ``core.documents``** : ``changer_statut``
  (réexporté de ``machine_etats``) reste le SEUL point de mutation du statut ;
  ``Contrat.TRANSITIONS``/``transitions_permises``/``transition_permise``
  (``models.py``) exposent le MÊME graphe en lecture seule, au format attendu
  par ``core.documents.DocumentMetier`` — sans dupliquer la garde « ≥2 parties »
  du kit générique, absente du socle. ``rendre_contrat_pdf`` ci-dessous délègue
  déjà à ``core.pdf.render_pdf`` (ARC12), le MÊME point d'entrée que le hook du
  kit ``render_document_pdf`` (SCA33). Aucune numérotation ``core.numbering``
  n'est câblée sur ``Contrat.reference`` : c'est un champ libre saisi par
  l'appelant (import, gabarit, ou API) depuis toujours — ``Devis``/``Facture``/
  ``Avoir`` restent les seuls documents CLM à passer par la fabrique
  ``create_with_reference`` dans ce module (renouvellement, avoirs) ; wirer une
  numérotation forcée sur ``Contrat`` lui-même changerait son comportement
  (règle interdite pour ce pilote — voir ``docs/PLAN.md`` SCA35).
"""
import html as _html
import re
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.pdf import render_pdf

from .machine_etats import (  # noqa: F401 — réexport (point d'entrée services)
    TRANSITIONS_AUTORISEES,
    TransitionInterdite,
    changer_statut,
    statuts_suivants,
    transition_permise,
)

# ---------------------------------------------------------------------------
# ARC34 — émission automation générique sur transition de statut du Contrat
# ---------------------------------------------------------------------------
#
# Frontière : même précédent que ``gestion_projet.services`` (appel direct
# ``apps.automation.engine.evaluate()``, import FONCTION-LOCAL, chemin
# parallèle documenté dans automation/models.py). L'émission part du SERVICE
# (jamais du modèle) ; le couple (contrats.contrat, statut) est déclaré
# automatisable dans ``apps/contrats/platform.py`` (automation_state_fields).
# Le statut visé est le ``Contrat.Statut`` de DOMAINE, jamais STAGES.py.


def emettre_changement_statut_automation(contrat, *, ancien_statut, user=None):
    """ARC34 — évalue les règles no-code ``RECORD_STATE_CHANGE`` après une
    transition de statut RÉUSSIE du contrat. Best-effort : aucune erreur ne
    remonte (la transition, côté appelant, est déjà actée)."""
    if contrat.statut == ancien_statut:
        return
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType

        evaluate(
            TriggerType.RECORD_STATE_CHANGE, contrat, contrat.company,
            context={
                'model': 'contrats.contrat', 'field': 'statut',
                'old_value': ancien_statut, 'new_value': contrat.statut,
            },
            user=user)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


_changer_statut_machine = changer_statut


def changer_statut(contrat, statut_cible, *, persister=True, user=None):  # noqa: F811 — enveloppe ARC34 du réexport ci-dessus
    """ARC34 — enveloppe du point d'entrée services : applique la transition
    GARDÉE (``machine_etats.changer_statut`` — mêmes gardes, mêmes exceptions,
    comportement inchangé) puis émet le déclencheur automation générique sur un
    changement RÉELLEMENT persisté. Tous les appelants du service (vue
    ``changer-statut``, ``activer_si_eligible``, ``signer_contrat``) émettent
    donc sans modification. ``user`` (optionnel) est journalisé sur les runs."""
    ancien = contrat.statut
    _changer_statut_machine(contrat, statut_cible, persister=persister)
    if persister and contrat.statut != ancien:
        emettre_changement_statut_automation(
            contrat, ancien_statut=ancien, user=user)
    return contrat


# ---------------------------------------------------------------------------
# CONTRAT10 — Génération par fusion (merge tokens)
# ---------------------------------------------------------------------------

# Un jeton de fusion : ``{{ nom_du_jeton }}`` (espaces optionnels autour du nom).
# Le nom est limité à [A-Za-z0-9_.] pour rester prévisible et inoffensif.
_JETON_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def _fmt_montant(montant, devise):
    """Formate un montant + devise de façon stable (ex. ``12 500.00 MAD``)."""
    try:
        valeur = f"{montant:,.2f}".replace(",", " ")
    except (TypeError, ValueError):  # pragma: no cover - défensif
        valeur = str(montant)
    return f"{valeur} {devise}".strip()


def _fmt_date(valeur):
    """Date au format ISO (``AAAA-MM-JJ``) ou chaîne vide si absente."""
    return valeur.isoformat() if valeur else ""


def contexte_fusion(contrat):
    """Construit le dictionnaire de jetons de fusion d'un ``Contrat``.

    Les clés sont les noms de jetons disponibles dans un gabarit ; les valeurs
    sont des chaînes prêtes à l'affichage. Lecture seule : ne modifie jamais le
    contrat. Inclut les champs du contrat, un résumé des parties et la liste
    ordonnée des clauses résolues.
    """
    parties = list(contrat.parties.all().order_by("ordre", "id"))
    client = next(
        (p for p in parties if p.type_partie == p.TypePartie.CLIENT), None
    )
    prestataire = next(
        (p for p in parties if p.type_partie == p.TypePartie.PRESTATAIRE), None
    )

    lignes_parties = [
        f"- {p.nom}"
        + (f" ({p.fonction})" if p.fonction else "")
        + f" — {p.get_type_partie_display()}"
        for p in parties
    ]

    clauses = list(contrat.clauses_resolues.all().order_by("ordre", "id"))
    blocs_clauses = [
        f"{i}. {c.titre}\n{c.corps}" for i, c in enumerate(clauses, start=1)
    ]

    return {
        "reference": contrat.reference or "",
        "objet": contrat.objet or "",
        "type_contrat": contrat.get_type_contrat_display(),
        "statut": contrat.get_statut_display(),
        "montant": _fmt_montant(contrat.montant, contrat.devise),
        "devise": contrat.devise or "",
        "date_debut": _fmt_date(contrat.date_debut),
        "date_fin": _fmt_date(contrat.date_fin),
        "confidentialite": contrat.get_confidentialite_display(),
        # Parties
        "client": client.nom if client else "",
        "prestataire": prestataire.nom if prestataire else "",
        "parties": "\n".join(lignes_parties),
        # Clauses résolues (CONTRAT9)
        "clauses": "\n\n".join(blocs_clauses),
    }


def fusionner(gabarit, contexte):
    """Remplace chaque jeton ``{{ x }}`` du ``gabarit`` par ``contexte['x']``.

    Un jeton inconnu (absent du contexte) est rendu par une chaîne vide — on ne
    laisse jamais un ``{{ ... }}`` brut dans le rendu et on n'exécute jamais de
    code. Dépendance-légère : ``re`` de la bibliothèque standard uniquement.
    """
    if not gabarit:
        return ""

    def _remplacer(match):
        nom = match.group(1)
        valeur = contexte.get(nom, "")
        return str(valeur) if valeur is not None else ""

    return _JETON_RE.sub(_remplacer, gabarit)


def rendre_contrat(contrat, gabarit=None):
    """Rend le texte final d'un contrat par fusion de jetons.

    - ``gabarit`` : le corps-modèle à fusionner. Si ``None``, on tente le corps
      du ``ModeleContrat`` lié via ``contrat.modele`` (CONTRAT10 le pose), sinon
      on compose un corps par défaut à partir des clauses résolues.
    - Renvoie un dict ``{'gabarit', 'rendu', 'jetons'}`` : le gabarit utilisé,
      le texte fusionné, et le contexte de jetons (utile pour le débogage et le
      rendu PDF de CONTRAT11).

    Lecture seule : ne persiste rien.
    """
    contexte = contexte_fusion(contrat)

    if gabarit is None:
        modele = getattr(contrat, "modele", None)
        if modele is not None and modele.corps:
            gabarit = modele.corps
        else:
            gabarit = _gabarit_par_defaut(contexte)

    return {
        "gabarit": gabarit,
        "rendu": fusionner(gabarit, contexte),
        "jetons": contexte,
    }


# ---------------------------------------------------------------------------
# CONTRAT11 — Rendu PDF interne du contrat (hors /proposal)
# ---------------------------------------------------------------------------

def _contrat_html(contrat):
    """Construit le HTML interne (français) d'un contrat à partir de son rendu.

    Le texte fusionné (CONTRAT10) est échappé puis inséré dans un gabarit HTML
    sobre. Aucun jeton non résolu ni HTML utilisateur n'est interprété (tout est
    échappé) — pas d'injection possible.
    """
    rendu = rendre_contrat(contrat)["rendu"]
    corps = _html.escape(rendu).replace("\n", "<br/>")
    titre = _html.escape(contrat.objet or "Contrat")
    reference = _html.escape(contrat.reference or "")
    return (
        "<html><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:11pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;"
        "padding-bottom:6px;}"
        ".ref{color:#555;font-size:10pt;margin-bottom:18px;}"
        ".corps{white-space:normal;}"
        "</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<div class='ref'>Référence : {reference}</div>"
        f"<div class='corps'>{corps}</div>"
        "</body></html>"
    )


def rendre_contrat_pdf(contrat):
    """Rend un PDF INTERNE du contrat (bytes) — hors ``/proposal``.

    PDF de travail interne : ce N'EST PAS un PDF de devis client (``/proposal``
    reste l'unique chemin des PDF de devis). ARC12 — la plomberie WeasyPrint
    (import paresseux + ``write_pdf()``) est déléguée au service partagé
    ``core.pdf.render_pdf`` ; le GABARIT HTML de ``_contrat_html`` reste
    STRICTEMENT identique, donc le rendu est inchangé à l'octet près.

    SCA35 — c'est le MÊME point de délégation que le hook du kit
    ``core.documents.render_document_pdf`` (SCA33) : ce dernier n'est qu'un
    fin emballage de ``core.pdf.render_pdf`` limité à un gabarit Django nommé
    (``template=``), alors qu'ici le HTML est déjà construit à la main
    (``_contrat_html``, échappement testé — ``tests/test_pdf_interne.py``) et
    passé en ``html=``. Appeler le hook du kit exigerait de convertir ce HTML
    en gabarit Django SANS aucun gain (même fonction sous-jacente), au risque
    de changer le rendu à l'octet près — préservé tel quel plutôt que dupliqué.
    """
    html_str = _contrat_html(contrat)
    return render_pdf(html=html_str)


def _gabarit_par_defaut(contexte):
    """Gabarit de repli (français) quand aucun corps de modèle n'est fourni.

    Produit un contrat lisible à partir des seuls jetons disponibles — sert de
    filet pour qu'un contrat sans gabarit donne tout de même un rendu propre.
    """
    return (
        "CONTRAT — {{ objet }}\n"
        "Référence : {{ reference }}\n"
        "Type : {{ type_contrat }}\n"
        "Montant : {{ montant }}\n"
        "Période : {{ date_debut }} → {{ date_fin }}\n\n"
        "Parties :\n{{ parties }}\n\n"
        "Clauses :\n{{ clauses }}\n"
    )


# ---------------------------------------------------------------------------
# CONTRAT14 — Workflow d'approbation interne (étapes + avancement)
# ---------------------------------------------------------------------------


class ApprobationError(Exception):
    """Levée quand une opération de workflow d'approbation est invalide.

    Ex. : tenter de lancer un workflow déjà en cours, décider une étape qui
    n'est plus en attente, ou décider une étape hors séquence (une étape
    antérieure encore en attente).
    """


def workflow_actif(contrat):
    """``True`` si un workflow d'approbation est déjà en cours pour ce contrat.

    Un workflow est « actif » dès qu'il reste au moins une étape ``en_attente``.
    Sert de garde idempotente : on ne relance pas un workflow déjà ouvert.
    """
    from .models import EtapeApprobation

    return contrat.etapes_approbation.filter(
        statut=EtapeApprobation.Statut.EN_ATTENTE
    ).exists()


@transaction.atomic
def lancer_workflow_approbation(contrat, *, regle=None):
    """Instancie les étapes d'approbation d'un contrat depuis la règle CONTRAT13.

    - Résout la ``RegleApprobation`` la plus spécifique couvrant le contrat
      (montant + type) via ``selectors.resoudre_regle_approbation`` — sauf si une
      ``regle`` est passée explicitement. Aucun seuil n'est codé en dur.
    - Si aucune règle ne couvre le contrat, renvoie une liste vide (rien à
      approuver — l'appelant décide alors d'un comportement par défaut).
    - Crée une ``EtapeApprobation`` par approbation requise
      (``regle.nombre_approbateurs``, au moins 1), numérotées ``niveau`` 1..N,
      toutes ``en_attente``, dans la société du contrat.
    - Idempotent-safe : lever ``ApprobationError`` si un workflow est déjà actif
      (au moins une étape en attente) pour éviter les doublons.

    Ne touche JAMAIS au ``Contrat.statut`` : seules les étapes locales sont
    créées (préservation des statuts).

    Renvoie la liste ordonnée des étapes créées (vide si aucune règle).
    """
    # Import paresseux pour rester cohérent avec le reste du module (pas de
    # cycle au chargement) et n'importer que ce qui est utilisé ici.
    from . import selectors
    from .models import EtapeApprobation

    if workflow_actif(contrat):
        raise ApprobationError(
            "Un workflow d'approbation est déjà en cours pour ce contrat.")

    if regle is None:
        regle = selectors.resoudre_regle_approbation(
            contrat.company, contrat.montant, contrat.type_contrat or None)

    if regle is None:
        return []

    nombre = max(1, regle.nombre_approbateurs)
    etapes = [
        EtapeApprobation(
            company=contrat.company,
            contrat=contrat,
            regle=regle,
            niveau=rang,
            niveau_approbation=regle.niveau_approbation,
            statut=EtapeApprobation.Statut.EN_ATTENTE,
        )
        for rang in range(1, nombre + 1)
    ]
    EtapeApprobation.objects.bulk_create(etapes)
    # Recharge dans l'ordre canonique (bulk_create ne garantit pas les ids
    # peuplés sur toutes les bases, mais le tri par niveau reste stable).
    return list(
        contrat.etapes_approbation.order_by('niveau', 'id'))


def _premiere_etape_en_attente(contrat):
    """Première étape encore ``en_attente`` (ordre ``niveau``) ou ``None``."""
    from .models import EtapeApprobation

    return (
        contrat.etapes_approbation
        .filter(statut=EtapeApprobation.Statut.EN_ATTENTE)
        .order_by('niveau', 'id')
        .first()
    )


def _decider_etape(etape, *, statut_cible, approbateur=None, commentaire=''):
    """Applique une décision (approuve/rejete) GARDÉE sur une étape.

    Gardes :
    - L'étape doit être ``en_attente`` (on ne re-décide pas une étape close).
    - On décide les étapes DANS L'ORDRE : l'étape visée doit être la première
      étape encore en attente de son contrat (pas de saut d'étape).

    Pose ``approbateur`` (peut être ``None``), ``decision_le`` (maintenant),
    ``commentaire`` et ``statut``. N'effleure JAMAIS le ``Contrat.statut``.
    """
    from .models import EtapeApprobation

    if etape.statut != EtapeApprobation.Statut.EN_ATTENTE:
        raise ApprobationError(
            "Cette étape d'approbation a déjà été décidée.")

    premiere = _premiere_etape_en_attente(etape.contrat)
    if premiere is not None and premiere.pk != etape.pk:
        raise ApprobationError(
            "Une étape d'approbation antérieure est encore en attente.")

    etape.statut = statut_cible
    etape.approbateur = approbateur
    etape.decision_le = timezone.now()
    if commentaire:
        etape.commentaire = commentaire
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire'])
    return etape


@transaction.atomic
def approuver_etape(etape, *, approbateur=None, commentaire=''):
    """Approuve une étape et fait avancer le workflow (CONTRAT14).

    Garde l'ordre (l'étape doit être la première encore en attente) et refuse de
    re-décider une étape close (``ApprobationError``). L'approbation de la
    dernière étape laisse le workflow « complet » (plus aucune étape en
    attente) ; le ``Contrat.statut`` n'est jamais modifié ici.
    """
    from .models import EtapeApprobation

    return _decider_etape(
        etape,
        statut_cible=EtapeApprobation.Statut.APPROUVE,
        approbateur=approbateur,
        commentaire=commentaire,
    )


@transaction.atomic
def rejeter_etape(etape, *, approbateur=None, commentaire=''):
    """Rejette une étape (CONTRAT14).

    Un rejet stoppe de fait l'avancement (les étapes suivantes restent en
    attente mais ne peuvent plus être approuvées tant que l'étape rejetée est la
    première en attente : elle ne l'est plus, mais une étape antérieure rejetée
    bloque l'ordre). Comme pour l'approbation : garde l'ordre, refuse une étape
    déjà décidée, et ne touche jamais au ``Contrat.statut``.
    """
    from .models import EtapeApprobation

    return _decider_etape(
        etape,
        statut_cible=EtapeApprobation.Statut.REJETE,
        approbateur=approbateur,
        commentaire=commentaire,
    )


def workflow_complet(contrat):
    """``True`` si le workflow existe et que toutes ses étapes sont approuvées.

    Renvoie ``False`` s'il n'existe aucune étape, ou s'il reste au moins une
    étape ``en_attente`` ou ``rejete``.
    """
    from .models import EtapeApprobation

    etapes = contrat.etapes_approbation.all()
    if not etapes.exists():
        return False
    return not etapes.exclude(
        statut=EtapeApprobation.Statut.APPROUVE).exists()


# ---------------------------------------------------------------------------
# CONTRAT15 — Chatter / journal du contrat (audit des transitions)
# ---------------------------------------------------------------------------


def journaliser_transition(contrat, *, field, old_value='', new_value='',
                           auteur=None, message=''):
    """Écrit une entrée de chatter AUTOMATIQUE (``type=log``) — CONTRAT15.

    Consigne une transition auditée du contrat : champ touché (``field``) et son
    instantané AVANT → APRÈS (``old_value`` → ``new_value``). La société est
    déduite du contrat (posée côté serveur) ; l'auteur est passé par la vue
    appelante (utilisateur courant) et reste ``None`` pour un changement
    automatisé sans utilisateur.

    Les valeurs sont coercées en chaîne — les champs cibles sont des
    ``TextField`` (aucune limite de longueur à dépasser, leçon FG136).

    Renvoie l'entrée créée.
    """
    from .models import ContratActivity

    return ContratActivity.objects.create(
        company=contrat.company,
        contrat=contrat,
        type=ContratActivity.Kind.LOG,
        field=field,
        old_value='' if old_value is None else str(old_value),
        new_value='' if new_value is None else str(new_value),
        message=message or '',
        auteur=auteur,
    )


def noter_contrat(contrat, *, message, auteur=None):
    """Écrit une note manuelle (``type=note``) sur le chatter d'un contrat.

    Société déduite du contrat (côté serveur) ; auteur = utilisateur courant
    passé par la vue. Renvoie l'entrée créée.
    """
    from .models import ContratActivity

    return ContratActivity.objects.create(
        company=contrat.company,
        contrat=contrat,
        type=ContratActivity.Kind.NOTE,
        message=message,
        auteur=auteur,
    )


# ---------------------------------------------------------------------------
# CONTRAT16 — Signature électronique IN-APP + bascule du statut « signé »
# ---------------------------------------------------------------------------


class SignatureError(Exception):
    """Levée quand une signature ne peut pas être enregistrée.

    Ex. : tenter de faire signer la même partie (même rôle) deux fois pour un
    contrat, ou signer dans un état documentaire incompatible.
    """


# Parties dont la signature est REQUISE pour qu'un contrat soit « signé » : le
# client ET le prestataire. Un témoin renforce la preuve mais n'est pas une
# condition de bascule. Aucun funnel STAGES.py n'intervient ici (rule #2).
def _roles_requis():
    from .models import SignatureContrat

    return {
        SignatureContrat.RoleSignataire.CLIENT,
        SignatureContrat.RoleSignataire.PRESTATAIRE,
    }


def roles_signataires(contrat):
    """Ensemble des rôles ayant déjà signé ce contrat (scopé société)."""
    from .models import SignatureContrat

    return set(
        SignatureContrat.objects
        .filter(contrat=contrat, company=contrat.company)
        .values_list('role_signataire', flat=True)
    )


def toutes_parties_signataires(contrat):
    """``True`` si toutes les parties REQUISES (client + prestataire) ont signé.

    Lecture seule. Sert de garde de bascule : ``signer_contrat`` ne fait passer
    le contrat à ``signe`` qu'une fois cet ensemble couvert.
    """
    return _roles_requis().issubset(roles_signataires(contrat))


# ---------------------------------------------------------------------------
# CONTRAT17 — Transition automatique « signé → actif » sur signature
# ---------------------------------------------------------------------------


def peut_activer_automatiquement(contrat, *, today=None):
    """``True`` si un contrat « signé » peut s'activer automatiquement.

    Garde de date : un contrat ne devient ``actif`` automatiquement que si sa
    prise d'effet est atteinte — c.-à-d. ``date_debut`` est absente (effet
    immédiat) OU ``date_debut`` ≤ aujourd'hui. Un contrat dont la prise d'effet
    est dans le FUTUR reste ``signe`` jusqu'à cette date (l'activation pourra
    alors se faire via la machine d'états gardée, ``changer-statut``, ou un
    futur déclencheur de dates — CONTRAT20).

    Lecture seule : ne modifie ni ne persiste rien. ``today`` est injectable
    pour les tests ; par défaut on prend la date du jour (fuseau du projet).
    """
    from .models import Contrat

    if contrat.statut != Contrat.Statut.SIGNE:
        return False
    if today is None:
        today = timezone.localdate()
    return contrat.date_debut is None or contrat.date_debut <= today


def activer_si_eligible(contrat, *, today=None, auteur=None):
    """Active automatiquement un contrat ``signe`` éligible (CONTRAT17).

    Une fois un contrat passé à ``signe`` (toutes les parties requises ont
    signé), on tente de le faire avancer à ``actif`` via la machine d'états
    GARDÉE (``changer_statut``) — jamais d'écriture directe du statut, jamais de
    funnel STAGES.py (rule #2). L'activation n'a lieu que si :

    - le contrat est bien ``signe`` ET la garde de date est satisfaite
      (``peut_activer_automatiquement``), ET
    - la transition ``signe → actif`` est permise par la machine d'états.

    Sinon le statut est LAISSÉ INCHANGÉ (préservation des statuts — CONTRAT12).
    La bascule est journalisée dans le chatter (CONTRAT15) avec auteur et
    société posés côté serveur.

    Renvoie ``True`` si l'activation a eu lieu lors de cet appel, sinon
    ``False``.
    """
    from .models import Contrat

    if not peut_activer_automatiquement(contrat, today=today):
        return False
    if not transition_permise(contrat.statut, Contrat.Statut.ACTIF):
        return False

    ancien = contrat.statut
    try:
        changer_statut(contrat, Contrat.Statut.ACTIF)
    except TransitionInterdite:
        # Garde de la machine : on n'écrit pas le statut (préservation).
        return False

    journaliser_transition(
        contrat, field='statut', old_value=ancien,
        new_value=contrat.statut,
        message='Activation automatique à la signature.',
        auteur=auteur)

    # YSUBS8 — dérive le plan de facturation des dates du contrat dès
    # l'activation, pour CHAQUE échéancier récurrent (facturation_active)
    # existant. Best-effort : un échec de génération ne doit jamais annuler
    # l'activation déjà actée (le statut a déjà basculé ci-dessus).
    try:
        from .models import EcheancierContrat

        for echeancier in EcheancierContrat.objects.filter(
                contrat=contrat, facturation_active=True):
            generer_echeancier_depuis_dates(
                contrat, echeancier, auteur=auteur)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass

    # YDOCF5 — émet l'événement métier EXACTEMENT une fois (une seule
    # bascule → actif par appel, garantie par la garde de transition
    # ci-dessus). Best-effort : un abonné qui échoue ne doit jamais faire
    # échouer l'activation, déjà actée.
    try:
        from core.events import contrat_actif as contrat_actif_signal

        contrat_actif_signal.send(
            sender=None, contrat=contrat, user=auteur,
            company=contrat.company)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass

    return True


@transaction.atomic
def signer_contrat(contrat, *, signataire_nom, role_signataire,
                   signataire=None, ip_adresse='', user_agent='',
                   methode=None, auteur=None, today=None):
    """Enregistre une signature électronique IN-APP d'un contrat (CONTRAT16).

    - Crée une ``SignatureContrat`` portant le nom dactylographié
      (``signataire_nom``, fait foi — loi 53-05), le rôle (client / prestataire /
      témoin), l'utilisateur agissant éventuel (``signataire``, NULL pour une
      partie externe) et les preuves (``ip_adresse`` ≤ 45, ``user_agent``,
      ``methode`` typed/draw). La société est posée côté serveur (celle du
      contrat).
    - Une même partie (rôle) ne signe qu'une fois : une seconde signature du même
      rôle lève ``SignatureError`` (la contrainte DB est le filet de sécurité).
    - Journalise la signature via le chatter CONTRAT15 (``journaliser_transition``)
      quand ce module est disponible.
    - BASCULE DE STATUT : si toutes les parties REQUISES (client + prestataire)
      ont alors signé ET que la transition ``→ signe`` est permise par la machine
      d'états gardée (``changer_statut``), le contrat passe à ``signe``. Sinon le
      statut est LAISSÉ INCHANGÉ (signature partielle, ou état documentaire
      n'autorisant pas encore la signature) — jamais d'écriture directe du
      statut, jamais de funnel STAGES.py (rule #2). La préservation des statuts
      documentaires (CONTRAT12) reste donc intacte.
    - ACTIVATION AUTOMATIQUE (CONTRAT17) : dans la foulée du passage à ``signe``,
      le contrat est avancé à ``actif`` via la même machine d'états gardée si sa
      prise d'effet est atteinte (``date_debut`` absente ou ≤ ``today``). Une
      prise d'effet FUTURE laisse le contrat à ``signe``. ``today`` est
      injectable pour les tests (défaut : date du jour).

    Renvoie un dict ``{'signature', 'contrat_signe', 'contrat_actif'}`` : la
    signature créée, un booléen indiquant si la bascule ``signe`` a eu lieu, et
    un booléen indiquant si l'activation automatique ``→ actif`` a eu lieu lors
    de cet appel.
    """
    from .models import Contrat, SignatureContrat

    nom = (signataire_nom or '').strip()
    if not nom:
        raise SignatureError('Le nom du signataire est requis (loi 53-05).')

    if methode is None:
        methode = SignatureContrat.Methode.TYPED

    # Garde explicite contre le doublon de rôle (la contrainte DB double la
    # garde, mais on lève une erreur métier propre plutôt qu'IntegrityError).
    if role_signataire in roles_signataires(contrat):
        raise SignatureError(
            "Cette partie a déjà signé ce contrat.")

    signature = SignatureContrat.objects.create(
        company=contrat.company,
        contrat=contrat,
        signataire_nom=nom,
        signataire=signataire,
        role_signataire=role_signataire,
        ip_adresse=ip_adresse or '',
        user_agent=user_agent or '',
        methode=methode,
    )

    # CONTRAT15 — audit de la signature (champ ``signature``). Auteur posé côté
    # serveur (l'utilisateur agissant, ou None pour une partie externe).
    journaliser_transition(
        contrat, field='signature', old_value='',
        new_value=f'{nom} ({role_signataire})',
        auteur=auteur if auteur is not None else signataire)

    # Bascule vers « signe » uniquement si toutes les parties requises ont signé
    # ET que la machine d'états autorise la transition depuis l'état courant.
    contrat_signe = False
    contrat_actif = False
    if (
        contrat.statut != Contrat.Statut.SIGNE
        and toutes_parties_signataires(contrat)
        and transition_permise(contrat.statut, Contrat.Statut.SIGNE)
    ):
        ancien = contrat.statut
        try:
            changer_statut(contrat, Contrat.Statut.SIGNE)
        except TransitionInterdite:
            # Garde de la machine (ex. parties insuffisantes) : on n'écrit pas le
            # statut, la signature reste enregistrée (préservation des statuts).
            contrat_signe = False
        else:
            contrat_signe = True
            journaliser_transition(
                contrat, field='statut', old_value=ancien,
                new_value=contrat.statut,
                message='Toutes les parties requises ont signé.',
                auteur=auteur if auteur is not None else signataire)

            # YDOCF5 — émet l'événement métier EXACTEMENT une fois (une seule
            # bascule → signe par appel de ``signer_contrat``, garantie par la
            # condition ``contrat.statut != Contrat.Statut.SIGNE`` ci-dessus).
            # Best-effort : jamais bloquant pour la signature déjà actée.
            try:
                from core.events import contrat_signe as contrat_signe_signal

                contrat_signe_signal.send(
                    sender=None, contrat=contrat,
                    user=auteur if auteur is not None else signataire,
                    company=contrat.company)
            except Exception:  # pragma: no cover - défensif (best-effort)
                pass

            # CONTRAT17 — activation automatique « signé → actif » si la prise
            # d'effet est atteinte. Passe par la machine d'états gardée et
            # journalise la bascule ; une prise d'effet future laisse à « signe ».
            # (émet son propre événement ``contrat_actif`` — voir
            # ``activer_si_eligible``.)
            contrat_actif = activer_si_eligible(
                contrat, today=today,
                auteur=auteur if auteur is not None else signataire)

    # CONTRAT18 — instantané IMMUABLE du rendu lors de la bascule « signé ».
    # On fige le contenu du contrat au moment où il devient signé pour préserver
    # l'état contractuellement engageant. L'instantané est best-effort : un échec
    # du rendu ne doit jamais empêcher l'enregistrement de la signature.
    if contrat_signe:
        try:
            creer_version(
                contrat,
                cree_par=auteur if auteur is not None else signataire,
                motif='Signature du contrat',
            )
        except Exception:  # pragma: no cover - défensif (rendu best-effort)
            pass

    return {
        'signature': signature,
        'contrat_signe': contrat_signe,
        'contrat_actif': contrat_actif,
    }


# ---------------------------------------------------------------------------
# CONTRAT18 — Versionnage IMMUABLE des rendus de contrat
# ---------------------------------------------------------------------------


def _prochaine_version(contrat):
    """Numéro de la prochaine version d'un contrat (``max(version)+1``).

    Lecture du plus haut numéro DÉJÀ utilisé pour ce contrat, +1. Repli sur 1
    quand aucune version n'existe encore. À appeler SOUS verrou de ligne
    (``select_for_update`` sur le contrat) pour rester sûr face aux courses —
    JAMAIS un ``count()+1`` (qui collisionne après une suppression et en
    concurrence, cf. la règle de numérotation du repo).
    """
    from django.db.models import Max

    from .models import VersionContrat

    plus_haut = (
        VersionContrat.objects
        .filter(contrat=contrat, company=contrat.company)
        .aggregate(m=Max('version'))['m']
    )
    return (plus_haut or 0) + 1


@transaction.atomic
def creer_version(contrat, *, contenu=None, fichier_key='', motif='',
                  cree_par=None):
    """Fige un instantané IMMUABLE du rendu d'un contrat (CONTRAT18).

    Crée une ``VersionContrat`` portant :

    - ``contenu`` : le corps figé du contrat. Si ``None``, on le calcule au vol
      via le rendu par fusion (``rendre_contrat`` — CONTRAT10) ; passer une
      chaîne (même vide) court-circuite le rendu et fige exactement ce contenu.
    - ``fichier_key`` : clé d'un rendu PDF stocké (MinIO), optionnelle.
    - ``motif`` : justification facultative (signature, envoi client…).
    - ``cree_par`` : utilisateur agissant, posé côté serveur (NULL pour un
      instantané automatisé sans utilisateur).

    NUMÉROTATION SÛRE FACE AUX COURSES : on verrouille la LIGNE du contrat
    (``select_for_update``) puis on calcule ``max(version)+1`` — jamais un
    ``count()+1``. Sous le verrou, deux créations concurrentes pour le même
    contrat sont sérialisées et obtiennent des numéros distincts (la contrainte
    d'unicité ``(contrat, version)`` reste le filet de sécurité ultime).

    La société est déduite du contrat (posée côté serveur). Renvoie la
    ``VersionContrat`` créée. Les versions sont IMMUABLES : aucune mise à jour ni
    suppression n'est exposée par l'API.
    """
    from .models import Contrat, VersionContrat

    # Verrou de ligne sur le contrat pour sérialiser la numérotation concurrente.
    Contrat.objects.select_for_update().get(pk=contrat.pk)

    if contenu is None:
        contenu = rendre_contrat(contrat).get('rendu', '')

    numero = _prochaine_version(contrat)

    version = VersionContrat.objects.create(
        company=contrat.company,
        contrat=contrat,
        version=numero,
        contenu=contenu or '',
        fichier_key=fichier_key or '',
        motif=motif or '',
        cree_par=cree_par,
    )

    # CONTRAT19 — dépôt automatique de la version dans la GED (référentiel
    # documentaire central). Best-effort + idempotent : un échec (stockage
    # indisponible, GED absente…) ne doit JAMAIS empêcher la création de la
    # version. Le dépôt est délégué à `ged.services` (frontière cross-app).
    try:
        deposer_version_en_ged(version)
    except Exception:  # pragma: no cover - défensif (dépôt best-effort)
        pass

    return version


# ---------------------------------------------------------------------------
# CONTRAT19 — Dépôt en GED des versions & PDF signés
# ---------------------------------------------------------------------------


def deposer_version_en_ged(version):
    """Dépose une ``VersionContrat`` dans la GED (référentiel central) — CONTRAT19.

    Chaque instantané de version d'un contrat (y compris l'instantané figé à la
    SIGNATURE) est enregistré comme document GED, de sorte que les contrats
    versionnés et signés vivent dans le magasin documentaire central. L'écriture
    cross-app passe par ``ged.services.deposit_document`` (frontière cross-app :
    jamais d'import des modèles/vues de la GED) — import paresseux/fonction-local
    pour éviter tout cycle.

    Le dépôt est IDEMPOTENT : ``deposit_document`` déduplique sur l'objet source
    (``contrats.versioncontrat`` + pk), donc redéposer la même version ne crée
    jamais de doublon GED. Si la version porte une clé de rendu PDF stocké
    (``fichier_key``), on dépose ce binaire ; sinon on dépose un pointeur de
    version traçant l'instantané (le contenu textuel reste dans l'app source).

    La société est posée CÔTÉ SERVEUR (celle du contrat) — jamais lue d'un corps
    de requête. Renvoie ``(document, created)`` tel que renvoyé par la GED.
    """
    from apps.ged import services as ged_services

    contrat = version.contrat
    ref = (contrat.reference or '').strip()
    objet = (contrat.objet or '').strip()
    base = ref or objet or f'Contrat {contrat.pk}'
    nom = f'{base} — version {version.version}'
    if version.motif:
        nom = f'{nom} ({version.motif})'

    return ged_services.deposit_document(
        company=contrat.company,
        nom=nom,
        source_type='contrats.versioncontrat',
        source_id=version.pk,
        file_key=version.fichier_key or '',
        mime='application/pdf' if version.fichier_key else '',
        description=f'Contrat {base} — instantané de version (CONTRAT18).',
        created_by=version.cree_par,
    )


def deposer_contrat_signe_en_ged(signature):
    """Dépose le contrat SIGNÉ d'une ``SignatureContrat`` dans la GED — CONTRAT19.

    La signature elle-même ne porte pas de PDF : c'est la bascule « signé » qui
    fige un instantané immuable du contrat (``creer_version`` avec le motif
    « Signature du contrat »). On dépose donc la DERNIÈRE version de ce contrat
    (l'instantané de signature) dans la GED via ``deposer_version_en_ged`` —
    idempotent (pas de doublon si la version est déjà déposée).

    Renvoie ``(document, created)`` ou ``None`` si le contrat n'a encore aucune
    version figée (rien à déposer). Société posée côté serveur (celle du
    contrat). Best-effort par construction (délègue au dépôt idempotent GED).
    """
    from .models import VersionContrat

    contrat = signature.contrat
    derniere = (
        VersionContrat.objects
        .filter(contrat=contrat, company=contrat.company)
        .order_by('-version', '-id')
        .first()
    )
    if derniere is None:
        return None
    return deposer_version_en_ged(derniere)


# ---------------------------------------------------------------------------
# CONTRAT22 — Alertes de contrat + rappels via le système de notifications
# ---------------------------------------------------------------------------

# Lien vers le contrat dans l'ERP (rappel cliquable depuis la notification).
def _lien_contrat(contrat):
    return f'/contrats/{contrat.pk}'


def creer_alerte(contrat, *, type_alerte=None, date_declenchement,
                 message='', cree_par=None):
    """Crée une ``AlerteContrat`` planifiée pour un contrat (CONTRAT22).

    La société est TOUJOURS déduite du contrat (posée côté serveur) — jamais
    lue du corps de requête. ``type_alerte`` par défaut ``personnalise``.
    L'alerte naît ``planifiee`` ; elle sera dispatchée à
    ``date_declenchement`` par ``declencher_alertes_contrat``.

    Renvoie l'``AlerteContrat`` créée.
    """
    from .models import AlerteContrat

    if type_alerte is None:
        type_alerte = AlerteContrat.TypeAlerte.PERSONNALISE
    return AlerteContrat.objects.create(
        company=contrat.company,
        contrat=contrat,
        type_alerte=type_alerte,
        date_declenchement=date_declenchement,
        message=message or '',
        statut=AlerteContrat.Statut.PLANIFIEE,
        cree_par=cree_par,
    )


def _message_alerte_defaut(alerte):
    """Libellé par défaut d'une alerte (français) si aucun message saisi."""
    from .models import AlerteContrat

    contrat = alerte.contrat
    base = (contrat.reference or contrat.objet or f'contrat #{contrat.pk}')
    if alerte.type_alerte == AlerteContrat.TypeAlerte.PREAVIS:
        return (
            f"Échéance de préavis à venir pour le {base} "
            f"(à traiter avant le {alerte.date_declenchement.isoformat()})."
        )
    if alerte.type_alerte == AlerteContrat.TypeAlerte.ECHEANCE:
        return (
            f"Le {base} arrive à échéance — à renouveler ou clôturer "
            f"(le {alerte.date_declenchement.isoformat()})."
        )
    return (
        f"Rappel sur le {base} "
        f"(le {alerte.date_declenchement.isoformat()})."
    )


def _alerter_destinataires(alerte):
    """Diffuse UNE alerte de contrat via le point d'entrée notifications.

    Frontière cross-app (CLAUDE.md) : on appelle EXCLUSIVEMENT le helper
    ``apps.notifications.services.notify`` / ``notify_many`` et le résolveur de
    destinataires ``resolve_recipients`` — jamais d'import des modèles/vues de
    l'app notifications. Imports FONCTION-LOCAUX pour éviter tout cycle au
    chargement et dégrader proprement si l'app notifications est absente.

    Best-effort : toute erreur est avalée — une alerte ratée ne doit jamais
    interrompre le balayage des autres alertes ni casser une transaction.
    Renvoie le nombre de notifications créées (0 si l'app est indisponible ou
    s'il n'y a aucun destinataire).
    """
    from .models import AlerteContrat

    try:
        from apps.notifications.services import (
            notify_many, resolve_recipients,
        )
    except Exception:  # pragma: no cover - app notifications absente
        return 0

    # Événement de notification générique « récapitulatif/rappel » : un rappel
    # de contrat n'a pas d'événement métier dédié — on réutilise l'événement
    # existant DIGEST (« Récapitulatif »), valide dans EventType, sans en
    # inventer un nouveau (frontière cross-app respectée).
    event_type = 'digest'

    titres = {
        AlerteContrat.TypeAlerte.PREAVIS: 'Rappel : échéance de préavis',
        AlerteContrat.TypeAlerte.ECHEANCE: 'Rappel : contrat à renouveler',
        AlerteContrat.TypeAlerte.PERSONNALISE: 'Rappel de contrat',
    }
    contrat = alerte.contrat
    title = titres.get(alerte.type_alerte, 'Rappel de contrat')
    body = alerte.message or _message_alerte_defaut(alerte)

    try:
        recipients = resolve_recipients(alerte.company, event_type)
        created = notify_many(
            recipients, event_type, title, body=body,
            link=_lien_contrat(contrat), company=alerte.company)
        return len(created)
    except Exception:  # pragma: no cover - défensif (best-effort)
        return 0


@transaction.atomic
def declencher_alertes_contrat(company, today=None):
    """Dispatche les ``AlerteContrat`` DUES d'une société (CONTRAT22).

    Trouve les alertes ``planifiee`` dont la ``date_declenchement`` est ≤
    ``today`` (scopées société) et, pour chacune, diffuse un rappel via le
    système de notifications (``_alerter_destinataires`` → ``notify_many``),
    puis marque l'alerte ``envoyee`` avec ``date_envoi``.

    IDEMPOTENT : une alerte n'est dispatchée qu'une fois — un second appel ne
    re-notifie aucune alerte déjà ``envoyee`` (filtre sur ``planifiee``). Le
    marquage ``envoyee`` est posé MÊME si la diffusion best-effort n'a touché
    aucun destinataire (sinon l'alerte serait re-tentée indéfiniment) — la
    diffusion elle-même reste best-effort et ne lève jamais.

    Multi-tenant : ``company`` est toujours posée côté serveur ; on ne dispatche
    que les alertes de cette société. ``today`` est injectable pour les tests.

    Ne touche JAMAIS au ``Contrat.statut`` ni au funnel STAGES.py (rule #2).

    Renvoie un dict ::

        {'company_id', 'nb_dues', 'nb_envoyees', 'nb_notifications',
         'alertes': [<AlerteContrat>, …]}  # les alertes marquées envoyées
    """
    from .models import AlerteContrat

    if today is None:
        today = timezone.localdate()

    dues = list(
        AlerteContrat.objects
        .filter(company=company,
                statut=AlerteContrat.Statut.PLANIFIEE,
                date_declenchement__lte=today)
        .select_related('contrat')
        .order_by('date_declenchement', 'id')
    )

    envoyees = []
    nb_notifications = 0
    maintenant = timezone.now()
    for alerte in dues:
        nb_notifications += _alerter_destinataires(alerte)
        alerte.statut = AlerteContrat.Statut.ENVOYEE
        alerte.date_envoi = maintenant
        alerte.save(update_fields=['statut', 'date_envoi'])
        envoyees.append(alerte)

    return {
        'company_id': company.id,
        'nb_dues': len(dues),
        'nb_envoyees': len(envoyees),
        'nb_notifications': nb_notifications,
        'alertes': envoyees,
    }


def semer_alertes_echeances(company, *, within_days=30, today=None,
                            cree_par=None):
    """Sème des ``AlerteContrat`` à partir des contrats dont l'échéance approche.

    Réutilise les sélecteurs existants (CONTRAT20/21) :
    - ``selectors.contrats_a_preavis`` → une alerte ``preavis`` datée à
      l'échéance de préavis (``date_fin − preavis_jours``) ;
    - ``selectors.contrats_a_renouveler`` → une alerte ``echeance`` datée à la
      fin du contrat (``date_fin``).

    IDEMPOTENT : on ne crée pas de doublon — pour un contrat donné, un type
    d'alerte donné et une date de déclenchement donnée, si une alerte
    NON-annulée existe déjà on la saute. La société est posée côté serveur
    (celle de chaque contrat, garantie identique par les sélecteurs scopés).

    Ne dispatche RIEN : sème seulement des alertes ``planifiee`` (le dispatch
    est le rôle de ``declencher_alertes_contrat``). ``today`` est injectable.

    Renvoie un dict ``{'company_id', 'nb_creees', 'alertes': [...]}``.
    """
    from . import selectors
    from .models import AlerteContrat

    if today is None:
        today = timezone.localdate()

    creees = []

    def _semer(contrat, type_alerte, date_decl):
        if date_decl is None:
            return
        existe = AlerteContrat.objects.filter(
            company=contrat.company,
            contrat=contrat,
            type_alerte=type_alerte,
            date_declenchement=date_decl,
        ).exclude(statut=AlerteContrat.Statut.ANNULEE).exists()
        if existe:
            return
        creees.append(creer_alerte(
            contrat,
            type_alerte=type_alerte,
            date_declenchement=date_decl,
            cree_par=cree_par,
        ))

    for contrat in selectors.contrats_a_preavis(
            company, within_days=within_days, today=today):
        _semer(
            contrat, AlerteContrat.TypeAlerte.PREAVIS,
            contrat.echeance_preavis())

    for contrat in selectors.contrats_a_renouveler(
            company, within_days=within_days, today=today):
        _semer(
            contrat, AlerteContrat.TypeAlerte.ECHEANCE,
            contrat.date_fin)

    return {
        'company_id': company.id,
        'nb_creees': len(creees),
        'alertes': creees,
    }


# ---------------------------------------------------------------------------
# CONTRAT23 — Renouvellement (manuel + tacite reconduction)
# ---------------------------------------------------------------------------


class RenouvellementError(Exception):
    """Levée quand un renouvellement de contrat est invalide.

    Ex. : tenter de renouveler un contrat résilié/expiré (états terminaux —
    plus rien à reconduire), ou demander une durée/date de reconduction qui ne
    permet pas de calculer une nouvelle fin.
    """


# Statuts pour lesquels un renouvellement n'a PAS de sens (états terminaux de la
# machine d'états CONTRAT12 : résilié / expiré). On refuse alors de renouveler.
def _statuts_non_renouvelables():
    from .models import Contrat

    return {Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE}


@transaction.atomic
def renouveler_contrat(contrat, *, nouvelle_date_fin=None, duree_mois=None,
                       auteur=None, snapshot=True, today=None):
    """Renouvelle EFFECTIVEMENT un contrat (action manuelle) — CONTRAT23.

    Complémentaire de CONTRAT20 (alerte de préavis) et CONTRAT21 (liste des
    contrats à échéance) qui ne font que SURFACER les contrats : ici on PROLONGE
    réellement la période contractuelle.

    Calcul de la nouvelle période :

    - si ``nouvelle_date_fin`` est fournie, elle devient la nouvelle ``date_fin``
      (priorité au choix explicite) ;
    - sinon on décale ``date_fin`` (ou ``today`` si aucune fin n'est posée) de
      ``duree_mois`` mois — ou, à défaut, de ``contrat.duree_reconduction_mois``
      (durée déclarée de la tacite reconduction). Sans aucune durée exploitable,
      ``RenouvellementError`` est levée.

    Effets de bord (posés CÔTÉ SERVEUR, jamais lus d'un corps de requête) :

    - ``date_debut`` est avancée à l'ancienne ``date_fin`` quand celle-ci existe
      et précède la nouvelle fin (la nouvelle période démarre à la fin de
      l'ancienne — comportement attendu d'une reconduction) ;
    - ``date_fin`` reçoit la nouvelle échéance calculée ;
    - ``preavis_traite`` est REMIS à ``False`` (un nouveau cycle de préavis
      s'ouvre pour la nouvelle période) ;
    - ``date_dernier_renouvellement`` = ``today`` (date du jour, injectable) ;
    - ``nb_renouvellements`` est incrémenté de 1.

    Le ``Contrat.statut`` n'est JAMAIS modifié (préservation des statuts —
    CONTRAT12) et aucun funnel ``STAGES.py`` n'intervient (rule #2). Un contrat
    résilié/expiré (état terminal) ne peut pas être renouvelé →
    ``RenouvellementError``.

    Si ``snapshot`` (défaut), un instantané immuable est figé via
    ``creer_version(motif='Renouvellement')`` (CONTRAT18) — best-effort : un
    échec de rendu n'empêche jamais le renouvellement. Le renouvellement est
    journalisé dans le chatter (CONTRAT15), auteur posé côté serveur.

    Renvoie le ``contrat`` rafraîchi.
    """
    from .models import Contrat

    if contrat.statut in _statuts_non_renouvelables():
        raise RenouvellementError(
            "Un contrat résilié ou expiré ne peut pas être renouvelé.")

    if today is None:
        today = timezone.localdate()

    ancienne_fin = contrat.date_fin

    # Détermine la nouvelle date de fin.
    if nouvelle_date_fin is not None:
        nouvelle_fin = nouvelle_date_fin
    else:
        mois = duree_mois if duree_mois is not None else \
            contrat.duree_reconduction_mois
        if not mois or int(mois) <= 0:
            raise RenouvellementError(
                "Impossible de calculer la nouvelle échéance : fournir une "
                "nouvelle date de fin, une durée en mois, ou une durée de "
                "reconduction sur le contrat.")
        base = ancienne_fin or today
        nouvelle_fin = Contrat.ajouter_mois(base, int(mois))

    # La nouvelle période démarre à la fin de l'ancienne (quand elle existe et
    # précède la nouvelle fin) — sinon on laisse ``date_debut`` inchangée.
    champs_maj = [
        'date_fin', 'preavis_traite', 'date_dernier_renouvellement',
        'nb_renouvellements',
    ]
    if (
        ancienne_fin is not None
        and nouvelle_fin is not None
        and ancienne_fin < nouvelle_fin
    ):
        contrat.date_debut = ancienne_fin
        champs_maj.append('date_debut')

    contrat.date_fin = nouvelle_fin
    contrat.preavis_traite = False
    contrat.date_dernier_renouvellement = today
    contrat.nb_renouvellements = (contrat.nb_renouvellements or 0) + 1
    contrat.save(update_fields=champs_maj)

    # CONTRAT15 — audit du renouvellement (ancienne → nouvelle fin).
    journaliser_transition(
        contrat, field='renouvellement',
        old_value=_fmt_date(ancienne_fin),
        new_value=_fmt_date(nouvelle_fin),
        message='Renouvellement du contrat.',
        auteur=auteur)

    # CONTRAT18 — instantané immuable best-effort du contrat renouvelé.
    if snapshot:
        try:
            creer_version(contrat, cree_par=auteur, motif='Renouvellement')
        except Exception:  # pragma: no cover - défensif (rendu best-effort)
            pass

    return contrat


def traiter_reconductions_tacites(company, today=None, *, auteur=None):
    """Reconduit AUTOMATIQUEMENT les contrats en tacite reconduction dus — CONTRAT23.

    Trouve les contrats de ``company`` :

    - dont ``tacite_reconduction`` est vrai,
    - non résiliés/expirés (états terminaux),
    - avec une ``duree_reconduction_mois`` exploitable (> 0),
    - dont l'échéance est ATTEINTE (``date_fin`` ≤ ``today``),

    et les renouvelle chacun d'une période de ``duree_reconduction_mois`` via
    ``renouveler_contrat`` (mêmes effets : avance ``date_fin``/``date_debut``,
    remet ``preavis_traite=False``, snapshot, audit).

    IDEMPOTENT : ``renouveler_contrat`` avance ``date_fin`` au-delà de ``today``,
    donc un second passage le même jour ne re-sélectionne plus le contrat
    (``date_fin`` n'est plus ≤ ``today``) — pas de double reconduction de la même
    période. Boucle TANT QUE l'échéance reste dépassée pour rattraper plusieurs
    périodes manquées (borne de sécurité pour éviter une boucle infinie).

    Multi-tenant : ``company`` est posée côté serveur ; seuls les contrats de
    cette société sont traités. Ne touche JAMAIS au ``Contrat.statut`` ni au
    funnel ``STAGES.py`` (rule #2). ``today`` est injectable pour les tests.

    Renvoie un dict ::

        {'company_id', 'nb_traites', 'nb_renouvellements',
         'contrats': [<Contrat>, …]}  # les contrats reconduits (au moins une fois)
    """
    from .models import Contrat

    if today is None:
        today = timezone.localdate()

    dus = list(
        Contrat.objects
        .filter(company=company, tacite_reconduction=True,
                date_fin__isnull=False, date_fin__lte=today)
        .exclude(statut__in=list(_statuts_non_renouvelables()))
        .filter(duree_reconduction_mois__isnull=False,
                duree_reconduction_mois__gt=0)
        .order_by('date_fin', 'id')
    )

    traites = []
    nb_renouvellements = 0
    for contrat in dus:
        n = 0
        # Rattrape les périodes manquées : on reconduit jusqu'à dépasser today.
        # Borne dure (240 = 20 ans de reconductions mensuelles) anti-boucle.
        while (
            contrat.date_fin is not None
            and contrat.date_fin <= today
            and contrat.duree_reconduction_mois
            and contrat.duree_reconduction_mois > 0
            and n < 240
        ):
            renouveler_contrat(
                contrat,
                duree_mois=contrat.duree_reconduction_mois,
                auteur=auteur,
                today=today,
            )
            n += 1
        if n:
            traites.append(contrat)
            nb_renouvellements += n

    return {
        'company_id': company.id,
        'nb_traites': len(traites),
        'nb_renouvellements': nb_renouvellements,
        'contrats': traites,
    }


# ---------------------------------------------------------------------------
# CONTRAT24 — Avenant (amendement → nouvelle version immuable)
# ---------------------------------------------------------------------------


def _prochain_numero_avenant(contrat):
    """Numéro du prochain avenant d'un contrat (``max(numero)+1``).

    Lecture du plus haut numéro DÉJÀ utilisé pour ce contrat, +1. Repli sur 1
    quand aucun avenant n'existe encore. À appeler SOUS verrou de ligne
    (``select_for_update`` sur le contrat) pour rester sûr face aux courses —
    JAMAIS un ``count()+1`` (qui collisionne après une suppression et en
    concurrence, cf. la règle de numérotation du repo).
    """
    from django.db.models import Max

    from .models import Avenant

    plus_haut = (
        Avenant.objects
        .filter(contrat=contrat, company=contrat.company)
        .aggregate(m=Max('numero'))['m']
    )
    return (plus_haut or 0) + 1


@transaction.atomic
def creer_avenant(contrat, *, objet, description='', date_effet=None,
                  montant_delta=None, auteur=None):
    """Enregistre un AVENANT (amendement) à un contrat — CONTRAT24.

    Un avenant recense une MODIFICATION apportée à un ``Contrat`` existant et
    produit, dans la foulée, un INSTANTANÉ IMMUABLE du contrat (``VersionContrat``
    — CONTRAT18) figeant son état au moment de l'amendement.

    Déroulé (tout est posé CÔTÉ SERVEUR, jamais lu d'un corps de requête) :

    - NUMÉROTATION SÛRE FACE AUX COURSES : on verrouille la LIGNE du contrat
      (``select_for_update``) puis on calcule ``max(numero)+1`` — jamais un
      ``count()+1``. Sous le verrou, deux créations concurrentes pour le même
      contrat sont sérialisées et obtiennent des numéros distincts (la contrainte
      d'unicité ``(contrat, numero)`` reste le filet de sécurité ultime).
    - APPLICATION DU DELTA : si ``montant_delta`` est fourni (non ``None``), il
      est AJOUTÉ à ``Contrat.montant`` (garde : on ne touche le montant que
      lorsque le delta est explicitement passé) ; l'audit chatter consigne
      l'ancien → nouveau montant. Un avenant rédactionnel (``montant_delta``
      ``None``) ne modifie pas le montant.
    - INSTANTANÉ : on appelle ``creer_version`` AVANT-AVENANT-aware (après
      l'éventuelle application du delta, pour figer l'état amendé) avec le motif
      ``« Avenant n°X — <objet> »`` et on relie la version à l'avenant
      (``version_creee``).
    - AUDIT : la création de l'avenant est journalisée dans le chatter (CONTRAT15)
      avec l'auteur posé côté serveur.

    Le ``Contrat.statut`` n'est JAMAIS modifié (préservation des statuts —
    CONTRAT12) et aucun funnel ``STAGES.py`` n'intervient (rule #2). La société
    est déduite du contrat. Renvoie l'``Avenant`` créé (``version_creee``
    renseigné).
    """
    from .models import Avenant, Contrat

    nom = (objet or '').strip()
    if not nom:
        raise ValueError("L'objet de l'avenant est requis.")

    # Verrou de ligne sur le contrat pour sérialiser la numérotation concurrente
    # (et l'éventuelle application du delta de montant).
    Contrat.objects.select_for_update().get(pk=contrat.pk)

    numero = _prochain_numero_avenant(contrat)

    # Application du delta de montant côté serveur (gardée : seulement si fourni).
    if montant_delta is not None:
        ancien_montant = contrat.montant
        contrat.montant = (contrat.montant or Decimal('0')) + montant_delta
        contrat.save(update_fields=['montant'])
        journaliser_transition(
            contrat, field='montant',
            old_value=_fmt_montant(ancien_montant, contrat.devise),
            new_value=_fmt_montant(contrat.montant, contrat.devise),
            message=f'Avenant n°{numero} — {nom}',
            auteur=auteur)

    avenant = Avenant.objects.create(
        company=contrat.company,
        contrat=contrat,
        numero=numero,
        objet=nom,
        description=description or '',
        date_effet=date_effet,
        montant_delta=montant_delta,
        cree_par=auteur,
    )

    # CONTRAT18 — instantané IMMUABLE figeant l'état amendé du contrat. On relie
    # la version à l'avenant. Best-effort sur le rendu : un échec ne doit jamais
    # empêcher l'enregistrement de l'avenant lui-même.
    try:
        version = creer_version(
            contrat,
            cree_par=auteur,
            motif=f'Avenant n°{numero} — {nom}',
        )
    except Exception:  # pragma: no cover - défensif (rendu best-effort)
        version = None

    if version is not None:
        avenant.version_creee = version
        avenant.save(update_fields=['version_creee'])

    # CONTRAT15 — audit de la création de l'avenant.
    journaliser_transition(
        contrat, field='avenant', old_value='',
        new_value=f'Avenant n°{numero} — {nom}',
        auteur=auteur)

    return avenant


# ---------------------------------------------------------------------------
# XCTR6 — Prorata temporis sur avenant en cours de période
# ---------------------------------------------------------------------------

# Nombre de mois couverts par UNE période, par périodicité d'échéancier (même
# table que ``selectors._MOIS_PAR_PERIODE`` — un avenant sur une périodicité
# unique/personnalisée n'a pas de « prochaine échéance » calculable).
_MOIS_PAR_PERIODE_PRORATA = {
    'mensuelle': 1,
    'trimestrielle': 3,
    'semestrielle': 6,
    'annuelle': 12,
}


class ProrataError(Exception):
    """Levée quand un prorata d'avenant ne peut pas être calculé/appliqué.

    Ex. : la ligne n'appartient pas à une périodicité prorata-able, l'avenant
    n'a pas de ``date_effet``/``montant_delta``, ou la ligne est déjà facturée.
    """


def calculer_prorata_avenant(avenant, ligne, *, base_jours=None):
    """Calcule le montant PRORATA TEMPORIS d'un avenant sur UNE échéance — XCTR6.

    PUREMENT DÉCLARATIF (lecture seule) : ne crée AUCUNE écriture. La période
    couverte par ``ligne`` est déduite de la ``periodicite`` de son échéancier :
    ``[date_echeance − N mois, date_echeance[`` (N = 1/3/6/12 selon
    mensuelle/trimestrielle/semestrielle/annuelle). Le calcul base « jours
    réels » (par défaut) répartit ``avenant.montant_delta`` au prorata des
    jours restants de la période APRÈS ``date_effet`` :

        prorata = montant_delta × (jours_restants / jours_periode)

    - ``date_effet`` HORS de la période (avant le début ou à/après la fin,
      c.-à-d. à l'échéance elle-même) → prorata NUL (rien à répartir sur cette
      échéance — l'avenant s'applique en totalité, ou ne concerne pas encore
      cette période).
    - ``base_jours`` : nombre de jours de la période, si fourni (permet une
      base 30/360 conventionnelle) ; sinon les jours RÉELS calendaires
      (défaut — ``(fin − debut).days``).

    Renvoie un dict ``{'periode_debut', 'periode_fin', 'jours_periode',
    'jours_restants', 'prorata'}`` (``Decimal`` arrondi 2 décimales). Renvoie
    ``None`` si la périodicité de l'échéancier n'est pas prorata-able
    (unique/personnalisée) ou si ``montant_delta`` est ``None``.
    """
    from .models import Contrat

    if avenant.montant_delta is None or avenant.date_effet is None:
        return None

    periodicite = ligne.echeancier.periodicite
    mois = _MOIS_PAR_PERIODE_PRORATA.get(periodicite)
    if not mois:
        return None

    periode_fin = ligne.date_echeance
    periode_debut = Contrat.ajouter_mois(periode_fin, -mois)

    if avenant.date_effet <= periode_debut or avenant.date_effet >= periode_fin:
        # Hors période (avant le début, ou à/après la fin = pas de prorata à
        # appliquer sur CETTE échéance).
        jours_periode = base_jours or (periode_fin - periode_debut).days
        return {
            'periode_debut': periode_debut,
            'periode_fin': periode_fin,
            'jours_periode': jours_periode,
            'jours_restants': 0,
            'prorata': Decimal('0.00'),
        }

    jours_periode = base_jours or (periode_fin - periode_debut).days
    jours_restants = (periode_fin - avenant.date_effet).days
    if jours_periode <= 0:
        prorata = Decimal('0.00')
    else:
        prorata = (
            avenant.montant_delta * Decimal(jours_restants)
            / Decimal(jours_periode)
        ).quantize(Decimal('0.01'))

    return {
        'periode_debut': periode_debut,
        'periode_fin': periode_fin,
        'jours_periode': jours_periode,
        'jours_restants': jours_restants,
        'prorata': prorata,
    }


@transaction.atomic
def appliquer_prorata_avenant(avenant, ligne, *, auteur=None, base_jours=None):
    """Applique le prorata d'un avenant sur UNE échéance à venir — XCTR6.

    Calcule le prorata (``calculer_prorata_avenant``) puis, s'il est NON nul :

    - HAUSSE (prorata > 0) : ajoute une ligne COMPLÉMENTAIRE à l'échéancier de
      la ligne (``services.ajouter_ligne_echeance`` — numéro max+1 sous verrou,
      jamais ``count()+1``), datée à ``ligne.date_echeance``, montant = prorata.
      Cette ligne complémentaire est facturée normalement au cycle suivant
      (CONTRAT31/XCTR5) — elle n'émet PAS de facture elle-même ici.
    - BAISSE (prorata < 0) : crée un ``ventes.Avoir`` lié à la DERNIÈRE facture
      émise pour le contrat (frontière cross-app, import fonction-local ;
      ``ventes.services`` n'est pas encore requis ici — création directe du
      modèle Avoir, cohérente avec ``ventes.services`` qui fait de même) pour
      le montant absolu du prorata. Sans facture antérieure à créditer, l'avoir
      n'est pas créé (rien à créditer) — le prorata reste tracé au chatter.
    - Un avenant à date d'échéance (prorata nul) n'a AUCUN effet : ni ligne, ni
      avoir.

    Journalise le résultat dans le chatter du contrat (CONTRAT15). Lève
    ``ProrataError`` si la ligne est déjà facturée (rien à ajuster) ou si le
    calcul renvoie ``None`` (périodicité non prorata-able / avenant sans delta).

    Renvoie un dict ``{'prorata', 'ligne_complementaire', 'avoir'}``
    (``ligne_complementaire``/``avoir`` sont ``None`` si non applicables).
    """
    if ligne.facture_id:
        raise ProrataError(
            "Cette échéance est déjà facturée — le prorata ne peut plus être "
            "ajusté dessus.")

    calcul = calculer_prorata_avenant(avenant, ligne, base_jours=base_jours)
    if calcul is None:
        raise ProrataError(
            "Le prorata n'est pas calculable pour cette échéance (périodicité "
            "non prorata-able ou avenant sans montant_delta/date_effet).")

    prorata = calcul['prorata']
    ligne_complementaire = None
    avoir = None

    if prorata > 0:
        ligne_complementaire = ajouter_ligne_echeance(
            ligne.echeancier,
            date_echeance=ligne.date_echeance,
            montant=prorata,
            libelle=(
                f'Prorata avenant n°{avenant.numero} — {avenant.objet}'),
        )
    elif prorata < 0:
        avoir = _creer_avoir_prorata(avenant, ligne.echeancier.contrat,
                                     abs(prorata))

    journaliser_transition(
        avenant.contrat, field='prorata_avenant',
        old_value='',
        new_value=_fmt_montant(prorata, avenant.contrat.devise),
        message=(
            f'Prorata temporis avenant n°{avenant.numero} sur échéance '
            f'n°{ligne.numero} (période {calcul["periode_debut"]} → '
            f'{calcul["periode_fin"]}).'),
        auteur=auteur)

    return {
        'prorata': prorata,
        'ligne_complementaire': ligne_complementaire,
        'avoir': avoir,
    }


def _creer_avoir_prorata(avenant, contrat, montant_abs):
    """Crée un ``ventes.Avoir`` lié à la dernière facture du contrat — XCTR6.

    Frontière cross-app (CLAUDE.md) : import FONCTION-LOCAL de
    ``ventes.models``/``ventes.utils.references`` uniquement (jamais une vue).
    Sans facture antérieure émise pour ce contrat, renvoie ``None`` (rien à
    créditer — le prorata reste tracé au chatter seul).
    """
    from decimal import ROUND_HALF_UP

    from .models import LigneEcheance

    from apps.ventes.models import Avoir, Facture
    from apps.ventes.utils.references import create_with_reference

    facture_id = (
        LigneEcheance.objects
        .filter(echeancier__contrat=contrat, facture_id__isnull=False)
        .exclude(statut=LigneEcheance.Statut.ANNULEE)
        .order_by('-date_echeance', '-id')
        .values_list('facture_id', flat=True)
        .first()
    )
    if not facture_id:
        return None

    try:
        facture = Facture.objects.get(pk=facture_id, company=contrat.company)
    except Facture.DoesNotExist:  # pragma: no cover - défensif
        return None

    tva_pct = facture.taux_tva or Decimal('20')
    montant_ttc = Decimal(str(montant_abs))
    montant_ht = (montant_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ttc - montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _create(ref):
        return Avoir.objects.create(
            reference=ref,
            company=contrat.company,
            facture=facture,
            client=facture.client,
            taux_tva=tva_pct,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            motif=(
                f'Prorata temporis avenant n°{avenant.numero} '
                f'(baisse) — contrat #{contrat.id}'),
        )

    return create_with_reference(Avoir, 'AV', contrat.company, _create)


# ---------------------------------------------------------------------------
# CONTRAT25 — Résiliation (motif / préavis / solde) → statut « résilié »
# ---------------------------------------------------------------------------


class ResiliationError(Exception):
    """Levée quand une résiliation de contrat est invalide.

    Ex. : tenter de résilier un contrat depuis un état NON résiliable (la machine
    d'états gardée refuse la transition ``→ resilie``), ou rouvrir une seconde
    résiliation active alors qu'une résiliation non annulée existe déjà.
    """


def resiliation_active(contrat):
    """Résiliation ACTIVE (non annulée) du contrat, ou ``None``.

    Garde idempotente : on n'ouvre pas une seconde résiliation active sur un
    contrat qui en porte déjà une (``demande`` ou ``effective``). Scopée société
    (portée par le contrat).
    """
    from .models import Resiliation

    return (
        Resiliation.objects
        .filter(contrat=contrat, company=contrat.company)
        .exclude(statut=Resiliation.Statut.ANNULEE)
        .order_by('-id')
        .first()
    )


@transaction.atomic
def resilier_contrat(contrat, *, motif='', motif_ref=None, date_effet=None,
                     preavis_jours=None, solde=None, auteur=None, today=None,
                     snapshot=True):
    """Résilie un contrat (motif / préavis / solde) — CONTRAT25.

    Enregistre une ``Resiliation`` (motif, date d'effet, préavis observé, solde
    de tout compte éventuel) ET fait basculer le ``Contrat.statut`` vers
    ``resilie`` via la machine d'états GARDÉE (``changer_statut``) — JAMAIS une
    écriture directe du statut, JAMAIS un funnel ``STAGES.py`` (rule #2). La
    machine d'états est l'UNIQUE gardienne de la résiliabilité : un contrat dans
    un état d'où ``→ resilie`` n'est pas permis (p. ex. déjà ``resilie`` ou
    ``expire``, états terminaux) fait lever ``ResiliationError`` et RIEN n'est
    créé (la transaction protège l'atomicité).

    Déroulé (tout est posé CÔTÉ SERVEUR, jamais lu d'un corps de requête) :

    - GARDE D'IDEMPOTENCE : si une résiliation ACTIVE (non annulée) existe déjà
      pour ce contrat, ``ResiliationError`` est levée (pas de doublon).
    - GARDE DE TRANSITION : la transition ``statut courant → resilie`` doit être
      permise par la machine d'états (``transition_permise``) ; sinon
      ``ResiliationError``. La bascule passe par ``changer_statut`` (gardée).
    - ENREGISTREMENT : création de la ``Resiliation`` (``statut=demande``), avec
      ``date_demande`` = ``today`` (date du jour, injectable), la société déduite
      du contrat.
    - SNAPSHOT (si ``snapshot``) : un instantané immuable est figé via
      ``creer_version(motif='Résiliation')`` (CONTRAT18) — best-effort : un échec
      de rendu n'empêche jamais la résiliation. La version est reliée à la
      résiliation (``version_creee``).
    - AUDIT : la bascule de statut est journalisée dans le chatter (CONTRAT15),
      auteur et société posés côté serveur.
    - DE-PROVISIONING (YSUBS5) : les ``LigneEcheance`` FUTURES non encore
      facturées (``facture_id`` NULL, ``date_echeance > today``) de TOUS les
      échéanciers du contrat passent ``annulee`` — la résiliation stoppe la
      facturation récurrente à venir sans jamais toucher aux échéances déjà
      facturées (historique immuable). Puis un signal ``contrat_resilie``
      (``core/events.py``) est émis pour la propagation aval DÉCOUPLÉE (ex.
      arrêt des visites préventives SAV, ``apps/sav/receivers.py``) — best-
      effort, jamais bloquant pour la résiliation elle-même (déjà actée).
    - ZCTR3 : ``motif_ref`` (optionnel) rattache un ``MotifResiliation``
      NORMALISÉ, en PLUS du texte libre ``motif`` (jamais en remplacement).
      Doit appartenir à la MÊME société que le contrat — sinon
      ``ResiliationError`` et rien n'est créé.

    Renvoie la ``Resiliation`` créée (``version_creee`` renseigné si snapshot).
    """
    from .models import Contrat, LigneEcheance, MotifResiliation, Resiliation

    if today is None:
        today = timezone.localdate()

    # Garde d'idempotence : pas de seconde résiliation active.
    if resiliation_active(contrat) is not None:
        raise ResiliationError(
            "Une résiliation est déjà en cours pour ce contrat.")

    # Garde de transition : la machine d'états doit autoriser « → resilie » depuis
    # l'état courant. On vérifie AVANT d'écrire quoi que ce soit (atomicité).
    if not transition_permise(contrat.statut, Contrat.Statut.RESILIE):
        raise ResiliationError(
            f"Le contrat ne peut pas être résilié depuis l'état "
            f"« {contrat.statut} ».")

    # ZCTR3 — le motif référentiel, s'il est fourni, doit appartenir à la même
    # société que le contrat (jamais un motif d'une autre société).
    if motif_ref is not None:
        if isinstance(motif_ref, MotifResiliation):
            if motif_ref.company_id != contrat.company_id:
                raise ResiliationError(
                    "Le motif de résiliation n'appartient pas à votre "
                    "société.")
        else:
            try:
                motif_ref = MotifResiliation.objects.get(
                    pk=motif_ref, company=contrat.company)
            except MotifResiliation.DoesNotExist:
                raise ResiliationError(
                    "Le motif de résiliation est introuvable dans votre "
                    "société.")

    ancien = contrat.statut

    # Bascule de statut via la machine d'états GARDÉE (jamais un write direct).
    try:
        changer_statut(contrat, Contrat.Statut.RESILIE)
    except TransitionInterdite as exc:
        # La machine d'états refuse : on reformule et RIEN n'est persisté (la
        # transaction est annulée par la levée).
        raise ResiliationError(str(exc))

    resiliation = Resiliation.objects.create(
        company=contrat.company,
        contrat=contrat,
        motif=motif or '',
        motif_ref=motif_ref,
        date_demande=today,
        date_effet=date_effet,
        preavis_jours=preavis_jours,
        solde=solde,
        statut=Resiliation.Statut.DEMANDE,
        cree_par=auteur,
    )

    # CONTRAT15 — audit de la bascule de statut (ancien → resilie).
    journaliser_transition(
        contrat, field='statut', old_value=ancien,
        new_value=contrat.statut,
        message='Résiliation du contrat.',
        auteur=auteur)

    # CONTRAT18 — instantané immuable best-effort figeant l'état au moment de la
    # résiliation. On relie la version à la résiliation.
    if snapshot:
        try:
            version = creer_version(
                contrat, cree_par=auteur, motif='Résiliation')
        except Exception:  # pragma: no cover - défensif (rendu best-effort)
            version = None
        if version is not None:
            resiliation.version_creee = version
            resiliation.save(update_fields=['version_creee'])

    # YSUBS5 — de-provisioning : annule les échéances FUTURES non facturées
    # (aucun impact sur l'historique déjà facturé). Même app, pas de
    # frontière cross-app ici.
    (
        LigneEcheance.objects
        .filter(
            echeancier__contrat=contrat, facture_id__isnull=True,
            date_echeance__gt=today,
        )
        .exclude(statut=LigneEcheance.Statut.ANNULEE)
        .update(statut=LigneEcheance.Statut.ANNULEE)
    )

    # YSUBS5 — propagation aval DÉCOUPLÉE (de-provisioning). Best-effort :
    # un abonné qui échoue ne doit jamais faire échouer la résiliation,
    # déjà actée ci-dessus.
    try:
        from core.events import contrat_resilie as contrat_resilie_signal

        contrat_resilie_signal.send(
            sender=None, contrat_id=contrat.id, company=contrat.company,
            date_effet=date_effet)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass

    return resiliation


# ---------------------------------------------------------------------------
# CONTRAT26 — Obligations (livrables) & jalons
# ---------------------------------------------------------------------------


def _prochain_numero_jalon(contrat):
    """Numéro du prochain jalon d'un contrat (``max(numero)+1``).

    Lecture du plus haut numéro DÉJÀ utilisé pour ce contrat, +1. Repli sur 1
    quand aucun jalon n'existe encore. À appeler SOUS verrou de ligne
    (``select_for_update`` sur le contrat) pour rester sûr face aux courses —
    JAMAIS un ``count()+1`` (qui collisionne après une suppression et en
    concurrence, cf. la règle de numérotation du repo).
    """
    from django.db.models import Max

    from .models import JalonContrat

    plus_haut = (
        JalonContrat.objects
        .filter(contrat=contrat, company=contrat.company)
        .aggregate(m=Max('numero'))['m']
    )
    return (plus_haut or 0) + 1


@transaction.atomic
def creer_jalon(contrat, *, intitule, description='', date_cible=None,
                auteur=None):
    """Crée un JALON d'un contrat (étape clé datée) — CONTRAT26.

    NUMÉROTATION SÛRE FACE AUX COURSES : on verrouille la LIGNE du contrat
    (``select_for_update``) puis on calcule ``max(numero)+1`` — jamais un
    ``count()+1``. Sous le verrou, deux créations concurrentes pour le même
    contrat sont sérialisées (la contrainte d'unicité ``(contrat, numero)``
    reste le filet de sécurité ultime).

    La société est déduite du contrat (posée CÔTÉ SERVEUR). Le ``statut`` du
    contrat n'est JAMAIS modifié (préservation des statuts — CONTRAT12) ;
    aucun funnel ``STAGES.py`` n'intervient (rule #2). L'opération est journalisée
    au chatter (CONTRAT15). Renvoie le ``JalonContrat`` créé.
    """
    from .models import Contrat, JalonContrat

    nom = (intitule or '').strip()
    if not nom:
        raise ValueError("L'intitulé du jalon est requis.")

    # Verrou de ligne sur le contrat pour sérialiser la numérotation concurrente.
    Contrat.objects.select_for_update().get(pk=contrat.pk)

    numero = _prochain_numero_jalon(contrat)

    jalon = JalonContrat.objects.create(
        company=contrat.company,
        contrat=contrat,
        numero=numero,
        intitule=nom,
        description=description or '',
        date_cible=date_cible,
    )

    journaliser_transition(
        contrat, field='jalon', old_value='',
        new_value=f'Jalon n°{numero} — {nom}',
        auteur=auteur)

    return jalon


def marquer_jalon_atteint(jalon, *, today=None, auteur=None):
    """Marque un jalon ATTEINT (statut + date d'atteinte côté serveur) — CONTRAT26.

    Pose ``statut=atteint`` et ``date_atteinte=today`` (date du jour injectable).
    Idempotent : un jalon déjà ``atteint`` n'est pas re-touché. Journalise au
    chatter du contrat (CONTRAT15). Ne change AUCUN ``Contrat.statut``. Renvoie
    le jalon.
    """
    from .models import JalonContrat

    if today is None:
        today = timezone.localdate()
    if jalon.statut == JalonContrat.Statut.ATTEINT:
        return jalon
    ancien = jalon.statut
    jalon.statut = JalonContrat.Statut.ATTEINT
    jalon.date_atteinte = today
    jalon.save(update_fields=['statut', 'date_atteinte'])
    journaliser_transition(
        jalon.contrat, field='jalon_statut', old_value=ancien,
        new_value=jalon.statut,
        message=f'Jalon n°{jalon.numero} atteint.', auteur=auteur)
    return jalon


def marquer_obligation_faite(obligation, *, today=None, auteur=None):
    """Marque une obligation RÉALISÉE (statut + date côté serveur) — CONTRAT26.

    Pose ``statut=faite`` et ``date_realisation=today`` (date du jour injectable).
    Idempotent : une obligation déjà ``faite`` n'est pas re-touchée. Journalise
    au chatter du contrat (CONTRAT15). Ne change AUCUN ``Contrat.statut``. Renvoie
    l'obligation.
    """
    from .models import Obligation

    if today is None:
        today = timezone.localdate()
    # Déjà réalisée ET datée → rien à faire. Si elle a été créée directement
    # avec statut=faite (POST) sans date, on POSE la date côté serveur ici.
    if obligation.statut == Obligation.Statut.FAITE and \
            obligation.date_realisation:
        return obligation
    ancien = obligation.statut
    obligation.statut = Obligation.Statut.FAITE
    obligation.date_realisation = obligation.date_realisation or today
    obligation.save(update_fields=['statut', 'date_realisation'])
    journaliser_transition(
        obligation.contrat, field='obligation_statut', old_value=ancien,
        new_value=obligation.statut,
        message=f'Obligation « {obligation.intitule} » réalisée.',
        auteur=auteur)
    return obligation


# ---------------------------------------------------------------------------
# CONTRAT27 — SLA & pénalités (taux SLA, valeur pénalité)
# ---------------------------------------------------------------------------


def calculer_penalite_sla(sla, *, taux_realise=None, montant_contrat=None):
    """Calcule la pénalité encourue pour un ``EngagementSLA`` — CONTRAT27.

    PUREMENT DÉCLARATIF (lecture seule) : ne crée AUCUNE écriture, ne touche
    AUCUN ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2),
    et n'émet aucune facture.

    Si ``taux_realise`` est fourni et qu'il ATTEINT/dépasse le ``taux_cible`` du
    SLA, AUCUNE pénalité n'est due (renvoie 0). Sinon (ou si ``taux_realise``
    n'est pas fourni — calcul du barème théorique), la pénalité est calculée par
    ``sla.calculer_penalite`` (montant fixe ou pourcentage du montant du contrat,
    plafonné par ``penalite_max``).

    Renvoie un dict ``{'penalite': Decimal, 'respecte': bool|None,
    'taux_cible': Decimal, 'taux_realise': Decimal|None}``.
    """
    cible = sla.taux_cible or Decimal('0')
    respecte = None
    if taux_realise is not None:
        taux_realise = Decimal(str(taux_realise))
        respecte = taux_realise >= cible
        if respecte:
            return {
                'penalite': Decimal('0.00'),
                'respecte': True,
                'taux_cible': cible,
                'taux_realise': taux_realise,
            }
    penalite = sla.calculer_penalite(montant_contrat=montant_contrat)
    return {
        'penalite': penalite,
        'respecte': respecte,
        'taux_cible': cible,
        'taux_realise': taux_realise,
    }


# ---------------------------------------------------------------------------
# CONTRAT28 — Retenue de garantie (suivi de libération)
# ---------------------------------------------------------------------------


def liberer_retenue(retenue, *, today=None, auteur=None):
    """Libère une retenue de garantie (statut + date côté serveur) — CONTRAT28.

    Pose ``statut=liberee`` et ``date_liberation_effective=today`` (date du jour
    injectable). Idempotent : une retenue déjà ``liberee`` reste inchangée ; une
    retenue ``annulee`` ne peut pas être libérée (lève ``ValueError``). Journalise
    au chatter du contrat (CONTRAT15). Ne change AUCUN ``Contrat.statut`` et
    n'émet aucune facture/aucun mouvement comptable (déclaratif). Renvoie la
    retenue.
    """
    from .models import RetenueGarantie

    if today is None:
        today = timezone.localdate()
    if retenue.statut == RetenueGarantie.Statut.LIBEREE:
        return retenue
    if retenue.statut == RetenueGarantie.Statut.ANNULEE:
        raise ValueError("Une retenue annulée ne peut pas être libérée.")
    ancien = retenue.statut
    retenue.statut = RetenueGarantie.Statut.LIBEREE
    retenue.date_liberation_effective = today
    retenue.save(update_fields=['statut', 'date_liberation_effective'])
    journaliser_transition(
        retenue.contrat, field='retenue_statut', old_value=ancien,
        new_value=retenue.statut,
        message=f'Retenue de garantie libérée ({retenue.montant_retenu}).',
        auteur=auteur)
    return retenue


# ---------------------------------------------------------------------------
# CONTRAT30 — Échéancier de paiement (en-tête + lignes)
# ---------------------------------------------------------------------------


def recalculer_total_echeancier(echeancier):
    """Recalcule ``montant_total`` = somme des lignes non annulées — CONTRAT30.

    Pose le total CÔTÉ SERVEUR (cache) à partir des montants des lignes dont le
    statut n'est pas ``annulee``. Renvoie l'échéancier mis à jour. Ne change
    AUCUN ``Contrat.statut``.
    """
    from django.db.models import Sum

    from .models import LigneEcheance

    total = (
        LigneEcheance.objects
        .filter(echeancier=echeancier, company=echeancier.company)
        .exclude(statut=LigneEcheance.Statut.ANNULEE)
        .aggregate(s=Sum('montant'))['s']
    ) or Decimal('0')
    echeancier.montant_total = total
    echeancier.save(update_fields=['montant_total'])
    return echeancier


def _prochain_numero_ligne(echeancier):
    """Numéro de la prochaine ligne d'un échéancier (``max(numero)+1``).

    Lecture du plus haut numéro DÉJÀ utilisé, +1. Repli sur 1. À appeler SOUS
    verrou de ligne (``select_for_update`` sur l'échéancier) — JAMAIS un
    ``count()+1`` (qui collisionne, cf. la règle de numérotation du repo).
    """
    from django.db.models import Max

    from .models import LigneEcheance

    plus_haut = (
        LigneEcheance.objects
        .filter(echeancier=echeancier, company=echeancier.company)
        .aggregate(m=Max('numero'))['m']
    )
    return (plus_haut or 0) + 1


@transaction.atomic
def ajouter_ligne_echeance(echeancier, *, date_echeance, montant=None,
                           libelle=''):
    """Ajoute une ligne (échéance) à un échéancier — CONTRAT30.

    NUMÉROTATION SÛRE FACE AUX COURSES : on verrouille la LIGNE de l'échéancier
    (``select_for_update``) puis on calcule ``max(numero)+1`` — jamais un
    ``count()+1`` (la contrainte d'unicité ``(echeancier, numero)`` reste le
    filet de sécurité ultime). La société est déduite de l'échéancier (posée
    côté serveur). Recalcule ensuite ``montant_total``. Renvoie la
    ``LigneEcheance`` créée.
    """
    from .models import EcheancierContrat, LigneEcheance

    if date_echeance is None:
        raise ValueError("La date d'échéance est requise.")

    # Verrou de ligne sur l'échéancier pour sérialiser la numérotation.
    EcheancierContrat.objects.select_for_update().get(pk=echeancier.pk)

    numero = _prochain_numero_ligne(echeancier)

    ligne = LigneEcheance.objects.create(
        company=echeancier.company,
        echeancier=echeancier,
        numero=numero,
        libelle=libelle or '',
        date_echeance=date_echeance,
        montant=montant if montant is not None else Decimal('0'),
    )

    recalculer_total_echeancier(echeancier)
    return ligne


# Nombre de mois par pas de périodicité — utilisé par
# ``generer_echeancier_depuis_dates`` (YSUBS8) pour dériver le jeu de dates de
# facturation. ``unique``/``personnalisee`` ne sont PAS matérialisables
# automatiquement (aucun pas défini) : ``generer_echeancier_depuis_dates`` les
# ignore (no-op, comportement actuel préservé).
_MOIS_PAR_PERIODICITE = {
    'mensuelle': 1,
    'trimestrielle': 3,
    'semestrielle': 6,
    'annuelle': 12,
}


@transaction.atomic
def generer_echeancier_depuis_dates(contrat, echeancier, *, avance=True,
                                    auteur=None):
    """Matérialise le plan de facturation à l'ACTIVATION du contrat — YSUBS8.

    `signer_contrat` → `activer_si_eligible` (CONTRAT17) fait passer le contrat
    à ``actif`` mais ne générait AUCUNE ``LigneEcheance`` : l'échéancier restait
    vide et les lignes devaient être ajoutées à la main
    (``ajouter_ligne_echeance``). Le blueprint exige que le jeu de dates de
    facturation soit DÉRIVÉ des dates du contrat dès l'activation (visible
    d'avance, jamais calculé paresseusement).

    Sur un ``EcheancierContrat`` ``facturation_active`` dont la ``periodicite``
    a un pas connu (mensuelle/trimestrielle/semestrielle/annuelle —
    ``unique``/``personnalisee`` n'ont pas de pas et sont laissés inchangés),
    matérialise une ``LigneEcheance`` par période entre ``contrat.date_debut``
    (ou ``contrat.date_fin`` si absent, garde) et ``contrat.date_fin``, au
    montant du ``Contrat.montant`` (échéance UNIQUE = tout le montant à
    ``date_debut`` — pas de découpage). ``avance=True`` (par défaut) date
    chaque échéance en DÉBUT de période ; ``avance=False`` la date en FIN de
    période (échu).

    IDEMPOTENT : une ligne dont la ``date_echeance`` coïncide avec une période
    déjà présente n'est PAS recréée (comparaison par ensemble des
    ``date_echeance`` déjà matérialisées). ``montant_total`` est recalculé une
    fois à la fin. Renvoie la liste des ``LigneEcheance`` créées lors de CET
    appel (liste vide si rien à faire ou déjà matérialisé).

    Aucune écriture cross-app, aucun changement de ``Contrat.statut``.
    """
    from .models import Contrat, EcheancierContrat, LigneEcheance

    if not echeancier.facturation_active:
        return []
    if contrat.date_debut is None or contrat.date_fin is None:
        # Sans les deux bornes, pas de plan dérivable — comportement actuel
        # préservé (aucune ligne générée).
        return []

    pas_mois = _MOIS_PAR_PERIODICITE.get(echeancier.periodicite)
    dates_a_generer = []
    if pas_mois is None:
        if echeancier.periodicite == EcheancierContrat.Periodicite.UNIQUE:
            dates_a_generer = [contrat.date_debut]
        else:
            # ``personnalisee`` : aucun pas standard, laissé à la main
            # (no-op — comportement actuel préservé).
            return []
    else:
        from datetime import timedelta

        curseur = contrat.date_debut
        while curseur <= contrat.date_fin:
            fin_periode = min(
                Contrat.ajouter_mois(curseur, pas_mois) - timedelta(days=1),
                contrat.date_fin)
            dates_a_generer.append(curseur if avance else fin_periode)
            curseur = Contrat.ajouter_mois(curseur, pas_mois)

    deja_presentes = set(
        LigneEcheance.objects
        .filter(echeancier=echeancier, company=echeancier.company)
        .values_list('date_echeance', flat=True)
    )

    lignes_creees = []
    for date_echeance in dates_a_generer:
        if date_echeance in deja_presentes:
            continue
        ligne = ajouter_ligne_echeance(
            echeancier, date_echeance=date_echeance,
            montant=contrat.montant,
            libelle=f'Échéance {contrat.objet}')
        lignes_creees.append(ligne)
        deja_presentes.add(date_echeance)

    if lignes_creees:
        journaliser_transition(
            contrat, field='echeancier_genere', old_value='',
            new_value=str(len(lignes_creees)),
            message=(
                f'Échéancier de facturation généré à l\'activation : '
                f'{len(lignes_creees)} échéance(s) créée(s).'),
            auteur=auteur)

    return lignes_creees


def pointer_paiement_echeance(ligne, *, today=None):
    """Pointe une ligne d'échéance comme PAYÉE (statut + date côté serveur) — CONTRAT30.

    Pose ``statut=payee`` et ``date_paiement=today`` (date du jour injectable).
    Idempotent : une ligne déjà ``payee`` reste inchangée. Ne change AUCUN
    ``Contrat.statut`` et n'émet aucune facture. Renvoie la ligne.
    """
    from .models import LigneEcheance

    if today is None:
        today = timezone.localdate()
    if ligne.statut == LigneEcheance.Statut.PAYEE:
        return ligne
    ligne.statut = LigneEcheance.Statut.PAYEE
    ligne.date_paiement = today
    ligne.save(update_fields=['statut', 'date_paiement'])
    return ligne


# ---------------------------------------------------------------------------
# CONTRAT31 — Lien facturation récurrente (via ventes)
# ---------------------------------------------------------------------------


class FacturationError(Exception):
    """Levée quand une échéance ne peut pas être facturée.

    Ex. : facturation non activée sur l'échéancier, échéance déjà facturée
    (garde d'idempotence), contrat sans client résolu, ou ligne au montant nul.
    """


@transaction.atomic
def facturer_ligne_echeance(ligne, *, user=None, taux_tva=Decimal('20')):
    """Émet une Facture récurrente pour une échéance — CONTRAT31.

    Crée une ``ventes.Facture`` (statut émise) à partir d'une ``LigneEcheance``
    d'un échéancier dont la ``facturation_active`` est vraie, et relie la facture
    à la ligne (``ligne.facture_id`` — lien LÂCHE par id, jamais un FK dur).

    FRONTIÈRE CROSS-APP (CLAUDE.md) : le CLIENT du contrat est résolu via le
    sélecteur de lecture de l'app cible (``crm.selectors.get_company_client``) —
    jamais un import du modèle ``crm.Client``. La Facture est créée via le
    référentiel de numérotation de ``ventes``
    (``ventes.utils.references.create_with_reference``) — même point d'entrée
    qu'utilise déjà l'app ``sav`` pour ses factures de maintenance —, sans jamais
    importer une ``view`` d'une autre app. Le ``montant`` de la ligne est traité
    comme TTC (cohérent avec l'ERP 100 % TTC) et ventilé HT/TVA au ``taux_tva``.

    GARDES (toutes lèvent ``FacturationError`` sans rien écrire — atomicité) :

    - l'échéancier doit avoir ``facturation_active=True`` ;
    - la ligne ne doit pas être déjà facturée (``facture_id`` non nul) ni
      annulée ;
    - le montant de la ligne doit être strictement positif ;
    - le contrat doit porter un ``client_id`` résoluble en client de la société.

    Le ``Contrat.statut`` n'est JAMAIS modifié (préservation des statuts —
    CONTRAT12) ; aucun funnel ``STAGES.py`` (rule #2). La société est celle de la
    ligne (posée côté serveur). Renvoie la Facture créée.
    """
    from decimal import ROUND_HALF_UP

    from .models import LigneEcheance

    echeancier = ligne.echeancier
    if not echeancier.facturation_active:
        raise FacturationError(
            "La facturation récurrente n'est pas activée sur cet échéancier.")
    if ligne.facture_id:
        raise FacturationError("Cette échéance a déjà été facturée.")
    if ligne.statut == LigneEcheance.Statut.ANNULEE:
        raise FacturationError("Une échéance annulée ne peut pas être facturée.")
    montant_ttc = ligne.montant or Decimal('0')
    if montant_ttc <= 0:
        raise FacturationError("Le montant de l'échéance doit être positif.")

    contrat = echeancier.contrat
    if not contrat.client_id:
        raise FacturationError(
            "Le contrat n'a pas de client : impossible d'émettre une facture.")

    # Frontière cross-app : résolution du client via le sélecteur crm (lecture),
    # jamais un import de crm.models.
    from apps.crm.selectors import get_company_client

    client = get_company_client(echeancier.company, contrat.client_id)
    if client is None:
        raise FacturationError(
            "Le client du contrat est introuvable dans votre société.")

    # NTSUB2 — ajoute le montant des add-ons ACTIFS de la période au total
    # facturé (0 si aucun add-on rattaché : comportement STRICTEMENT inchangé
    # pour tout contrat sans add-on — la quasi-totalité des contrats existants).
    from .models import AbonnementAddOnLigne

    montant_addons = montant_addons_periode(
        echeancier.company,
        type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
        cible_id=contrat.id, periode_fin=ligne.date_echeance)
    if montant_addons:
        montant_ttc += montant_addons

    tva_pct = Decimal(str(taux_tva))
    montant_ht = (montant_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ttc - montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    libelle = (
        f'Échéance n°{ligne.numero} — contrat #{contrat.id} '
        f'({echeancier.get_periodicite_display()})'
    )
    if montant_addons:
        libelle += f' — inclut {montant_addons} MAD d\'add-ons'

    # YSUBS9 — période de service couverte par CETTE échéance : de l'échéance
    # PRÉCÉDENTE (numéro le plus proche en-dessous) à celle-ci, ou de
    # `Contrat.date_debut` pour la toute première ligne. Best-effort : une
    # date de début de contrat absente laisse `periode_service_debut` à NULL
    # (comportement actuel intact), `periode_service_fin` reste toujours la
    # date d'échéance de cette ligne.
    ligne_precedente = (
        LigneEcheance.objects
        .filter(echeancier=echeancier, numero__lt=ligne.numero)
        .order_by('-numero')
        .first()
    )
    periode_debut = (
        ligne_precedente.date_echeance if ligne_precedente is not None
        else getattr(contrat, 'date_debut', None)
    )
    periode_fin = ligne.date_echeance

    # Frontière cross-app : création de la Facture via le référentiel de
    # numérotation de ventes (même point d'entrée qu'utilise sav), sans importer
    # de view d'une autre app.
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=echeancier.company,
            client=client,
            statut=Facture.Statut.EMISE,
            taux_tva=tva_pct,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
            periode_service_debut=periode_debut,
            periode_service_fin=periode_fin,
        )

    facture = create_with_reference(Facture, 'FAC', echeancier.company, _create)

    # Lien LÂCHE retour (id seul) + garde d'idempotence.
    ligne.facture_id = facture.id
    ligne.save(update_fields=['facture_id'])

    # YSUBS6 — cette facture est créée EMISE directement (échéancier récurrent,
    # jamais de passage par l'action `emettre`) : émettre l'événement
    # documentaire pour que l'auto-écriture compta (YLEDG1, gardée par le
    # toggle COMPTA_AUTO_ECRITURES, OFF par défaut) se déclenche comme sur une
    # facture émise via l'écran. core.events est une fondation (M6) — jamais
    # d'import d'apps.compta ici.
    from core.events import facture_emise
    facture_emise.send(
        sender=Facture, instance=facture, company=echeancier.company)

    journaliser_transition(
        contrat, field='facturation', old_value='',
        new_value=f'Facture {facture.reference} (échéance n°{ligne.numero})',
        message='Facturation récurrente d\'une échéance.', auteur=user)

    return facture


# ---------------------------------------------------------------------------
# CONTRAT32 — Indexation / révision de prix
# ---------------------------------------------------------------------------


def calculer_prix_indexe(indexation, *, valeur_actuelle, prix_base=None):
    """Calcule le prix révisé d'une indexation (lecture seule) — CONTRAT32.

    PUREMENT DÉCLARATIF : ne crée AUCUNE écriture, ne change AUCUN statut. Délègue
    à ``IndexationPrix.calculer_prix_indexe``. Renvoie un dict
    ``{'prix_base': Decimal, 'prix_revise': Decimal, 'delta': Decimal,
    'valeur_actuelle': Decimal}``.
    """
    if prix_base is None:
        prix_base = indexation.contrat.montant or Decimal('0')
    prix_base = Decimal(str(prix_base))
    prix_revise = indexation.calculer_prix_indexe(
        valeur_actuelle=valeur_actuelle, prix_base=prix_base)
    return {
        'prix_base': prix_base,
        'prix_revise': prix_revise,
        'delta': (prix_revise - prix_base).quantize(Decimal('0.01')),
        'valeur_actuelle': Decimal(str(valeur_actuelle)),
    }


@transaction.atomic
def appliquer_indexation(indexation, *, valeur_actuelle, auteur=None,
                         today=None):
    """Applique une révision de prix indexée via un AVENANT — CONTRAT32.

    Calcule le prix révisé pour ``valeur_actuelle`` puis, si le delta est non nul,
    crée un AVENANT (CONTRAT24) ajustant ``Contrat.montant`` du delta (la création
    d'avenant passe par ``creer_avenant`` — numérotation max+1, instantané immuable,
    audit chatter). Trace ``date_derniere_revision`` côté serveur. Le
    ``Contrat.statut`` n'est JAMAIS modifié (préservation des statuts — CONTRAT12)
    et aucun funnel ``STAGES.py`` n'intervient (rule #2).

    Renvoie un dict ``{'avenant': Avenant|None, 'prix_base', 'prix_revise',
    'delta'}``. ``avenant`` est ``None`` quand le delta est nul (aucune révision
    nécessaire) — on trace tout de même la date de révision.
    """
    if today is None:
        today = timezone.localdate()

    calcul = calculer_prix_indexe(
        indexation, valeur_actuelle=valeur_actuelle)
    delta = calcul['delta']

    avenant = None
    if delta != Decimal('0'):
        avenant = creer_avenant(
            indexation.contrat,
            objet=f'Indexation prix ({indexation.indice})',
            description=(
                f'Révision indexée : indice {indexation.indice} '
                f'valeur {calcul["valeur_actuelle"]} (base '
                f'{indexation.valeur_base}). '
                f'Prix {calcul["prix_base"]} → {calcul["prix_revise"]}.'),
            date_effet=today,
            montant_delta=delta,
            auteur=auteur)

    indexation.date_derniere_revision = today
    indexation.save(update_fields=['date_derniere_revision'])

    lignes_reappliquees = 0
    if delta != Decimal('0'):
        lignes_reappliquees = reappliquer_montant_echeancier(
            indexation.contrat, delta=delta, date_effet=today,
            auteur=auteur)

    return {
        'avenant': avenant,
        'prix_base': calcul['prix_base'],
        'prix_revise': calcul['prix_revise'],
        'delta': delta,
        'lignes_reappliquees': lignes_reappliquees,
    }


def reappliquer_montant_echeancier(contrat, *, delta, date_effet, auteur=None):
    """Re-tarife l'échéancier de facturation après une indexation — YSUBS7.

    ``appliquer_indexation`` (CONTRAT32) crée un AVENANT ajustant
    ``Contrat.montant`` du ``delta`` mais NE touchait pas les ``LigneEcheance``
    futures : la facture récurrente suivante billait l'ANCIEN montant. Ce
    service ajoute ``delta`` (peut être négatif) au ``montant`` de chaque
    ``LigneEcheance`` du contrat dont :

    - ``date_echeance >= date_effet`` (périodes futures uniquement), ET
    - ``facture_id`` est NULL (pas encore facturée), ET
    - ``statut != annulee``.

    Les échéances DÉJÀ facturées sont INTOUCHÉES (une correction sur une ligne
    déjà émise passerait par un avoir — hors périmètre de cette révision).
    ``montant_total`` de chaque échéancier touché est recalculé
    (``recalculer_total_echeancier``) et la révision est journalisée dans le
    chatter du contrat (``ContratActivity``). ``delta`` nul = aucun changement
    (no-op explicite, appelant déjà gardé par ``appliquer_indexation`` mais
    utilisable directement).

    Renvoie le nombre de lignes re-tarifées.
    """
    from .models import EcheancierContrat, LigneEcheance

    if delta == Decimal('0'):
        return 0

    lignes = list(
        LigneEcheance.objects.select_for_update().filter(
            company=contrat.company,
            echeancier__contrat=contrat,
            date_echeance__gte=date_effet,
            facture_id__isnull=True,
        ).exclude(statut=LigneEcheance.Statut.ANNULEE)
    )

    echeanciers_touches = set()
    for ligne in lignes:
        ligne.montant = (ligne.montant or Decimal('0')) + delta
        ligne.save(update_fields=['montant'])
        echeanciers_touches.add(ligne.echeancier_id)

    for echeancier_id in echeanciers_touches:
        echeancier = EcheancierContrat.objects.get(pk=echeancier_id)
        recalculer_total_echeancier(echeancier)

    if lignes:
        journaliser_transition(
            contrat, field='echeancier_indexation',
            old_value='', new_value=str(delta),
            message=(
                f'Échéancier re-tarifé après indexation : {len(lignes)} '
                f'échéance(s) future(s) ajustée(s) de {delta} '
                f'à compter du {date_effet}.'),
            auteur=auteur)

    return len(lignes)


# ---------------------------------------------------------------------------
# CONTRAT34 — Pièces de conformité (pièces obligatoires & attestations)
# ---------------------------------------------------------------------------


def marquer_piece_fournie(piece, *, ged_document_id=None, date_expiration=None,
                          today=None, auteur=None):
    """Marque une pièce de conformité FOURNIE (statut + date côté serveur) — CONTRAT34.

    Pose ``statut=fournie`` et ``date_fourniture=today`` (date du jour
    injectable). Relie éventuellement la pièce à un document GED par son id seul
    (``ged_document_id`` — lien LÂCHE, jamais un import de ``ged.models``) et fixe
    une ``date_expiration`` si fournie. Journalise au chatter du contrat
    (CONTRAT15). Ne change AUCUN ``Contrat.statut``. Renvoie la pièce.
    """
    from .models import PieceConformite

    if today is None:
        today = timezone.localdate()
    ancien = piece.statut
    piece.statut = PieceConformite.Statut.FOURNIE
    piece.date_fourniture = today
    champs = ['statut', 'date_fourniture']
    if ged_document_id is not None:
        piece.ged_document_id = ged_document_id
        champs.append('ged_document_id')
    if date_expiration is not None:
        piece.date_expiration = date_expiration
        champs.append('date_expiration')
    piece.save(update_fields=champs)
    journaliser_transition(
        piece.contrat, field='piece_conformite', old_value=ancien,
        new_value=piece.statut,
        message=f'Pièce « {piece.libelle} » fournie.', auteur=auteur)
    return piece


# ---------------------------------------------------------------------------
# XCTR5 — Journal des cycles de facturation récurrente + file d'exceptions
# ---------------------------------------------------------------------------


class RejeuError(Exception):
    """Levée quand une entrée du journal de facturation ne peut pas être rejouée.

    Ex. : l'entrée n'est pas en ``echec`` (déjà générée/sautée), ou la période
    est déjà facturée avec succès par une AUTRE entrée (garde anti double-
    facturation — jamais deux factures pour la même période contrat).
    """


def _cycle_deja_genere(company, source_type, source_id, periode):
    """``True`` si un cycle ``genere`` existe déjà pour ce triplet — XCTR5.

    Garde anti double-facturation : sert de filet de sécurité applicatif
    derrière la garde native ``LigneEcheance.facture_id`` (CONTRAT31) — jamais
    deux factures pour la même période d'un même contrat.
    """
    from .models import CycleFacturationLog

    return CycleFacturationLog.objects.filter(
        company=company, source_type=source_type, source_id=source_id,
        periode=periode, statut=CycleFacturationLog.Statut.GENERE,
    ).exists()


@transaction.atomic
def enregistrer_cycle(company, *, source_type, source_id, periode,
                      statut, motif='', facture_id=None):
    """Écrit UNE ligne du journal de facturation récurrente — XCTR5.

    Appelée par les services de facturation récurrente (``facturer_ligne_echeance``
    ici, ``sav.services`` pour ``ContratMaintenance``) APRÈS chaque tentative
    (succès, échec ou saut). ``company`` est TOUJOURS posée côté serveur par
    l'appelant (jamais lue du corps de requête).

    GARDE ANTI DOUBLE-FACTURATION : si ``statut='genere'`` et qu'un cycle
    ``genere`` existe déjà pour ``(source_type, source_id, periode)``,
    ``RejeuError`` est levée sans rien écrire — jamais deux factures pour la
    même période contrat.

    Renvoie le ``CycleFacturationLog`` créé.
    """
    from .models import CycleFacturationLog

    if statut == CycleFacturationLog.Statut.GENERE and _cycle_deja_genere(
            company, source_type, source_id, periode):
        raise RejeuError(
            "Cette période a déjà été facturée avec succès — refus de "
            "double-facturation.")

    return CycleFacturationLog.objects.create(
        company=company,
        source_type=source_type,
        source_id=source_id,
        periode=periode,
        statut=statut,
        motif=motif or '',
        facture_id=facture_id,
    )


def facturer_ligne_echeance_journalisee(ligne, *, user=None,
                                        taux_tva=Decimal('20'),
                                        periode=None):
    """Facture une échéance (CONTRAT31) ET journalise le résultat — XCTR5.

    Enveloppe ``facturer_ligne_echeance`` : sur succès, écrit un
    ``CycleFacturationLog`` ``genere`` (facture liée) ; sur ``FacturationError``,
    écrit un ``echec`` avec le motif et RE-LÈVE l'exception (le comportement de
    l'appelant est inchangé — seul le journal est un effet de bord additif).

    ``periode`` par défaut = ``date_echeance`` ISO de la ligne (une échéance
    datée EST sa propre période). Renvoie la ``Facture`` créée (comme
    ``facturer_ligne_echeance``).
    """
    from .models import CycleFacturationLog

    contrat = ligne.echeancier.contrat
    company = ligne.echeancier.company
    if periode is None:
        periode = ligne.date_echeance.isoformat()

    try:
        facture = facturer_ligne_echeance(ligne, user=user, taux_tva=taux_tva)
    except FacturationError as exc:
        enregistrer_cycle(
            company, source_type=CycleFacturationLog.SourceType.CONTRAT,
            source_id=contrat.id, periode=periode,
            statut=CycleFacturationLog.Statut.ECHEC, motif=str(exc))
        raise

    enregistrer_cycle(
        company, source_type=CycleFacturationLog.SourceType.CONTRAT,
        source_id=contrat.id, periode=periode,
        statut=CycleFacturationLog.Statut.GENERE, facture_id=facture.id)
    return facture


@transaction.atomic
def rejouer_cycle(log, *, user=None, taux_tva=Decimal('20')):
    """Rejoue UN échec du journal de facturation — XCTR5.

    Ne re-tente qu'une entrée ``echec`` (``RejeuError`` sinon). Pour une source
    ``contrat`` (échéancier CONTRAT31), retrouve la ``LigneEcheance`` NON encore
    facturée de la période et relance ``facturer_ligne_echeance_journalisee`` :
    - succès → la ligne obtient sa facture, une NOUVELLE entrée ``genere`` est
      journalisée, et CETTE entrée ``echec`` est marquée rejouée (incrémente
      ``nb_tentatives``, ne change pas son ``statut`` — l'historique reste
      fidèle) ;
    - la garde anti double-facturation (``enregistrer_cycle``) empêche tout
      second succès pour la même période — un échec ne se rejoue donc EXACTEMENT
      qu'une fois avec succès.

    Lève ``RejeuError`` si l'entrée n'est pas ``echec``, ou si aucune échéance
    facturable n'est retrouvable pour la période (source disparue/déjà réglée
    autrement).
    """
    from .models import CycleFacturationLog, LigneEcheance

    if log.statut != CycleFacturationLog.Statut.ECHEC:
        raise RejeuError("Seule une entrée en échec peut être rejouée.")

    if log.source_type != CycleFacturationLog.SourceType.CONTRAT:
        raise RejeuError(
            "Le rejeu automatique n'est disponible que pour les échéanciers "
            "de contrats (sav.ContratMaintenance se rejoue via son propre "
            "service `facturer`).")

    ligne = (
        LigneEcheance.objects
        .filter(
            company=log.company,
            echeancier__contrat_id=log.source_id,
            date_echeance=log.periode if _est_iso_date(log.periode) else None,
            facture_id__isnull=True,
        )
        .exclude(statut=LigneEcheance.Statut.ANNULEE)
        .order_by('id')
        .first()
    )
    if ligne is None:
        raise RejeuError(
            "Aucune échéance non facturée n'a été retrouvée pour cette "
            "période — rien à rejouer.")

    facture = facturer_ligne_echeance_journalisee(
        ligne, user=user, taux_tva=taux_tva, periode=log.periode)

    log.nb_tentatives = (log.nb_tentatives or 1) + 1
    log.save(update_fields=['nb_tentatives'])

    return facture


def _est_iso_date(valeur):
    """``True`` si ``valeur`` ressemble à une date ISO (``AAAA-MM-JJ``)."""
    import re

    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', valeur or ''))


def exceptions_facturation(company):
    """Cycles ``echec`` en file d'exceptions (QuerySet scopé société) — XCTR5.

    Lecture seule : alimente la carte « Exceptions de facturation » du tableau
    de bord contrats. Ordonné par date de création décroissante (les plus
    récentes d'abord).
    """
    from .models import CycleFacturationLog

    return CycleFacturationLog.objects.filter(
        company=company, statut=CycleFacturationLog.Statut.ECHEC,
    ).order_by('-date_creation', '-id')


# ---------------------------------------------------------------------------
# XCTR11 — Campagne de révision tarifaire en masse
# ---------------------------------------------------------------------------


def _filtrer_contrats_campagne(company, filtres):
    """Applique les ``filtres`` (dict) d'une campagne de révision — XCTR11.

    Filtres reconnus (tous optionnels) : ``type_contrat``, ``statut`` (défaut
    ``actif`` seulement — on ne révise pas un contrat brouillon/résilié),
    ``responsable_id``. Toujours scopé société. Renvoie un QuerySet.
    """
    from .models import Contrat

    filtres = filtres or {}
    qs = Contrat.objects.filter(company=company)
    statut = filtres.get('statut')
    if statut:
        qs = qs.filter(statut=statut)
    else:
        qs = qs.filter(statut=Contrat.Statut.ACTIF)
    type_contrat = filtres.get('type_contrat')
    if type_contrat:
        qs = qs.filter(type_contrat=type_contrat)
    responsable_id = filtres.get('responsable_id')
    if responsable_id:
        qs = qs.filter(responsable_id=responsable_id)
    return qs.order_by('id')


def previsualiser_campagne_revision(company, *, filtres=None, pct):
    """Mode PREVIEW d'une campagne de révision tarifaire — AUCUNE écriture (XCTR11).

    Liste, pour chaque contrat couvert par les ``filtres``, l'ancien montant et
    le nouveau montant (``ancien × (1 + pct/100)``, arrondi 2 décimales) —
    purement déclaratif, ne crée ni avenant ni notification. ``pct`` est un
    POURCENTAGE (ex. 5 = +5 %, -3 = -3 %).

    Renvoie une liste de dicts ``{'contrat_id', 'objet', 'ancien_montant',
    'nouveau_montant', 'delta'}``.
    """
    from decimal import ROUND_HALF_UP

    pct_d = Decimal(str(pct))
    facteur = Decimal('1') + (pct_d / Decimal('100'))

    resultats = []
    for contrat in _filtrer_contrats_campagne(company, filtres):
        ancien = contrat.montant or Decimal('0')
        nouveau = (ancien * facteur).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        resultats.append({
            'contrat_id': contrat.id,
            'objet': contrat.objet,
            'ancien_montant': ancien,
            'nouveau_montant': nouveau,
            'delta': (nouveau - ancien).quantize(Decimal('0.01')),
        })
    return resultats


@transaction.atomic
def campagne_revision(company, *, filtres=None, pct, date_effet=None,
                      preview=True, auteur=None):
    """Campagne de révision tarifaire en masse (preview OU application) — XCTR11.

    - ``preview=True`` (défaut) : délègue à ``previsualiser_campagne_revision``
      — AUCUNE écriture, renvoie la liste des montants ancien/nouveau.
    - ``preview=False`` : APPLIQUE la révision — un AVENANT d'indexation par
      contrat couvert (réutilise ``creer_avenant``, CONTRAT24 — numérotation
      max+1 sous verrou, instantané immuable, chatter journalisé), delta =
      nouveau − ancien montant. IDEMPOTENT : un contrat déjà révisé par CETTE
      campagne (même date d'effet, objet d'avenant identique) n'est PAS
      re-révisé (0 nouvel avenant sur un re-run) — détecté via un avenant
      existant du contrat portant l'objet ``« Révision tarifaire {pct}% —
      {date_effet} »`` EXACT. Notifie les responsables (``notifications.
      services``, import fonction-local, événement ``digest`` — best-effort,
      jamais bloquant) et renvoie la liste des ids d'avenants créés
      (``rollback_ids``) pour un rollback manuel ultérieur.

    Endpoint réservé admin (vérifié côté vue). ``pct`` en pourcentage (ex. 5 =
    +5 %). Renvoie un dict ``{'preview': bool, 'lignes'|'avenants_crees',
    'rollback_ids'}``.
    """
    if preview:
        return {
            'preview': True,
            'lignes': previsualiser_campagne_revision(
                company, filtres=filtres, pct=pct),
        }

    if date_effet is None:
        date_effet = timezone.localdate()

    objet_avenant = f'Révision tarifaire {pct}% — {date_effet.isoformat()}'

    avenants_crees = []
    rollback_ids = []
    for contrat in _filtrer_contrats_campagne(company, filtres):
        # Garde d'idempotence : cette campagne EXACTE a déjà révisé ce contrat.
        deja_revise = contrat.avenants.filter(
            objet=objet_avenant, date_effet=date_effet).exists()
        if deja_revise:
            continue

        ancien = contrat.montant or Decimal('0')
        pct_d = Decimal(str(pct))
        nouveau = (ancien * (Decimal('1') + pct_d / Decimal('100'))).quantize(
            Decimal('0.01'))
        delta = (nouveau - ancien).quantize(Decimal('0.01'))
        if delta == Decimal('0'):
            continue

        avenant = creer_avenant(
            contrat, objet=objet_avenant,
            description=(
                f'Campagne de révision tarifaire en masse : {ancien} → '
                f'{nouveau} ({pct}%).'),
            date_effet=date_effet, montant_delta=delta, auteur=auteur)
        avenants_crees.append(avenant)
        rollback_ids.append(avenant.id)

    _notifier_campagne_revision(company, len(avenants_crees), pct)

    return {
        'preview': False,
        'avenants_crees': len(avenants_crees),
        'rollback_ids': rollback_ids,
    }


def _notifier_campagne_revision(company, nb_avenants, pct):
    """Notifie les responsables du résultat d'une campagne — XCTR11.

    Frontière cross-app (CLAUDE.md) : appelle EXCLUSIVEMENT
    ``apps.notifications.services`` (jamais ses ``models``/``views``), import
    FONCTION-LOCAL. BEST-EFFORT : une erreur de notification ne doit JAMAIS
    faire échouer la campagne elle-même (déjà appliquée à ce stade).
    """
    if nb_avenants <= 0:
        return
    try:
        from apps.notifications.services import notify_many, resolve_recipients
    except Exception:  # pragma: no cover - app notifications absente
        return
    try:
        recipients = resolve_recipients(company, 'digest')
        notify_many(
            recipients, 'digest',
            'Campagne de révision tarifaire appliquée',
            body=(
                f'{nb_avenants} contrat(s) révisé(s) de {pct}% — '
                'un avenant a été créé pour chacun.'),
            link='/contrats', company=company)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


def rollback_campagne_revision(company, avenant_ids, *, auteur=None):
    """Annule les avenants d'une campagne de révision (rollback manuel) — XCTR11.

    Pour chaque avenant de la liste ``avenant_ids`` (scopés société) : crée un
    avenant COMPENSATOIRE (delta inverse) via ``creer_avenant`` — on n'efface
    JAMAIS un avenant existant (historique immuable, CONTRAT18/24), on
    compense. Ignore silencieusement un id introuvable/hors société (best-
    effort, l'appelant a la liste de ``rollback_ids`` retournée à
    l'application). Renvoie la liste des avenants compensatoires créés.
    """
    from .models import Avenant

    compensations = []
    for avenant in Avenant.objects.filter(
            id__in=avenant_ids, company=company).select_related('contrat'):
        if avenant.montant_delta is None or avenant.montant_delta == 0:
            continue
        compensation = creer_avenant(
            avenant.contrat,
            objet=f'Rollback — {avenant.objet}',
            description=(
                f'Annulation (rollback) de l\'avenant n°{avenant.numero}.'),
            date_effet=timezone.localdate(),
            montant_delta=-avenant.montant_delta,
            auteur=auteur,
        )
        compensations.append(compensation)
    return compensations


# ---------------------------------------------------------------------------
# XCTR12 — Devis de renouvellement généré avant échéance
# ---------------------------------------------------------------------------


class RenouvellementDevisError(Exception):
    """Levée quand un devis de renouvellement ne peut pas être généré.

    Ex. : un devis de renouvellement OUVERT (brouillon/envoyé) existe déjà
    pour ce contrat (garde anti-doublon — un double clic ne crée jamais deux
    devis), ou le contrat n'a pas de client résoluble.
    """


_STATUTS_DEVIS_FERMES = ('accepte', 'refuse', 'expire')


def devis_renouvellement_ouvert(contrat):
    """``ContratLien`` DEVIS de renouvellement OUVERT du contrat, ou ``None`` — XCTR12.

    « Ouvert » = un lien vers un devis dont le statut ventes (résolu via
    ``ventes.selectors.get_devis_by_pk``, frontière cross-app — lecture seule,
    jamais d'import de ``ventes.models`` directement) n'est ni ``accepte`` ni
    ``refuse`` ni ``expire`` — sert de GARDE ANTI-DOUBLON : un double clic sur
    « générer le devis de renouvellement » ne crée jamais un second devis tant
    qu'un devis ouvert existe déjà.
    """
    from .models import ContratLien

    try:
        from apps.ventes import selectors as ventes_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None

    liens = ContratLien.objects.filter(
        contrat=contrat, company=contrat.company,
        type_cible=ContratLien.TypeCible.DEVIS,
    ).order_by('-id')
    for lien in liens:
        try:
            devis = ventes_selectors.get_devis_by_pk(lien.cible_id)
        except Exception:  # pragma: no cover - défensif
            continue
        if devis is None or devis.company_id != contrat.company_id:
            continue
        if devis.statut not in _STATUTS_DEVIS_FERMES:
            return lien
    return None


@transaction.atomic
def generer_devis_renouvellement(contrat, *, auteur=None, valeur_indice=None,
                                 today=None):
    """Génère un devis de renouvellement AVANT échéance — XCTR12.

    Crée un ``ventes.Devis`` (frontière cross-app : import FONCTION-LOCAL de
    ``ventes.models``/``ventes.utils.references`` — jamais une vue) reprenant
    le montant COURANT du contrat, éventuellement révisé par l'indexation
    active (première ``IndexationPrix`` active du contrat, si
    ``valeur_indice`` est fournie — sinon le montant courant sans révision).
    Le client est résolu depuis ``contrat.client_id`` via ``crm.selectors``
    (même frontière que ``facturer_ligne_echeance`` — CONTRAT31).

    Le montant proposé (avec/sans révision) est porté dans ``Devis.note`` et
    ``Devis.etude_params`` (résumé structuré : montant courant, montant
    proposé, indexation appliquée) — un devis de renouvellement n'a pas de
    lignes catalogue (aucune ligne inventée) ; l'affichage détaillé du
    récapitulatif est un raffinement PDF ultérieur, hors périmètre ici (la
    référence/numérotation passe déjà par le chemin standard
    ``ventes.utils.references``, jamais ``count()+1``).

    GARDE ANTI-DOUBLON : refuse (``RenouvellementDevisError``) si un devis de
    renouvellement OUVERT existe déjà pour ce contrat
    (``devis_renouvellement_ouvert``) — un double clic ne crée jamais de
    doublon.

    Relie le devis créé au contrat via un ``ContratLien`` (type ``devis``).
    Journalise au chatter (CONTRAT15). Le ``Contrat.statut`` n'est JAMAIS
    modifié (préservation des statuts — CONTRAT12) et aucun funnel
    ``STAGES.py`` n'intervient (rule #2). Renvoie le ``Devis`` créé.
    """
    from .models import ContratLien

    if devis_renouvellement_ouvert(contrat) is not None:
        raise RenouvellementDevisError(
            "Un devis de renouvellement est déjà ouvert pour ce contrat.")

    if not contrat.client_id:
        raise RenouvellementDevisError(
            "Le contrat n'a pas de client : impossible de générer un devis "
            "de renouvellement.")

    from apps.crm.selectors import get_company_client

    client = get_company_client(contrat.company, contrat.client_id)
    if client is None:
        raise RenouvellementDevisError(
            "Le client du contrat est introuvable dans votre société.")

    montant_courant = contrat.montant or Decimal('0')
    montant_propose = montant_courant
    indexation_appliquee = None

    if valeur_indice is not None:
        indexation = contrat.indexations.filter(actif=True).order_by(
            'id').first()
        if indexation is not None:
            calcul = calculer_prix_indexe(
                indexation, valeur_actuelle=valeur_indice,
                prix_base=montant_courant)
            montant_propose = calcul['prix_revise']
            indexation_appliquee = {
                'indice': indexation.indice,
                'valeur_base': str(indexation.valeur_base),
                'valeur_actuelle': str(calcul['valeur_actuelle']),
                'delta': str(calcul['delta']),
            }

    note = (
        f'Renouvellement du contrat {contrat.reference or contrat.pk} — '
        f'montant courant {_fmt_montant(montant_courant, contrat.devise)} '
        f'→ proposé {_fmt_montant(montant_propose, contrat.devise)}.'
    )
    etude_params = {
        'renouvellement_contrat_id': contrat.id,
        'montant_courant': str(montant_courant),
        'montant_propose': str(montant_propose),
        'indexation_appliquee': indexation_appliquee,
    }

    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Devis.objects.create(
            reference=ref,
            company=contrat.company,
            client=client,
            statut=Devis.Statut.BROUILLON,
            note=note,
            etude_params=etude_params,
            created_by=auteur,
        )

    devis = create_with_reference(Devis, 'DEV', contrat.company, _create)

    ContratLien.objects.create(
        company=contrat.company,
        contrat=contrat,
        type_cible=ContratLien.TypeCible.DEVIS,
        cible_id=devis.id,
        libelle=f'Renouvellement — {devis.reference}',
    )

    journaliser_transition(
        contrat, field='devis_renouvellement', old_value='',
        new_value=devis.reference,
        message='Devis de renouvellement généré.', auteur=auteur)

    return devis


def marquer_renouvellement_accepte(contrat, devis, *, auteur=None,
                                   today=None):
    """Marque le renouvellement proposé ACCEPTÉ sur le contrat — XCTR12.

    Appelé par ``receivers.py`` sur l'événement ``devis_accepted`` (core.events)
    quand le devis accepté est lié au contrat via un ``ContratLien`` de type
    ``devis``. Journalise l'acceptation au chatter (CONTRAT15) — NE modifie
    JAMAIS ``Contrat.statut`` (préservation des statuts CONTRAT12) : le
    renouvellement effectif (prolongation de ``date_fin``) reste un acte
    SÉPARÉ et EXPLICITE (``renouveler_contrat`` — CONTRAT23), jamais déclenché
    automatiquement par la seule acceptation du devis (décision métier : le
    founder peut vouloir revoir les termes avant de prolonger réellement).
    """
    journaliser_transition(
        contrat, field='devis_renouvellement_accepte', old_value='',
        new_value=getattr(devis, 'reference', str(devis.pk)),
        message='Devis de renouvellement accepté par le client.',
        auteur=auteur)
    return contrat


# ---------------------------------------------------------------------------
# XCTR14 — Portail client : demandes en un clic (renouvellement/résiliation)
# ---------------------------------------------------------------------------


class DemandePortailError(Exception):
    """Levée quand une demande client (portail) ne peut pas être enregistrée."""


def demander_action_portail(contrat, *, type_demande, message=''):
    """Enregistre une demande client 1-clic depuis le portail — XCTR14.

    ``type_demande`` vaut ``'renouvellement'`` ou ``'resiliation'``. AUCUN
    changement de statut n'est appliqué ici (préservation des statuts —
    CONTRAT12) : la demande est journalisée au chatter (``ContratActivity``,
    type note) puis une notification best-effort est diffusée au responsable
    du contrat (ou, à défaut, aux destinataires société de l'événement
    générique ``digest``) via ``apps.notifications.services`` — jamais un
    import de ses modèles/vues. Une erreur de notification n'empêche jamais
    l'enregistrement de la demande. Renvoie l'entrée ``ContratActivity`` créée.
    """
    from .models import ContratActivity

    libelles = {
        'renouvellement': 'Demande de renouvellement',
        'resiliation': 'Demande de résiliation',
    }
    if type_demande not in libelles:
        raise DemandePortailError('Type de demande invalide.')

    texte = libelles[type_demande]
    if message:
        texte = f'{texte} — {message.strip()[:2000]}'

    activite = ContratActivity.objects.create(
        company=contrat.company,
        contrat=contrat,
        type=ContratActivity.Kind.NOTE,
        message=f'[Portail client] {texte}',
    )

    _notifier_demande_portail(contrat, type_demande, libelles[type_demande])

    return activite


def _notifier_demande_portail(contrat, type_demande, titre):
    """Notifie le responsable (ou la société) d'une demande portail — XCTR14.

    Frontière cross-app (CLAUDE.md) : appelle EXCLUSIVEMENT
    ``apps.notifications.services`` (jamais ses ``models``/``views``), import
    FONCTION-LOCAL. BEST-EFFORT : une erreur de notification ne fait jamais
    échouer l'enregistrement de la demande (déjà journalisée au chatter)."""
    try:
        from apps.notifications.services import notify, notify_many, resolve_recipients
    except Exception:  # pragma: no cover - app notifications absente
        return

    body = (
        f'Le client a demandé « {titre.lower()} » '
        f'sur le contrat « {contrat.objet} ».'
    )
    link = '/contrats'
    try:
        if contrat.responsable_id:
            notify(
                contrat.responsable, 'digest', titre, body=body,
                link=link, company=contrat.company)
        else:
            recipients = resolve_recipients(contrat.company, 'digest')
            notify_many(
                recipients, 'digest', titre, body=body,
                link=link, company=contrat.company)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


# ---------------------------------------------------------------------------
# XCTR17 — Location de matériel SORTANTE (aux clients) — fondation
# ---------------------------------------------------------------------------


class OrdreLocationError(Exception):
    """Levée quand un ``OrdreLocation`` ne peut pas être créé/transitionné."""


def _ordres_actifs_qs(produit, numero_serie, *, exclure_id=None):
    """QuerySet des ordres ACTIFS (réservée/enlevée) du MÊME produit + même
    numéro de série — base de la détection de chevauchement (XCTR17)."""
    from .models import OrdreLocation

    qs = OrdreLocation.objects.filter(
        produit=produit,
        numero_serie=numero_serie or '',
        statut__in=OrdreLocation.STATUTS_ACTIFS,
    )
    if exclure_id is not None:
        qs = qs.exclude(id=exclure_id)
    return qs


def _parametres_location(company):
    """``ParametresLocation`` de la société, ou ``None`` si non créés — ZCTR4.
    Une société sans ligne créée garde le comportement XCTR17/19 inchangé."""
    from .models import ParametresLocation

    return ParametresLocation.objects.filter(company=company).first()


def _padding_jours(company):
    """Temps de sécurité (padding), en JOURS ENTIERS arrondis au supérieur —
    ZCTR4. ``0`` (comportement XCTR17 inchangé) si aucun ``ParametresLocation``
    n'existe pour la société, ou si ``temps_securite_heures`` est ``0``."""
    import math

    parametres = _parametres_location(company)
    if parametres is None or not parametres.temps_securite_heures:
        return 0
    return math.ceil(parametres.temps_securite_heures / 24)


def _verifier_disponibilite(produit, numero_serie, date_debut, date_fin, *,
                            exclure_id=None, company=None):
    """Lève ``OrdreLocationError`` si un ordre ACTIF chevauche la fenêtre
    ``[date_debut, date_fin]`` pour le même produit + numéro de série.

    ZCTR4 — si ``company`` est fournie et porte un ``ParametresLocation``
    avec ``temps_securite_heures`` > 0, la fenêtre occupée de CHAQUE ordre
    existant est élargie de ce padding (arrondi au jour supérieur) de part
    et d'autre AVANT de tester le chevauchement — deux locations séparées de
    moins que le temps de sécurité (entretien) sont refusées. ``company``
    absente ou sans réglages = comportement XCTR17 strict inchangé."""
    padding = _padding_jours(company) if company is not None else 0
    for autre in _ordres_actifs_qs(
            produit, numero_serie, exclure_id=exclure_id):
        debut_elargi = autre.date_enlevement_prevue - timedelta(days=padding)
        fin_elargie = autre.date_retour_prevue + timedelta(days=padding)
        if debut_elargi <= date_fin and date_debut <= fin_elargie:
            if padding:
                raise OrdreLocationError(
                    "Ce produit (n° de série "
                    f"« {numero_serie or '—'} ») est déjà réservé/loué sur "
                    "une période qui chevauche celle demandée (ou ne "
                    f"respecte pas le temps de sécurité de {padding} "
                    "jour(s))."
                )
            raise OrdreLocationError(
                "Ce produit (n° de série "
                f"« {numero_serie or '—'} ») est déjà réservé/loué sur une "
                "période qui chevauche celle demandée."
            )


@transaction.atomic
def creer_ordre_location(company, *, client_id, produit, numero_serie='',
                         date_reservation, date_enlevement_prevue,
                         date_retour_prevue, tarif_jour=None,
                         frais_retard_jour=None, note='', created_by=None):
    """Crée un ``OrdreLocation`` avec détection de conflit — XCTR17 (+ ZCTR4).

    GARDES (lèvent ``OrdreLocationError`` sans rien écrire) :
    - ``produit`` doit être ``louable`` (vérifié par l'appelant via
      ``stock.selectors.get_produit_louable`` — jamais réimporté ici) ;
    - ``date_enlevement_prevue`` doit être ≤ ``date_retour_prevue`` ;
    - ZCTR4 : si ``ParametresLocation.duree_minimale_jours`` est posé pour la
      société, la durée (bornes incluses) doit être ≥ ce minimum, sinon 400
      (message FR) ;
    - aucun ordre ACTIF (réservée/enlevée) du même produit + numéro de série
      ne doit chevaucher la fenêtre ``[date_enlevement_prevue,
      date_retour_prevue]`` ÉLARGIE du temps de sécurité/padding (ZCTR4,
      ``ParametresLocation.temps_securite_heures`` — 0/absent = strict
      XCTR17 inchangé) — double réservation ou padding insuffisant refusés.

    ``tarif_jour`` : si absent, retombe sur ``produit.tarif_location_jour``.
    ``montant_estime`` = ``tarif_jour`` × nombre de jours (bornes incluses),
    posé côté serveur (jamais lu du corps de requête). ``frais_retard_jour``
    (ZCTR4) : si absent, hérite de
    ``ParametresLocation.frais_retard_jour_defaut`` (NULL si aucun réglage) —
    XCTR19 s'applique ensuite sans changement. Renvoie l'``OrdreLocation``
    créé.
    """
    from .models import OrdreLocation

    if date_enlevement_prevue > date_retour_prevue:
        raise OrdreLocationError(
            "La date d'enlèvement prévue doit précéder ou égaler la date de "
            "retour prévue.")

    nb_jours = (date_retour_prevue - date_enlevement_prevue).days + 1

    parametres = _parametres_location(company)
    duree_minimale = (
        parametres.duree_minimale_jours if parametres else None)
    if duree_minimale and nb_jours < duree_minimale:
        raise OrdreLocationError(
            f"La durée de location ({nb_jours} jour(s)) est inférieure à "
            f"la durée minimale requise ({duree_minimale} jour(s))."
        )

    _verifier_disponibilite(
        produit, numero_serie, date_enlevement_prevue, date_retour_prevue,
        company=company)

    tarif = tarif_jour if tarif_jour is not None else produit.tarif_location_jour
    montant_estime = (
        Decimal(str(tarif)) * nb_jours if tarif is not None else Decimal('0'))

    frais_retard = frais_retard_jour
    if frais_retard is None and parametres is not None:
        frais_retard = parametres.frais_retard_jour_defaut

    return OrdreLocation.objects.create(
        company=company,
        client_id=client_id,
        produit=produit,
        numero_serie=numero_serie or '',
        date_reservation=date_reservation,
        date_enlevement_prevue=date_enlevement_prevue,
        date_retour_prevue=date_retour_prevue,
        tarif_jour=tarif,
        montant_estime=montant_estime,
        frais_retard_jour=frais_retard,
        note=note or '',
        created_by=created_by,
    )


@transaction.atomic
def changer_statut_ordre_location(ordre, statut_cible):
    """Applique une transition GARDÉE sur un ``OrdreLocation`` (XCTR17).

    Fine enveloppe sur ``machine_etats.changer_statut_ordre_location`` (reformule
    ``TransitionInterdite`` en ``OrdreLocationError``, cohérent avec le reste
    des services de ce module). Pose ``date_enlevement_reelle`` /
    ``date_retour_reelle`` côté serveur quand la transition l'implique.
    """
    from . import machine_etats
    from .models import OrdreLocation

    if (ordre.statut == OrdreLocation.Statut.RESERVEE
            and statut_cible == OrdreLocation.Statut.ENLEVEE
            and ordre.date_enlevement_reelle is None):
        ordre.date_enlevement_reelle = timezone.localdate()
        ordre.save(update_fields=['date_enlevement_reelle'])
    if (ordre.statut == OrdreLocation.Statut.ENLEVEE
            and statut_cible == OrdreLocation.Statut.RETOURNEE
            and ordre.date_retour_reelle is None):
        ordre.date_retour_reelle = timezone.localdate()
        ordre.save(update_fields=['date_retour_reelle'])

    try:
        machine_etats.changer_statut_ordre_location(ordre, statut_cible)
    except machine_etats.TransitionInterdite as exc:
        raise OrdreLocationError(str(exc))
    return ordre


# ---------------------------------------------------------------------------
# XCTR18 — Caution (dépôt de garantie) sur location
# ---------------------------------------------------------------------------


class CautionLocationError(Exception):
    """Levée quand une opération de caution de location n'est pas permise."""


def _journaliser_caution(ordre, *, ancien_statut, nouveau_statut,
                         montant=None, motif='', auteur=None):
    """Écrit une entrée du journal de caution — XCTR18. Voir
    ``models.CautionLocationLog`` (``OrdreLocation`` n'a pas de FK ``Contrat``,
    donc ce journal est dédié plutôt que ``ContratActivity``)."""
    from .models import CautionLocationLog

    return CautionLocationLog.objects.create(
        company=ordre.company,
        ordre_location=ordre,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        montant=montant,
        motif=motif or '',
        auteur=auteur,
    )


@transaction.atomic
def encaisser_caution(ordre, *, montant, auteur=None):
    """Encaisse la caution d'un ordre de location — XCTR18.

    Pose ``caution_montant`` et bascule ``caution_statut`` → ``encaissee``.
    Refuse (``CautionLocationError``) un montant non strictement positif ou
    une caution déjà encaissée/restituée/retenue (idempotence : on n'encaisse
    qu'une fois — repartir de zéro exige un nouvel ordre)."""
    from .models import OrdreLocation

    if montant is None or Decimal(str(montant)) <= 0:
        raise CautionLocationError(
            'Le montant de la caution doit être strictement positif.')
    if ordre.caution_statut != OrdreLocation.CautionStatut.AUCUNE:
        raise CautionLocationError(
            'Une caution a déjà été encaissée pour cet ordre.')

    ancien = ordre.caution_statut
    ordre.caution_montant = Decimal(str(montant))
    ordre.caution_statut = OrdreLocation.CautionStatut.ENCAISSEE
    ordre.save(update_fields=['caution_montant', 'caution_statut'])

    _journaliser_caution(
        ordre, ancien_statut=ancien, nouveau_statut=ordre.caution_statut,
        montant=ordre.caution_montant, auteur=auteur)
    return ordre


@transaction.atomic
def restituer_caution(ordre, *, auteur=None):
    """Restitue INTÉGRALEMENT la caution — XCTR18.

    GARDE : la restitution est IMPOSSIBLE avant le retour effectif du
    matériel (``ordre.date_retour_reelle`` posée, c.-à-d. statut ``retournee``
    ou ``cloturee``) — sinon ``CautionLocationError``. Exige une caution
    ``encaissee`` (jamais ``aucune``/``restituee``/``retenue_partielle``)."""
    from .models import OrdreLocation

    if ordre.date_retour_reelle is None:
        raise CautionLocationError(
            'La restitution de caution est impossible avant le retour du '
            'matériel.')
    if ordre.caution_statut != OrdreLocation.CautionStatut.ENCAISSEE:
        raise CautionLocationError(
            'Aucune caution encaissée à restituer pour cet ordre.')

    ancien = ordre.caution_statut
    ordre.caution_statut = OrdreLocation.CautionStatut.RESTITUEE
    ordre.save(update_fields=['caution_statut'])

    _journaliser_caution(
        ordre, ancien_statut=ancien, nouveau_statut=ordre.caution_statut,
        montant=ordre.caution_montant, auteur=auteur)
    return ordre


@transaction.atomic
def retenir_caution_partielle(ordre, *, montant_retenu, motif, user=None,
                              auteur=None, taux_tva=Decimal('20')):
    """Retenue PARTIELLE sur la caution — XCTR18.

    GARDE : impossible avant le retour effectif (même garde que
    ``restituer_caution``). Exige une caution ``encaissee`` et
    ``0 < montant_retenu <= caution_montant``. Génère une ligne facturable
    (``ventes.services.creer_facture_regie``) pour le montant retenu, via le
    client résolu du contrat lié éventuel ou, à défaut (``OrdreLocation`` n'a
    pas de FK contrat), du ``client_id`` propre de l'ordre — frontière
    cross-app : résolution par le sélecteur ``crm.selectors.get_company_client``
    (jamais un import de son modèle). Renvoie un dict ``{'ordre', 'facture'}``.
    """
    from .models import OrdreLocation

    if ordre.date_retour_reelle is None:
        raise CautionLocationError(
            'La retenue de caution est impossible avant le retour du '
            'matériel.')
    if ordre.caution_statut != OrdreLocation.CautionStatut.ENCAISSEE:
        raise CautionLocationError(
            'Aucune caution encaissée sur laquelle appliquer une retenue.')
    if ordre.caution_montant is None:
        raise CautionLocationError('Cet ordre ne porte aucun montant de caution.')

    montant_retenu = Decimal(str(montant_retenu))
    if montant_retenu <= 0 or montant_retenu > ordre.caution_montant:
        raise CautionLocationError(
            'Le montant retenu doit être strictement positif et ne peut '
            'excéder le montant de la caution.')
    if not (motif or '').strip():
        raise CautionLocationError('Un motif est requis pour une retenue.')

    from apps.crm.selectors import get_company_client

    client = get_company_client(ordre.company, ordre.client_id)
    if client is None:
        raise CautionLocationError(
            'Le client de la location est introuvable dans votre société.')

    from apps.ventes.services import creer_facture_regie

    montant_ht = (montant_retenu / (1 + taux_tva / 100)).quantize(
        Decimal('0.01'))
    facture = creer_facture_regie(
        company=ordre.company, client=client, user=user,
        libelle=f'Retenue sur caution — ordre de location #{ordre.id}',
        montant_ht=montant_ht, taux_tva=taux_tva)

    ancien = ordre.caution_statut
    ordre.caution_statut = OrdreLocation.CautionStatut.RETENUE_PARTIELLE
    ordre.caution_retenue = montant_retenu
    ordre.caution_motif_retenue = motif.strip()
    ordre.save(update_fields=[
        'caution_statut', 'caution_retenue', 'caution_motif_retenue'])

    _journaliser_caution(
        ordre, ancien_statut=ancien, nouveau_statut=ordre.caution_statut,
        montant=montant_retenu, motif=motif, auteur=auteur)

    return {'ordre': ordre, 'facture': facture}


# ---------------------------------------------------------------------------
# XCTR19 — Retour de location : retards, frais automatiques, inspection
# ---------------------------------------------------------------------------


class RetourLocationError(Exception):
    """Levée quand une opération de retour de location n'est pas permise."""


def _resoudre_client_ordre(ordre):
    """Résout le ``crm.Client`` d'un ordre de location — frontière cross-app
    (sélecteur, jamais un import du modèle ``crm``)."""
    from apps.crm.selectors import get_company_client

    client = get_company_client(ordre.company, ordre.client_id)
    if client is None:
        raise RetourLocationError(
            'Le client de la location est introuvable dans votre société.')
    return client


def _notifier_retard_ordre(ordre, jours_retard):
    """Notifie le responsable du retard détecté — XCTR19. Best-effort, jamais
    bloquant (frontière cross-app : ``apps.notifications.services`` seulement)."""
    try:
        from apps.notifications.services import notify_many, resolve_recipients
    except Exception:  # pragma: no cover - app notifications absente
        return
    try:
        recipients = resolve_recipients(ordre.company, 'digest')
        notify_many(
            recipients, 'digest', 'Location en retard',
            body=(
                f'Ordre de location #{ordre.id} en retard de '
                f'{jours_retard} jour(s) (retour prévu '
                f'{ordre.date_retour_prevue.isoformat()}).'
            ),
            link='/contrats', company=ordre.company)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


@transaction.atomic
def cloturer_ordre_location(ordre, *, user=None, today=None):
    """Clôture un ordre RETOURNÉ, calcule et facture les frais de retard
    éventuels avant de basculer au statut ``cloturee`` — XCTR19.

    Le retard se mesure entre ``date_retour_prevue`` et
    ``date_retour_reelle`` (posée par la transition ``→ retournee``) — jamais
    la date du jour (une clôture tardive après un retour ponctuel ne doit pas
    inventer un retard qui n'existe pas). Si ``frais_retard_jour`` est posé ET
    qu'un retard existe, une facture (``ventes.creer_facture_regie``) est
    émise pour ``frais_retard_jour × jours_de_retard`` et le client est
    notifié AVANT facturation (best-effort). Sans retard ou sans
    ``frais_retard_jour`` : aucun frais, comportement inchangé.

    GARDE : l'ordre doit être ``retournee`` (sinon ``RetourLocationError`` —
    on ne clôture pas un ordre pas encore rendu). Renvoie l'``OrdreLocation``.
    """
    from .models import OrdreLocation

    if ordre.statut != OrdreLocation.Statut.RETOURNEE:
        raise RetourLocationError(
            "Seul un ordre « retournée » peut être clôturé.")

    if ordre.date_retour_reelle and ordre.frais_retard_jour:
        jours_retard = max(
            0, (ordre.date_retour_reelle - ordre.date_retour_prevue).days)
        if jours_retard > 0:
            montant = (
                Decimal(str(ordre.frais_retard_jour)) * jours_retard)
            client = _resoudre_client_ordre(ordre)

            # Notification client AVANT facturation (best-effort).
            try:
                from apps.notifications.services import notify_many, resolve_recipients
                recipients = resolve_recipients(ordre.company, 'digest')
                notify_many(
                    recipients, 'digest',
                    'Frais de retard — location',
                    body=(
                        f'Des frais de retard de {montant} MAD seront '
                        f'facturés (ordre #{ordre.id}, {jours_retard} '
                        'jour(s) de retard).'),
                    link='/contrats', company=ordre.company)
            except Exception:  # pragma: no cover - défensif (best-effort)
                pass

            from apps.ventes.services import creer_facture_regie

            montant_ht = (montant / Decimal('1.2')).quantize(Decimal('0.01'))
            facture = creer_facture_regie(
                company=ordre.company, client=client, user=user,
                libelle=(
                    f'Frais de retard — ordre de location #{ordre.id} '
                    f'({jours_retard} jour(s))'),
                montant_ht=montant_ht)

            ordre.frais_retard_montant = montant
            ordre.frais_retard_facture_id = facture.id
            ordre.save(update_fields=[
                'frais_retard_montant', 'frais_retard_facture_id'])

    try:
        changer_statut_ordre_location(ordre, OrdreLocation.Statut.CLOTUREE)
    except OrdreLocationError as exc:
        raise RetourLocationError(str(exc))

    return ordre


@transaction.atomic
def inspecter_retour(ordre, *, checklist=None, releve_compteur='',
                     dommages_montant=None, motif_dommages='', user=None):
    """Enregistre l'inspection de retour d'un ordre — XCTR19.

    ``checklist`` : dict JSON libre (ex. ``{"pneus": "ok", "moteur":
    "endommage"}``). ``dommages_montant`` : montant chiffré des dommages
    constatés (``None``/0 = aucun dommage — rien n'est facturé ni ouvert).

    Si des dommages sont chiffrés (> 0) :
    - une ligne facturable est créée (``ventes.creer_facture_regie``) pour le
      montant des dommages ;
    - un ticket SAV de remise en état est ouvert
      (``sav.services.create_corrective_ticket``, frontière cross-app —
      jamais un import de ses modèles/vues) — BEST-EFFORT : un échec
      d'ouverture du ticket n'empêche jamais l'enregistrement de
      l'inspection ni la facturation, déjà actées.

    Sans dommage chiffré : la checklist/relevé sont enregistrés et RIEN
    d'autre ne se produit (pas de facture, pas de ticket). Renvoie un dict
    ``{'ordre', 'facture', 'ticket_id'}`` (``facture``/``ticket_id`` = ``None``
    si aucun dommage)."""
    ordre.inspection_checklist = checklist or {}
    ordre.inspection_releve_compteur = releve_compteur or ''
    ordre.inspection_date = timezone.now()

    facture = None
    ticket_id = None

    montant = Decimal(str(dommages_montant)) if dommages_montant else Decimal('0')
    if montant > 0:
        ordre.inspection_dommages_montant = montant

        client = _resoudre_client_ordre(ordre)
        from apps.ventes.services import creer_facture_regie

        montant_ht = (montant / Decimal('1.2')).quantize(Decimal('0.01'))
        facture = creer_facture_regie(
            company=ordre.company, client=client, user=user,
            libelle=(
                f'Dommages constatés au retour — ordre de location #{ordre.id}'
                + (f' — {motif_dommages.strip()}' if motif_dommages else '')),
            montant_ht=montant_ht)
        ordre.inspection_facture_id = facture.id

        try:
            from apps.sav.services import create_corrective_ticket

            ticket = create_corrective_ticket(
                company=ordre.company, client=client, installation=None,
                description=(
                    f'Remise en état après location #{ordre.id} — '
                    f'dommages constatés à l\'inspection de retour.'
                    + (f' Motif : {motif_dommages.strip()}'
                       if motif_dommages else '')),
                created_by=user)
            ticket_id = ticket.id
            ordre.inspection_ticket_sav_id = ticket_id
        except Exception:  # pragma: no cover - défensif (best-effort)
            pass

    ordre.save(update_fields=[
        'inspection_checklist', 'inspection_releve_compteur',
        'inspection_date', 'inspection_dommages_montant',
        'inspection_facture_id', 'inspection_ticket_sav_id'])

    return {'ordre': ordre, 'facture': facture, 'ticket_id': ticket_id}


# ---------------------------------------------------------------------------
# XCTR20 — Location longue durée : facturation récurrente + prolongation/
# écourtage
# ---------------------------------------------------------------------------


def facturer_ordre_location_recurrent(ordre, *, user=None, periode=None):
    """Émet UNE facture de cycle pour un ordre de location longue durée —
    XCTR20. Réutilise le patron XCTR5 (``enregistrer_cycle`` — même garde
    anti double-facturation par ``(source_type, source_id, periode)``).

    GARDES (lèvent ``RetourLocationError`` sans rien écrire, RIEN journalisé
    en cas de garde AMONT — mais une ``FacturationError`` du référentiel de
    cycle EST journalisée en échec, cohérent avec le patron XCTR5) :
    - ``facturation_recurrente_active`` doit être vrai ;
    - ``tarif_jour`` doit être renseigné et positif.

    ``periode`` par défaut = mois courant (``AAAA-MM``, 1 facture par mois
    max — la garde anti-doublon d'``enregistrer_cycle`` l'assure). Avance
    ``derniere_facturation`` à la date du jour. Renvoie la ``Facture`` créée.
    """
    from .models import CycleFacturationLog

    if not ordre.facturation_recurrente_active:
        raise RetourLocationError(
            "La facturation récurrente n'est pas activée sur cet ordre.")
    if not ordre.tarif_jour or ordre.tarif_jour <= 0:
        raise RetourLocationError(
            'Un tarif journalier positif est requis pour facturer.')

    today = timezone.localdate()
    if periode is None:
        periode = today.strftime('%Y-%m')

    # 30 jours de location par cycle mensuel (patron simple, cohérent avec le
    # calcul de ``montant_estime`` à la création — pas de calendrier tiers).
    montant_ttc = Decimal(str(ordre.tarif_jour)) * 30

    client = _resoudre_client_ordre(ordre)
    from apps.ventes.services import creer_facture_regie

    montant_ht = (montant_ttc / Decimal('1.2')).quantize(Decimal('0.01'))

    try:
        facture = creer_facture_regie(
            company=ordre.company, client=client, user=user,
            libelle=(
                f'Location longue durée — ordre #{ordre.id} '
                f'({ordre.get_facturation_moment_display()}, {periode})'),
            montant_ht=montant_ht)
    except Exception as exc:  # pragma: no cover - défensif
        enregistrer_cycle(
            ordre.company,
            source_type=CycleFacturationLog.SourceType.ORDRE_LOCATION,
            source_id=ordre.id, periode=periode,
            statut=CycleFacturationLog.Statut.ECHEC, motif=str(exc))
        raise

    enregistrer_cycle(
        ordre.company,
        source_type=CycleFacturationLog.SourceType.ORDRE_LOCATION,
        source_id=ordre.id, periode=periode,
        statut=CycleFacturationLog.Statut.GENERE, facture_id=facture.id)

    ordre.derniere_facturation = today
    ordre.save(update_fields=['derniere_facturation'])

    return facture


@transaction.atomic
def prolonger_ordre_location(ordre, *, nouvelle_date_retour):
    """Prolonge un ordre de location — XCTR20.

    Re-vérifie la disponibilité (``_verifier_disponibilite``) sur la NOUVELLE
    fenêtre ``[date_enlevement_prevue, nouvelle_date_retour]`` en EXCLUANT
    l'ordre lui-même de la détection de conflit — 400 (``OrdreLocationError``)
    si un autre ordre actif chevauche la prolongation. Recalcule
    ``montant_estime`` sur la nouvelle durée totale. Renvoie l'``OrdreLocation``.
    """
    if nouvelle_date_retour <= ordre.date_retour_prevue:
        raise OrdreLocationError(
            'La nouvelle date de retour doit être postérieure à la date '
            'actuelle.')

    _verifier_disponibilite(
        ordre.produit, ordre.numero_serie, ordre.date_enlevement_prevue,
        nouvelle_date_retour, exclure_id=ordre.id, company=ordre.company)

    ordre.date_retour_prevue = nouvelle_date_retour
    if ordre.tarif_jour:
        nb_jours = (
            nouvelle_date_retour - ordre.date_enlevement_prevue).days + 1
        ordre.montant_estime = Decimal(str(ordre.tarif_jour)) * nb_jours
    ordre.save(update_fields=['date_retour_prevue', 'montant_estime'])
    return ordre


@transaction.atomic
def ecourter_ordre_location(ordre, *, nouvelle_date_retour, user=None):
    """Écourte un ordre de location : delta → avoir — XCTR20.

    Le delta (jours retranchés × ``tarif_jour``) devient un ``ventes.Avoir``
    lié à la DERNIÈRE facture émise pour cet ordre (via
    ``CycleFacturationLog``, patron XCTR6 ``_creer_avoir_prorata``) — sans
    facture antérieure, l'écourtage recalcule seulement ``montant_estime``
    (rien à créditer). Renvoie un dict ``{'ordre', 'avoir'}`` (``avoir`` =
    ``None`` si aucune facture à créditer ou aucun tarif renseigné)."""
    from .models import CycleFacturationLog

    if nouvelle_date_retour >= ordre.date_retour_prevue:
        raise OrdreLocationError(
            'La nouvelle date de retour doit être antérieure à la date '
            'actuelle pour un écourtage.')
    if nouvelle_date_retour < ordre.date_enlevement_prevue:
        raise OrdreLocationError(
            "La nouvelle date de retour ne peut précéder l'enlèvement.")

    ancien_nb_jours = (
        ordre.date_retour_prevue - ordre.date_enlevement_prevue).days + 1
    nouveau_nb_jours = (
        nouvelle_date_retour - ordre.date_enlevement_prevue).days + 1
    delta_jours = ancien_nb_jours - nouveau_nb_jours

    avoir = None
    if ordre.tarif_jour and delta_jours > 0:
        montant_delta = Decimal(str(ordre.tarif_jour)) * delta_jours
        facture_id = (
            CycleFacturationLog.objects
            .filter(
                company=ordre.company,
                source_type=CycleFacturationLog.SourceType.ORDRE_LOCATION,
                source_id=ordre.id,
                statut=CycleFacturationLog.Statut.GENERE,
                facture_id__isnull=False,
            )
            .order_by('-date_creation', '-id')
            .values_list('facture_id', flat=True)
            .first()
        )
        if facture_id:
            avoir = _creer_avoir_location(
                ordre, facture_id, montant_delta, user=user)

    ordre.date_retour_prevue = nouvelle_date_retour
    if ordre.tarif_jour:
        ordre.montant_estime = Decimal(str(ordre.tarif_jour)) * nouveau_nb_jours
    ordre.save(update_fields=['date_retour_prevue', 'montant_estime'])

    return {'ordre': ordre, 'avoir': avoir}


def _creer_avoir_location(ordre, facture_id, montant_abs, *, user=None):
    """Crée un ``ventes.Avoir`` lié à une facture de l'ordre — XCTR20 (même
    patron que ``_creer_avoir_prorata`` XCTR6). Renvoie ``None`` si la
    facture n'est plus trouvable dans la société (défensif)."""
    from decimal import ROUND_HALF_UP

    from apps.ventes.models import Avoir, Facture
    from apps.ventes.utils.references import create_with_reference

    try:
        facture = Facture.objects.get(pk=facture_id, company=ordre.company)
    except Facture.DoesNotExist:  # pragma: no cover - défensif
        return None

    tva_pct = facture.taux_tva or Decimal('20')
    montant_ttc = Decimal(str(montant_abs))
    montant_ht = (montant_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ttc - montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _create(ref):
        return Avoir.objects.create(
            reference=ref,
            company=ordre.company,
            facture=facture,
            client=facture.client,
            taux_tva=tva_pct,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            motif=f'Écourtage de location — ordre #{ordre.id}',
        )

    return create_with_reference(Avoir, 'AV', ordre.company, _create)


# ---------------------------------------------------------------------------
# ZCTR2 — Clôture automatique des contrats impayés (délai de clôture auto)
# ---------------------------------------------------------------------------


def _jours_impaye_contrat(contrat):
    """Jours d'impayé du contrat — ZCTR2. Renvoie le MAX des jours d'impayé
    (``ventes.selectors.jours_impaye_facture``, jamais un import direct de
    ``ventes.models``) sur toutes les ``LigneEcheance`` facturées du contrat
    (``facture_id`` non NULL), ``0`` si aucune échéance facturée ou si
    aucune n'est en retard (rien à clôturer)."""
    from apps.ventes.selectors import jours_impaye_facture

    from .models import LigneEcheance

    facture_ids = list(
        LigneEcheance.objects
        .filter(echeancier__contrat=contrat, facture_id__isnull=False)
        .exclude(statut=LigneEcheance.Statut.ANNULEE)
        .values_list('facture_id', flat=True)
    )
    max_jours = 0
    for facture_id in facture_ids:
        jours = jours_impaye_facture(facture_id, contrat.company)
        if jours > max_jours:
            max_jours = jours
    return max_jours


@transaction.atomic
def suspendre_contrat_si_impaye(contrat, *, today=None, auteur=None):
    """Suspend un ``Contrat`` ACTIF dont une facture de cycle est impayée
    depuis plus que ``PlanRecurrent.delai_cloture_auto_jours`` — ZCTR2.

    RÈGLES :
    - Un contrat SANS ``plan_recurrent`` rattaché, ou dont
      ``delai_cloture_auto_jours`` est NULL, n'est JAMAIS clôturé
      automatiquement (comportement neutre par défaut).
    - Seul un contrat ``actif`` peut être suspendu ici (transition GARDÉE par
      la machine d'états, ``actif → suspendu``) ; tout autre statut est un
      no-op silencieux (renvoie ``None``).
    - IDEMPOTENT : un contrat déjà ``suspendu`` n'est jamais re-suspendu — on
      court-circuite dès l'entrée (pas de double notification/journal).
    - Ne résilie JAMAIS le contrat (uniquement ``suspendu``) — la clôture
      définitive reste un acte manuel distinct (``resilier_contrat``).

    Renvoie le ``Contrat`` si suspendu, ``None`` sinon (rien à faire).
    """
    from .machine_etats import transition_permise
    from .models import Contrat

    if today is None:
        today = timezone.localdate()

    if contrat.statut != Contrat.Statut.ACTIF:
        return None

    plan = contrat.plan_recurrent
    delai = plan.delai_cloture_auto_jours if plan else None
    if not delai:
        return None

    jours_impaye = _jours_impaye_contrat(contrat)
    if jours_impaye <= delai:
        return None

    if not transition_permise(contrat.statut, Contrat.Statut.SUSPENDU):
        return None  # pragma: no cover - défensif (garde machine d'états)

    ancien = contrat.statut
    changer_statut(contrat, Contrat.Statut.SUSPENDU)

    journaliser_transition(
        contrat, field='statut', old_value=ancien,
        new_value=contrat.statut,
        message=(
            f'Suspension automatique — facture impayée depuis '
            f'{jours_impaye} jour(s) (délai {delai} j).'),
        auteur=auteur)

    try:
        from apps.notifications.services import notify_many, resolve_recipients

        recipients = resolve_recipients(contrat.company, 'digest')
        notify_many(
            recipients, 'digest', 'Contrat suspendu — impayé',
            body=(
                f'Le contrat #{contrat.id} a été suspendu automatiquement '
                f'(facture impayée depuis {jours_impaye} jour(s)).'),
            link='/contrats', company=contrat.company)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass

    return contrat


def cloturer_contrats_impayes(company, *, today=None, auteur=None):
    """Parcourt les ``Contrat`` ACTIFS d'une société et suspend ceux dont une
    facture de cycle est impayée depuis plus que le délai de leur
    ``PlanRecurrent`` — ZCTR2 (commande ``cloturer_contrats_impayes``).

    Multi-tenant : ``company`` doit être fournie par l'appelant (la commande
    boucle par société, jamais de lecture de company du corps de requête).
    Une exception sur UN contrat n'empêche jamais le traitement des suivants.

    Renvoie la liste des ``Contrat`` effectivement suspendus.
    """
    from .models import Contrat

    if today is None:
        today = timezone.localdate()

    suspendus = []
    contrats = Contrat.objects.filter(
        company=company, statut=Contrat.Statut.ACTIF,
        plan_recurrent__isnull=False,
        plan_recurrent__delai_cloture_auto_jours__isnull=False,
    ).select_related('plan_recurrent')

    for contrat in contrats:
        try:
            resultat = suspendre_contrat_si_impaye(
                contrat, today=today, auteur=auteur)
        except Exception:  # pragma: no cover - défensif (best-effort par contrat)
            continue
        if resultat is not None:
            suspendus.append(resultat)

    return suspendus


# ---------------------------------------------------------------------------
# ZCTR6 — Devis/commande portant des lignes de location (Rental order via
# ventes)
# ---------------------------------------------------------------------------


@transaction.atomic
def creer_ordres_location_depuis_devis(devis, *, company, created_by=None,
                                       date_enlevement_prevue=None,
                                       date_retour_prevue=None,
                                       today=None):
    """Crée un ``OrdreLocation`` PAR LIGNE louable d'un devis ACCEPTÉ — ZCTR6.

    Chez Odoo une location naît d'une ligne de vente avec période et prix
    calculé par les Rental Prices ; ici ``OrdreLocation`` (XCTR17) était un
    objet isolé sans passerelle depuis le devis. Cette action, pour CHAQUE
    ligne du devis dont le produit est ``louable`` (lu via
    ``ventes.selectors.lignes_louables_devis`` + ``stock.selectors.
    produits_louables_qs`` — jamais un import direct de ``ventes.models`` ni
    ``stock.models``), crée un ``OrdreLocation`` pré-rempli (client résolu du
    devis, produit, tarif jour/semaine/mois du produit) — les dates
    d'enlèvement/retour sont celles fournies par l'appelant (repli : demain →
    dans 7 jours si absentes, un placeholder éditable ensuite sur l'ordre).

    IDEMPOTENT : un ``OrdreLocation`` déjà créé pour la même (devis, ligne)
    (``devis_id``/``devis_ligne_id``, ZCTR6) n'est jamais recréé — un re-run
    ne duplique pas. Une ligne dont le produit n'est PAS louable est
    simplement ignorée. GARDE : le devis doit être ACCEPTÉ et porter un
    client — sinon ``OrdreLocationError`` et rien n'est créé. Aucun
    changement au moteur devis ni aux statuts (règle #4).

    Renvoie la liste des ``OrdreLocation`` créés (liste vide si tout était
    déjà créé, ou si aucune ligne n'est louable).
    """
    from .models import OrdreLocation

    if today is None:
        today = timezone.localdate()

    from apps.ventes import selectors as ventes_selectors

    if devis.company_id != company.id:
        raise OrdreLocationError(
            "Le devis n'appartient pas à votre société.")
    if not ventes_selectors.is_devis_accepte(devis):
        raise OrdreLocationError(
            'Seul un devis ACCEPTÉ peut créer des ordres de location.')
    if not devis.client_id:
        raise OrdreLocationError(
            "Le devis n'a pas de client : impossible de créer des ordres "
            "de location.")

    from apps.stock.selectors import produits_louables_qs

    produit_ids_louables = set(
        produits_louables_qs(company).values_list('id', flat=True))
    lignes = ventes_selectors.lignes_louables_devis(
        devis, produit_ids_louables)
    if not lignes:
        return []

    debut = date_enlevement_prevue or (today + timedelta(days=1))
    fin = date_retour_prevue or (debut + timedelta(days=7))

    from apps.stock.models import Produit

    crees = []
    for ligne in lignes:
        # GARDE ANTI-DOUBLON — un ordre existe déjà pour cette (devis, ligne).
        if OrdreLocation.objects.filter(
                devis_id=devis.id, devis_ligne_id=ligne['ligne_id']).exists():
            continue
        produit = Produit.objects.filter(
            id=ligne['produit_id'], company=company).first()
        if produit is None:
            continue  # pragma: no cover - défensif (produit supprimé entre-temps)
        ordre = OrdreLocation.objects.create(
            company=company,
            client_id=devis.client_id,
            devis_id=devis.id,
            devis_ligne_id=ligne['ligne_id'],
            produit=produit,
            date_reservation=today,
            date_enlevement_prevue=debut,
            date_retour_prevue=fin,
            tarif_jour=produit.tarif_location_jour,
            created_by=created_by,
        )
        crees.append(ordre)

    return crees


# ── ARC13 — import générique (framework `apps.dataimport`) ─────────────────

def _parse_date_import(valeur):
    """Normalise une valeur de date issue d'un import (str ISO/FR ou objet
    date/datetime déjà résolu par openpyxl) ; ``None`` si vide/invalide."""
    import datetime as _dt

    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, _dt.datetime):
        return valeur.date()
    if isinstance(valeur, _dt.date):
        return valeur
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return _dt.datetime.strptime(str(valeur).strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def creer_contrat_import(company, ligne, *, user=None):
    """ARC13 — Crée (ou saute si doublon) UN contrat depuis une ligne d'import
    CSV/XLSX (dict de colonnes déjà nettoyées), via ``apps.contrats.services``
    — jamais le modèle ``Contrat`` directement (contrat du framework
    ``apps.dataimport``, même motif que ``creer_vehicule_import`` XFLT22).

    Colonnes attendues : ``objet`` (obligatoire), ``reference`` (clé
    d'idempotence si fournie), ``type_contrat``, ``statut``, ``date_debut``,
    ``date_fin``, ``montant``, ``devise``. Idempotent sur ``reference`` : une
    ligne dont la référence est déjà utilisée pour la société est SAUTÉE
    (retourne ``'doublon'``), jamais mise à jour ni dupliquée — une ligne SANS
    référence est toujours créée (pas de clé d'idempotence disponible).
    Retourne ``('cree'|'doublon'|'erreur', message|None)``.
    """
    from decimal import Decimal, InvalidOperation

    from .models import Contrat

    objet = str(ligne.get('objet', '') or '').strip()
    if not objet:
        return 'erreur', 'Objet manquant.'

    reference = str(ligne.get('reference', '') or '').strip()
    if reference and Contrat.objects.filter(
            company=company, reference=reference).exists():
        return 'doublon', None

    type_brut = str(ligne.get('type_contrat', '') or '').strip().lower()
    types_valides = {c for c, _ in Contrat.TypeContrat.choices}
    type_contrat = type_brut if type_brut in types_valides \
        else Contrat.TypeContrat.AUTRE

    statut_brut = str(ligne.get('statut', '') or '').strip().lower()
    statuts_valides = {c for c, _ in Contrat.Statut.choices}
    statut = statut_brut if statut_brut in statuts_valides \
        else Contrat.Statut.BROUILLON

    montant_brut = ligne.get('montant')
    montant = Decimal('0')
    if montant_brut not in (None, ''):
        raw = str(montant_brut).replace('\xa0', '').replace(' ', '').replace(',', '.')
        try:
            montant = Decimal(raw)
        except (InvalidOperation, ValueError):
            montant = Decimal('0')

    try:
        Contrat.objects.create(
            company=company,
            reference=reference,
            objet=objet,
            type_contrat=type_contrat,
            statut=statut,
            date_debut=_parse_date_import(ligne.get('date_debut')),
            date_fin=_parse_date_import(ligne.get('date_fin')),
            montant=montant,
            devise=str(ligne.get('devise', '') or '').strip() or 'MAD',
            created_by=user if getattr(user, 'pk', None) else None,
        )
    except Exception as exc:  # pragma: no cover - défensif, erreur inattendue
        return 'erreur', str(exc)

    return 'cree', None


# ---------------------------------------------------------------------------
# NTSUB1 — Catalogue d'offres (``PlanAbonnement``) : pré-remplissage snapshot
# ---------------------------------------------------------------------------


def appliquer_plan_abonnement(contrat, plan_abonnement):
    """Pré-remplit ``montant``/``plan_recurrent`` d'un ``Contrat`` depuis un
    ``PlanAbonnement`` (NTSUB1) — SNAPSHOT, jamais un lien vivant.

    Copie ``plan_abonnement.prix_base`` → ``contrat.montant`` et
    ``plan_abonnement.plan_recurrent`` → ``contrat.plan_recurrent`` UNE FOIS, à
    l'appel. Les valeurs restent ensuite PROPRES au contrat, éditables
    librement — modifier l'offre catalogue après coup ne touche JAMAIS un
    contrat déjà créé (pas de recalcul dynamique). Renvoie le contrat mis à
    jour.
    """
    contrat.montant = plan_abonnement.prix_base
    contrat.plan_recurrent = plan_abonnement.plan_recurrent
    contrat.save(update_fields=['montant', 'plan_recurrent'])
    return contrat


# ---------------------------------------------------------------------------
# NTSUB2 — Add-ons (options payantes) : montant facturable d'une période
# ---------------------------------------------------------------------------


def lignes_addon_actives_periode(company, *, type_cible, cible_id, periode_fin):
    """Lignes ``AbonnementAddOnLigne`` ACTIVES d'une cible à ``periode_fin``
    (date de référence du cycle de facturation, NTSUB2).

    Une ligne est active si ``actif_depuis <= periode_fin`` et
    (``actif_jusqua`` est NULL OU ``actif_jusqua >= periode_fin``) — même
    contrat que ``AbonnementAddOnLigne.actif_le``, filtré au niveau requête
    pour éviter de charger des lignes hors période. Ne renvoie que les add-ons
    encore ``actif=True`` au catalogue.
    """
    from django.db.models import Q

    from .models import AbonnementAddOnLigne

    return (
        AbonnementAddOnLigne.objects
        .filter(
            company=company, type_cible=type_cible, cible_id=cible_id,
            addon__actif=True, actif_depuis__lte=periode_fin)
        .filter(Q(actif_jusqua__isnull=True) | Q(actif_jusqua__gte=periode_fin))
        .select_related('addon')
    )


def montant_addons_periode(company, *, type_cible, cible_id, periode_fin):
    """Somme facturable des add-ons ACTIFS d'une cible à ``periode_fin`` — NTSUB2.

    Renvoie ``Decimal('0')`` si aucun add-on actif (comportement inchangé pour
    un contrat sans add-on — n'ajoute rien au cycle de facturation).
    """
    total = Decimal('0')
    for ligne in lignes_addon_actives_periode(
            company, type_cible=type_cible, cible_id=cible_id,
            periode_fin=periode_fin):
        total += ligne.montant_periode()
    return total


# ---------------------------------------------------------------------------
# NTSUB4 — Compteurs d'usage génériques (metering) : ingestion + agrégation
# ---------------------------------------------------------------------------


def ingerer_compteur_usage(company, *, type_cible, cible_id, code_compteur,
                           periode_debut, periode_fin, quantite,
                           source='manuel'):
    """Ingère (ou MET À JOUR) un relevé de compteur d'usage — NTSUB4.

    Idempotent par ``(company, type_cible, cible_id, code_compteur,
    periode_debut, periode_fin)`` (contrainte d'unicité du modèle) :
    ré-ingérer la MÊME période remplace la quantité (pas de doublon créé) —
    utile pour un relevé corrigé/recalculé sans devoir d'abord supprimer
    l'ancien. Renvoie ``(compteur, cree)``.
    """
    from .models import CompteurUsage

    compteur, cree = CompteurUsage.objects.update_or_create(
        company=company, type_cible=type_cible, cible_id=cible_id,
        code_compteur=code_compteur, periode_debut=periode_debut,
        periode_fin=periode_fin,
        defaults={'quantite': quantite, 'source': source},
    )
    return compteur, cree


def total_usage_periode(company, *, type_cible, cible_id, code_compteur,
                        periode_debut, periode_fin):
    """Somme des ``CompteurUsage`` d'une cible/compteur RECOUVRANT la fenêtre
    ``[periode_debut, periode_fin]`` — NTSUB4.

    Renvoie ``Decimal('0')`` si aucun compteur ingéré (absence de compteur =
    ligne d'usage omise, comportement symétrique de XCTR16).
    """
    from django.db.models import Sum

    from .models import CompteurUsage

    total = (
        CompteurUsage.objects
        .filter(
            company=company, type_cible=type_cible, cible_id=cible_id,
            code_compteur=code_compteur,
            periode_debut__gte=periode_debut, periode_fin__lte=periode_fin)
        .aggregate(total=Sum('quantite'))['total']
    )
    return total if total is not None else Decimal('0')
