# CLAUDE.md — Contexte permanent du projet

> Mémoire persistante du projet. À lire en premier à chaque nouvelle session.
> À mettre à jour après chaque session importante : nouvelle décision, test effectué,
> échec rencontré, changement d'orientation. Ne pas laisser ce fichier devenir obsolète.

## 1. Vision du produit

Service d'alertes immobilières en temps réel pour la **location**.
Démarrage sur **Nancy**, mais architecture pensée multi-villes dès le départ :
ajouter une ville doit être une opération de configuration, jamais de code.

Fonctionnement cible :
- Scraping continu des annonces de location (Leboncoin, sites d'agences locales)
- Détection des nouvelles annonces le plus rapidement possible
- Notification des abonnés via bot Telegram
- Modèle freemium :
  - **Gratuit** : alerte avec délai (~30 min)
  - **Payant** (~5-10€/mois) : alerte quasi instantanée

## 2. État actuel

**Phase : conception de l'architecture — en attente de validation utilisateur.**
Aucun code applicatif écrit. Dépôt vide à part ce fichier.

Proposition d'architecture complète soumise le 2026-06-21 (stack, structure de repo,
schéma BDD, plan de déploiement Railway). En cours de discussion.

## 3. Décisions prises (et pourquoi)

| Décision | Choix | Raison |
|---|---|---|
| _(aucune décision finalisée encore — section à remplir après validation)_ | | |

## 4. Décisions proposées, en attente de validation explicite

- **Stack** : Python (httpx/parsel pour le scraping, python-telegram-bot, SQLAlchemy + Alembic, Postgres) — alternative envisageable : Node/TypeScript.
- **Topologie de déploiement** : un seul service Railway au démarrage (bot + boucle de scraping dans le même process, tâches asyncio séparées) plutôt que plusieurs services, pour limiter le coût. Scission possible plus tard si la charge l'exige.
- **Pas de file de message (Redis/queue) au démarrage** : la déduplication et la planification des notifications se font via des contraintes SQL en base Postgres. Réévaluer si le volume augmente fortement.
- **Stratégie face à Leboncoin** : prioriser RSS/API officielles des agences ; traiter Leboncoin comme source "best effort", remplaçable, scrapée avec rate-limiting raisonnable et identification honnête — pas de contournement actif des protections anti-bot (pas de proxies rotatifs pour évader un WAF).
- **Latence réaliste** : "quelques secondes" n'est tenable que pour les sources RSS/API. Pour le scraping HTML, cible réaliste = 30-90 secondes en respectant un rate-limiting raisonnable. À calibrer dans le discours produit pour ne pas survendre.

## 5. Contraintes business

- **Budget de démarrage : 100 €** (hébergement, domaine éventuel, pub éventuelle).
- **Toute dépense ou création de compte externe (Railway, Stripe, domaine, etc.) doit être validée par l'utilisateur avant exécution.** Aucune création de compte ou achat ne doit être fait de manière autonome.
- Hébergement cible : **Railway**.
- Le coût de fonctionnement mensuel doit rester bas ; priorité à la simplicité de maintenance sur la sophistication technique.

## 6. Risques identifiés

- **Leboncoin** : les CGU interdisent généralement l'extraction automatisée de données, et le site dispose probablement de protections anti-bot (type WAF/Datadome). Risque légal/ToS et risque technique (blocage IP). → Architecture conçue pour traiter chaque source comme interchangeable ; Leboncoin n'est pas une dépendance structurelle.
- **Sites d'agences locales** : structure HTML non standardisée et instable dans le temps → scrapers fragiles par nature, prévoir une détection des échecs (alerting interne) plutôt qu'un échec silencieux.
- **Survente produit** : le délai d'alerte "instantané" doit être cohérent avec ce que permet un scraping respectueux des limites de débit, sous peine de promesse non tenue envers les abonnés payants.

## 7. Ce qui a été testé / a échoué

_(vide — aucun test technique effectué à ce stade)_

## 8. Conventions de code

_(à définir une fois la stack validée par l'utilisateur)_

## 9. Métriques de suivi à instrumenter

- Nombre de villes actives
- Nombre d'annonces détectées par jour, par ville, par source
- Délai moyen détection → notification, par tier (gratuit/payant)
- Nombre d'abonnés (gratuit / payant) et taux de conversion
- Taux d'échec de scraping par source (santé des scrapers)
- Coût d'hébergement mensuel réel vs budget

## 10. Historique des sessions

### 2026-06-21 — Session 1
- Cadrage initial du projet par l'utilisateur : concept, contraintes techniques,
  budget (100€), exigence de validation préalable pour toute dépense/compte externe.
- Création de ce fichier CLAUDE.md.
- Proposition d'architecture complète soumise pour validation (stack, structure
  de repo, schéma BDD, plan de déploiement) — voir conversation pour le détail,
  à résumer ici une fois validée.
