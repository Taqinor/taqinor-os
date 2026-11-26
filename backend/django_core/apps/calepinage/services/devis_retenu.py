"""ACAL1951-ACAL1956 — le calepinage d'un devis LIT la conception que ce devis a
retenue (demande du fondateur : « one engine, the CRM one »).

La conception vient d'UN sélecteur de ventes (``apps.ventes.selectors_calepinage.
conception_retenue_du_devis``, ACAL1950, contrat
``contract_samples/calepinage_conception_retenue.json``) : option retenue, module
et quantité, onduleurs, chaînes, production annuelle. Ce module n'en recalcule
rien et n'écrit rien sur le devis ; il ne range qu'une seule chose, dans le
``resultat`` du calepinage (écrivain unique ``services.resultat.
modifier_resultat``) : l'option que le dernier enregistrement du dessin visait.
"""
from __future__ import annotations

from . import pret_a_envoyer as _pret_a_envoyer  # H5 — une_fois_par_lecture

#: ACAL1951 — clé de ``Calepinage.resultat`` : ``{devis, option}`` que le dernier
#: enregistrement du dessin visait (absente sans devis lié).
CLE_OPTION_DESSINEE = 'option_dessinee'


#: Mémoire de la conception lue, posée sur l'INSTANCE du calepinage (une requête) :
#: ``(devis_id, conception)`` — un re-lien change ``devis_id``, donc relit.
_MEMOIRE = '_acal1950_conception_retenue'


@_pret_a_envoyer.une_fois_par_lecture('conception_retenue')
def conception_du_devis_lie(calepinage, devis=None):
    """ACAL1950 — la conception retenue du devis lié (``devis`` déjà lu par
    l'appelant, sinon lu ici, borné à la société), ou ``None`` sans devis lié.
    Lue UNE fois par instance (budget de requêtes des écrans)."""
    from .equipements import conception_retenue, conception_retenue_par_id

    if devis is not None:
        return conception_retenue(devis)
    devis_id = getattr(calepinage, 'devis_id', None)
    memoire = getattr(calepinage, _MEMOIRE, None)
    if memoire is not None and memoire[0] == devis_id:
        return memoire[1]
    valeur = (conception_retenue_par_id(devis_id, getattr(calepinage, 'company', None))
              if devis_id else None)
    try:
        setattr(calepinage, _MEMOIRE, (devis_id, valeur))
    except AttributeError:  # double de test sans attributs libres : relu à chaque appel
        pass
    return valeur


#: Coût des requêtes (lot 4) — vrai pendant une LISTE (file « à traiter ») : la conception est
#: lue telle que rangée, sans rien du moteur (péremption, relance), et le devis reçu comparé
#: est le seul devis lié (aucun repli sur le lead) — la liste n'en lit que ses signaux.
_EN_LISTE = __import__('contextvars').ContextVar('calepinage_lecture_de_liste', default=False)


def lecture_de_liste():
    """Le bloc ``with`` d'une LISTE de calepinages (voir :data:`_EN_LISTE`)."""
    import contextlib

    @contextlib.contextmanager
    def _bloc():
        jeton = _EN_LISTE.set(True)
        try:
            yield
        finally:
            _EN_LISTE.reset(jeton)
    return _bloc()


#: ACAL2012 — mémoire de la conception COURANTE lue, posée sur l'instance (une requête).
_MEMOIRE_CONCEPTION = '_acal2012_conception_courante'
#: ACAL2012 — le refus NOMMÉ d'un porteur sans version rangée : jamais une taille inventée.
CODE_CONCEPTION_ABSENTE = 'conception_absente'
REFUS_CONCEPTION_ABSENTE = ("Conception du lead pas encore calculée par le moteur : elle se calcule dès qu'une "
                            "entrée de la fiche (facture, ville, taille souhaitée…) est enregistrée.")
#: Relecture E5 B1 — aucune version rangée, son premier calcul est en file : l'atelier attend et relit.
CODE_CONCEPTION_EN_COURS = 'conception_en_cours'
REFUS_CONCEPTION_EN_COURS = ("Conception du lead en cours de calcul : elle s'affichera dans quelques secondes.")
#: Refus gardé tel quel (ACAL194) : le champ d'un lead agricole découle de sa pompe, pas d'une facture.
REFUS_AGRICOLE = "Lead agricole : le pompage se chiffre depuis l'écran devis agricole."


