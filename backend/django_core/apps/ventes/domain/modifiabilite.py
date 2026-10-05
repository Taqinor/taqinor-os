"""QJR516 (Groupe QJR5, D-QJR5-1 / D-QJR5-2 / D-QJR5-5) — UN SEUL prédicat de
modifiabilité d'un devis, PAR GESTE, servi au front.

LE CONSTAT. La règle « ce devis se modifie-t-il encore ? » était recopiée en
ligne à six endroits (``_MODIFIABLES`` ×2 dans ``views/devis.py``, ``FROZEN``
×2 dans ``views/devis.py`` et ``views/ligne_devis.py``, le tuple des options
de ``cycle_vie.activate_optional_line``, le brouillon-seul de la
resynchronisation) — et huit écritures (layout, roof-image, overrides,
etude-params, offres-tailles config/regenerer, lots) n'en portaient AUCUNE :
un devis ACCEPTÉ, dont la chaîne BC/Facture dépend, restait modifiable par
elles. Le sélecteur du contexte 3D déclarait modifiable un calepinage que
sync-layout refusait.

LA TABLE (geste → statuts qui l'acceptent). Un devis INACTIF (remplacé par une
révision, archivé) n'accepte AUCUN geste et n'est pas révisable (on révise sa
remplaçante) ; un devis accepté / refusé / expiré n'accepte aucun geste mais
est révisable (D-QJR5-2).

* ``LIGNES`` / ``ENTETE`` / ``BOQ`` / ``OPTIONS`` / ``ETUDE`` — brouillon +
  envoyé (D-QJR5-1 : un envoyé se corrige SUR PLACE). ``ETUDE`` couvre les
  écritures d'étude et de rendu qui ne recomposent pas les lignes
  (etude-params, overrides, offres-tailles config/regenerer, layout brut,
  roof-image).
* ``CALEPINAGE`` / ``TAILLE`` — brouillon + envoyé depuis QJR557
  (D-QJR5-5, même règle que l'Édition complète : la resynchronisation des
  lignes depuis un calepinage et l'application d'une taille d'offre
  corrigent un envoyé SUR PLACE, tracées par ``fin_de_geste_devis`` —
  chatter « corrigé après envoi : calepinage » / « : taille d'offre »).

Ce module LIT le statut, il ne l'écrit jamais (règle #4). Les tuples de CYCLE
DE VIE (acceptation, expiration, gammes…) n'en font PAS partie : ce prédicat ne
dit que « ce geste d'ÉDITION est-il permis ? ».
"""

LIGNES = 'LIGNES'
ENTETE = 'ENTETE'
BOQ = 'BOQ'
OPTIONS = 'OPTIONS'
ETUDE = 'ETUDE'
CALEPINAGE = 'CALEPINAGE'
TAILLE = 'TAILLE'

_BROUILLON = 'brouillon'
_ENVOYE = 'envoye'

#: La table unique geste → statuts qui l'acceptent.
GESTES = {
    LIGNES: frozenset({_BROUILLON, _ENVOYE}),
    ENTETE: frozenset({_BROUILLON, _ENVOYE}),
    BOQ: frozenset({_BROUILLON, _ENVOYE}),
    OPTIONS: frozenset({_BROUILLON, _ENVOYE}),
    ETUDE: frozenset({_BROUILLON, _ENVOYE}),
    # QJR557 (D-QJR5-5) — un envoyé se corrige aussi par le calepinage 3D et
    # par « appliquer une taille d'offre » (accepté/refusé/expiré → Réviser).
    CALEPINAGE: frozenset({_BROUILLON, _ENVOYE}),
    TAILLE: frozenset({_BROUILLON, _ENVOYE}),
}

#: Les statuts CLOS (document engagé ou abandonné) : révisables, jamais
#: modifiables.
STATUTS_CLOS = frozenset({'accepte', 'refuse', 'expire'})


class DevisNonModifiable(Exception):
    """Levée par :func:`exiger_modifiable` — l'appelant la traduit en 409
    ``{detail, statut, revision_possible}`` (ou garde son propre code
    historique, voir les sites d'appel)."""

    def __init__(self, detail, *, statut='', revision_possible=False):
        super().__init__(detail)
        self.detail = detail
        self.statut = statut
        self.revision_possible = revision_possible

    def corps(self):
        return {'detail': self.detail, 'statut': self.statut,
                'revision_possible': self.revision_possible}


def _libelle_statut(devis):
    try:
        return devis.get_statut_display()
    except Exception:  # noqa: BLE001 — objet léger sans choices
        return str(getattr(devis, 'statut', '') or '')


def _reference_successeur(devis):
    if not getattr(devis, 'superseded_by_id', None):
        return None
    try:
        return devis.superseded_by.reference
    except Exception:  # noqa: BLE001 — successeur supprimé entre-temps
        return None


def revision_possible(devis):
    """D-QJR5-2 — actif ET pas brouillon (envoyé, accepté, refusé, expiré)."""
    return bool(getattr(devis, 'is_active', True)
                and getattr(devis, 'statut', None) != _BROUILLON)


