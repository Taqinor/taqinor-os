"""Historique de configuration du devis (SPL262, déplacé de ``domain/cycle_vie.py``).

NTCPQ20 / QJR550-552 : contenu JSON-safe et restaurable d'un devis
(``configuration_devis_contenu``), instantané dédoublonné
(``capturer_configuration_devis``), instantané de geste
(``instantane_de_geste``) et diff par identité stable
(``diff_configurations_devis``). Ne dépend que du journal ; ses lectures
d'autres modules restent des imports FONCTION-LOCAUX. Le statut n'est jamais
écrit (règle #4). Déplacement pur : corps octet-identiques, prouvé par
``tests/golden/split_dm_hist.json``.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


def _valeur_json(valeur):
    """Une valeur de ligne JSON-safe (Decimal → str, le reste tel quel)."""
    from decimal import Decimal as _D
    if isinstance(valeur, _D):
        return str(valeur)
    return valeur


def _ligne_contenu(ligne):
    """QJR551 — UNE ligne, sur le jeu ``domain/lignes.CHAMPS_CLONES`` (jamais
    une liste retapée) : c'est ce qui rend « Revenir à cette version »
    possible (D-QJR5-7). Les clés étrangères voyagent par leur id
    (``produit``, ``lot``) ; aucun id de LIGNE (replace-lines les recrée)."""
    from apps.ventes.domain.lignes import CHAMPS_CLONES
    contenu = {}
    for champ in CHAMPS_CLONES:
        if champ in ('produit', 'lot'):
            contenu[champ] = getattr(ligne, f'{champ}_id', None)
        else:
            contenu[champ] = _valeur_json(getattr(ligne, champ, None))
    return contenu


def _etude_contenu(devis):
    """QJR551 — les clés d'ENTRÉE de l'étude que l'ÉCRAN possède (schéma
    ``etude_schema.SCHEMA``, aucune liste codée en dur) : ce que
    « Revenir à cette version » rejoue par ``etude_params`` (contrat QJR504)."""
    from apps.ventes.domain.etude_schema import ECRAN, ENTREE, SCHEMA
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    return {cle: etude[cle] for cle, regle in SCHEMA.items()
            if regle.get('nature') == ENTREE
            and regle.get('proprietaire') == ECRAN and cle in etude}


def _entete_valeur(valeur):
    """ADEV18 — une valeur d'en-tête JSON-safe (Decimal → str, date → ISO)."""
    import datetime as _dt
    if isinstance(valeur, (_dt.date, _dt.datetime)):
        return valeur.isoformat()
    if isinstance(valeur, list):
        return list(valeur)
    return _valeur_json(valeur)


def cle_entete(champ):
    """ADEV18 — la clé d'instantané d'un champ d'en-tête visible : la clé
    étrangère voyage par son nom d'écriture (``client_id`` → ``client``),
    celui qu'accepte l'``entete`` de replace-lines (contrat QJR504)."""
    return champ[:-3] if champ.endswith('_id') else champ


def _entete_contenu(devis):
    """ADEV18 — TOUS les champs d'en-tête que le client voit, sur la liste
    UNIQUE ``modifiabilite.CHAMPS_ENTETE_VISIBLES`` (celle que lit
    ``empreinte_visible`` : aucune liste retapée). Rejouée telle quelle comme
    ``entete`` de replace-lines par « Revenir à cette version »."""
    from apps.ventes.domain.modifiabilite import CHAMPS_ENTETE_VISIBLES
    return {cle_entete(champ): _entete_valeur(getattr(devis, champ, None))
            for champ in CHAMPS_ENTETE_VISIBLES}


def _totaux_contenu(devis):
    """QJR551 — totaux HT net / TTC par la façade ``argent`` (vue NET)."""
    from apps.ventes.domain.argent import Vue, totaux as totaux_argent
    try:
        vue = totaux_argent(devis, vue=Vue.NET)
        return {'ht_net': str(vue.ht_net), 'ttc': str(vue.ttc)}
    except Exception:  # noqa: BLE001 — un total illisible ne bloque rien
        return {'ht_net': None, 'ttc': None}


