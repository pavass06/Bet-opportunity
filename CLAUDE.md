# Edge Scanner — CLAUDE.md

> Ce fichier est la source de vérité du projet. Il doit être lu en entier à chaque commande.
> Il est mis à jour dès qu'une fonctionnalité est ajoutée, modifiée ou corrigée.

---

## IDENTITÉ DU PROJET

**Nom** : Edge Scanner
**Objectif** : Logiciel de détection d'opportunités de valeur sur les marchés sportifs — arbitrage, middles, et paris à espérance positive (+EV) — via comparaison de cotes multi-bookmakers en temps quasi-réel.
**Auteur** : Julien Pavassier (M2 Ingénierie Financière, École Centrale Marseille)
**Origine** : Fork d'un repo GitHub de sports arbitrage scanner, personnalisé et étendu.

---

## STACK TECHNIQUE ACTUELLE

| Couche | Technologie |
|---|---|
| Backend | Python 3.11+, Flask |
| Frontend | HTML/CSS/JS vanilla (Jinja2 pour le rendu serveur) |
| Source de données | The Odds API v4 (`https://api.the-odds-api.com/v4`) |
| Config | `.env` via `python-dotenv` (`ODDS_API_KEY`) |
| Dépendances | `flask`, `requests`, `python-dotenv`, `apscheduler` (voir `requirements.txt`) |
| Déploiement | Local uniquement — `python app.py` ouvre le navigateur automatiquement |
| Persistance | SQLite (`data/edge_scanner.db`) via `db.py` — opportunités +EV sauvegardées à chaque scan |
| Scheduler | APScheduler (background, daemon) — closing odds Pinnacle fetchés toutes les 30 min |

---

## ARCHITECTURE DES FICHIERS

```
edge-scanner/
├── app.py          # Serveur Flask : routes /, /scan, /history, /export, /clv-summary
├── scanner.py      # Logique métier : fetch API, calculs EV/arb/middles/+EV/Kelly
├── config.py       # Constantes : bookmakers, sports, marchés, Kelly options, EDGE_BANDS
├── db.py           # Persistance SQLite : init, save_plus_ev, get_history, CLV summary, export CSV
├── scheduler.py    # APScheduler : job closing odds Pinnacle toutes les 30 min
├── templates/
│   └── index.html  # SPA : 5 onglets (Arbitrage / Middles / +EV / Builder / History), JS inline
├── static/
│   └── style.css   # CSS : dark/light theme, tables, cards, badges
├── data/
│   └── edge_scanner.db  # SQLite (créé automatiquement au premier lancement)
├── .env            # ODDS_API_KEY (non versionné)
└── requirements.txt
```

---

## FONCTIONNEMENT GÉNÉRAL

1. L'utilisateur lance `python app.py` → Flask démarre sur le port 5000 (fallback 5050/8000) et ouvre le navigateur.
2. L'UI affiche un formulaire de configuration (clé API, sports, régions, stake, commission exchange, paramètres +EV/Kelly).
3. Au clic "Scan Now" → POST `/scan` avec la config en JSON.
4. `app.py` délègue à `scanner.run_scan()` qui :
   a. Récupère la liste des sports actifs via `/sports/`
   b. Pour chaque sport sélectionné, fetch les cotes via `/sports/{key}/odds/`
   c. Calcule en mémoire : arbitrages, middles, opportunités +EV
   d. Retourne un JSON structuré avec les 3 blocs de résultats
5. L'UI affiche les résultats dans 3 onglets sans rechargement de page.

---

## CE QUE LE PRODUIT FAIT AUJOURD'HUI

### Arbitrage (✅ Implémenté)
- Détecte les cas où la somme des probabilités implicites inter-bookmakers descend sous 100%.
- Calcule les mises proportionnelles pour garantir un profit quel que soit le résultat.
- Gère les exchanges (Betfair, Matchbook, Sportsbet Exchange) avec commission configurable.
- Affiche ROI net (après commission) et ROI brut séparément pour les exchanges.
- Marchés couverts : `h2h`, `spreads`, `totals`.