def conception_du_calepinage(calepinage):
    """ACAL2012 (D-ACAL-97) — LA conception COURANTE qui sert le calepinage : celle
    de son lead, sinon celle du calepinage lui-même (porteur sans lead, Q3), lue par
    la porte de lecture de ventes (``apps.ventes.services.conception_ou_calcul`` →
    ``conception_courante``, contrat ``conception_lead.json``) ; ``None`` sans version
    rangée (son premier calcul est alors mis en file : ``calcul_en_cours``) ou pour un
    dossier d'appel d'offres (hors moteur). Lue UNE fois par instance ; rien n'est écrit."""
    return _lire_conception(calepinage)[0]


def _calcul_en_cours(calepinage):
    """Relecture E5 B1 — vrai quand le lead n'a encore aucune conception rangée et que
    son premier calcul vient d'être mis en file (ou l'était déjà) : l'atelier attend."""
    return _lire_conception(calepinage)[1]


def _lire_conception(calepinage):
    from django.db.models import Model

    from .equipements import conception_ou_calcul  # la porte de ventes, par un importateur existant

    company = getattr(calepinage, 'company', None)
    # Une société qui n'est pas une ligne enregistrée (double de calcul pur) ne se lit pas en base.
    if not isinstance(company, Model) or not company.pk or getattr(calepinage, 'appel_offre_id', None):
        return None, False
    lead_id, en_liste = getattr(calepinage, 'lead_id', None), _EN_LISTE.get()
    cle = (lead_id, getattr(calepinage, 'pk', None), en_liste)
    memoire = getattr(calepinage, _MEMOIRE_CONCEPTION, None)
    if memoire is not None and memoire[0] == cle:
        return memoire[1]
    valeur = (conception_ou_calcul(company, lead_id, en_liste=en_liste) if lead_id
              else conception_ou_calcul(company, calepinage_id=cle[1], en_liste=en_liste) if cle[1]
              else (None, False))
    try:
        setattr(calepinage, _MEMOIRE_CONCEPTION, (cle, valeur))
    except AttributeError:  # double de test sans attributs libres : relu à chaque appel
        pass
    return valeur


def _source_de_la_taille(calepinage):
    """``'lead'`` quand la taille souhaitée du lead fait la taille (souveraine), sinon ``'factures'`` ;
    relecture E5 m2 — ``'conception'`` pour un calepinage SANS lead (sa propre conception, aucune facture)."""
    from apps.crm.selectors import get_company_lead

    if not getattr(calepinage, 'lead_id', None):
        return 'conception'
    lead = get_company_lead(calepinage.company, calepinage.lead_id, avec_corbeille=True)
    try:
        return 'lead' if float(getattr(lead, 'taille_souhaitee_kwc', None) or 0) > 0 else 'factures'
    except (TypeError, ValueError):
        return 'factures'


def _refus(message, code, source='factures'):
    return {'panneaux': None, 'kwc': None, 'panel_watt': None, 'source': source, 'refus': message,
            'motif_code': code, 'option': None, 'version': None, 'raison': None}


def attend_son_premier_calcul(calepinage):
    """Relecture E5 B1 — l'atelier ATTEND (« calcul en cours ») : le premier calcul de la conception est
    en file ET le lead a de quoi être dimensionné. Un lead sans facture ni taille n'attend rien : aucun
    calcul ne lui donnera de taille, le refus nomme ce qu'il faut saisir (question de taille, ACAL922)."""
    from .devis import lead_sans_facture_ni_taille

    return _calcul_en_cours(calepinage) and not lead_sans_facture_ni_taille(calepinage)