def verdict(devis, geste=ENTETE):
    """Le verdict d'UN geste sur ce devis, sous la forme du contrat
    ``contract_samples/devis_modifiabilite.json`` :
    ``{modifiable, raison_non_modifiable, revision_possible}`` — la raison est
    toujours une chaîne (``''`` quand modifiable)."""
    if geste not in GESTES:
        raise ValueError(f'Geste de modification inconnu : {geste!r}.')
    statut = getattr(devis, 'statut', None)
    actif = bool(getattr(devis, 'is_active', True))
    revisable = revision_possible(devis)
    if not actif:
        ref = _reference_successeur(devis)
        raison = (f'Remplacé par {ref}' if ref
                  else 'Devis archivé : il ne se modifie plus')
        return {'modifiable': False, 'raison_non_modifiable': raison,
                'revision_possible': False}
    if statut in GESTES[geste]:
        return {'modifiable': True, 'raison_non_modifiable': '',
                'revision_possible': revisable}
    if statut == 'accepte':
        raison = 'Devis accepté : révisez-le'
    elif statut in STATUTS_CLOS:
        raison = 'Révisez-le (nouvelle version)'
    else:
        # Statut ouvert mais geste plus étroit (aucun depuis QJR557 ; garde
        # défensive si la table se resserre un jour).
        raison = (f'Devis « {_libelle_statut(devis)} » : révisez-le pour '
                  'faire ce changement')
    return {'modifiable': False, 'raison_non_modifiable': raison,
            'revision_possible': revisable}


def est_modifiable(devis, geste=ENTETE):
    return verdict(devis, geste)['modifiable']


def exiger_modifiable(devis, geste):
    """Lève :class:`DevisNonModifiable` si ``geste`` n'est pas permis."""
    v = verdict(devis, geste)
    if not v['modifiable']:
        raise DevisNonModifiable(
            v['raison_non_modifiable'],
            statut=str(getattr(devis, 'statut', '') or ''),
            revision_possible=v['revision_possible'])
    return v


# ── QJR518 — UNE CORRECTION APRÈS ENVOI EST TRACÉE À UN SEUL POINT ─────────
#
# D-QJR5-1 : un devis ENVOYÉ se corrige SUR PLACE — même référence, même lien
# public, statut « envoyé » intouché. Mais l'état que le client a vu ne doit
# pas disparaître (replace-lines recrée les lignes, nouveaux ids), et la
# correction doit se voir : chatter du devis ET du lead, « Document mis à jour
# le … » sur la page publique (``etude_params.resync_apres_envoi``).
#
# LE PATRON, À CHAQUE SITE D'ÉCRITURE (pipeline MODE_ECRIRE / RECONCILIER,
# perform_update, etude-params, overrides, LigneDevisViewSet,
# catalogue_events) :
#
#     avant = debut_de_geste_devis(devis, user)   # AVANT la 1re écriture
#     ... écritures ...
#     fin_de_geste_devis(devis, user, avant=avant, objet='…')
#
# ``debut`` ne fait rien hors ENVOYÉ (rend ``None``) ; sur un envoyé il prend
# l'instantané (dédoublonné : un contenu identique au dernier n'en crée pas un
# second) et rend l'empreinte VISIBLE. ``fin`` compare : SEULEMENT si un
# contenu visible a changé, ``consigner_correction_apres_envoi`` écrit la
# trace. Aucun événement core ici (``devis_corrige_apres_envoi`` relève de
# QJR660). Le statut n'est JAMAIS écrit (règle #4).

#: Les champs d'une ligne que le client voit (jamais ``prix_achat``, jamais
#: l'id — replace-lines recrée les lignes, un id neuf n'est pas un changement).
_CHAMPS_LIGNE_VISIBLES = (
    'type_ligne', 'produit_id', 'designation', 'quantite', 'prix_unitaire',
    'remise', 'taux_tva', 'optionnelle', 'variante', 'groupe_index',
    'groupe_label',
)
#: L'en-tête CLIENT (ce que le PDF / la proposition impriment).
_CHAMPS_ENTETE_VISIBLES = (
    'client_id', 'date_validite', 'taux_tva', 'remise_globale', 'echeancier',
    'acompte_pct', 'acompte_montant',
)
_LIBELLES = {
    'lignes': 'lignes',
    'entete': 'en-tête',
    'note': 'note',
    'option': 'option recommandée',
}
#: QJR557 — les gestes NOMMÉS dans le chatter (« corrigé après envoi :
#: calepinage (lignes) »). Les autres objets gardent le résumé seul.
_OBJETS_NOMMES = {
    'calepinage': 'calepinage',
    'taille': "taille d'offre",
}


