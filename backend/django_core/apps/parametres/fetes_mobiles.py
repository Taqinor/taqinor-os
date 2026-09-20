"""NTI18N33 — assistant de saisie guidée des fêtes mobiles hégiriennes.

Écran Paramètres → Localisation → Fêtes mobiles : liste les 4 fêtes
attendues pour l'année N+1 (Aïd el-Fitr, Aïd el-Adha, 1er Moharram, Aïd
el-Mawlid), avec un champ date vide à remplir chacune. Le calcul hégirien
précis nécessite une observation lunaire locale — JAMAIS calculé
algorithmiquement (principe déjà en place dans ``rh/holidays.py``, étendu
ici) : la saisie reste TOUJOURS manuelle.

Persistance en ``apps.notifications.models.Holiday`` (``recurrent_annuel=
False``) — app FONDATION exemptée de la frontière cross-app CLAUDE.md
(``parametres`` y figure explicitement), lue/écrite ici par import tardif
(function-local), jamais au niveau module (pas de dépendance dure au
chargement de l'app).

Déclenchement par le rappel automatique de fin d'année (NTI18N37 — job
Celery beat, autre tâche/lane) : hors périmètre de ce fichier, qui ne fournit
que la VALIDATION + l'ENREGISTREMENT consommés par cet écran/ce rappel.
"""
from __future__ import annotations

import datetime

#: Les 4 fêtes hégiriennes attendues, dans l'ordre d'affichage de l'écran.
FETES_MOBILES_CLES = (
    'aid_el_fitr', 'aid_el_adha', '1er_moharram', 'aid_el_mawlid')

FETES_MOBILES_LIBELLES = {
    'aid_el_fitr': 'Aïd el-Fitr',
    'aid_el_adha': 'Aïd el-Adha',
    '1er_moharram': '1er Moharram',
    'aid_el_mawlid': 'Aïd el-Mawlid',
}


def _aujourd_hui():
    from core.dates import aujourd_hui_local
    return aujourd_hui_local()


def _to_date(valeur):
    if isinstance(valeur, datetime.date):
        return valeur
    if isinstance(valeur, str):
        return datetime.date.fromisoformat(valeur)
    raise ValueError(f'Date invalide : {valeur!r}')


def valider_saisie(annee: int, dates: dict) -> list[str]:
    """Valide la saisie des 4 fêtes mobiles pour ``annee`` avant sauvegarde.

    Renvoie la liste des erreurs (VIDE = saisie valide, prête à enregistrer).
    Règles : les 4 clés doivent être présentes et non vides ; aucune date ne
    peut être dans le passé ; chaque date doit tomber dans l'année cible
    ``annee`` (cohérence — on ne saisit pas la fête de l'année suivante ici
    par erreur).
    """
    erreurs = []
    aujourd_hui = _aujourd_hui()
    for cle in FETES_MOBILES_CLES:
        libelle = FETES_MOBILES_LIBELLES[cle]
        brut = dates.get(cle)
        if not brut:
            erreurs.append(f'La date de {libelle} est manquante.')
            continue
        try:
            valeur = _to_date(brut)
        except ValueError:
            erreurs.append(f'Date invalide pour {libelle}.')
            continue
        if valeur < aujourd_hui:
            erreurs.append(f'La date de {libelle} est dans le passé.')
        if valeur.year != annee:
            erreurs.append(
                f'La date de {libelle} ({valeur.isoformat()}) ne tombe pas '
                f'en {annee}.')
    return erreurs


def enregistrer_fetes_mobiles(company, annee: int, dates: dict):
    """Valide puis enregistre les 4 fêtes mobiles comme ``Holiday``
    (``recurrent_annuel=False``) pour ``company``.

    Lève ``ValueError`` (message = erreurs jointes) si la saisie est
    invalide — l'appelant (vue) le traduit en 400. JAMAIS d'enregistrement
    partiel : la validation complète précède toute écriture.
    """
    erreurs = valider_saisie(annee, dates)
    if erreurs:
        raise ValueError(' '.join(erreurs))

    from apps.notifications.models import Holiday

    resultats = []
    for cle in FETES_MOBILES_CLES:
        valeur = _to_date(dates[cle])
        obj, _ = Holiday.objects.update_or_create(
            company=company, date=valeur, nom=FETES_MOBILES_LIBELLES[cle],
            defaults={'recurrent_annuel': False},
        )
        resultats.append(obj)
    return resultats


def fetes_mobiles_saisies(company, annee: int) -> dict:
    """``{cle: 'YYYY-MM-DD'|None}`` — l'état actuel de saisie pour ``annee``
    (pré-remplit l'écran ; une fête déjà saisie est visible, jamais écrasée
    silencieusement par le formulaire)."""
    from apps.notifications.models import Holiday

    lignes = Holiday.objects.filter(
        company=company, recurrent_annuel=False, date__year=annee,
        nom__in=list(FETES_MOBILES_LIBELLES.values()))
    par_nom = {ligne.nom: ligne.date for ligne in lignes}
    return {
        cle: (par_nom[libelle].isoformat() if libelle in par_nom else None)
        for cle, libelle in FETES_MOBILES_LIBELLES.items()
    }