def cible_de_la_conception(calepinage):
    """ACAL2012 — la cible de l'atelier : la taille de la conception COURANTE (option que
    le moteur retient), avec ou sans devis — un devis lié, même envoyé, n'est plus la
    source (son écart est servi à part, ACAL2015). ``{panneaux, kwc, panel_watt, source,
    refus, motif_code, option, version, raison}`` (lane E9 : version et raison de la
    conception, ``None`` sans conception complète) ; un refus du moteur (ou aucune version rangée) est
    rendu NOMMÉ, panneaux nuls ; ``None`` pour un dossier d'appel d'offres, ou un
    calepinage sans lead dont aucune conception n'est rangée (rien ne le dimensionne,
    comme avant). ``motif_code`` vaut ``facture_absente`` quand le refus nomme la
    facture d'hiver (question de taille de la génération, ACAL922)."""
    from .equipements import motif_facture_absente

    if getattr(calepinage, 'appel_offre_id', None) or getattr(calepinage, 'company', None) is None:
        return None
    conception = conception_du_calepinage(calepinage)
    if conception is None:
        if not getattr(calepinage, 'lead_id', None):
            return None
        if attend_son_premier_calcul(calepinage):  # relecture E5 B1 : jamais 0 panneau, l'atelier attend
            return _refus(REFUS_CONCEPTION_EN_COURS, CODE_CONCEPTION_EN_COURS)
        return _refus(REFUS_CONCEPTION_ABSENTE, CODE_CONCEPTION_ABSENTE)
    if conception.get('marche') == 'agricole':
        return _refus(REFUS_AGRICOLE, None, 'lead')
    if conception.get('etat') != 'complet':
        refus = conception.get('refus') or {}
        code = motif_facture_absente() if refus.get('champ') == 'facture_hiver' else refus.get('code')
        return _refus(refus.get('message') or '', code)
    option = conception.get('option_retenue')
    valeurs = (conception.get('valeurs') or {}).get(option) or {}
    panneaux = (valeurs.get('nb_panneaux') or {}).get('valeur')
    kwc = (valeurs.get('puissance_kwc') or {}).get('valeur')
    watt = round(float(kwc) * 1000 / panneaux) if panneaux and kwc else None
    # Lane E9 — la version et la raison (mots de l'utilisateur) de CETTE conception : l'atelier dit pourquoi
    # ses chiffres ont changé depuis son ouverture, jamais en silence (aucune lecture de plus : même conception).
    return {'panneaux': panneaux, 'kwc': kwc, 'panel_watt': watt, 'source': _source_de_la_taille(calepinage),
            'refus': None, 'motif_code': None, 'option': option, 'version': conception.get('version'),
            'raison': (conception.get('declencheur') or {}).get('raison') or None}


def memoriser_option_dessinee(calepinage):
    """ACAL1951 — range ``{devis, option}`` visés par l'enregistrement du dessin
    dans ``resultat`` : ACAL2025, l'option est celle de la conception COURANTE
    (cible de l'atelier), jamais celle des lignes du devis ; retirée sans option
    (aucune conception complète). N'écrit rien quand la valeur rangée est déjà
    la bonne. Rend la valeur rangée."""
    from .resultat import modifier_resultat

    option = (cible_de_la_conception(calepinage) or {}).get('option')
    valeur = ({'devis': getattr(calepinage, 'devis_id', None), 'option': option}
              if option else None)
    if (getattr(calepinage, 'resultat', None) or {}).get(CLE_OPTION_DESSINEE) == valeur:
        return valeur

    def _poser(resultat):
        if valeur is None:
            resultat.pop(CLE_OPTION_DESSINEE, None)
        else:
            resultat[CLE_OPTION_DESSINEE] = valeur

    modifier_resultat(calepinage, _poser)
    return valeur


def _onduleur_retenu(conception):
    """ACAL1952 — la première ligne onduleur de l'option retenue, ou ``None``."""
    onduleurs = (conception or {}).get('onduleurs') or []
    return onduleurs[0] if onduleurs and onduleurs[0].get('produit') else None


def _longueur_du_devis(conception):
    return ((conception or {}).get('chaines') or {}).get('longueur') or None


