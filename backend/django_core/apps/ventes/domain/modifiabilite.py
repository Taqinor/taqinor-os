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
* ``CALEPINAGE`` / ``TAILLE`` — brouillon SEUL jusqu'à QJR557 (la
  resynchronisation des lignes depuis un calepinage, l'application d'une
  taille d'offre).

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
    CALEPINAGE: frozenset({_BROUILLON}),
    TAILLE: frozenset({_BROUILLON}),
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
        # Statut ouvert mais geste plus étroit (CALEPINAGE/TAILLE sur un
        # envoyé) : le client a déjà cette version sous les yeux.
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
