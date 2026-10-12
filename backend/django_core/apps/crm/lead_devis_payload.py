"""VNT69 -- charge utile ``Lead.devis[]`` (lignes devis de la fiche lead).

Extrait tel quel de ``LeadSerializer.get_devis`` (crm/serializers.py) : aucune
cle ne change, le serializer delegue d'une ligne. Lectures cross-app via
``apps.ventes.selectors`` / ``apps.installations.selectors`` uniquement
(frontiere inter-app respectee, jamais ``ventes.models``).

Contrat partage : ``apps/crm/contract_samples/lead_devis_ligne.json``.
"""


def lignes_devis_du_lead(obj, context):
    """Lignes ``devis[]`` du lead ``obj`` (du plus recent au plus ancien).

    ``context`` = ``serializer.context`` : ``LeadViewSet.list()`` y precharge
    ``chantier_map`` / ``share_link_map`` / ``lecture_map`` (garde N+1).
    """
    # Devis « empilés » sur le lead, du plus récent au plus ancien.
    # A4 — on expose le chantier lié (s'il existe) et l'option acceptée pour
    # que la fiche lead propose en ligne « Générer la facture » et « Créer le
    # chantier » (sans doublon) après acceptation.
    # YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge les
    # chantiers de TOUS les devis de la page en UNE requête et la pose
    # dans le contexte (``chantier_map``), pour éviter une requête
    # Installation PAR LIGNE (N+1). Sans contexte, on retombe sur l'appel
    # individuel — comportement inchangé.
    # YOPSB13/perf_n1 — ``obj.devis.order_by(...)`` clone le manager et
    # IGNORE le cache prefetch (``prefetch_related('devis')`` posé par
    # ``LeadViewSet``), ré-exécutant une requête PAR ligne (N+1). On lit le
    # cache via ``.all()`` puis on trie en Python (ordre identique), sans
    # importer le modèle ``ventes`` (frontière inter-app respectée).
    rows = sorted(
        obj.devis.all(),
        key=lambda d: (d.date_creation is not None, d.date_creation),
        reverse=True,
    )
    chantier_map = context.get('chantier_map')
    if chantier_map is not None:
        chantiers = {d.id: chantier_map.get(d.id) for d in rows}
    else:
        from apps.installations.selectors import (
            installation_summaries_for_devis,
        )
        chantiers = installation_summaries_for_devis(rows)
    # L-NIV-UI (24/08/2026) — niveau/otp_lecture du ShareLink DÉJÀ EXISTANT
    # (jamais un mint) : sans ça, l'onglet Devis (DevisTab.jsx) n'affichait
    # le badge de niveau qu'après un premier clic sur le sélecteur/case,
    # car son état `linkMeta` ne se remplissait qu'à partir de la réponse
    # d'un POST share-link explicite. Lecture cross-app via
    # `apps.ventes.selectors` (jamais `apps.ventes.models`).
    # YOPSB13 — MÊME garde N+1 que ``chantier_map`` : sur une LISTE,
    # ``LeadViewSet.list()`` précharge les ShareLink de TOUS les devis de
    # la page en UNE requête (``share_link_map`` dans le contexte). Sans
    # ce préchargement (retrieve, usage direct du serializer), on retombe
    # sur l'appel pour ce lead seul — comportement identique.
    share_link_map = context.get('share_link_map')
    if share_link_map is not None:
        niveau_map = share_link_map
    else:
        from apps.ventes.selectors import share_link_niveau_map
        niveau_map = share_link_niveau_map([d.id for d in rows])
    # QJ-VUES (fondateur 09/09/2026) — lectures CLIENT du devis (compteur +
    # dernière consultation), TOUJOURS présentes sur la fiche lead : le
    # commercial voit d'un coup d'œil combien de fois chaque devis a été
    # ouvert, sans ouvrir quoi que ce soit. Agrégé sur TOUS les ShareLink
    # du devis (expirés compris — l'historique ne se remet pas à zéro),
    # via `apps.ventes.selectors.share_link_lecture_map` (jamais les
    # modèles ventes). Même garde N+1 que `share_link_map` : la LISTE
    # précharge (`lecture_map` du contexte), le détail interroge pour ce
    # lead seul. `None` = devis jamais partagé (le front dit « jamais
    # envoyé/ouvert »).
    lecture_map = context.get('lecture_map')
    if lecture_map is None:
        from apps.ventes.selectors import share_link_lecture_map
        lecture_map = share_link_lecture_map([d.id for d in rows])
    # QJR516 (contrat QJR500 ``lead_devis_ligne.json``) — chaque ligne
    # porte le verdict de modifiabilité du devis (modifiable,
    # raison_non_modifiable, revision_possible) + is_active, servis par
    # `apps.ventes.selectors.devis_modifiabilite` — la MÊME règle que le
    # détail du devis, jamais recopiée ici.
    from apps.ventes.selectors import devis_modifiabilite
    return [
        {
            'id': d.id,
            'reference': d.reference,
            'statut': d.statut,
            'total_ttc': str(d.total_ttc),
            'date_creation': d.date_creation.isoformat(),
            'option_acceptee': d.option_acceptee,
            'chantier': chantiers.get(d.id),
            'share_link': niveau_map.get(d.id),
            'lecture': lecture_map.get(d.id),
            **devis_modifiabilite(d),
            # QJR535 (contrat ``lead_devis_ligne.json``) — `version` et
            # `superseded_by` (id du remplaçant) : attributs de
            # l'instance déjà chargée (aucun import de ventes.models). La
            # carte d'une V1 remplacée s'affiche « Remplacé par … » côté
            # cockpit au lieu de rester vivante et renvoyable.
            'version': d.version,
            'superseded_by': d.superseded_by_id,
            # QJR566 (contrat ``lead_devis_ligne.json``) — date de la
            # dernière correction après envoi (marqueur
            # ``etude_params.resync_apres_envoi``), lue sur l'instance
            # déjà chargée ; null si jamais corrigé. Le cockpit dit alors
            # « lu le X — avant la correction du Y ».
            'corrige_le': _corrige_le(d),
        }
        for d in rows
    ]


def _corrige_le(devis):
    """QJR566 — ISO de ``etude_params.resync_apres_envoi.date`` ou ``None``
    (marqueur absent, booléen hérité ou sans date)."""
    params = getattr(devis, 'etude_params', None)
    marqueur = params.get('resync_apres_envoi') if isinstance(params, dict) else None
    if isinstance(marqueur, dict):
        return marqueur.get('date') or None
    return None
