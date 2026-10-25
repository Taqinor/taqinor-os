"""SPL165 — liste blanche des options PDF du moteur de devis (move only).

Déplacés tels quels de ``builder.py`` : ``DEFAULT_PDF_OPTIONS``,
``LANGUES_SORTIE_PDF``, ``VARIANTES_PDF``, ``_SHARE_TOKEN_RE`` et
``clean_pdf_options`` (la whitelist des options client, ré-exportée par
``quote_engine/__init__.py``). Seule dépendance : ``re``. Ce module n'importe
JAMAIS ``builder``. Les drapeaux serveur ``_embed_roof_render`` /
``_embed_calepinage_planche`` restent HORS de la liste blanche.
"""
from __future__ import annotations

import re


# Whitelisted PDF format options (mirroring the simulator's payload). The
# defaults reproduce today's premium 3-page output exactly.
DEFAULT_PDF_OPTIONS = {
    'pdf_mode': 'full',        # 'full' (3 pages) | 'onepage' (1 page)
    'show_monthly': True,      # monthly-savings chart on page 2
    'devis_final': False,      # payment terms + RIB block on page 3
    'include_etude': False,    # page Étude (industriel) — 4th premium page
    # PV46/PVSLD — page « Annexe technique » (schéma unifilaire + nomenclature
    # de la conception électrique PV41). DÉFAUT ``None`` = AUTO : la page est
    # ajoutée dès que le devis PORTE une conception électrique, et omise sinon.
    # C'est ce qui la rend enfin atteignable par un client : `/proposal`, le
    # document public et le PDF signé appellent tous `clean_pdf_options({})`,
    # donc un défaut `False` la mettait hors de portée de tout le monde sauf de
    # l'agent qui cochait la case. Un `True`/`False` EXPLICITE (dialogue PDF,
    # paramètre de requête) reste souverain — l'opt-out marche toujours.
    'include_annexe_technique': None,
    # CAL182 — page « Calepinage » (la PLANCHE COTÉE de CAL171, avec son
    # cartouche, son échelle, son nord et son empreinte). DÉFAUT ``None`` =
    # AUTO : la page est ajoutée dès que le devis PORTE un calepinage
    # dessinable, et omise sinon.
    #
    # Pourquoi l'AUTO est LÉGITIME ici, là où L-1V l'a RETIRÉ à l'annexe :
    # ``electrical_design`` est posé sur CHAQUE devis à sa création
    # (``rafraichir_etudes_du_devis``), donc « l'étude existe » est vrai
    # partout et l'auto ajoutait une page à TOUS les PDF. Un calepinage, lui,
    # n'existe que si quelqu'un l'a DESSINÉ : l'auto ne peut donc ajouter la
    # page qu'aux devis qui en ont vraiment un. Un ``True``/``False``
    # EXPLICITE (dialogue PDF, paramètre de requête) reste souverain.
    'include_calepinage': None,
    # AGR319 — annexe « Note de calcul du kit de pompage » (pièce du dossier
    # FDA, Guide 2024 p.21) du document agricole de 3 pages : +1 page, SEULEMENT
    # sur demande EXPLICITE (défaut ``False`` : tout appelant existant reste
    # byte-identique). Aucune option ne pilote un montant d'aide (Q22).
    'include_note_calcul': False,
    # AGR303 — les six options agricoles (cinq bascules « de persuasion » :
    # aide, comparatif carburant, environnement, schéma, eau livrée ; plus
    # ``current_fuel``) sont RETIRÉES : aucun renderer ne
    # les lisait depuis QJR236/DV1, et ``current_fuel`` ÉCRASAIT l'énergie
    # déclarée dans l'étude (un paramètre de rendu ne modifie jamais une donnée
    # client — D-AGR-5). Le renderer agricole ne déclare AUCUNE option qui
    # pilote un montant d'aide (Q22, D-AGR-6).
    # ── L-NIV (24/08/2026) — anticopie « niveau standard » ────────────────────
    # ``True`` regroupe les lignes fixation/câblage/protection en UNE ligne
    # « Kit … » au sous-total EXACT (``utils/anticopie.agreger_lignes_kit`` —
    # LA règle, partagée avec la charge utile JSON publique). Le client ne peut
    # plus recopier la nomenclature accessoire ; les TOTAUX ne bougent pas d'un
    # centime (ils sont figés avant la dégradation). Défaut ``False`` : le
    # chemin ERP authentifié (generer-pdf, Celery, /proposal en confiance) reste
    # byte-identique. Posé côté SERVEUR par les vues publiques d'après
    # ``ShareLink.niveau`` — jamais une décision du client.
    'kit_agrege': False,
    # ── L-VAR (ordre fondateur, 24/08/2026) — VARIANTE TÉLÉCHARGÉE ───────────
    # ``None`` (défaut) = le document tel que le COMMERCIAL l'a composé
    # (``etude_params['scenario']``) : tous les appelants existants restent
    # byte-identiques. ``'sans'`` / ``'avec'`` / ``'les_deux'`` = le CLIENT
    # choisit quelle version du devis il télécharge depuis la page publique.
    # C'est un choix de LECTURE : il ne touche aucun statut (règle #4) et
    # n'engage rien — l'option SIGNÉE reste ``Devis.option_acceptee``.
    'variante_option': None,
    # QRP1/A5 — jeton du ShareLink qui SERT ce PDF (anticopie du QR page 1).
    # ``None`` = appel interne (ERP, Celery) : le moteur retombe sur
    # ``ShareLink.for_devis`` — comportement historique, byte-identique.
    'share_token': None,
    # NTI18N4 — langue de sortie DÉJÀ RÉSOLUE par l'appelant (voir
    # ``apps.parametres.i18n_resolver.resolve_langue_sortie`` —
    # ``DevisViewSet.proposal`` la calcule systématiquement avant d'appeler ce
    # moteur). ``None`` = appelant historique qui ne la passe pas encore
    # (Celery, generer-pdf) : le moteur retombe sur son comportement FR actuel,
    # byte-identique. Le moteur ne fait QUE RECEVOIR cette valeur — il choisit
    # son propre gabarit de libellés (NTI18N5), jamais de second moteur.
    'langue_sortie': None,
}