def empreinte_visible(devis):
    """Ce que le CLIENT voit de ce devis, relu en BASE (jamais l'instance en
    mémoire, qui peut être périmée ou déjà mutée) : ``{lignes, entete, note,
    option}``."""
    from apps.ventes.models import Devis, LigneDevis

    lignes = [
        tuple(str(v) if v is not None else None for v in ligne)
        for ligne in LigneDevis.objects.filter(devis_id=devis.pk)
        .order_by('ordre', 'id').values_list(*_CHAMPS_LIGNE_VISIBLES)
    ]
    ligne_devis = (Devis.objects.filter(pk=devis.pk)
                   .values(*_CHAMPS_ENTETE_VISIBLES, 'note', 'etude_params')
                   .first()) or {}
    etude = ligne_devis.get('etude_params') or {}
    if not isinstance(etude, dict):
        etude = {}
    return {
        'lignes': lignes,
        'entete': tuple(str(ligne_devis.get(c)) for c in
                        _CHAMPS_ENTETE_VISIBLES),
        'note': (ligne_devis.get('note') or '').strip(),
        'option': str(etude.get('recommended_option') or ''),
    }


def _est_envoye(devis):
    from apps.ventes.models import Devis
    statut = (Devis.objects.filter(pk=getattr(devis, 'pk', None))
              .values_list('statut', flat=True).first())
    return statut == Devis.Statut.ENVOYE


def debut_de_geste_devis(devis, user=None):
    """AVANT la première écriture d'un geste. Hors ENVOYÉ → ``None`` (rien à
    tracer). Sur un envoyé : instantané de l'état vu par le client
    (dédoublonné) + l'empreinte visible, à rendre à :func:`fin_de_geste_devis`.
    Ne lève jamais : la trace ne bloque pas une écriture."""
    if devis is None or getattr(devis, 'pk', None) is None:
        return None
    try:
        if not _est_envoye(devis):
            return None
        from apps.ventes.models import Devis
        from apps.ventes.domain.historique_config import capturer_configuration_devis
        frais = Devis.objects.get(pk=devis.pk)
        capturer_configuration_devis(frais, user=user, avant_correction=True)
        return empreinte_visible(frais)
    except Exception:  # noqa: BLE001 — jamais bloquant
        import logging
        logging.getLogger(__name__).exception(
            'QJR518 : début de geste ignoré (devis %s)', devis.pk)
        return None


def fin_de_geste_devis(devis, user=None, *, avant=None, objet=''):
    """APRÈS les écritures d'un geste. Si ``avant`` (l'empreinte de
    :func:`debut_de_geste_devis`) diffère de l'empreinte courante, consigne
    la correction ; sinon rien (un enregistrement sans changement réel
    n'écrit ni chatter ni marqueur). Rend l'activité créée ou ``None``."""
    if avant is None or devis is None:
        return None
    try:
        if not _est_envoye(devis):
            return None
        apres = empreinte_visible(devis)
        changes = [cle for cle in ('lignes', 'entete', 'note', 'option')
                   if avant.get(cle) != apres.get(cle)]
        if not changes:
            return None
        resume = ', '.join(_LIBELLES[c] for c in changes)
        if objet in _OBJETS_NOMMES:
            resume = '%s (%s)' % (_OBJETS_NOMMES[objet], resume)
        return consigner_correction_apres_envoi(
            devis, user=user, objet=objet, resume=resume)
    except Exception:  # noqa: BLE001 — jamais bloquant
        import logging
        logging.getLogger(__name__).exception(
            'QJR518 : fin de geste ignorée (devis %s)', devis.pk)
        return None


def consigner_correction_apres_envoi(devis, *, user=None, objet='',
                                     resume=''):
    """La TRACE d'une correction après envoi, en un seul point :

    * une ``DevisActivity`` « Corrigé après envoi — <resume> » ;
    * ``etude_params.resync_apres_envoi = {'date': <iso>}`` sous son
      propriétaire (CALEPINAGE, ``etude_schema``), écrit sur une RELECTURE du
      devis (l'instance de l'appelant peut porter des études périmées) ;
    * un reflet best-effort sur le chatter du lead
      (``crm.services.noter_devis_corrige``).

    Référence, jeton et statut inchangés (règle #4). No-op hors ENVOYÉ."""
    from django.utils import timezone

    from apps.ventes import activity
    from apps.ventes.models import Devis
    from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire

    frais = Devis.objects.select_related('lead').filter(pk=devis.pk).first()
    if frais is None or frais.statut != Devis.Statut.ENVOYE:
        return None
    libelle = resume or objet or 'contenu'
    entree = activity.log_devis_correction_apres_envoi(frais, user, libelle)
    ecrire(frais, proprietaire=CALEPINAGE,
           resync_apres_envoi={'date': timezone.now().isoformat()})
    # L'instance de l'appelant suit (sa réponse sérialise le marqueur) : on ne
    # recopie QUE la clé du marqueur, jamais le bloc (QJR105).
    if isinstance(devis.etude_params, dict):
        devis.etude_params['resync_apres_envoi'] = (
            frais.etude_params or {}).get('resync_apres_envoi')
    # QJR668 — les clauses/CGV gelées à l'envoi sont RE-gelées sur le contenu
    # corrigé (le PDF les imprime telles quelles) ; l'instance suit.
    from apps.ventes.domain.cycle_vie import figer_clauses_devis
    figer_clauses_devis(frais)
    devis.clauses_appliquees = frais.clauses_appliquees
    if frais.lead_id:
        try:
            from apps.crm.services import noter_devis_corrige
            noter_devis_corrige(frais.reference, frais.lead, libelle)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            pass
    return entree
