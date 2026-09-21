"""XPLT21 — Sélecteurs LECTURE SEULE du softphone VoIP."""


def cible_info(appel):
    """Dict léger `{'type': <model>, 'id': <pk>}` de la fiche résolue pour cet
    appel, ou None si aucune cible n'a matché — sert au « call-pop » (le
    frontend ouvre la fiche à partir de ce couple type/id)."""
    if not appel.content_type_id or not appel.object_id:
        return None
    return {'type': appel.content_type.model, 'id': appel.object_id}
