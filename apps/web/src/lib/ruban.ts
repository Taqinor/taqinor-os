/**
 * WAUD46-b (D-WAUD-7=a, 03/11/2026) — pages (chemin FR, barre finale) où le ruban Article 33 s'affiche,
 * dans les trois langues : accueil, /loi-82-21, /regularization-article-33, /résidentiel. Ailleurs, le
 * composant ne rend rien (il reste importé par les pages, sans effet).
 */
export const PAGES_DU_RUBAN: readonly string[] = ['/', '/loi-82-21/', '/regularization-article-33/', '/résidentiel/'];
