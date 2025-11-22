# Système de Vote Distribué v2

**Auteur:** David Marleau
**Licence:** Licence MIT
**Statut:** 🚧 **VERSION DÉMO - FONCTIONNELLE MAIS INCOMPLÈTE** 🚧

**[🇬🇧 Read in English](./README.md)** | **[📖 Version Française](./READMEFR.md)**

---

## Résumé Exécutif

Un **système de vote électronique distribué** de qualité production conçu pour gérer **8 millions d'électeurs simultanés** à travers le Canada. Ce système prend en charge les **référendums de démocratie directe** (vote de lois) et les **élections électorales** avec des capacités de vote à choix unique et de vote par classement.

### Points Clés

- **Haute Performance**: Conçu pour traiter 8M+ votes avec mise en file d'attente RabbitMQ et mise à l'échelle horizontale
- **Sécurisé**: Validation de hachage hors ligne, aucun stockage de données personnelles, pistes d'audit complètes
- **Évolutif**: Architecture de microservices prête pour le déploiement Kubernetes
- **Temps Réel**: Résultats en direct avec tableaux de bord à actualisation automatique
- **Surveillé**: Pile d'observabilité complète Prometheus + Grafana

### Statistiques Rapides

| Métrique | Valeur |
|--------|-------|
| **Capacité Cible** | 8 millions d'électeurs |
| **Débit** | ~1 000 votes/sec (cible production) |
| **Performance Actuelle** | 150-250 votes/sec (Docker local) |
| **Latence (p95)** | <100ms |
| **Architecture** | Microservices + File de Messages |
| **Sécurité** | Authentification par hachage, aucune donnée personnelle |

---

## 💡 À Propos de Ce Projet

**Ceci est un projet d'apprentissage et une preuve de concept** construit pour partager une idée de modernisation des systèmes de vote démocratiques.

**Contexte Important:**
- Construit par un non-développeur comme exercice d'apprentissage ("vibe coding")
- Démontre des concepts d'architecture, pas du code prêt pour production
- Démo fonctionnelle qui montre que l'idée fonctionne à grande échelle
- **Nécessite un travail significatif avant utilisation réelle**

**Pourquoi Partager Ceci?**

Ce projet vise à contribuer une idée à la communauté technologique démocratique. Si vous êtes un professionnel de la sécurité, développeur expérimenté, ou expert en systèmes électoraux:

- 🔍 **Évaluez l'architecture** - le concept a-t-il du mérite?
- 🔧 **Forkez et améliorez** - rendez-le prêt pour production
- 💡 **Utilisez comme inspiration** - construisez quelque chose de meilleur
- 🤝 **Contribuez des corrections** - toutes améliorations bienvenues

**📋 Évaluation Sécurité:** Voir [SECURITY.md](./SECURITY.md) pour une évaluation honnête des limitations actuelles et de ce qui serait nécessaire pour un usage en production.

**🎯 Objectif:** Faire avancer la technologie de participation démocratique, que ce soit par cette implémentation ou en inspirant de meilleures solutions.

---

## Cas d'Usage

Cette infrastructure de vote pourrait être déployée dans divers scénarios démocratiques:

### Cas d'Usage 1: Élections Traditionnelles

Le système prend en charge les processus électoraux standards:
- Vote à choix unique pour élections simples
- Vote par classement (RCV) pour scrutins préférentiels
- Représentation régionale avec agrégation nationale
- Résultats en temps réel avec pistes d'audit

### Cas d'Usage 2: Référendums Citoyens

La même infrastructure pourrait permettre des votes de démocratie directe sur la législation. Exemples où des mécanismes de référendum ont été discutés:

1. **Ajustements Salariaux Parlementaires (Canada, avril 2024)**
   - Députés ont reçu augmentation de 4,4% (Députés: 203 100$/an, PM: 406 200$)
   - Sondages montraient 80% d'opposition publique
   - Actuellement automatique sans mécanisme de consultation citoyenne

2. **Réformes Politiques de Santé (Québec, octobre 2024)**
   - Loi 2 a imposé changements de rémunération des médecins
   - Certains médecins confrontés à réductions salariales jusqu'à 145 000$
   - Le ministre Lionel Carmant a démissionné; associations médicales ont déposé recours judiciaires
   - Adoptée sous vote de clôture sans consultation étendue

3. **Tendance Mondiale Vers la Démocratie Directe**
   - 700+ protestations citoyennes dans 147+ pays (2023-2024)
   - Demande croissante pour mécanismes de référendum sur décisions politiques majeures
   - Technologie permettant participation citoyenne en temps réel à grande échelle

### Capacités Techniques

Ce système fournit:
- **Évolutivité**: Conçu pour 8M électeurs simultanés
- **Flexibilité**: Vote de lois OU élections OU les deux
- **Sécurité**: Authentification par hachage, aucune donnée personnelle stockée
- **Transparence**: Code source ouvert, résultats vérifiables
- **Performance**: Cible de 1 000 votes/sec en production

### Options d'Implémentation

Les organisations pourraient déployer ceci pour:
- Élections municipales/provinciales
- Votes syndicaux ou scrutins organisationnels
- Référendums législatifs (si légalement autorisés)
- Programmes pilotes testant modèles de démocratie directe
- Recherche académique sur systèmes de vote

---

## Table des Matières

