"""Groupe NTWMS — sélecteurs LECTURE SEULE de la couche entrepôt.

Ré-exporté par ``apps/stock/selectors.py`` (fin de fichier) : les appelants
continuent d'écrire ``from apps.stock.selectors import …``.

FRONTIÈRE INTER-APPS. La hiérarchie de casiers zone/allée/casier existe DÉJÀ
et vit dans ``installations`` (``BinLocation``/``BinAffectation``, FG319 ;
``RegleRangement``/``CategorieStockage``, ZSTK9). Ce module ne la duplique
JAMAIS : il la lit soit par l'accesseur inverse posé sur ``stock.Produit``
(``produit.installations_bin_affectations``), soit via
``apps.installations.selectors`` — jamais en important ses modèles.
"""


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS1 — Localisation d'un produit, CASIER PAR CASIER
# ═══════════════════════════════════════════════════════════════════════════

def localisation_casiers(produit):
    """Localisation casier par casier d'un produit, dans l'ordre de parcours
    physique du magasin.

    Renvoie ``[{bin_id, code, zone, allee, casier, ordre, emplacement_id,
    emplacement_nom, quantite}]`` — liste VIDE tant qu'aucun casier n'est
    affecté (comportement historique préservé). Les casiers archivés sont
    exclus.
    """
    if produit is None:
        return []
    affectations = (produit.installations_bin_affectations
                    .select_related('bin', 'bin__emplacement')
                    .filter(bin__archived=False)
                    .order_by('bin__ordre', 'bin__code'))
    return [{
        'bin_id': aff.bin_id,
        'code': aff.bin.code,
        'zone': aff.bin.zone or '',
        'allee': aff.bin.allee or '',
        'casier': aff.bin.casier or '',
        'ordre': aff.bin.ordre,
        'emplacement_id': aff.bin.emplacement_id,
        'emplacement_nom': (aff.bin.emplacement.nom
                            if aff.bin.emplacement_id else ''),
        'quantite': aff.quantite,
    } for aff in affectations]


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS3 — Stratégies de prélèvement FIFO / FEFO / ZONE
# ═══════════════════════════════════════════════════════════════════════════

def strategie_picking_produit(produit):
    """Stratégie de prélèvement applicable à un produit : celle de sa
    catégorie, ou ``aucune`` (comportement historique) sans catégorie."""
    from .models import Categorie
    categorie = getattr(produit, 'categorie', None)
    if categorie is None:
        return Categorie.StrategiePicking.AUCUNE
    return (categorie.strategie_picking_defaut
            or Categorie.StrategiePicking.AUCUNE)


def resoudre_allocation_picking(produit, quantite, strategie=None):
    """Plan de prélèvement d'un produit : QUOI prendre, OÙ, dans quel ordre.

    Renvoie ``[{bin_id, bin_code, lot_id, numero_lot, date_peremption,
    quantite}]`` couvrant au mieux ``quantite``. ``strategie`` (défaut : celle
    de la catégorie du produit, NTWMS3) pilote l'ORDRE :

      * ``fefo`` — lots triés par ``date_peremption`` croissante (sans date en
        dernier), départage par ancienneté ;
      * ``fifo`` — lots triés par ``date_creation`` croissante ;
      * ``zone`` — casiers triés par ordre de parcours (le plus proche de la
        sortie d'abord), la traçabilité lot n'entrant pas en compte ;
      * ``aucune`` — une seule ligne sans lot ni casier : le comportement
        historique (le magasinier prend où il veut), JAMAIS une erreur.

    LECTURE SEULE : ne décrémente ni lot, ni stock, ni casier.
    """
    from django.db.models import F
    from .models import Categorie, LotEntrepot

    if produit is None:
        return []
    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        return []
    if quantite <= 0:
        return []

    strategie = strategie or strategie_picking_produit(produit)
    company = produit.company

    def _ligne(quantite_prise, lot=None, casier=None):
        return {
            'bin_id': casier['bin_id'] if casier else None,
            'bin_code': casier['code'] if casier else '',
            'lot_id': lot.id if lot is not None else None,
            'numero_lot': lot.numero_lot if lot is not None else '',
            'date_peremption': (lot.date_peremption
                                if lot is not None else None),
            'quantite': quantite_prise,
        }

    if strategie == Categorie.StrategiePicking.ZONE:
        restant = quantite
        plan = []
        for casier in localisation_casiers(produit):
            if restant <= 0:
                break
            disponible = casier['quantite'] or 0
            if disponible <= 0:
                continue
            prise = min(disponible, restant)
            plan.append(_ligne(prise, casier=casier))
            restant -= prise
        if not plan:
            # Aucun casier renseigné : ne jamais renvoyer une liste vide qui
            # ferait croire à une rupture — on retombe sur la ligne libre.
            return [_ligne(quantite)]
        return plan

    if strategie in (Categorie.StrategiePicking.FIFO,
                     Categorie.StrategiePicking.FEFO):
        lots = (LotEntrepot.objects
                .filter(company=company, produit=produit,
                        quantite_restante__gt=0))
        if strategie == Categorie.StrategiePicking.FEFO:
            lots = lots.order_by(
                F('date_peremption').asc(nulls_last=True), 'date_creation',
                'id')
        else:
            lots = lots.order_by('date_creation', 'id')
        restant = quantite
        plan = []
        for lot in lots:
            if restant <= 0:
                break
            prise = min(lot.quantite_restante, restant)
            plan.append(_ligne(prise, lot=lot))
            restant -= prise
        if not plan:
            # Produit non suivi par lot : ligne libre, jamais une erreur.
            return [_ligne(quantite)]
        return plan

    # AUCUNE (défaut) — comportement historique.
    return [_ligne(quantite)]


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS5 — Résolution universelle d'un code scanné (poste scanner mobile)
# ═══════════════════════════════════════════════════════════════════════════

