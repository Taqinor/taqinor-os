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
"""
import html as _html
import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .machine_etats import (  # noqa: F401 — réexport (point d'entrée services)
    TRANSITIONS_AUTORISEES,
    TransitionInterdite,
    changer_statut,
    statuts_suivants,
    transition_permise,
)

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
    reste l'unique chemin des PDF de devis). Import de ``weasyprint``
    FONCTION-LOCAL pour ne pas alourdir le chargement du module ni casser les
    environnements sans la lib.
    """
    import weasyprint  # import local : lib lourde, chargée à la demande

    html_str = _contrat_html(contrat)
    return weasyprint.HTML(string=html_str).write_pdf()


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
            # CONTRAT17 — activation automatique « signé → actif » si la prise
            # d'effet est atteinte. Passe par la machine d'états gardée et
            # journalise la bascule ; une prise d'effet future laisse à « signe ».
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
def resilier_contrat(contrat, *, motif='', date_effet=None, preavis_jours=None,
                     solde=None, auteur=None, today=None, snapshot=True):
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

    Renvoie la ``Resiliation`` créée (``version_creee`` renseigné si snapshot).
    """
    from .models import Contrat, Resiliation

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

    tva_pct = Decimal(str(taux_tva))
    montant_ht = (montant_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ttc - montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    libelle = (
        f'Échéance n°{ligne.numero} — contrat #{contrat.id} '
        f'({echeancier.get_periodicite_display()})'
    )

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
        )

    facture = create_with_reference(Facture, 'FAC', echeancier.company, _create)

    # Lien LÂCHE retour (id seul) + garde d'idempotence.
    ligne.facture_id = facture.id
    ligne.save(update_fields=['facture_id'])

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

    return {
        'avenant': avenant,
        'prix_base': calcul['prix_base'],
        'prix_revise': calcul['prix_revise'],
        'delta': delta,
    }


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