### Middles (✅ Implémenté)
- Détecte les opportunités où deux books proposent des lignes non-alignées sur le même marché (spreads/totals), créant une zone "middle" où les deux paris gagnent.
- Estime la probabilité de toucher le middle via des distributions historiques par sport (`PROBABILITY_PER_INTEGER` dans `config.py`).
- Traitement spécial des **NFL key numbers** (3, 7, 10, 6, 14…) avec probabilités empiriques plus précises.
- Calcule l'EV en dollars et en % du stake.
- Filtre configurable : gap minimum, positive EV only, tri (EV / probabilité / gap / heure).

### +EV — Value Betting (✅ Implémenté)
- Utilise Pinnacle (par défaut), Betfair Exchange, ou Matchbook comme livre "sharp" (référence de probabilité réelle).
- Supprime le vig du sharp book via méthode proportionnelle (`_remove_vig_n`).
- Compare les cotes des soft books (DraftKings, FanDuel, Winamax, Unibet, etc.) à la cote fair calculée.
- Calcule `edge% = (soft_odds / fair_odds − 1) × 100`.
- Calcule `EV_per_100 = true_prob × (odds−1) × 100 − (1−true_prob) × 100`.
- Filtre configurable : edge minimum, sharp book sélectionnable.

### Kelly Sizing (✅ Implémenté)
- Formule : `f* = (p×b − q) / b` avec `b = odds − 1`.
- 4 modes : Full Kelly / Half (0.5x) / Quarter (0.25x) / Tenth (0.1x).
- Bankroll configurable dans l'UI.
- Mise recommandée en dollars affichée dans le tableau +EV.

