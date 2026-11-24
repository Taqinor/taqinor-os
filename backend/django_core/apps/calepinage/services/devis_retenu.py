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


#: ACAL2012 — mémoire de la conception COURANTE lue, posée sur l'instance (une requête).
_MEMOIRE_CONCEPTION = '_acal2012_conception_courante'
#: ACAL2012 — le refus NOMMÉ d'un porteur sans version rangée : jamais une taille inventée.
CODE_CONCEPTION_ABSENTE = 'conception_absente'
REFUS_CONCEPTION_ABSENTE = ("Conception du lead pas encore calculée par le moteur : elle se calcule dès qu'une "
                            "entrée de la fiche (facture, ville, taille souhaitée…) est enregistrée.")
#: Refus gardé tel quel (ACAL194) : le champ d'un lead agricole découle de sa pompe, pas d'une facture.
REFUS_AGRICOLE = "Lead agricole : le pompage se chiffre depuis l'écran devis agricole."


def conception_du_calepinage(calepinage):
    """ACAL2012 (D-ACAL-97) — LA conception COURANTE qui sert le calepinage : celle
    de son lead, sinon celle du calepinage lui-même (porteur sans lead, Q3), lue par
    ``apps.ventes.selectors.conception_courante`` (contrat ``conception_lead.json``) ;
    ``None`` sans version rangée ou pour un dossier d'appel d'offres (hors moteur).
    Lue UNE fois par instance ; rien n'est écrit."""
    from django.db.models import Model

    from apps.ventes.selectors import conception_courante

    company = getattr(calepinage, 'company', None)
    # Une société qui n'est pas une ligne enregistrée (double de calcul pur) ne se lit pas en base.
    if not isinstance(company, Model) or not company.pk or getattr(calepinage, 'appel_offre_id', None):
        return None
    lead_id = getattr(calepinage, 'lead_id', None)
    cle = (lead_id, getattr(calepinage, 'pk', None))
    memoire = getattr(calepinage, _MEMOIRE_CONCEPTION, None)
    if memoire is not None and memoire[0] == cle:
        return memoire[1]
    valeur = (conception_courante(company, lead_id) if lead_id
              else conception_courante(company, calepinage_id=cle[1]) if cle[1] else None)
    try:
        setattr(calepinage, _MEMOIRE_CONCEPTION, (cle, valeur))
    except AttributeError:  # double de test sans attributs libres : relu à chaque appel
        pass
    return valeur


def _source_de_la_taille(calepinage):
    """``'lead'`` quand la taille souhaitée du lead fait la taille (souveraine), sinon ``'factures'``."""
    from apps.crm.selectors import get_company_lead

    if not getattr(calepinage, 'lead_id', None):
        return 'factures'
    lead = get_company_lead(calepinage.company, calepinage.lead_id, avec_corbeille=True)
    try:
        return 'lead' if float(getattr(lead, 'taille_souhaitee_kwc', None) or 0) > 0 else 'factures'
    except (TypeError, ValueError):
        return 'factures'


def _refus(message, code, source='factures'):
    return {'panneaux': None, 'kwc': None, 'panel_watt': None, 'source': source, 'refus': message,
            'motif_code': code, 'option': None}