#: Valeurs acceptées pour ``langue_sortie`` — mêmes 3 langues que le cadre
#: i18n léger frontend (fr/en/ar). Toute autre valeur retombe sur ``None``
#: (comportement FR historique), jamais une langue arbitraire transmise au
#: moteur.
LANGUES_SORTIE_PDF = ('fr', 'en', 'ar')

#: Valeurs acceptées pour ``variante_option`` (liste blanche STRICTE — tout le
#: reste retombe sur ``None``, c'est-à-dire le document complet du commercial).
VARIANTES_PDF = ('sans', 'avec', 'les_deux')

# QRP1/A5 — forme admissible d'un jeton de ShareLink (garde de surface : la
# VRAIE validation est la recherche en base, bornée au devis rendu).
_SHARE_TOKEN_RE = re.compile(r'[A-Za-z0-9_\-]{8,128}')


def clean_pdf_options(raw) -> dict:
    """Sanitize client-supplied options to the simulator's exact value space."""
    raw = raw or {}
    opts = dict(DEFAULT_PDF_OPTIONS)
    if raw.get('pdf_mode') in ('full', 'onepage'):
        opts['pdf_mode'] = raw['pdf_mode']
    if 'show_monthly' in raw:
        opts['show_monthly'] = bool(raw['show_monthly'])
    if 'devis_final' in raw:
        opts['devis_final'] = bool(raw['devis_final'])
    if 'include_etude' in raw:
        opts['include_etude'] = bool(raw['include_etude'])
    # L-NIV — dégradation anticopie : ne peut QUE retirer du détail, jamais en
    # révéler. La whitelister est donc sans risque (aucun appelant existant ne
    # la porte ⇒ défaut ``False`` ⇒ rendu inchangé partout).
    if 'kit_agrege' in raw:
        opts['kit_agrege'] = bool(raw['kit_agrege'])
    # L-VAR — variante téléchargée : liste blanche STRICTE. Une valeur inconnue
    # (ou absente) laisse ``None`` = document complet du commercial : un
    # paramètre bricolé ne peut donc RIEN faire d'autre que le comportement
    # historique.
    if raw.get('variante_option') in VARIANTES_PDF:
        opts['variante_option'] = raw['variante_option']
    if 'include_annexe_technique' in raw:
        _annexe = raw['include_annexe_technique']
        # Tri-état : ``None`` EXPLICITE vaut « auto » (le défaut), jamais un
        # opt-out déguisé ; seul un booléen tranche pour de bon.
        opts['include_annexe_technique'] = (
            None if _annexe is None else bool(_annexe))
    # CAL183 — page « Calepinage » : MÊME tri-état que l'annexe. ``None``
    # EXPLICITE vaut « auto » (le défaut), jamais un opt-out déguisé ; seul un
    # booléen tranche pour de bon, et cette valeur explicite est SOUVERAINE sur
    # l'AUTO. La whitelister est sans risque : l'option ne peut QUE choisir
    # entre montrer et cacher une pièce technique du devis courant — elle ne
    # révèle rien qu'un autre appel ne puisse déjà obtenir, et n'ouvre l'accès
    # à aucune donnée d'un autre dossier. Le drapeau de RENDU
    # ``_embed_calepinage_planche``, lui, reste SERVEUR et hors whitelist.
    if 'include_calepinage' in raw:
        _cal = raw['include_calepinage']
        opts['include_calepinage'] = None if _cal is None else bool(_cal)
    # AGR319 — annexe « Note de calcul » agricole : booléen explicite seul.
    if 'include_note_calcul' in raw:
        opts['include_note_calcul'] = bool(raw['include_note_calcul'])
    # NTI18N4 — langue de sortie déjà résolue par l'appelant (whitelist
    # stricte, jamais une valeur arbitraire transmise plus loin).
    if raw.get('langue_sortie') in LANGUES_SORTIE_PDF:
        opts['langue_sortie'] = raw['langue_sortie']
    # QRP1/A5 — JETON DU LIEN QUI SERT CE PDF (anticopie). Sans lui, le QR de
    # la proposition descend de ``ShareLink.for_devis``, qui rend le lien à
    # l'EXPIRATION LA PLUS LOINTAINE — pas celui qui sert le document : un PDF
    # rendu au niveau STANDARD (filigrané, nomenclature dégradée) pouvait
    # porter un QR vers la page CONFIANCE. L'appelant public passe donc le
    # jeton du lien qu'il vient de résoudre.
    # Whitelister ce paramètre est SANS RISQUE parce que le moteur ne le croit
    # pas sur parole : il ne s'en sert que si un ShareLink de CE devis porte ce
    # jeton (et n'a pas expiré). Un jeton bricolé, périmé, ou appartenant à un
    # autre devis retombe donc EXACTEMENT sur le comportement historique.
    _tok = raw.get('share_token')
    if isinstance(_tok, str) and _SHARE_TOKEN_RE.fullmatch(_tok):
        opts['share_token'] = _tok
    # QJR624 — ``payment_mode`` / ``custom_acompte`` ne sont PLUS des options
    # de rendu : l'acompte personnalisé est écrit dans ``Devis.echeancier``
    # (dialogue PDF → PATCH) et le PDF lit l'échéancier, comme la facture.
    return opts
