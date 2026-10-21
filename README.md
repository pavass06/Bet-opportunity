# Bet-opportunity (Edge Scanner)

**Arbitrage • Middles • +EV • Kelly • CLV**

Scanner de paris sportifs qui compare les cotes de plusieurs bookmakers (via [The Odds API](https://the-odds-api.com/)) pour détecter des arbitrages, des middles et des paris à espérance positive (+EV), puis suit la qualité de ces signaux dans le temps (CLV, Brier, ROI réalisé).

> Fork d'un scanner d'arbitrage open source, étendu : +EV avec démarge du book sharp, Kelly, combinés, persistance SQLite, suivi du CLV et des résultats.

## Fonctionnalités

| Onglet | Ce qu'il trouve | Profil de risque |
|---|---|---|
| **Arbitrage** | Profit garanti en pariant sur toutes les issues chez différents books | Quasi nul (risque d'exécution) |
| **Middles** | Lignes non alignées entre deux books : les deux paris peuvent gagner | Variance élevée, +EV si la probabilité est juste |
| **+EV** | Cotes d'un book « soft » supérieures à la cote fair du book « sharp » | Variance moyenne, profit sur le volume |
| **Builder** | Combinés construits à partir des +EV du dernier scan | Variance élevée |
| **History** | Paris suivis en base : CLV, résultats W/L, ROI réalisé, Brier | Outil de validation |

## Installation

```bash
git clone https://github.com/pavass06/Bet-opportunity.git
cd Bet-opportunity
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Le navigateur s'ouvre automatiquement (port 5000, sinon 5050 ou 8000 ; sur Mac le 5000 est souvent pris par AirPlay, l'app bascule alors sur 5050).

**Clé API** : gratuite sur [the-odds-api.com](https://the-odds-api.com/) (500 requêtes/mois). Saisis-la dans l'interface, ou crée un fichier `.env` à la racine :

```
ODDS_API_KEY=ta_clé_ici
```

Le `.env` est nécessaire pour le calcul automatique du CLV (le scheduler tourne en tâche de fond et lit la clé au démarrage).

---

## La théorie en bref

### Probabilité implicite et marge (vig)

Une cote décimale `c` correspond à une probabilité implicite `1/c`. Sur un match à deux issues, un book affiche par exemple 1.91 / 1.91 : 52,4 % + 52,4 % = **104,8 %**. Les 4,8 % en trop sont sa marge, ce qui le fait gagner à long terme.

### EV : l'espérance de gain

L'espérance est la somme de chaque résultat pondéré par sa probabilité. Pour 1 € misé :

| Événement | Probabilité | Gain net |
|---|---|---|
| Le pari gagne | `p` | `+(cote − 1)` |
| Le pari perd | `1 − p` | `−1` |

```
EV = p × (cote − 1) − (1 − p)  =  p × cote − 1
```

Le pari est +EV quand **`p × cote > 1`**, c'est-à-dire quand la cote est supérieure à la cote fair `1/p`. Exemple : cote 2.20 et vraie probabilité 50 % → EV = +0,10 € par euro misé. Pour une mise `B`, tout est multiplié par `B`.

Un pari +EV peut perdre : l'EV est une moyenne sur un grand nombre de paris. Tout le problème est de connaître `p`.

### Comment `p` est estimé : le book sharp

Personne ne connaît la vraie probabilité. On prend un book très précis comme référence (Pinnacle par défaut, ou Betfair Exchange / Matchbook) :

1. On retire sa marge (méthode proportionnelle : on divise chaque probabilité implicite par leur somme).
2. On obtient la **cote fair**.
3. On compare avec les books soft (DraftKings, FanDuel, Winamax, Unibet…).

```
edge % = (cote_soft / cote_fair − 1) × 100
```

C'est du *value betting*. L'hypothèse est que le sharp a raison et que le soft se trompe.

### Critère de Kelly

L'EV dit **s'il faut parier**, Kelly dit **combien miser**. Il maximise la croissance composée de la bankroll :

```
f* = (p × b − q) / b      avec b = cote − 1 et q = 1 − p
```

C'est l'EV par euro (`p×b − q`) divisée par `b` : à edge égal, une cote élevée est plus risquée, donc on mise moins.

Pourquoi pas simplement maximiser l'EV ? Parce qu'elle conseillerait de miser toute la bankroll, ce qui mène à la ruine : la bankroll évolue par **multiplication**, pas par addition. Kelly maximise le taux de croissance géométrique :

```
g(f) = (1 + f·b)^p × (1 − f)^q          (équivalent à maximiser p·ln(1+f·b) + q·ln(1−f))
```

Cette fonction est en cloche : sous-miser coûte peu de croissance, sur-miser (au-delà de `2f*`) fait perdre de l'argent malgré un edge positif. Comme `p` n'est qu'estimé, on utilise un **Kelly fractionné** : ½, **¼ (défaut)** ou 1/10.

### Arbitrage

Aucune hypothèse sur `p`. Si la somme des probabilités implicites des meilleures cotes de chaque issue est **inférieure à 100 %**, on mise sur toutes les issues avec des mises proportionnelles et on gagne quel que soit le résultat.

Exemple : 2.10 sur l'équipe 1 chez A, 2.10 sur l'équipe 2 chez B → `1/2,1 + 1/2,1 = 95,2 %` → profit garanti d'environ 5 %.

Risques pratiques : les cotes bougent avant le second pari, les règles diffèrent d'un book à l'autre, les comptes gagnants sont limités. Les exchanges prennent une commission, déduite par l'app (ROI net et brut affichés).

### Middle

Deux books proposent des lignes différentes sur le même marché, par exemple Équipe X **−2,5** chez A et Équipe Y **+4,5** chez B. Si X gagne de 3 ou 4 points, les deux paris gagnent. Hors de cette zone, un seul gagne et on perd la marge (~5 %) sur l'autre.

```
EV = P(middle) × gain_double − (1 − P(middle)) × perte_simple
```

`P(middle)` vient de distributions historiques des écarts par sport (`PROBABILITY_PER_INTEGER` dans `config.py`). Au NFL, les **key numbers** (3, 7, 10, 6, 14…) sont des marges très fréquentes : un middle qui les englobe vaut bien plus qu'un autre de même largeur. Profil : petite perte fréquente, gros gain rare, rentable seulement si la probabilité estimée est juste.

### CLV (Closing Line Value)

On compare la cote prise à la cote de **clôture** de Pinnacle, juste avant le match :

```
CLV % = (cote_prise / cote_clôture − 1) × 100
```

La ligne de clôture est le meilleur estimateur public de la vraie probabilité. Un CLV moyen positif sur quelques dizaines de paris indique un vrai edge, alors que le ROI réalisé demande des milliers de paris pour être fiable.

### Combinés (Builder)

Les cotes et les probabilités se multiplient, **les marges aussi**. Un combiné n'est intéressant que si chaque jambe est +EV. Le Builder impose un seul book par ticket, exclut deux jambes du même match (corrélation) et trie par edge composé.

---

## Suivi et validation

- Chaque +EV détecté est sauvegardé en SQLite (`data/edge_scanner.db`), dédupliqué par `(event, marché, issue, book)` et par jour.
- Un job APScheduler (toutes les 30 min) récupère la cote de clôture Pinnacle des événements qui démarrent dans l'heure et calcule le CLV.
- L'onglet **History** permet de saisir W/L à la main et affiche : win rate réel vs attendu, ROI réalisé en mise plate, **score de Brier** (`AVG((1/cote_fair − résultat)²)`, bon si < 0,25).
- `/export` télécharge tout l'historique en CSV.

Hypothèse assumée : pas d'état push/void, un nul (soccer h2h) sur la sélection prise compte comme perdu.

## Utilisation de l'API

Un scan complet de 11 sports consomme 12 requêtes (1 pour la liste des sports + 1 par sport). Le tier gratuit (500/mois) permet environ 40 scans complets. La région EU est toujours incluse pour garantir la présence de Pinnacle.

## Configuration (interface)

Régions (US, US2, UK, EU, AU), sports, stake, commission exchange, gap minimum des middles, edge minimum +EV, book sharp de référence, fraction de Kelly, bankroll, cotes décimales/américaines, thème sombre/clair.

## Stack

Python 3.11+, Flask, HTML/CSS/JS vanilla, SQLite, APScheduler, The Odds API.

## Roadmap

- Alertes Telegram
- Auto-refresh de l'interface
- Near-arbs (somme < 103 %)
- Démarge par méthode Shin
- Filtres de fraîcheur des cotes et score de confiance
- Polymarket / Kalshi comme références

## Avertissement

Projet à but éducatif et de recherche. Les paris sportifs comportent un risque de perte, les estimations de probabilité peuvent être fausses et les bookmakers peuvent limiter les comptes gagnants. Ne mise jamais plus que ce que tu peux te permettre de perdre.

## Licence

MIT. Basé sur un projet open source d'origine, voir `LICENSE`.
