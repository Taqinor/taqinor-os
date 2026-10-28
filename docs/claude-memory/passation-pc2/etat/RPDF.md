ETAT: CONSTRUIT (correctifs hôte + critique Fable traités ; contrôles hôte verts)
BRANCHE: pc2-rpdf @ (voir git log) — base claude/res-rpdf-r1 ffec91237 + merge origin/main c53599b8f  PR: #1114 (auto-merge OFF, éjectée)
FAIT: NTI18N5 normalisé (RPDF30 gardé) ; garde devis envoyés : RPDF8/RPDF15/RPDF9/RPDF16 au niveau 3 (drapeau _regles_2710) ; rpdf_* masqués dans le golden d'origine ; Fable 1 appel (B1 : garantie par option cassait la synthèse C&I et n'était pas gardée → corrigé) ; flake8, check_stages, codemap --check, ownership, forme_code, test_placement, money_rounding, api_shapes verts.
RESTE: JETON DOCKER : recapture goldens moteur + split public (SPLIT_GOLDEN_CAPTURE) + modules ; DONE LOG ; push ; JETON CI.
ATTEND: JETON DOCKER
DECISIONS: voir decisions-prises.txt (2 lignes RPDF du 28/10).