### Dashboard (✅ Implémenté)
- 5 onglets : Arbitrage / Middles / +EV / **Builder** / **History**.
- Stat cards (nombre d'opportunités, events scannés, sports, API calls).
- Bar charts par sport et par bande de ROI/edge.
- Toggle cotes décimales / américaines (persisté dans `localStorage`).
- Dark mode / Light mode (persisté dans `localStorage`).
- Badge exchange + note de commission sur les opportunités impliquant Betfair/Matchbook.
- Avertissement partiel si un sport échoue lors du fetch.

### Parlay / Combiné Builder (✅ Implémenté)
- S'appuie sur les +EV du dernier scan, côté client, sans nouvelle requête API.
- Construit les combinés à partir d'un seul bookmaker par ticket, avec une contrainte dure de cote produit min/max.
- Exclut toute paire de jambes provenant du même match pour limiter la corrélation.
- Trie les combinés par edge compound, puis par probabilité de hit.
- Affiche la cote fair du combiné, l'EV composé, la probabilité de hit, la mise Kelly recommandée et une comparaison face aux mêmes jambes jouées en simples.
- Paramètres visibles dans l'UI : cote combinée min/max et nombre maximal de jambes.

### Persistance + CLV Tracking (✅ Implémenté)
- Chaque opportunité +EV détectée est sauvegardée en SQLite (`data/edge_scanner.db`) via `db.py`.
- Déduplication : une seule entrée par combinaison `(event, market, outcome, soft_book)` par jour calendaire.
- APScheduler tourne en background (daemon, toutes les 30 min) et re-fetch la cote Pinnacle pour les événements qui démarrent dans la prochaine heure.
- CLV calculé automatiquement : `CLV% = (soft_odds / closing_odds − 1) × 100`.
- Onglet **History** dans l'UI : tableau de tous les bets trackés avec CLV en couleur (vert/rouge), stats agrégées (total, avg CLV, % CLV positif).
- Endpoint `/export` : téléchargement CSV de tout l'historique.
- Endpoint `/history` : JSON `{ rows, summary }` consommé par l'onglet History.
- Endpoint `/clv-summary` : stats agrégées JSON.
- **Contrainte** : le scheduler nécessite `ODDS_API_KEY` dans `.env` — si la clé est entrée uniquement dans l'UI, le closing odds job ne se déclenchera pas.

### Résultats manuels + Brier + ROI réalisé (✅ Implémenté)
- Colonnes `result` (1=win, 0=loss, NULL=en attente) et `result_set_at` ajoutées à `plus_ev_opportunity` (migration auto via `ALTER TABLE` dans `init_db`).
- Saisie manuelle dans l'onglet **History** : boutons **W/L** par ligne ; re-cliquer remet le pari en attente.
- Endpoint `POST /result` (`{id, result}`) → `db.set_result()` ; `result` ∈ {0, 1, null}.
- **ROI réalisé** en mise plate (1 unité/pari) : `profit = soft_odds−1` si win, `−1` si loss ; `ROI% = profit_total / nb_résolus × 100`.
- **Win rate réel vs attendu** : taux de réussite observé comparé à `AVG(1/fair_odds)` sur les paris résolus.
- **Brier score** : `AVG((1/fair_odds − result)²)` ; vert si < 0.25, sinon rouge.
- 4 nouvelles stat cards dans History : Résolus, Win rate (réel/attendu), ROI réalisé, Brier.
- `GET /history` renvoie désormais `summary = {…CLV…, …performance…}` via `get_performance_summary()`.
- **Hypothèse assumée** : pas d'état push/void — un nul (soccer h2h) sur la sélection prise compte comme Loss.

### Configuration disponible dans l'UI
- Clé API (ou lecture depuis `.env`)
- Sports sélectionnables individuellement (ou "scan all active sports")
- Régions : US, US2, UK, EU, AU
- Stake total pour le calcul des mises arb/middles
- Commission exchange (%)
- Sharp book de référence (+EV)
- Edge minimum (%)
- Bankroll + fraction Kelly
- Gap minimum (middles)
- Filtre positive EV only (middles)
- Tri des résultats (par onglet)

---

## CE QUE LE PRODUIT NE FAIT PAS (ROADMAP)

### ~~PRIORITÉ 1 — Persistance + Export CSV~~ ✅ TERMINÉ
- [x] SQLite (`data/edge_scanner.db`) via `db.py` — sauvegarde automatique à chaque scan
- [x] Onglet History dans l'UI avec stats CLV agrégées
- [x] Export CSV via `/export` + bouton dans l'UI
- [x] APScheduler closing odds (30 min interval)
- [x] CLV calculé automatiquement : `CLV% = (soft_odds / closing_odds − 1) × 100`

### PRIORITÉ 2 — Brier Score + Résultats manuels (prochaine phase)
- [ ] Ajouter colonne `result` (0/1) saisie manuellement dans l'UI pour chaque bet
- [ ] Calculer le Brier score : `AVG((predicted_prob - result)²)` sur les bets avec résultat
- [ ] Afficher le Brier score dans le dashboard History

_Note : remplacé par la section ci-dessus « Résultats manuels + Brier + ROI réalisé » (✅ TERMINÉ)._

### PRIORITÉ 3 — Alertes Telegram
- [ ] Bot Telegram via `python-telegram-bot` ou appel direct `requests`
- [ ] Polling automatique toutes les 5 min via APScheduler
- [ ] Seuil configurable (edge minimum pour déclencher l'alerte)
- [ ] Format : `[+EV] Arsenal @ 2.15 (Winamax) | Edge: 4.2% | Fair: 2.07 | Kelly: €47`

### PRIORITÉ 4 — Auto-refresh UI
- [ ] Toggle "Auto-refresh toutes les N minutes" côté JS (sans backend scheduler)
- [ ] `setInterval(() => form.submit(), N * 60 * 1000)`

### PRIORITÉ 5 — Parlay / Combiné Builder
- [x] Calcul du `log_edge = ln(true_prob × soft_odds)` pour chaque +EV single
- [x] Nouvel onglet "Builder" avec input fourchette de cote cible [min, max]
- [x] Algorithme combinatoire (N ≤ 6 jambes) qui maximise la somme des log-edges sous contrainte de cote produit
- [x] Avertissement de corrélation si deux jambes proviennent du même match

### PRIORITÉ 6 — Soft Arb < 103%
- [ ] Détecter les "near-arbs" où `sum(implied) < 1.03` sans être < 1.00
- [ ] Affichage séparé dans l'onglet Arbitrage avec badge "Near-Arb"

### PRIORITÉ 7 — Méthode Shin (démarginalization avancée)
- [ ] Remplacer la méthode proportionnelle par la méthode Shin dans `_remove_vig_n`
- [ ] Plus précis sur les marchés avec forte marge ou markets asymétriques

### PRIORITÉ 8 — Polymarket / Kalshi (long terme)
- [ ] Intégration Polymarket CLOB API (lecture sans auth)
- [ ] Intégration Kalshi API (auth requise, tier gratuit disponible)
- [ ] Mapping événements bookmaker ↔ marchés de prédiction
- [ ] Nouveau sharp book sélectionnable : "Polymarket consensus"

---

## PARAMÈTRES CLÉS (config.py)

| Paramètre | Valeur par défaut | Description |
|---|---|---|
| `DEFAULT_SHARP_BOOK` | `"pinnacle"` | Référence +EV |
| `DEFAULT_KELLY_FRACTION` | `0.25` | Quarter Kelly |
| `DEFAULT_BANKROLL` | `1000.0` | Bankroll en $ |
| `MIN_EDGE_PERCENT` | `1.0` | Seuil minimum +EV |
| `DEFAULT_COMMISSION` | `0.05` | 5% commission exchange |
| `MIN_MIDDLE_GAP` | `1.5` | Gap minimum en points |
| `SHOW_POSITIVE_EV_ONLY` | `True` | Filtre middles EV > 0 |
| `DEFAULT_REGION_KEYS` | `["us", "eu"]` | Régions par défaut |
| `DEFAULT_SPORT_KEYS` | NFL, NBA, MLB, NHL, EPL, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Coupe du Monde | Sports par défaut |

---

## SPORTS ET MARCHÉS SUPPORTÉS

| Sport | Clé API | Marchés |
|---|---|---|
| NFL | `americanfootball_nfl` | h2h, spreads, totals |
| NBA | `basketball_nba` | h2h, spreads, totals |
| MLB | `baseball_mlb` | h2h, spreads, totals |
| NHL | `icehockey_nhl` | h2h, spreads, totals |
| Premier League | `soccer_epl` | h2h, spreads, totals |
| La Liga | `soccer_spain_la_liga` | h2h, spreads, totals |
| Bundesliga | `soccer_germany_bundesliga` | h2h, spreads, totals |
| Serie A | `soccer_italy_serie_a` | h2h, spreads, totals |
| Ligue 1 | `soccer_france_ligue_one` | h2h, spreads, totals |
| MLS | `soccer_usa_mls` | h2h, spreads, totals |
| FIFA Coupe du Monde 2026 | `soccer_fifa_world_cup` | h2h, spreads, totals |

---

## SHARP BOOKS DISPONIBLES

| Clé | Nom | Région | Type |
|---|---|---|---|
| `pinnacle` | Pinnacle | EU | Bookmaker sharp |
| `betfair_ex_eu` | Betfair Exchange | EU | Exchange |
| `matchbook` | Matchbook | EU | Exchange |

---

## CONTRAINTES ET POINTS DE VIGILANCE

- **Rate limits The Odds API** : 500 requêtes/mois en tier gratuit. Chaque scan complet (11 sports) consomme 12 requêtes (1 pour `/sports/` + 11 pour les odds). Environ 40 scans complets par mois en gratuit.
- **La région EU est toujours incluse** automatiquement (`_ensure_sharp_region`) pour garantir la présence de Pinnacle comme référence sharp.
- **Les exchanges** (Betfair, Matchbook) voient leur prix ajusté avec `_apply_commission()` avant tout calcul de ROI/edge.
- **Déduplication** : `_deduplicate_plus_ev()` et `_deduplicate_middles()` évitent les doublons entre sports/marchés.
- **Marchés 3-way** (soccer h2h avec nul) : `_all_market_outcomes()` les supporte, mais l'arb pur sur 3-way est exclu (`len(offers) != 2` dans `_collect_market_entries`).
- **Spreads** : la logique vérifie que les deux côtés sont bien des équipes opposées (signes de ligne opposés) avant de considérer un arb.

---

## COMMANDES DE LANCEMENT

```bash
# Installation
pip install -r requirements.txt

# Configuration
echo "ODDS_API_KEY=votre_clé_ici" > .env

# Lancement (ouvre le navigateur automatiquement)
python app.py

# Port personnalisé
python app.py --port 8080
```

---

## ÉTAT DE VALIDATION (à mettre à jour au fil du temps)

| Critère | Seuil cible | Statut actuel |
|---|---|---|
| CLV moyen sur 100+ paris | > 0% | En cours de mesure (persistance opérationnelle) |
| ROI simulé sur 50+ arbs | > 0.5% après commission | Non mesuré |
| Précision middles (Brier score) | < 0.25 | Non mesuré |
| Taux de faux positifs arb | < 10% | Non mesuré |

---

*Dernière mise à jour : 2026-06-30 — Résultats manuels (Win/Loss) + Brier score + ROI réalisé + Win rate vs attendu (Phase 2) + Parlay Builder (Phase 5).* 
