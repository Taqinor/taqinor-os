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


@transaction.atomic
def signer_contrat(contrat, *, signataire_nom, role_signataire,
                   signataire=None, ip_adresse='', user_agent='',
                   methode=None, auteur=None):
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

    Renvoie un dict ``{'signature', 'contrat_signe'}`` : la signature créée et un
    booléen indiquant si la bascule ``signe`` a eu lieu lors de cet appel.
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

    return {'signature': signature, 'contrat_signe': contrat_signe}
