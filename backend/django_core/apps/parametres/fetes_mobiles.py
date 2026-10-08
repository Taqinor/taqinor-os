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


def erreurs_par_champ(annee: int, dates: dict, existantes: dict | None = None,
                      aujourd_hui: datetime.date | None = None) -> dict:
    """Erreurs de saisie par clé de fête : ``{cle: [message, ...]}`` (vide =
    saisie valide).

    Règles :
    * une clé ABSENTE/vide n'est tolérée que si la fête est déjà enregistrée
      pour ``annee`` (``existantes[cle]``) — APAR14 : saisie partielle d'une
      correction ; une première saisie reste « tout ou rien » (NTI18N33) ;
    * le passé n'est refusé que pour une date NOUVELLE ou MODIFIÉE (APAR14) :
      renvoyer telle quelle une fête déjà passée (Aïd el-Fitr) ne bloque plus
      la correction d'une fête future ;
    * chaque date doit tomber dans l'année cible ``annee``.

    ``existantes`` : ``{cle: 'YYYY-MM-DD'|None}`` (forme de
    ``fetes_mobiles_saisies``) ; ``aujourd_hui`` injectable (jamais un mock).
    """
    existantes = existantes or {}
    if aujourd_hui is None:
        aujourd_hui = _aujourd_hui()
    erreurs = {}
    for cle in FETES_MOBILES_CLES:
        libelle = FETES_MOBILES_LIBELLES[cle]
        brut = dates.get(cle)
        deja = existantes.get(cle)
        if not brut:
            if not deja:
                erreurs.setdefault(cle, []).append(
                    f'La date de {libelle} est manquante.')
            continue
        try:
            valeur = _to_date(brut)
        except ValueError:
            erreurs.setdefault(cle, []).append(
                f'Date invalide pour {libelle}.')
            continue
        inchangee = bool(deja) and _to_date(deja) == valeur
        if valeur < aujourd_hui and not inchangee:
            erreurs.setdefault(cle, []).append(
                f'La date de {libelle} est dans le passé.')
        if valeur.year != annee:
            erreurs.setdefault(cle, []).append(
                f'La date de {libelle} ({valeur.isoformat()}) ne tombe pas '
                f'en {annee}.')
    return erreurs


def valider_saisie(annee: int, dates: dict, existantes: dict | None = None,
                   aujourd_hui: datetime.date | None = None) -> list[str]:
    """Valide la saisie des fêtes mobiles pour ``annee`` avant sauvegarde.

    Renvoie la liste à plat des erreurs (VIDE = saisie valide, prête à
    enregistrer) — règles : voir :func:`erreurs_par_champ`.
    """
    par_champ = erreurs_par_champ(annee, dates, existantes, aujourd_hui)
    return [msg for cle in FETES_MOBILES_CLES for msg in par_champ.get(cle, [])]


class SaisieFetesInvalide(ValueError):
    """Saisie refusée ; ``erreurs`` = ``{cle: [message, ...]}``."""

    def __init__(self, erreurs: dict):
        self.erreurs = erreurs
        super().__init__(' '.join(
            msg for cle in FETES_MOBILES_CLES for msg in erreurs.get(cle, [])))


def enregistrer_fetes_mobiles(company, annee: int, dates: dict,
                              aujourd_hui: datetime.date | None = None,
                              user=None):
    """Valide puis enregistre les fêtes mobiles saisies comme ``Holiday``
    (``recurrent_annuel=False``) pour ``company``.

    Lève ``SaisieFetesInvalide`` (``ValueError`` ; message = erreurs jointes,
    ``.erreurs`` par champ) si la saisie est invalide — l'appelant (vue) le
    traduit en 400. JAMAIS d'enregistrement partiel d'une saisie invalide : la
    validation complète précède toute écriture. Seules les clés FOURNIES sont
    écrites (APAR14 : une correction ne renvoie que la fête corrigée).
    """
    existantes = fetes_mobiles_saisies(company, annee)
    erreurs = erreurs_par_champ(annee, dates, existantes, aujourd_hui)
    if erreurs:
        raise SaisieFetesInvalide(erreurs)

    from django.db import transaction

    from apps.notifications.models import Holiday

    from .models import SettingsAuditLog

    resultats = []
    with transaction.atomic():
        for cle in FETES_MOBILES_CLES:
            if not dates.get(cle):
                continue
            valeur = _to_date(dates[cle])
            libelle = FETES_MOBILES_LIBELLES[cle]
            # APAR15 — une fête mobile = UNE ligne par société + libellé +
            # année : une correction REMPLACE la date (jamais une 2e ligne).
            lignes = list(Holiday.objects.select_for_update().filter(
                company=company, nom=libelle, date__year=annee,
                recurrent_annuel=False).order_by('date', 'pk'))
            ancienne = lignes[0].date if lignes else None
            # Doublons hérités (même fête, même année) : retirés, tracés.
            for doublon in lignes[1:]:
                SettingsAuditLog.log_change(
                    company=company, user=user, section='fetes_mobiles',
                    field=cle, field_label=f'{libelle} {annee} (doublon retiré)',
                    old=doublon.date.isoformat(), new='')
                Holiday.objects.filter(pk=doublon.pk).delete()
            if lignes:
                obj = lignes[0]
                if obj.date != valeur:
                    obj.date = valeur
                    obj.save(update_fields=['date'])
            else:
                obj = Holiday.objects.create(
                    company=company, nom=libelle, date=valeur,
                    recurrent_annuel=False)
            if ancienne != valeur:
                SettingsAuditLog.log_change(
                    company=company, user=user, section='fetes_mobiles',
                    field=cle, field_label=f'{libelle} {annee}',
                    old=ancienne.isoformat() if ancienne else '',
                    new=valeur.isoformat())
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
