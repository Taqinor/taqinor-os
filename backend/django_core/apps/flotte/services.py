"""Services (WRITE / orchestration) du module Gestion de flotte.

Point d'entrée des ÉCRITURES cross-app vers la flotte : les autres apps n'écrivent
jamais les modèles flotte directement, elles passent par ces fonctions. La société
est toujours posée côté serveur, jamais lue du corps de requête (multi-tenant).
"""
import datetime


def normaliser_categorie_permis(categorie):
    """FLOTTE9 — Normalise une catégorie de permis pour comparaison.

    Met en majuscules et retire les espaces : ``" ce "`` → ``"CE"``. Une valeur
    vide / ``None`` revient à la chaîne vide (aucune catégorie)."""
    if not categorie:
        return ''
    return ''.join(str(categorie).split()).upper()


def controle_permis(conducteur, vehicule, today=None):
    """FLOTTE9 — Contrôle « permis valide / catégorie » à l'affectation.

    Vérifie qu'un ``Conducteur`` peut légalement conduire un ``Vehicule``. Le
    contrôle est **piloté par l'exigence du véhicule** : il ne se déclenche que
    si le véhicule exige une catégorie de permis
    (``Vehicule.categorie_permis_requise`` non vide). Tant qu'aucune catégorie
    n'est requise, l'affectation est libre (un véhicule sans exigence — p. ex.
    un utilitaire léger sans contrainte saisie — n'impose rien), ce qui préserve
    le comportement historique de FLOTTE8.

    Quand une catégorie EST requise :

    1. **Permis renseigné** — le conducteur doit porter un numéro et une
       catégorie ; sinon → ``permis_manquant``.
    2. **Permis valide (non expiré)** — si ``date_expiration`` est renseignée et
       antérieure à ``today`` → ``permis_expire``.
    3. **Catégorie adaptée** — la catégorie requise doit figurer parmi celles du
       conducteur (un permis « B, CE » couvre « CE ») ; sinon →
       ``categorie_inadaptee``.

    Lecture seule : ne modifie rien, retourne ``(ok, code, message)`` —
    ``ok=True`` et ``code=''`` quand tout est conforme (ou quand le véhicule
    n'exige rien). Aucune exception levée : l'appelant (sérialiseur / service
    d'écriture) décide de rejeter ou de soft-warn selon le drapeau ``force``.
    """
    if today is None:
        today = datetime.date.today()

    requise = normaliser_categorie_permis(vehicule.categorie_permis_requise)
    if not requise:
        # Le véhicule n'impose aucune catégorie → rien à contrôler.
        return (True, '', '')

    numero = (conducteur.numero_permis or '').strip()
    categorie_cond = normaliser_categorie_permis(conducteur.categorie_permis)

    if not numero or not categorie_cond:
        return (
            False,
            'permis_manquant',
            "Le conducteur ne porte pas de permis valide "
            f"(catégorie {requise} requise par le véhicule).",
        )

    if conducteur.date_expiration is not None \
            and conducteur.date_expiration < today:
        return (
            False,
            'permis_expire',
            "Le permis du conducteur est expiré "
            f"(expiré le {conducteur.date_expiration.isoformat()}).",
        )

    # Catégories portées par le conducteur (« B, CE » → {'B', 'CE'}).
    portees = {
        normaliser_categorie_permis(part)
        for part in str(conducteur.categorie_permis).replace(';', ',').split(',')
    }
    portees.discard('')
    if requise not in portees:
        return (
            False,
            'categorie_inadaptee',
            f"La catégorie du permis ({categorie_cond}) ne couvre pas la "
            f"catégorie requise par le véhicule ({requise}).",
        )

    return (True, '', '')