def cible_de_la_conception(calepinage):
    """ACAL2012 — la cible de l'atelier : la taille de la conception COURANTE (option que
    le moteur retient), avec ou sans devis — un devis lié, même envoyé, n'est plus la
    source (son écart est servi à part, ACAL2015). ``{panneaux, kwc, panel_watt, source,
    refus, motif_code, option}`` ; un refus du moteur (ou aucune version rangée) est
    rendu NOMMÉ, panneaux nuls ; ``None`` pour un dossier d'appel d'offres, ou un
    calepinage sans lead dont aucune conception n'est rangée (rien ne le dimensionne,
    comme avant). ``motif_code`` vaut ``facture_absente`` quand le refus nomme la
    facture d'hiver (question de taille de la génération, ACAL922)."""
    from apps.ventes.services import MOTIF_FACTURE_ABSENTE

    if getattr(calepinage, 'appel_offre_id', None) or getattr(calepinage, 'company', None) is None:
        return None
    conception = conception_du_calepinage(calepinage)
    if conception is None:
        if not getattr(calepinage, 'lead_id', None):
            return None
        return _refus(REFUS_CONCEPTION_ABSENTE, CODE_CONCEPTION_ABSENTE)
    if conception.get('marche') == 'agricole':
        return _refus(REFUS_AGRICOLE, None, 'lead')
    if conception.get('etat') != 'complet':
        refus = conception.get('refus') or {}
        code = MOTIF_FACTURE_ABSENTE if refus.get('champ') == 'facture_hiver' else refus.get('code')
        return _refus(refus.get('message') or '', code)
    option = conception.get('option_retenue')
    valeurs = (conception.get('valeurs') or {}).get(option) or {}
    panneaux = (valeurs.get('nb_panneaux') or {}).get('valeur')
    kwc = (valeurs.get('puissance_kwc') or {}).get('valeur')
    watt = round(float(kwc) * 1000 / panneaux) if panneaux and kwc else None
    return {'panneaux': panneaux, 'kwc': kwc, 'panel_watt': watt, 'source': _source_de_la_taille(calepinage),
            'refus': None, 'motif_code': None, 'option': option}


def memoriser_option_dessinee(calepinage):
    """ACAL1951 — range ``{devis, option}`` visés par l'enregistrement du dessin
    dans ``resultat`` (retiré sans devis lié). N'écrit rien quand la valeur
    rangée est déjà la bonne. Rend la valeur rangée."""
    from .resultat import modifier_resultat

    conception = conception_du_devis_lie(calepinage)
    valeur = ({'devis': conception['devis'], 'option': conception['option']}
              if conception else None)
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


def _module_retenu(conception):
    module = (conception or {}).get('module')
    produit = module.get('produit') if isinstance(module, dict) else None
    return produit if produit not in (None, '') else None


def module_retenu_du_devis(calepinage):
    """Rejeu T3-VAGUEC2 — le produit MODULE de la conception retenue du devis
    lié (``apps.ventes.selectors_calepinage.conception_retenue_du_devis``),
    ou ``None`` sans devis lié ni ligne panneau : le module que l'atelier pose
    d'office, jamais un module d'essai du catalogue de même puissance."""
    return _module_retenu(conception_du_devis_lie(calepinage))


def produits_retenus(calepinage, produits):
    """ACAL1952 — ``{rôle: produit}`` du devis lié : l'onduleur ET le module
    sont ceux de l'option RETENUE par le devis (plus la première ligne hors
    « avec ») ; l'optimiseur reste celui de l'agrégat ``equipements``. Une
    désignation EXPLICITE de l'entrée garde la main (``resoudre_materiel`` ne
    lit le devis qu'à défaut)."""
    conception = conception_du_devis_lie(calepinage)
    retenus = dict(produits)
    onduleur = _onduleur_retenu(conception)
    if onduleur:
        retenus['onduleur'] = onduleur['produit']
    module = _module_retenu(conception)
    if module is not None:
        retenus['module'] = module
    return retenus


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
        ecarts.append(f'Onduleur : « {designe} » désigné, « {onduleur["designation"]} » au devis {reference}.')
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


def bloc_production_devis(calepinage):
    """ACAL1956 (D-ACAL-90) — ``production_devis`` de ``GET resultat/`` : la
    production annuelle RETENUE PAR LE DEVIS (``conception_retenue_du_devis``,
    aucun recalcul) quand le calepinage est lié à un devis envoyé ou accepté —
    l'étape Résultats n'est jamais vide, même avant la simulation de la pose.
    ``{devis, reference, statut, production_annuelle_kwh, production_origine}``
    ou ``None`` (sans devis lié, ou devis encore brouillon)."""
    conception = conception_du_devis_lie(calepinage)
    if not conception or not conception['recu']:
        return None
    return {cle: conception[cle] for cle in ('devis', 'reference', 'statut',
                                             'production_annuelle_kwh', 'production_origine')}