def bloc_devis_retenu(calepinage, stockee, resolu):
    """ACAL1952 — le bloc ``devis_retenu`` de ``GET entree-electrique/`` : le
    matériel électrique que le devis lié a retenu (provenance « devis ») et les
    ÉCARTS d'une saisie contraire — des informations, jamais un refus : la
    saisie reste permise. ``None`` sans devis lié."""
    conception = conception_du_devis_lie(calepinage)
    if not conception:
        return None
    onduleur = _onduleur_retenu(conception)
    longueur = _longueur_du_devis(conception)
    saisie = stockee or {}
    reference = conception['reference']
    ecarts = []
    saisi = saisie.get('onduleur_produit')
    if onduleur and saisi not in (None, '') and str(saisi) != str(onduleur['produit']):
        designe = ((resolu or {}).get('designations') or {}).get('onduleur') or 'un autre onduleur'
        from .variantes import onduleur_designe_a_la_main  # revue du 26/11 : un onduleur repris n'est pas « désigné »
        mot = 'désigné' if onduleur_designe_a_la_main(calepinage) else 'repris de l’original'
        ecarts.append(f'Onduleur : « {designe} » {mot}, « {onduleur["designation"]} » au devis {reference}.')
    for cle, devis_valeur, unite in (('nombre_onduleurs', (onduleur or {}).get('quantite'), 'onduleur(s)'),
                                     ('longueur_chaine_forcee', longueur, 'modules par chaîne')):
        valeur = saisie.get(cle)
        if valeur not in (None, '') and devis_valeur and str(valeur) != str(devis_valeur):
            ecarts.append(f'{valeur} {unite} saisi(s), {devis_valeur} au devis {reference}.')
    return {'devis': conception['devis'], 'reference': reference, 'statut': conception['statut'],
            'option': conception['option'], 'provenance': 'devis',
            'onduleur': ({'produit_id': onduleur['produit'], 'designation': onduleur['designation']}
                         if onduleur else None),
            'nombre_onduleurs': (onduleur or {}).get('quantite') or None,
            'longueur_chaine': longueur, 'ecarts': ecarts}


def bloc_conception(calepinage):
    """ACAL2015 (D-ACAL-96) — ``conception`` de ``GET resultat/`` : LE chiffre de production
    de la conception courante (option du moteur) que l'étape Résultats affiche, et — quand le
    devis lié a été REÇU par le client (envoyé, accepté) — ce devis NOMMÉ (référence, date
    d'envoi) avec l'écart que ventes sert (``apps.ventes.selectors.ecart_devis``, l'unique
    comparaison ; « Réviser le devis » quand ``reviser_possible``). Rien n'est recalculé,
    rien n'est écrit, le devis n'est jamais touché. ``None`` sans conception complète."""
    conception = conception_du_calepinage(calepinage)
    if not conception or conception.get('etat') != 'complet':
        return None
    option = conception.get('option_retenue')
    table = (conception.get('valeurs') or {}).get(option) or {}
    production = table.get('production_annuelle') or {}
    from .equipements import devis_lie_et_pose

    # T4-X7-013 — la production et LA taille pour laquelle elle est calculée, lues sur la même
    # option de la même version : l'écran ne les prend plus à deux lectures différentes.
    # T4-X7-006 — le devis LIÉ (une V2 brouillon comprise) et s'il porte la pose : l'écart
    # devis ↔ pose reste nommé après une révision (``a_jour`` faux ⇒ « à resynchroniser »).
    return {'production_annuelle_kwh': production.get('valeur'), 'option': option,
            'puissance_kwc': (table.get('puissance_kwc') or {}).get('valeur'),
            'nb_panneaux': (table.get('nb_panneaux') or {}).get('valeur'),
            'version': conception.get('version'), 'calcule_le': conception.get('calcule_le'),
            'designations': _phrases_des_designations(conception),
            'devis_envoye': _devis_envoye_lie(calepinage),
            'devis_lie': devis_lie_et_pose(calepinage)}


#: D-ACAL-109 / D-ACAL-110 — les champs des suppositions qui parlent du matériel DÉSIGNÉ à
#: l'étape Électrique (laquelle des options il sert, arrondi au module, désignation écartée).
CHAMPS_DESIGNATION = ('onduleur_produit', 'module_produit')