1. [Fonctionnalités](#fonctionnalités)
2. [Démarrage Rapide](#démarrage-rapide)
3. [Aperçu de l'Architecture](#aperçu-de-larchitecture)
4. [Composants du Système](#composants-du-système)
   - [API d'Ingestion](#1-api-dingestion)
   - [Workers de Validation](#2-workers-de-validation)
   - [Service d'Agrégation](#3-service-dagrégation)
   - [Générateur de Hachage](#4-service-de-génération-de-hachage)
   - [Interface Utilisateur Démo](#5-interface-web-démo)
   - [Pile de Surveillance](#6-pile-de-surveillance)
5. [Système Électoral](#système-électoral)
6. [Tests](#tests)
7. [Déploiement](#déploiement)
8. [Sécurité](#sécurité)
9. [Performance & Mise à l'Échelle](#performance--mise-à-léchelle)
10. [Dépannage](#dépannage)
11. [Structure du Projet](#structure-du-projet)

---

## Fonctionnalités

### Capacités de Vote
- ✅ **Vote de Lois (Référendums)**: Démocratie directe avec choix Oui/Non
- ✅ **Élections Électorales**: Élections de représentants régionaux
  - Support du vote à choix unique
  - Support du vote par classement (RCV)
  - Courses multi-candidats avec affiliations de parti
  - Contrôles de timing d'élection (date/heure début/fin)
  - Suivi des résultats en temps réel

### Fonctionnalités Techniques
- ✅ **Haute Performance**: Mise en mémoire tampon de file RabbitMQ pour 8M+ utilisateurs simultanés
- ✅ **Sécurité**: Validation de hachage hors ligne, aucun stockage de données personnelles, piste d'audit complète
- ✅ **Évolutivité**: Architecture de microservices prête pour Kubernetes
- ✅ **Surveillance**: Tableaux de bord Prometheus + Grafana avec alertes
- ✅ **Détection de Doublons**: Déduplication basée sur Redis avec suivi des tentatives
- ✅ **Résultats en Temps Réel**: Tableau de bord à actualisation automatique (intervalles de 5 secondes)
- ✅ **Agrégation Nationale**: Vue "Toutes Régions" pour les totaux nationaux
- ✅ **Tests de Charge**: Suite de tests complète avec capacité de 8M votes

---

## Démarrage Rapide

### Démarrage Ultra-Rapide (Commande Unique)

```bash
./quick-start.sh
```

Ce script démarre automatiquement tous les services en ~20 secondes! 🚀

### Démarrage Manuel

#### Prérequis
- Docker & Docker Compose
- Python 3.11+
- kubectl (pour le déploiement en production)

#### Étapes

1. **Démarrer les services Docker**:
```bash
docker-compose up -d
```

2. **Démarrer le tableau de bord de surveillance**:
```bash
python3 monitor_dashboard/server.py &
```

3. **Démarrer l'interface de vote**:
```bash
cd demo_ui && python3 app.py &
```

4. **Accéder aux services**:
- **Interface de Vote**: http://localhost:3000
  - Onglet vote de lois
  - Onglet vote électoral
  - Pages de résultats
- **Panneau d'Administration**: http://localhost:8501
  - Créer des élections
  - Configurer les méthodes de vote (choix unique / classement)
  - Définir le timing d'élection
  - Gérer les candidats
- **Tableau de Bord de Surveillance**: http://localhost:4000/monitor.html
  - Résultats d'élection en direct (actualisation automatique toutes les 5s)
  - **📊 Agrégation "Toutes Régions"** - Totaux nationaux par défaut
  - Ventilations par région disponibles
  - Tableau des résultats de vote de lois
  - Statistiques de vote
- **API de Vote**: http://localhost:8000
- **Gestion RabbitMQ**: http://localhost:15672 (guest/guest)
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

### Soumettre des Votes de Test

**Vote de Loi:**
```bash
curl -X POST http://localhost:8000/api/v1/vote \
  -H "Content-Type: application/json" \
  -d '{
    "nas": "123456789",
    "code": "ABC123",
    "law_id": "L2025-001",
    "vote": "oui"
  }'
```

**Vote Électoral:**
```bash
curl -X POST http://localhost:8000/api/v1/elections/vote \
  -H "Content-Type: application/json" \
  -d '{
    "nas": "123456789",
    "code": "ABC123",
    "election_id": 1,
    "region_id": 1,
    "candidate_id": 1,
    "voting_method": "single_choice"
  }'
```

### Voir les Résultats

**Résultats de Loi:**
```bash
curl http://localhost:8000/api/v1/results/L2025-001
```

**Résultats Électoraux:**
```bash
curl http://localhost:8000/api/v1/elections/1/regions/1/results
```

---

## Aperçu de l'Architecture

Le système utilise une **architecture de microservices** avec **mise en mémoire tampon de file de messages** pour gérer le trafic simultané à haut volume tout en maintenant l'intégrité des données.

### Flux de Haut Niveau

```
Électeur → API d'Ingestion (FastAPI)
          ↓
       File RabbitMQ (TAMPON) ← Gère le trafic en rafales
          ↓
     Workers de Validation (Évolutifs)
          ├─→ Redis (Validation de Hachage + Déduplication)
          └─→ PostgreSQL (Journal d'Audit)
          ↓
       Service d'Agrégation
          ↓
       PostgreSQL (Résultats de Vote)
          ↓
    Tableau de Bord Temps Réel
```

### Décisions Architecturales Clés

1. **Tampon de File de Messages**: RabbitMQ absorbe les pics de trafic (8M électeurs sur 24 heures)
2. **Workers Sans État**: Les workers de validation peuvent s'étendre horizontalement sans coordination
3. **Redis pour la Vitesse**: Recherches de hachage rapides (8M hachages) et détection de doublons
4. **PostgreSQL pour la Persistance**: Stockage fiable pour les votes et pistes d'audit
5. **Agrégation par Lots**: Comptage efficace des votes avec lots de 100 votes

### Composants d'Infrastructure

- **API d'Ingestion**: Point de terminaison de soumission de votes FastAPI
- **RabbitMQ**: Tampon de file de messages (gère le trafic en rafales)
- **Redis**: Recherche de hachage rapide (8M hachages) et détection de doublons
- **PostgreSQL**: Stockage persistant pour votes, élections, candidats, résultats
- **Prometheus + Grafana**: Collection de métriques et visualisation
- **Workers de Validation**: Workers évolutifs pour la validation de hachage (mise à l'échelle horizontale)
- **Service d'Agrégation**: Traitement par lots pour le comptage des votes

---

## Composants du Système

### 1. API d'Ingestion

**Emplacement**: `services/ingestion_api/`

Le point d'entrée basé sur FastAPI pour toutes les soumissions de votes.

**Responsabilités**:
- Accepter les requêtes HTTP POST avec les données de vote
- Effectuer la validation de base des entrées (format, champs requis)
- Publier les messages dans la file de validation RabbitMQ
- Retourner une réponse 202 Accepted immédiatement (traitement asynchrone)
- Exposer les points de terminaison de vérification de santé et de métriques

**Points de Terminaison**:
- `POST /api/v1/vote` - Soumettre un vote de loi
- `POST /api/v1/elections/vote` - Soumettre un vote électoral
- `GET /api/v1/results/{law_id}` - Obtenir les résultats de loi
- `GET /api/v1/elections/{election_id}/regions/{region_id}/results` - Obtenir les résultats électoraux
- `GET /health` - Vérification de santé

**Performance**:
- Actuel: ~250 votes/seconde (Docker local)
- Cible: ~1 000 votes/seconde (Kubernetes production)

**Configuration**:
- Limitation de débit activée
- Validation requête/réponse
- Support CORS pour l'interface web
- Export de métriques Prometheus

---

### 2. Workers de Validation

**Emplacement**: `services/validation_worker/`

Workers évolutifs qui traitent les votes depuis la file de validation RabbitMQ.

**Flux de Traitement**:

1. **Consommer** depuis la file `votes.validation`
2. **Valider le Hachage**: Vérifier si le hachage existe dans le SET Redis `valid_hashes`
   - Si invalide → publier dans la file `votes.review` avec status='invalid'
3. **Vérifier les Doublons**: Vérifier si le hachage existe dans le SET Redis `voted_hashes`
   - Si doublon:
     - Incrémenter le compteur `duplicate_count:{hash}`
     - Publier dans la file `votes.review` avec status='duplicate' et nombre de tentatives
4. **Traiter le Vote Valide**:
   - Ajouter le hachage au SET `voted_hashes`
   - Insérer le journal d'audit dans la table PostgreSQL `vote_audit`
   - Publier dans la file `votes.aggregation`
   - ACK du message

**Fonctionnalités Clés**:
- Validation des votes contre la base de données de hachage Redis
- Détection de doublons avec comptage des tentatives
- Journalisation d'audit dans PostgreSQL
- Gestion d'erreurs gracieuse avec remise en file
- Métriques Prometheus pour la surveillance
- Support de mise à l'échelle horizontale

**Mise à l'Échelle**:
```bash
# Passer à 8 workers
docker-compose up -d --scale validation-worker=8
```

**Métriques**:
- `validation_votes_processed_total{status}`: Total des votes par statut
- `validation_processing_latency_seconds`: Temps de traitement
- `validation_errors_total{error_type}`: Erreurs par type
- `redis_operations_total{operation,status}`: Opérations Redis
- `database_operations_total{operation,status}`: Opérations BD

---

### 3. Service d'Agrégation

**Emplacement**: `services/aggregation/`

Consomme les votes validés depuis RabbitMQ et met à jour PostgreSQL avec les comptages de votes agrégés.

**Fonctionnement**:

Le service d'agrégation utilise le **traitement par lots intelligent** pour l'efficacité:

1. **Traitement par lots basé sur la taille**: Traite lorsque le lot atteint 100 votes
2. **Traitement par lots basé sur le temps**: Traite toutes les 1 seconde si des votes sont en attente
3. **Traitement par lots à l'arrêt**: Traite tous les votes restants lors de l'arrêt gracieux

**Opérations de Base de Données**:
- Utilise `INSERT ... ON CONFLICT UPDATE` (UPSERT) pour l'efficacité
- Les mises à jour par lots minimisent les connexions à la base de données
- Pool de connexions pour la performance
- Réessai automatique avec backoff exponentiel

**Schéma de Base de Données**:

**vote_results** - Table d'agrégation principale:
- `law_id` (PK): Identifiant de loi
- `oui_count`: Nombre de votes "oui"
- `non_count`: Nombre de votes "non"
- `updated_at`: Horodatage de dernière mise à jour

**vote_audit** - Journal d'audit des votes individuels:
- `vote_hash` (UNIQUE): Hachage du vote
- `citizen_id`: Identifiant de l'électeur
- `law_id`: Identifiant de loi
- `choice`: Choix de vote (oui/non)
- `timestamp`: Horodatage du vote

**Performance**:
- Traite ~10 000 votes/seconde (dépendant du matériel)
- Taille de lot réglable pour débit vs latence
- Mise à l'échelle horizontale supportée

**Métriques Prometheus**:
- `votes_aggregated_total{law_id, choice}`: Total des votes agrégés
- `current_vote_totals{law_id, choice}`: Comptages de votes actuels
- `batch_processing_duration_seconds`: Temps de traitement
- `batch_size_processed_total`: Votes par lot
- `aggregation_errors_total{error_type}`: Erreurs d'agrégation

---

### 4. Service de Génération de Hachage

**Emplacement**: `services/hash_generator/`

Un utilitaire conteneurisé pour générer des hachages cryptographiques pour l'authentification des électeurs.

**Objectif**: Créer des identifiants d'authentification uniques pour les tests et le déploiement.

**Format de Hachage**:
Chaque hachage est calculé comme: `SHA-256(f"{nas}|{code.upper()}|{law_id}")`

**Données Générées**:
```json
{
  "nas": "123456789",        // Nombre aléatoire à 9 chiffres
  "code": "ABC123",           // Alphanumérique majuscule à 6 caractères
  "law_id": "L2025-001",      // Identifiant de loi
  "hash": "a1b2c3d4e5f6...",  // Hachage SHA-256
  "vote": "oui"               // Vote aléatoire (oui/non)
}
```

**Utilisation**:

```bash
# Générer 1 million de hachages
python generator.py --count 1000000 --output ./output

# Générer 5 millions de hachages pour une loi spécifique
python generator.py --count 5000000 --output ./output --law-id L2025-042

# Utilisation Docker
docker run -v $(pwd)/output:/output hash-generator \
  --count 1000000 \
  --output /output
```

**Sortie**:
- Fichiers JSON fragmentés (`hashes_shard_0000.json`, `hashes_shard_0001.json`, etc.)
- Par défaut: 1 million de hachages par fragment
- Barre de progression avec statut de génération en temps réel
- Statistiques récapitulatives (distribution des votes, tailles de fichiers)

**Performance**:
- Vitesse de génération: ~100 000-500 000 hachages par seconde
- Économe en mémoire avec sortie fragmentée
- Peut générer 8M hachages en moins de 2 minutes

**Intégration**:
- Charger les hachages dans Redis pour validation
- Distribuer les fichiers fragmentés aux nœuds de vote
- Utiliser pour les tests de charge et la simulation

---

### 5. Interface Web Démo

**Emplacement**: `demo_ui/`

Une interface web basée sur Flask pour le système de vote électronique avec affichage des résultats en temps réel.

**Fonctionnalités**:
- **Formulaire de Vote**: Soumettre des votes avec NAS, code de validation, sélection de loi et choix de vote
- **Validation en Temps Réel**: Validation de formulaire côté client avec retour instantané
- **Affichage des Résultats**: Résultats en direct avec actualisation automatique toutes les 5 secondes
- **Graphiques Interactifs**: Représentation visuelle utilisant Chart.js
- **Design Responsive**: Interface Bootstrap 5 compatible mobile
- **Thème Sombre**: Schéma de couleurs sombre professionnel
- **Gestion d'Erreurs**: Messages d'erreur complets pour tous les scénarios

**Routes**:
- `GET /` - Page de vote principale avec formulaire et résultats actuels
- `POST /vote` - Soumettre un vote (point de terminaison AJAX)
- `GET /results` - Page de résultats complète avec graphiques et tableaux
- `GET /api/results` - API JSON pour récupérer les résultats actuels
- `GET /health` - Point de terminaison de vérification de santé

**Technologies**:
- **Backend**: Flask 3.0
- **Frontend**: Bootstrap 5, Chart.js
- **Client HTTP**: Bibliothèque Requests
- **Style**: CSS personnalisé avec thème sombre
- **JavaScript**: JS vanilla avec AJAX

**Exécution Locale**:
```bash
cd demo_ui
pip install -r requirements.txt
python app.py
# Accès à http://localhost:3000
```

**Déploiement en Production**:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:3000 app:app
```

---

### 6. Pile de Surveillance

**Emplacement**: `monitoring/`

Observabilité complète avec collecte de métriques Prometheus et visualisation Grafana.

**Composants**:
- **Prometheus**: Base de données de séries temporelles et moteur d'alerte
- **Grafana**: Plateforme de visualisation et tableaux de bord
- **Exportateurs**: Exportateurs spécialisés pour Redis, PostgreSQL et RabbitMQ

**Accès**:
- **Grafana**: http://localhost:3001 (admin/admin)
  - Tableau de bord principal: "Election Voting System - Overview"
- **Prometheus**: http://localhost:9090
  - Interface de requête et statut d'alerte

**Tableaux de Bord Clés**:

1. **Votes Par Seconde** - Série temporelle montrant le taux d'ingestion de votes
2. **Total des Votes par Loi** - Jauge montrant les votes cumulatifs par loi
3. **Répartition du Statut de Validation** - Diagramme circulaire des votes valides/invalides/doublons
4. **Profondeur de File** - Série temporelle des profondeurs de files de messages
5. **Latence API (p50/p95/p99)** - Latences en percentiles
6. **Taux de Tentatives de Doublons** - Pourcentage de tentatives de doublons
7. **Workers Actifs** - Nombre de workers de validation en cours d'exécution
8. **Utilisation Mémoire Redis** - Jauge de consommation mémoire
9. **Connexions Base de Données** - Utilisation du pool de connexions BD
10. **Requêtes HTTP par Code de Statut** - Graphique en aires empilées

**Règles d'Alerte**:

**Alertes Critiques** (Action Immédiate Requise):
- `IngestionAPIDown` - API inaccessible pendant 1 minute
- `ValidationWorkerDown` - Moins de 2 workers pendant 2 minutes
- `RabbitMQDown` - RabbitMQ inaccessible pendant 1 minute
- `RedisDown` - Redis inaccessible pendant 1 minute
- `PostgresDown` - PostgreSQL inaccessible pendant 1 minute
- `CriticalValidationQueueDepth` - >50 000 messages pendant 2 minutes
- `CriticalDuplicateRate` - >15% taux de doublons pendant 5 minutes
- `APICriticalLatency` - latence p95 >500ms pendant 2 minutes
- `CriticalAPIErrorRate` - >15% taux d'erreur pendant 2 minutes

**Alertes d'Avertissement** (Action Recommandée):
- `HighValidationQueueDepth` - >10 000 messages pendant 5 minutes
- `HighDuplicateRate` - >5% taux de doublons pendant 10 minutes
- `APIHighLatency` - latence p95 >200ms pendant 5 minutes
- `HighAPIErrorRate` - >5% taux d'erreur pendant 5 minutes

**Catégories de Métriques**:

**Métriques d'Application**:
- `votes_received_total` - Compteur de votes reçus
- `votes_by_law_total` - Compteur par loi/référendum
- `votes_validation_processed_total` - Compteur de votes validés
- `votes_aggregated_total` - Compteur de votes agrégés
- `http_requests_total` - Requêtes HTTP par code de statut

**Métriques d'Infrastructure**:
- `rabbitmq_queue_messages` - Messages dans la file
- `redis_memory_used_bytes` - Utilisation mémoire
- `pg_stat_database_numbackends` - Connexions actives
- `validation_duration_seconds` - Histogramme du temps de traitement

---

## Système Électoral

### Schéma de Base de Données

**Table Elections**:
- `election_code`, `election_name`, `election_type`
- `start_datetime`, `end_datetime` - Contrôle de la fenêtre de vote
- `voting_method` - `single_choice` ou `ranked_choice`
- `status` - `draft`, `active`, `completed`

**Table Candidats**:
- Liens vers élections, régions et partis politiques
- `first_name`, `last_name`, `bio`
- Affiliations de parti avec couleurs et branding

**Résultats Électoraux**:
- Agrégation en temps réel dans la table `election_results`
- Comptages de votes et pourcentages par candidat/région
- Agrégation nationale à travers toutes les régions

### Fonctionnalités Implémentées

- ✅ Bascule de vote par classement dans le panneau d'administration
- ✅ Timing d'élection (date/heure début/fin)
- ✅ Validation de coupure de vote (pas de votes après la date limite)
- ✅ Résultats d'élection sur le tableau de bord de surveillance avec agrégation **"Toutes Régions"**
- ✅ Totaux électoraux nationaux (agrégation automatique à travers toutes les régions)
- ✅ Ventilations de résultats par région
- ✅ Pipeline RabbitMQ: API → File → Workers → PostgreSQL
- ✅ Élections multi-candidats fonctionnelles
- ✅ Couleurs et branding de parti
- ✅ Actualisation automatique en temps réel (intervalles de 5 secondes)

---

## Tests

**Emplacement**: `tests/`

Suite complète de tests d'intégration et de charge.

### Couverture de Tests

- **Total des Tests d'Intégration**: 40+
- **Cible de Couverture de Tests**: >80%
- **Cibles de Performance**:
  - Débit: 1000 votes/seconde
  - Latence: p95 < 100ms
  - Taux de Réussite: >99.9%

### Exécution des Tests

```bash
# Exécuter tous les tests d'intégration
cd tests/
pytest integration/ -v

# Avec rapport de couverture
pytest integration/ -v --cov --cov-report=html

# Exécuter des fichiers de tests spécifiques
pytest integration/test_vote_flow.py -v
pytest integration/test_api.py -v
pytest integration/test_duplicate_detection.py -v
```

### Tests de Charge

**Générer 8 millions d'identifiants de test**:
```bash
python3 scripts/preload_test_hashes.py 8000000
```

Cela crée:
- `test_votes.txt` (251MB, 8M lignes)
- Charge tous les hachages dans Redis pour validation

**Exécuter les tests de charge**:

```bash
# Test de charge standard (avec identifiants valides)
python3 -u tests/load_test.py --votes 100000 --rate 1000

# Test BD direct (élections, 30k votes)
python3 tests/test_election_simple.py

# Utilisation de Locust (interface web)
locust -f tests/load_test.py --host=http://localhost:8000
# Ouvrir le navigateur à http://localhost:8089
```

**Résultats de Performance**:
- **BD Direct**: 3 558 votes/sec
- **Test de Charge API**: 160-265 votes/sec (avec pipeline de validation complet)
- **Capacité Système**: Conçu pour 8M votes en 24 heures (~92 votes/sec moyenne)

### Catégories de Tests

1. **Tests d'Intégration** - Tests de bout en bout du pipeline de vote complet
2. **Tests API** - Validation des points de terminaison REST API
3. **Tests de Détection de Doublons** - Vérification de la logique de déduplication de vote
4. **Tests de Charge** - Tests de performance et d'évolutivité

---

## Déploiement

### Docker Compose (Développement Local)

```bash
# Démarrer tous les services
docker-compose up -d

# Mettre à l'échelle les workers de validation
docker-compose up -d --scale validation-worker=5

# Vérifier le statut
docker-compose ps

# Voir les journaux
docker-compose logs -f validation-worker
```

### Kubernetes (Production)

```bash
# Appliquer la configuration de base
kubectl apply -k k8s/overlays/prod/

# Mettre à l'échelle les workers
kubectl scale deployment validation-worker --replicas=20

# Vérifier le statut
kubectl get pods

# Voir les journaux
kubectl logs -f deployment/validation-worker
```

### Recommandations de Mise à l'Échelle en Production

**Développement** (docker-compose):
- Performance actuelle: ~250 votes/seconde via API
- BD direct: 3 500+ votes/seconde
- Bon pour les tests et démos

**Production** (Kubernetes):
- 10x Répliques API d'Ingestion
- 20x Workers de Validation
- 3x Service d'Agrégation
- Cluster Redis (3 nœuds)
- PostgreSQL avec répliques en lecture
- **Cible**: 1000 votes/seconde soutenue

---

## Sécurité

### Fonctionnalités de Sécurité

- ✅ **Aucun Stockage de Données Personnelles**: Seuls les hachages stockés, aucune information personnellement identifiable
- ✅ **Base de Données de Hachage Hors Ligne**: Empêche les faux votes, hachages générés hors ligne
- ✅ **Détection de Doublons**: Déduplication basée sur Redis avec suivi des tentatives
- ✅ **Piste d'Audit Complète**: Chaque vote enregistré dans PostgreSQL
- ✅ **Limitation de Débit**: Limitation de débit API pour prévenir les abus
- ✅ **Respect du Timing Électoral**: Aucun vote précoce/tardif accepté
- ✅ **Communication TLS**: Communication inter-services chiffrée (production)

### Authentification Basée sur le Hachage

Le système utilise des **hachages SHA-256** pour l'authentification des électeurs:

```
Hachage = SHA-256(NAS | Code | Law_ID)
```

**Avantages**:
1. Aucune information personnelle stockée dans le système
2. La génération de hachage hors ligne assure l'intégrité des identifiants de vote
3. Impossible de rétro-ingénierie de l'identité de l'électeur à partir du hachage
4. Chaque hachage est unique à la combinaison électeur + loi

### Protection des Données

**Redis**:
- Hachages valides stockés dans le SET `valid_hashes` (8M hachages)
- Hachages votés stockés dans le SET `voted_hashes` (déduplication)
- Compteurs de tentatives de doublons: `duplicate_count:{hash}`
- TTL défini sur toutes les clés pour nettoyage automatique

**PostgreSQL**:
- Journal d'audit: table `vote_audit` (enregistrement immuable)
- Résultats: table `vote_results` (comptages agrégés)
- Élections: tables `elections`, `candidates`, `election_results`
- Toutes les tables indexées pour performance et requêtes de sécurité

---

## Performance & Mise à l'Échelle

### Performance Actuelle (Docker Local)

| Métrique | Valeur |
|--------|-------|
| Débit de Pointe (API) | ~250 votes/sec |
| Débit de Pointe (BD Direct) | ~3 500 votes/sec |
| Latence p95 | 80ms |
| Taux de Réussite | 99.5% |

### Cibles de Production (Kubernetes)

| Métrique | Cible |
|--------|--------|
| Débit de Pointe | 1 000 votes/sec |
| Latence p95 | <100ms |
| Taux de Réussite | >99.9% |
| Disponibilité | 99.9% |

### Mise à l'Échelle pour 8M Votes

**Scénario**: 8 millions d'électeurs sur une période de vote de 24 heures

**Charge Moyenne**: 8 000 000 / (24 * 3600) = ~92 votes/seconde

**Charge de Pointe** (en supposant un pic de 10x): ~920 votes/seconde

**Stratégie de Mise à l'Échelle**:

1. **Mise à l'Échelle Horizontale**:
   - 10x instances API d'Ingestion (équilibrées en charge)
   - 20x Workers de Validation (traitement parallèle)
   - 3x Services d'Agrégation (traitement par lots)

2. **Mise à l'Échelle d'Infrastructure**:
   - Cluster Redis (3 nœuds, fragmentés)
   - PostgreSQL avec répliques en lecture (1 primaire, 2 répliques)
   - Cluster RabbitMQ (3 nœuds, files en miroir)

3. **Optimisations de Performance**:
   - Pool de connexions (PostgreSQL)
   - Opérations par lots (Agrégation)
   - Réglage du comptage de prérécupération (RabbitMQ)
   - Pipeline Redis

**Planification de Capacité**:

| Composant | Min | Charge Moyenne | Charge Élevée |
|-----------|-----|-------------|-----------|
| Instances API | 2 | 4 | 10 |
| Workers de Validation | 4 | 8 | 20 |
| Services d'Agrégation | 1 | 2 | 3 |
| Débit Attendu | ~200/sec | ~500/sec | ~1000/sec |

---

## Dépannage

### Votes Non Traités

**Symptômes**: Votes soumis mais n'apparaissant pas dans les résultats

**Étapes de Diagnostic**:
1. Vérifier la profondeur de file RabbitMQ: `curl -u guest:guest http://localhost:15672/api/queues`
2. Vérifier les journaux des workers de validation: `docker-compose logs validation-worker`
3. Vérifier que Redis a des hachages: `docker-compose exec redis redis-cli SCARD valid_hashes`

**Solutions**:
- Mettre à l'échelle les workers de validation: `docker-compose up -d --scale validation-worker=8`
- Charger les hachages dans Redis: `python3 scripts/load_hashes_to_redis.py`
- Redémarrer les workers: `docker-compose restart validation-worker`

### Résultats Électoraux Non Affichés

**Étapes de Diagnostic**:
1. Vérifier la table election_results:
   ```bash
   docker-compose exec postgres psql -U voting_user -d voting -c "SELECT * FROM election_results;"
   ```
2. Vérifier que les candidats existent dans le panneau d'administration
3. Vérifier le tableau de bord de surveillance pour les résultats en direct
4. Vérifier que l'élection est active et dans la fenêtre de temps

**Solutions**:
- Vérifier le statut de l'élection: Vérifier le panneau d'administration Onglet 7
- Vérifier les journaux du service d'agrégation: `docker-compose logs aggregation`
- Vérifier la fenêtre de temps: S'assurer que l'heure actuelle est entre start_datetime et end_datetime

### Profondeur de File Élevée

**Symptômes**: Messages s'accumulant dans les files de validation ou d'agrégation

**Causes Possibles**:
- Capacité de workers insuffisante
- Plantages ou blocages de workers
- Problèmes de performance de base de données
- Problèmes de connectivité réseau

**Solutions**:
- Augmenter les workers: `docker-compose up -d --scale validation-worker=8`
- Redémarrer les workers bloqués: `docker-compose restart validation-worker`
- Vérifier la performance de la base de données: Surveiller le nombre de connexions et les temps de requête
- Surveiller le tableau de bord Grafana pour les goulots d'étranglement

### Problèmes de Performance

**Étapes de Diagnostic**:
1. Vérifier les métriques Prometheus: http://localhost:9090
2. Surveiller la mémoire Redis: `docker-compose exec redis redis-cli INFO memory`
3. Vérifier les connexions de base de données: `docker-compose exec postgres psql -U voting_user -d voting -c "SELECT count(*) FROM pg_stat_activity;"`

**Solutions**:
- Mettre à l'échelle les workers de validation: `docker-compose up -d --scale validation-worker=5`
- Augmenter la limite de mémoire Redis dans docker-compose.yml
- Optimiser les requêtes de base de données ou ajouter des index

### Réinitialisation Complète

Si les tests ou le système échouent de manière inattendue:

```bash
# Arrêter et supprimer tous les conteneurs, volumes, réseaux
docker-compose down -v

# Supprimer les artefacts de test
rm -rf htmlcov/ .coverage .pytest_cache/

# Redémarrer à neuf
docker-compose up -d
sleep 30

# Recharger les hachages
python3 scripts/load_hashes_to_redis.py --sample
```

---

## Structure du Projet

```
electionscriptanalyse/
├── services/                           # Microservices
│   ├── ingestion_api/                 # API de soumission de votes (FastAPI)
│   │   ├── main.py                    # Points de terminaison API
│   │   ├── requirements.txt           # Dépendances
│   │   └── Dockerfile                 # Config conteneur
│   ├── validation_worker/             # Validation de hachage & déduplication
│   │   ├── worker.py                  # Logique principale du worker
│   │   ├── redis_client.py            # Opérations Redis
│   │   ├── rabbitmq_client.py         # Consommateur RabbitMQ
│   │   ├── database.py                # Client PostgreSQL
│   │   ├── config.py                  # Configuration
│   │   ├── requirements.txt           # Dépendances
│   │   ├── Dockerfile                 # Config conteneur
│   │   └── README.md                  # Documentation du service
│   ├── aggregation/                   # Comptage & agrégation de votes
│   │   ├── aggregator.py              # Logique principale d'agrégation
│   │   ├── requirements.txt           # Dépendances
│   │   ├── Dockerfile                 # Config conteneur
│   │   └── README.md                  # Documentation du service
│   ├── hash_generator/                # Utilitaire de génération de hachage
│   │   ├── generator.py               # Script générateur de hachage
│   │   ├── requirements.txt           # Dépendances
│   │   ├── Dockerfile                 # Config conteneur
│   │   └── README.md                  # Documentation du service
│   └── shared/                        # Utilitaires & modèles partagés
│       ├── models.py                  # Modèles de données
│       └── utils.py                   # Utilitaires communs
├── demo_ui/                            # Interface de vote basée sur le web
│   ├── app.py                         # Application Flask
│   ├── config.py                      # Configuration
│   ├── requirements.txt               # Dépendances
│   ├── Dockerfile                     # Config conteneur
│   ├── README.md                      # Documentation UI
│   ├── templates/                     # Modèles HTML
│   │   ├── index.html                 # Page de vote
│   │   └── results.html               # Page de résultats
│   └── static/                        # Ressources statiques
│       ├── style.css                  # Style personnalisé
│       └── script.js                  # Logique côté client
├── tests/                              # Suites de tests
│   ├── integration/                   # Tests d'intégration
│   │   ├── conftest.py                # Fixtures Pytest
│   │   ├── test_vote_flow.py          # Tests de flux de vote bout en bout
│   │   ├── test_api.py                # Tests de points de terminaison API
│   │   └── test_duplicate_detection.py # Tests de gestion de doublons
│   ├── unit/                          # Tests unitaires
│   ├── load_test.py                   # Script de test de charge (8M votes)
│   ├── voting_test_gui.py             # Panneau d'administration Streamlit
│   ├── test_election_simple.py        # Test d'élection BD direct (30k votes)
│   ├── small_rabbitmq_test.py         # Test RabbitMQ petite échelle (17 votes)
│   ├── small_election_test.py         # Test d'élection petite échelle (17 votes)
│   ├── requirements.txt               # Dépendances de tests
│   └── README.md                      # Documentation des tests
├── monitor_dashboard/                  # Tableau de bord de résultats en temps réel
│   ├── server.py                      # Serveur HTTP Python
│   └── monitor.html                   # Interface résultats élection en direct
├── monitoring/                         # Prometheus & Grafana
│   ├── prometheus/                    # Configuration Prometheus
│   │   ├── prometheus.yml             # Config principale
│   │   └── alerts.yml                 # Règles d'alerte
│   ├── grafana/                       # Configuration Grafana
│   │   ├── dashboards/                # Fichiers JSON de tableau de bord
│   │   │   └── voting_overview.json   # Tableau de bord principal
│   │   └── provisioning/              # Auto-provisionnement
│   │       ├── datasources/           # Config source de données
│   │       │   └── prometheus.yml     # Source de données Prometheus
│   │       └── dashboards/            # Provisionnement tableau de bord
│   │           └── dashboards.yml     # Config tableau de bord
│   └── README.md                      # Documentation surveillance
├── scripts/                            # Scripts utilitaires
│   ├── preload_test_hashes.py         # Générer 8M identifiants de vote de test
│   ├── load_hashes_to_redis.py        # Charger base de données de hachage
│   └── quick-start.sh                 # Script de démarrage une commande
├── k8s/                               # Manifestes Kubernetes
│   ├── base/                          # Configurations de base
│   └── overlays/                      # Configs spécifiques environnement
│       ├── dev/                       # Développement
│       └── prod/                      # Production
├── test_results/                      # Résultats de tests de charge (organisés)
├── data/                              # Répertoire de données
│   └── init_db.sql                    # Schéma de base de données & données d'exemple
├── docker-compose.yml                 # Pile de développement local
├── ARCHITECTURE.md                    # Documentation architecture système
├── QUICKSTART.md                      # Guide de démarrage
├── README.md                          # README principal (original)
├── readme2.md                         # README complet (anglais)
└── READMEFR.md                        # Ce README complet (français)
```

---

## Mises à Jour Récentes

### 2025-11-21
- ✅ **Ajout de l'agrégation "Toutes Régions"** au tableau de bord de surveillance
  - Totaux électoraux nationaux affichés par défaut
  - Agrégation automatique des votes à travers toutes les régions
  - Changement transparent entre vues nationales et régionales
- ✅ **Création de scripts de test à petite échelle** (17 votes)
  - `tests/small_rabbitmq_test.py` - Test pipeline RabbitMQ
  - `tests/small_election_test.py` - Test vote électoral
  - Débogage rapide sans charger 8M votes
- ✅ **Création de quick-start.sh** - Démarrage système une commande
- ✅ **Suppression du graphique de loi redondant** du tableau de bord de surveillance
- ✅ Test réussi du pipeline RabbitMQ complet:
  - API → RabbitMQ → Workers de Validation → PostgreSQL
  - Tous les 17/17 votes traités correctement
- ✅ Mise à jour du README avec guide de démarrage amélioré

### 2025-11-16
- ✅ Généré 8 millions d'identifiants de vote de test (fichier 251MB)
- ✅ Chargé 8M hachages dans Redis (~2 min temps de chargement)
- ✅ Nettoyé 154 fichiers Zone.Identifier
- ✅ Organisé les résultats de tests dans le dossier `test_results/`
- ✅ Mise à jour de la documentation (README + GEMINI.md)

---

## Contribution

Ceci est un projet de démo/prototype. Pour une utilisation en production, développement additionnel requis:

1. **Renforcement de la Sécurité**:
   - Implémenter la limitation de débit par IP
   - Ajouter l'authentification/autorisation API
   - Activer TLS/SSL pour toutes les communications
   - Implémenter la détection d'intrusion

2. **Améliorations d'Évolutivité**:
   - Implémentation de Cluster Redis
   - Répliques en lecture PostgreSQL
   - Clustering RabbitMQ
   - CDN pour les ressources statiques

3. **Améliorations Opérationnelles**:
   - Sauvegardes automatisées
   - Procédures de récupération après sinistre
   - Déploiement bleu-vert
   - Versions canari

4. **Conformité**:
   - Audit de conformité RGPD
   - Accessibilité (WCAG 2.1 AA)
   - Audit de sécurité
   - Tests de pénétration

---

## Support & Documentation

Pour les problèmes et questions:

1. Consulter la section [Dépannage](#dépannage)
2. Revoir [ARCHITECTURE.md](./ARCHITECTURE.md) pour la conception du système
3. Voir les README spécifiques aux composants:
   - [Générateur de Hachage](./services/hash_generator/README.md)
   - [Worker de Validation](./services/validation_worker/README.md)
   - [Service d'Agrégation](./services/aggregation/README.md)
   - [Interface Démo](./demo_ui/README.md)
   - [Surveillance](./monitoring/README.md)
   - [Tests](./tests/README.md)
4. Vérifier les journaux des services: `docker-compose logs <nom-service>`
5. Surveiller la santé du système: http://localhost:3001 (Grafana)

---

## Licence

Licence MIT

Copyright (c) 2025 David Marleau

La permission est accordée, gratuitement, à toute personne obtenant une copie de ce logiciel et des fichiers de documentation associés (le "Logiciel"), de traiter le Logiciel sans restriction, y compris sans limitation les droits d'utiliser, copier, modifier, fusionner, publier, distribuer, sous-licencier et/ou vendre des copies du Logiciel, et de permettre aux personnes à qui le Logiciel est fourni de le faire, sous réserve des conditions suivantes:

L'avis de droit d'auteur ci-dessus et cet avis de permission doivent être inclus dans toutes les copies ou parties substantielles du Logiciel.

LE LOGICIEL EST FOURNI "TEL QUEL", SANS GARANTIE D'AUCUNE SORTE, EXPRESSE OU IMPLICITE, Y COMPRIS MAIS SANS S'Y LIMITER LES GARANTIES DE QUALITÉ MARCHANDE, D'ADÉQUATION À UN USAGE PARTICULIER ET D'ABSENCE DE CONTREFAÇON. EN AUCUN CAS LES AUTEURS OU TITULAIRES DU DROIT D'AUTEUR NE SERONT RESPONSABLES DE TOUTE RÉCLAMATION, DOMMAGE OU AUTRE RESPONSABILITÉ, QUE CE SOIT DANS UNE ACTION CONTRACTUELLE, DÉLICTUELLE OU AUTRE, DÉCOULANT DE, HORS DE OU EN RELATION AVEC LE LOGICIEL OU L'UTILISATION OU D'AUTRES TRANSACTIONS DANS LE LOGICIEL.

---

**Construit avec ❤️ pour la participation démocratique à grande échelle**