def resoudre_code_scanne(company, code):
    """Résout un code scanné vers l'objet du magasin qu'il désigne.

    Ordre de résolution (le premier qui répond gagne) : casier (code
    ``BinLocation``) → produit (code-barres GTIN, puis SKU) → emplacement
    (nom) → lot (numéro de lot avec du restant). Renvoie
    ``{type, id, label, detail}`` ou ``None`` — jamais une erreur, jamais un
    objet d'une autre société.
    """
    from .models import EmplacementStock, LotEntrepot, Produit

    code = (code or '').strip()
    if not code or company is None:
        return None

    # 1) Casier (FG319) — lu par l'accesseur inverse de NOTRE string-FK, sans
    #    importer `apps.installations.models`.
    from .models_wms import LignePicking
    modele_bin = LignePicking._meta.get_field('bin').related_model
    casier = modele_bin.objects.filter(
        company=company, code__iexact=code, archived=False).first()
    if casier is not None:
        return {
            'type': 'casier',
            'id': casier.id,
            'label': casier.code,
            'detail': {
                'zone': casier.zone or '',
                'allee': casier.allee or '',
                'casier': casier.casier or '',
                'ordre': casier.ordre,
                'emplacement_id': casier.emplacement_id,
            },
        }

    # 2) Produit — code-barres (GTIN) puis SKU.
    produit = Produit.objects.filter(
        company=company, code_barres=code).first()
    if produit is None:
        produit = Produit.objects.filter(company=company, sku=code).first()
    if produit is not None:
        return {
            'type': 'produit',
            'id': produit.id,
            'label': produit.nom,
            'detail': {
                'sku': produit.sku or '',
                'quantite_stock': produit.quantite_stock,
                'strategie_picking': strategie_picking_produit(produit),
            },
        }

    # 3) Emplacement (dépôt/camionnette).
    emplacement = EmplacementStock.objects.filter(
        company=company, nom__iexact=code, archived=False).first()
    if emplacement is not None:
        return {
            'type': 'emplacement',
            'id': emplacement.id,
            'label': emplacement.nom,
            'detail': {'is_principal': emplacement.is_principal},
        }

    # 4) Lot encore disponible.
    lot = (LotEntrepot.objects
           .filter(company=company, numero_lot=code, quantite_restante__gt=0)
           .order_by('date_peremption', 'id')
           .first())
    if lot is not None:
        return {
            'type': 'lot',
            'id': lot.id,
            'label': lot.numero_lot,
            'detail': {
                'produit_id': lot.produit_id,
                'quantite_restante': lot.quantite_restante,
                'date_peremption': lot.date_peremption,
            },
        }
    return None


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS7 — Planning des quais (vue jour / semaine)
# ═══════════════════════════════════════════════════════════════════════════