def configuration_devis_contenu(devis):
    """NTCPQ20 — Représentation JSON-safe de la configuration d'un devis.

    QJR551 — instantané COMPLET et RESTAURABLE : chaque ligne porte les champs
    de ``domain/lignes.CHAMPS_CLONES`` (sans id de ligne), plus
    ``remise_globale``, ``echeancier`` (D-QJR5-10), les clés d'entrée ÉCRAN de
    l'étude et les totaux HT net / TTC. JAMAIS de prix d'achat ni de marge.

    ADEV18 — plus la ``note`` client et l'``entete`` complet (client,
    validité, TVA, remise, échéancier, acompte) : une correction qui ne
    change QUE ces champs crée un nouvel instantané, et la restauration les
    rejoue (``entete`` + ``note`` → replace-lines)."""
    echeancier = devis.echeancier
    return {
        'lignes': [_ligne_contenu(li)
                   for li in devis.lignes.all().order_by('ordre', 'id')],
        'remise_globale': _valeur_json(devis.remise_globale),
        'echeancier': (list(echeancier) if isinstance(echeancier, list)
                       else echeancier),
        'note': devis.note or '',
        'entete': _entete_contenu(devis),
        'etude': _etude_contenu(devis),
        'totaux': _totaux_contenu(devis),
    }


def capturer_configuration_devis(devis, *, user=None, avant_correction=False,
                                 envoye=False):
    """NTCPQ20 — Enregistre un instantané de configuration si le devis est
    BROUILLON et que la configuration a RÉELLEMENT changé.

    No-op (renvoie ``None``) hors brouillon ou quand le contenu est identique
    au dernier instantané — un simple re-save ne pollue pas l'historique.
    Ne lève jamais : l'historique ne doit jamais bloquer une écriture.

    QJR518 — ``avant_correction=True`` capture AUSSI un devis ENVOYÉ :
    appelé AVANT la première écriture d'une correction après envoi
    (``domain/modifiabilite.debut_de_geste_devis``), l'instantané conserve
    l'état que le client a vu.

    QJR552 — ``envoye=True`` (l'instantané APRÈS geste, :func:`instantane_de_geste`)
    historise aussi un ENVOYÉ : la correction après envoi (D-QJR5-1) laisse
    l'état vu par le client (premier instantané, pris AVANT le geste par
    ``debut_de_geste_devis``) ET l'état corrigé (dernier instantané). Jamais
    un accepté / refusé / expiré : leurs gestes sont refusés en amont.

    QJR550 — la création est enveloppée dans un POINT DE SAUVEGARDE : une
    erreur SQL pendant la capture (appelée sous la transaction de
    replace-lines / atomic) n'avorte plus l'enregistrement qui l'entoure."""
    from django.db import transaction

    from apps.ventes.models import ConfigurationDevisSnapshot, Devis

    if devis is None or devis.pk is None:
        return None
    statuts = ((Devis.Statut.BROUILLON, Devis.Statut.ENVOYE)
               if (avant_correction or envoye) else (Devis.Statut.BROUILLON,))
    if devis.statut not in statuts:
        return None
    try:
        with transaction.atomic():
            contenu = configuration_devis_contenu(devis)
            dernier = ConfigurationDevisSnapshot.objects.filter(
                devis_id=devis.pk).order_by('-date_creation', '-id').first()
            if dernier is not None and dernier.contenu == contenu:
                return None
            return ConfigurationDevisSnapshot.objects.create(
                company=devis.company, devis=devis, contenu=contenu,
                auteur=user)
    except Exception:  # noqa: BLE001 — l'historique n'est jamais bloquant
        logger.exception(
            'NTCPQ20 : instantané de configuration ignoré (devis %s)',
            devis.pk)
        return None


def instantane_de_geste(devis, *, user=None):
    """QJR550 — UN instantané de configuration par GESTE d'enregistrement,
    avec son auteur.

    Remplace le signal ``post_save``/``post_delete`` de ``LigneDevis``
    (NTCPQ20) : ``remplacer_lignes`` supprime puis recrée toutes les lignes,
    et le signal produisait ~N+1 instantanés par enregistrement — dont des
    états PARTIELS — sans jamais d'auteur. Appelé, après les écritures, par
    le pipeline (``composer`` ; ``ecrire`` / ``reconcilier`` — jamais
    ``rafraichir``), ``LigneDevisViewSet`` et la resynchronisation catalogue
    (une fois par devis). Relit le devis (statut et lignes en base). Ne lève
    jamais.

    QJR552 — capture un BROUILLON comme un ENVOYÉ (l'état CORRIGÉ d'une
    correction après envoi) ; l'état AVANT, vu par le client, reste capturé
    par ``debut_de_geste_devis`` avant la première écriture du même geste —
    les deux passent par :func:`capturer_configuration_devis`, l'unique
    implémentation. Le statut n'est jamais écrit."""
    if devis is None or getattr(devis, 'pk', None) is None:
        return None
    try:
        from apps.ventes.models import Devis
        frais = Devis.objects.select_related('company').filter(
            pk=devis.pk).first()
        if frais is None:
            return None
        return capturer_configuration_devis(frais, user=user, envoye=True)
    except Exception:  # noqa: BLE001 — l'historique n'est jamais bloquant
        logger.exception(
            'QJR550 : instantané de geste ignoré (devis %s)',
            getattr(devis, 'pk', '?'))
        return None


