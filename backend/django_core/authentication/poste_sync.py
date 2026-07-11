"""DC17 — backfill non destructif du ``CustomUser.poste`` (texte libre) vers le
référentiel ``rh.Poste`` (FG160).

Pour chaque société, on déduplique les intitulés de poste distincts (non vides,
comparés sans tenir compte de la casse ni des espaces de bord) en lignes
``rh.Poste`` via ``get_or_create`` (clé d'unicité ``(company, intitule)``), puis
on pointe ``CustomUser.poste_ref`` sur le poste correspondant. La colonne texte
``poste`` reste INTACTE — la migration est entièrement réversible.

Le module reçoit les CLASSES de modèles (réelles ou historiques via
``apps.get_model``) pour être appelable depuis une migration comme depuis les
tests — même contrat que ``authentication.role_tiers.sync_role_legacy``.
"""


def _norm(value):
    """Normalise un intitulé de poste pour la déduplication.

    Retire les espaces de bord ; renvoie '' pour None/vide. La comparaison de
    dédup est insensible à la casse (deux comptes « Commercial » / « commercial »
    pointent le même Poste), mais l'intitulé STOCKÉ garde la casse de la première
    occurrence rencontrée — on ne réécrit jamais un Poste déjà existant.
    """
    if not value:
        return ''
    return str(value).strip()


def backfill_poste_ref(user_model, poste_model):
    """Crée/réutilise un ``rh.Poste`` par intitulé distinct et par société, et y
    rattache ``CustomUser.poste_ref``.

    PER COMPANY (le référentiel est cadré société) : on ne fusionne jamais des
    postes de sociétés différentes. Idempotente : un second passage ne crée aucun
    doublon (``get_or_create`` sur ``(company, intitule)``) et ne réécrit pas un
    ``poste_ref`` déjà correct. Ne touche jamais à la colonne texte ``poste``.

    Reçoit les classes de modèles (réelles ou historiques) pour rester appelable
    depuis une migration comme depuis les tests. Retourne le nombre de comptes
    rattachés (poste_ref posé ou corrigé).
    """
    updated = 0
    # Cache (company_id, intitule_normalisé_casefold) -> Poste, pour ne pas
    # interroger la base à chaque compte partageant le même intitulé.
    cache = {}
    # order_by('pk') : « première occurrence rencontrée » (docstring) = premier
    # CRÉÉ (plus petit pk), de façon DÉTERMINISTE. Sans tri explicite, Postgres
    # ne garantit aucun ordre de retour ; sous --keepdb/--parallel (CI) l'ordre
    # physique varie et l'intitulé stocké pouvait garder la casse d'un compte
    # arbitraire ('commercial' au lieu de 'Commercial'). Le tri ne change que le
    # DÉPARTAGE de casse : la déduplication (casefold/iexact) reste identique.
    qs = (user_model.objects
          .filter(company__isnull=False).exclude(poste='').order_by('pk'))
    for user in qs.iterator():
        intitule = _norm(user.poste)
        if not intitule:
            continue
        key = (user.company_id, intitule.casefold())
        poste = cache.get(key)
        if poste is None:
            # Réutilise un Poste existant à la casse près ; sinon crée-le.
            poste = (
                poste_model.objects
                .filter(company_id=user.company_id, intitule__iexact=intitule)
                .order_by('id')
                .first()
            )
            if poste is None:
                poste, _ = poste_model.objects.get_or_create(
                    company_id=user.company_id, intitule=intitule)
            cache[key] = poste
        if user.poste_ref_id != poste.id:
            user.poste_ref = poste
            user.save(update_fields=['poste_ref'])
            updated += 1
    return updated