def planning_quais(company, *, date_str=None, vue='jour', quai_id=None):
    """Planning des rendez-vous par quai, en vue JOUR ou SEMAINE.

    ``date_str`` (``YYYY-MM-DD``) est la date d'ancrage — OBLIGATOIRE : le
    serveur ne devine jamais « aujourd'hui » pour un planning (une réponse qui
    change à minuit rend l'écran et ses tests non déterministes).

    Renvoie ``{date_debut, date_fin, vue, quais: [{quai_id, quai_nom,
    type_quai, rendez_vous: [...]}]}``. LECTURE SEULE.
    """
    import datetime

    from .models_wms import Quai, RendezVousTransporteur

    if vue not in ('jour', 'semaine'):
        raise ValueError('Vue de planning inconnue (jour ou semaine).')
    if not date_str:
        raise ValueError('Paramètre date requis (AAAA-MM-JJ).')
    try:
        ancre = datetime.date.fromisoformat(str(date_str))
    except (TypeError, ValueError):
        raise ValueError('Date invalide (format attendu AAAA-MM-JJ).')

    if vue == 'semaine':
        debut = ancre - datetime.timedelta(days=ancre.weekday())
        fin = debut + datetime.timedelta(days=6)
    else:
        debut = fin = ancre

    quais = Quai.objects.filter(company=company, actif=True)
    if quai_id and str(quai_id).isdigit():
        quais = quais.filter(id=int(quai_id))
    quais = list(quais.order_by('nom'))

    rdvs = (RendezVousTransporteur.objects
            .filter(company=company, quai__in=quais,
                    date_heure_debut__date__gte=debut,
                    date_heure_debut__date__lte=fin)
            .select_related('transporteur')
            .order_by('date_heure_debut', 'id'))
    par_quai = {}
    for rdv in rdvs:
        par_quai.setdefault(rdv.quai_id, []).append({
            'id': rdv.id,
            'debut': rdv.date_heure_debut,
            'fin': rdv.date_heure_fin,
            'statut': rdv.statut,
            'transporteur_id': rdv.transporteur_id,
            'transporteur_nom': getattr(rdv.transporteur, 'nom', '') or '',
            'chauffeur_nom': rdv.chauffeur_nom,
            'immatriculation': rdv.immatriculation,
        })
    return {
        'date_debut': debut,
        'date_fin': fin,
        'vue': vue,
        'quais': [{
            'quai_id': quai.id,
            'quai_nom': quai.nom,
            'type_quai': quai.type_quai,
            'rendez_vous': par_quai.get(quai.id, []),
        } for quai in quais],
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS10 — Comparateur de tarifs transporteurs (rate shopping)
# ═══════════════════════════════════════════════════════════════════════════

def comparer_tarifs_transporteurs(unite_logistique, destination=''):
    """Tableau comparatif coût/délai AVANT de sceller le choix du transporteur.

    Interroge ``estimer_tarif`` de chaque connecteur GATED configuré pour la
    société (NTWMS9). REPLI GRACIEUX, sans aucune régression : les
    transporteurs du référentiel interne (``installations.Transporteur``,
    FG331) sont TOUJOURS listés avec leur ``tarif_base`` — donc sans le moindre
    connecteur configuré, la réponse est exactement l'information dont on
    disposait déjà.

    Renvoie ``[{source, code, libelle, cout, devise, delai_jours}]`` trié du
    moins cher au plus cher (les lignes sans coût connu en dernier).
    LECTURE SEULE : n'appelle aucun connecteur non configuré, n'écrit rien.
    """
    from decimal import Decimal

    from .models_wms import ExpeditionTransporteur
    from .providers import providers_configures

    if unite_logistique is None:
        return []
    company = unite_logistique.company
    poids = unite_logistique.poids_kg
    dimensions = unite_logistique.dimensions or ''

    lignes = []

    # 1) Connecteurs gated réellement configurés (le NoOp ne cote jamais).
    for code, provider in providers_configures(company):
        estimation = provider.estimer_tarif(
            poids_kg=poids, dimensions=dimensions, destination=destination)
        if not estimation:
            continue
        lignes.append({
            'source': 'provider',
            'code': code,
            'libelle': getattr(provider, 'label', '') or code,
            'cout': estimation.get('cout'),
            'devise': estimation.get('devise') or 'MAD',
            'delai_jours': estimation.get('delai_jours'),
        })

    # 2) Référentiel interne — le repli qui existait déjà (FG331).
    modele_transporteur = (
        ExpeditionTransporteur._meta.get_field('transporteur').related_model)
    internes = (modele_transporteur.objects
                .filter(company=company, active=True)
                .order_by('nom'))
    for transporteur in internes:
        lignes.append({
            'source': 'interne',
            'code': str(transporteur.id),
            'libelle': transporteur.nom,
            'cout': transporteur.tarif_base,
            'devise': 'MAD',
            'delai_jours': None,
        })

    def _cle(ligne):
        cout = ligne.get('cout')
        # Les lignes sans coût connu passent en dernier, jamais devant une
        # offre chiffrée.
        return (0, Decimal(str(cout))) if cout is not None else (1, Decimal(0))

    lignes.sort(key=_cle)
    return lignes
