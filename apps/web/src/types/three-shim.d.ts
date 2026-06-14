// Three.js ne publie pas ses propres types et @types/three n'est PAS installé
// (contrainte : Three.js est la SEULE nouvelle dépendance). Ce shim ambiant évite
// les erreurs TS sans ajouter de paquet : le module est traité comme `any`.
// Le bundler (esbuild/Vite) résout le vrai code de `three` normalement.
declare module 'three';