def _phrases_des_designations(conception):
    """Les phrases SERVIES par ventes (``suppositions`` de la conception) sur le matériel
    désigné à la main, dans leur ordre ; ``[]`` sans désignation. Aucune n'est réécrite."""
    return [s['message'] for s in conception.get('suppositions') or []
            if isinstance(s, dict) and s.get('champ') in CHAMPS_DESIGNATION and s.get('message')]


def _devis_envoye_lie(calepinage):
    """``{devis, reference, statut, envoye_le, option, production_annuelle_kwh, ecart_devis}`` du
    devis lié REÇU, ou ``None``. Relecture E5 M2 — ``option`` et ``production_annuelle_kwh`` sont
    CEUX DU DEVIS (rangés, ``conception_retenue_du_devis`` ; ``None`` quand il n'en range aucune) :
    l'écran les compare au chiffre qu'il affiche, jamais à la conception."""
    from .equipements import devis_et_ecart

    lu = _devis_recu_du_calepinage(calepinage)
    if not lu:
        return None
    devis, ecart = devis_et_ecart(lu['devis'], lu, getattr(calepinage, 'company_id', None))
    if devis is None:
        return None
    envoi = getattr(devis, 'date_envoi', None)
    return {'devis': devis.pk, 'reference': devis.reference or '', 'statut': devis.statut,
            'envoye_le': envoi.isoformat() if envoi else None, 'option': lu.get('option'),
            'production_annuelle_kwh': lu.get('production_annuelle_kwh'),
            'ecart_devis': ecart}


def _devis_recu_du_calepinage(calepinage):
    """T4-X5-004 — la conception retenue du devis que le client a REÇU, à comparer à ce
    calepinage : son devis lié s'il est reçu, sinon — calepinage DE LEAD — le dernier devis
    reçu du lead, lié ou non (``liens.dernier_devis_recu``, porte de ventes). ``None`` sinon.
    Rien n'est écrit, aucun devis n'est touché."""
    lu = conception_du_devis_lie(calepinage)
    if lu and lu.get('recu'):
        return lu
    lead_id = getattr(calepinage, 'lead_id', None)
    if not lead_id or getattr(calepinage, 'company', None) is None or _EN_LISTE.get():
        return None
    memoire = getattr(calepinage, _MEMOIRE_RECU_DU_LEAD, None)
    if memoire is not None and memoire[0] == lead_id:  # bloc_conception et production_devis : UNE lecture
        return memoire[1]
    valeur = _devis_recu_du_lead(calepinage, lead_id)
    try:
        setattr(calepinage, _MEMOIRE_RECU_DU_LEAD, (lead_id, valeur))
    except AttributeError:  # double de test sans attributs libres : relu à chaque appel
        pass
    return valeur


#: Coût des requêtes (lot 4) — le devis reçu du lead lu, posé sur l'instance (une requête).
_MEMOIRE_RECU_DU_LEAD = '_lot4_devis_recu_du_lead'


def _devis_recu_du_lead(calepinage, lead_id):
    """Le dernier devis reçu du lead (porte de ventes), sa conception retenue, ou ``None``."""
    from .equipements import conception_retenue
    from .liens import dernier_devis_recu

    devis = dernier_devis_recu(calepinage.company, lead_id)
    lu = conception_retenue(devis) if devis is not None else None
    return lu if lu and lu.get('recu') else None


def bloc_production_devis(calepinage):
    """ACAL1956 (D-ACAL-90) — ``production_devis`` de ``GET resultat/`` : la
    production annuelle RETENUE PAR LE DEVIS (``conception_retenue_du_devis``,
    aucun recalcul) quand le calepinage est lié à un devis envoyé ou accepté —
    l'étape Résultats n'est jamais vide, même avant la simulation de la pose.
    ``{devis, reference, statut, production_annuelle_kwh, production_origine}``
    ou ``None`` (sans devis lié, ou devis encore brouillon)."""
    conception = _devis_recu_du_calepinage(calepinage)  # T4-X5-004 : lié, sinon reçu du lead
    if not conception:
        return None
    return {cle: conception[cle] for cle in ('devis', 'reference', 'statut',
                                             'production_annuelle_kwh', 'production_origine')}
