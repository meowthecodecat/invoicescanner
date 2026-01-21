# 🚀 Guide de Lancement - InvoiceToSheet AI

## Option 1 : Docker Compose (Recommandé - Plus Simple)

### Étape 1 : Vérifier le fichier .env

Assurez-vous que votre fichier `.env` est **à la racine du projet** (même niveau que `docker-compose.yml`) et contient :

```env
SUPABASE_URL=https://votre-projet.supabase.co
SUPABASE_SERVICE_ROLE_KEY=votre-service-role-key
SUPABASE_ANON_KEY=votre-anon-key
OPENAI_API_KEY=sk-votre-cle-openai
GOOGLE_CLIENT_ID=votre-client-id
GOOGLE_CLIENT_SECRET=votre-client-secret
FRONTEND_URL=http://localhost:3000
```

**Important** : Docker Compose charge automatiquement le fichier `.env` à la racine.

### Étape 2 : Lancer avec Docker Compose

```bash
# À la racine du projet (où se trouve docker-compose.yml)
docker-compose up -d
```

**Ou pour voir les logs en temps réel (recommandé pour le premier lancement) :**
```bash
docker-compose up
```

**Ou pour voir les logs en temps réel :**
```bash
docker-compose up
```

### Étape 3 : Accéder à l'application

- **Frontend** : http://localhost:3000
- **Backend API** : http://localhost:8000
- **Prometheus** : http://localhost:9090

### Commandes utiles

```bash
# Voir les logs
docker-compose logs -f

# Voir les logs du backend uniquement
docker-compose logs -f backend

# Arrêter les services
docker-compose down

# Redémarrer
docker-compose restart
```

---

## Option 2 : Développement Local (Sans Docker)

### Backend

#### 1. Activer l'environnement virtuel

```bash
# Windows (PowerShell)
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

#### 2. Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

#### 3. Lancer le backend avec reload

```bash
# Dans le dossier backend
cd backend

# Lancer avec uvicorn (reload activé)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le backend sera accessible sur : **http://localhost:8000**

**✨ Fonctionnalités** :
- ✅ Reload automatique à chaque modification de code
- ✅ Fonctionne sur Windows, Linux et Mac
- ✅ Utilise le Python du venv grâce au fix dans `app/__init__.py`

**Alternative** : Vous pouvez aussi utiliser `python run_dev.py` qui fait la même chose

### Frontend

#### 1. Installer les dépendances

```bash
cd frontend
npm install
```

#### 2. Créer le fichier .env pour le frontend

Créez `frontend/.env` avec :

```env
VITE_SUPABASE_URL=https://votre-projet.supabase.co
VITE_SUPABASE_ANON_KEY=votre-anon-key
VITE_API_URL=http://localhost:8000
```

#### 3. Lancer le frontend

```bash
npm run dev
```

Le frontend sera accessible sur : **http://localhost:3000**

---

## Vérification

### 1. Vérifier que le backend fonctionne

Ouvrez dans votre navigateur :
- http://localhost:8000/health
- Devrait retourner : `{"status": "healthy"}`

### 2. Vérifier que le frontend fonctionne

Ouvrez : http://localhost:3000
- Vous devriez voir la page de connexion

### 3. Tester l'API

```bash
# Test de santé
curl http://localhost:8000/health

# Test de la racine
curl http://localhost:8000/
```

---

## Première Utilisation

1. **Ouvrir** http://localhost:3000
2. **Cliquer** sur "Sign in with Google"
3. **Autoriser** les permissions Google (Drive et Sheets)
4. **Entrer** votre Google Sheet ID dans le dashboard
5. **Uploader** une facture (drag & drop)
6. **Vérifier** votre Google Sheet - un nouvel onglet `Run_YYYY-MM-DD_HHmm` devrait apparaître avec les données

---

## Dépannage

### Erreur : "SUPABASE_URL must be set"

➡️ Vérifiez que votre fichier `.env` est bien à la racine du projet et contient toutes les variables

### Erreur : Port déjà utilisé

➡️ Changez les ports dans `docker-compose.yml` ou arrêtez les autres services qui utilisent ces ports

### Le backend ne démarre pas

```bash
# Vérifier les logs
docker-compose logs backend

# Ou en local
cd backend
python -m app.main
```

### Le frontend ne se connecte pas au backend

➡️ Vérifiez que :
- Le backend est bien lancé sur le port 8000
- Le fichier `frontend/.env` contient `VITE_API_URL=http://localhost:8000`

### Erreur de connexion Supabase

➡️ Vérifiez que :
- `SUPABASE_URL` est correct (sans slash à la fin)
- `SUPABASE_SERVICE_ROLE_KEY` est le bon (service_role, pas anon)
- Les tables existent dans Supabase (exécuter `supabase/invoicetosheet_schema.sql`)

---

## Commandes Rapides

### Tout lancer d'un coup (Docker)

```bash
docker-compose up -d
```

### Tout arrêter

```bash
docker-compose down
```

### Reconstruire après modification du code

```bash
docker-compose up -d --build
```

### Voir les logs en temps réel

```bash
docker-compose logs -f
```

---

## Prochaines Étapes

Une fois l'application lancée :

1. ✅ Connectez-vous avec Google OAuth
2. ✅ Configurez votre Google Sheet ID
3. ✅ Testez avec une facture
4. ✅ Vérifiez les métriques Prometheus sur http://localhost:9090

Bon développement ! 🎉
