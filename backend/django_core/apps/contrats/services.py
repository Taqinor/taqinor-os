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