#: QJR551 — champs d'une ligne qui ne disent pas une MODIFICATION : la
#: position (``ordre`` se décale à la première insertion).
_CHAMPS_POSITIONNELS = ('ordre',)


def _cles_appariement(lignes):
    """QJR551 — l'IDENTITÉ STABLE d'une ligne d'instantané : (type_ligne,
    produit — ou la désignation pour une section / une note —, variante),
    départagée par le RANG d'occurrence. Jamais l'id de ligne (replace-lines
    les recrée) ni ``ordre`` seul (il se décale). Anciens instantanés
    acceptés (``produit_id`` au lieu de ``produit``, clés absentes = None)."""
    rangs = {}
    indexees = {}
    for ligne in lignes or []:
        type_ligne = ligne.get('type_ligne') or 'produit'
        produit = ligne.get('produit', ligne.get('produit_id'))
        ident = (ligne.get('designation') or ''
                 if type_ligne in ('section', 'note') or produit is None
                 else produit)
        base = f"{type_ligne}:{ident}:{ligne.get('variante') or ''}"
        rang = rangs.get(base, 0)
        rangs[base] = rang + 1
        indexees[f'{base}#{rang}'] = ligne
    return indexees


def diff_configurations_devis(snapshot_a, snapshot_b):
    """NTCPQ20 — Diff entre deux instantanés de configuration.

    QJR551 — les lignes sont appariées par une IDENTITÉ STABLE
    (:func:`_cles_appariement`), plus par ``ligne_id`` : un replace-lines qui
    ne change qu'un prix rend UNE ligne modifiée, plus « tout retiré / tout
    ajouté ». Renvoie ``{ajoutees, retirees, modifiees, parametres}`` :
    ``modifiees`` porte ``{cle, champs: {champ: [avant, apres]}}`` ;
    ``parametres`` porte ``{cle: [avant, apres]}`` pour ``remise_globale``,
    ``echeancier`` et chaque clé ``etude.<cle>`` qui a changé."""
    contenu_a = getattr(snapshot_a, 'contenu', snapshot_a) or {}
    contenu_b = getattr(snapshot_b, 'contenu', snapshot_b) or {}
    avant = _cles_appariement(contenu_a.get('lignes'))
    apres = _cles_appariement(contenu_b.get('lignes'))
    modifiees = []
    for cle, ligne in apres.items():
        precedente = avant.get(cle)
        if precedente is None:
            continue
        champs = {
            champ: [precedente.get(champ), ligne.get(champ)]
            for champ in sorted(set(precedente) | set(ligne))
            if champ not in _CHAMPS_POSITIONNELS + ('ligne_id',)
            and precedente.get(champ) != ligne.get(champ)}
        if champs:
            modifiees.append({'cle': cle, 'champs': champs})
    parametres = {}
    for cle in ('remise_globale', 'echeancier'):
        if contenu_a.get(cle) != contenu_b.get(cle):
            parametres[cle] = [contenu_a.get(cle), contenu_b.get(cle)]
    etude_a = contenu_a.get('etude') or {}
    etude_b = contenu_b.get('etude') or {}
    for cle in sorted(set(etude_a) | set(etude_b)):
        if etude_a.get(cle) != etude_b.get(cle):
            parametres[f'etude.{cle}'] = [etude_a.get(cle), etude_b.get(cle)]
    return {
        'ajoutees': [{'cle': cle, **li} for cle, li in apres.items()
                     if cle not in avant],
        'retirees': [{'cle': cle, **li} for cle, li in avant.items()
                     if cle not in apres],
        'modifiees': modifiees,
        'parametres': parametres,
    }
