# Guide de Développement Local

## Prérequis

### Frontend
- Node.js 18+ et npm
- Un projet Supabase avec Google OAuth configuré

### Backend
- Python 3.11+
- pip (gestionnaire de paquets Python)

## Configuration Initiale

### 1. Variables d'Environnement

#### Backend (`.env` à la racine ou dans `backend/`)
Créez un fichier `.env` dans le dossier `backend/` :

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
REDIRECT_URI=http://localhost:3000/auth/callback

# Billing Configuration
MONTHLY_LIMIT=100

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

#### Frontend (`.env` dans `frontend/`)
Créez un fichier `.env` dans le dossier `frontend/` :

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

### 2. Base de Données

1. Ouvrez Supabase Dashboard → SQL Editor
2. Exécutez le fichier `supabase/invoicetosheet_schema.sql`
3. Vérifiez que les tables `invoicetosheet_profiles` et `invoicetosheet_usage_logs` sont créées

## Lancement en Développement

### Option 1 : Terminal séparés (Recommandé)

#### Terminal 1 - Backend (FastAPI)

```bash
# Aller dans le dossier backend
cd backend

# Créer un environnement virtuel Python (première fois)
python -m venv venv

# Activer l'environnement virtuel
# Sur Windows (PowerShell):
venv\Scripts\Activate.ps1
# Sur Windows (CMD):
venv\Scripts\activate.bat
# Sur Mac/Linux:
source venv/bin/activate

# Installer les dépendances (première fois)
pip install -r requirements.txt

# Lancer le serveur de développement
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le backend sera accessible sur : **http://localhost:8000**
- API : http://localhost:8000/api/...
- Health check : http://localhost:8000/health
- Metrics : http://localhost:8000/metrics
- Docs API : http://localhost:8000/docs

#### Terminal 2 - Frontend (React + Vite)

```bash
# Aller dans le dossier frontend
cd frontend

# Installer les dépendances (première fois)
npm install

# Lancer le serveur de développement
npm run dev
```

Le frontend sera accessible sur : **http://localhost:3000**

### Option 2 : Scripts NPM (Concurrent)

Créez un fichier `package.json` à la racine du projet :

```json
{
  "name": "invoicetosheet-ai",
  "version": "1.0.0",
  "scripts": {
    "dev": "concurrently \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
    "dev:frontend": "cd frontend && npm run dev"
  },
  "devDependencies": {
    "concurrently": "^8.2.2"
  }
}
```

Puis à la racine :

```bash
# Installer concurrently (première fois)
npm install

# Lancer les deux en même temps
npm run dev
```

## Vérification

### 1. Vérifier le Backend

```bash
# Test de santé
curl http://localhost:8000/health

# Ou dans le navigateur
# Ouvrir: http://localhost:8000/docs
```

### 2. Vérifier le Frontend

1. Ouvrir http://localhost:3000
2. Vous devriez voir la page de connexion Google

## Configuration Google OAuth

### 1. Dans Supabase
1. Allez dans Authentication → Providers → Google
2. Activez Google provider
3. Ajoutez Client ID et Client Secret depuis Google Cloud Console
4. Redirect URL : `http://localhost:3000/dashboard`

### 2. Dans Google Cloud Console
1. Créez un projet OAuth 2.0
2. Autorisez les redirect URIs :
   - `https://your-project.supabase.co/auth/v1/callback`
   - `http://localhost:3000/dashboard`
3. Scopes requis :
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive.file`

## Dépannage

### Backend ne démarre pas

```bash
# Vérifier Python
python --version  # Doit être 3.11+

# Réinstaller les dépendances
pip install -r requirements.txt --force-reinstall

# Vérifier les variables d'environnement
# Le fichier .env doit être dans backend/
```

### Frontend ne démarre pas

```bash
# Nettoyer et réinstaller
cd frontend
rm -rf node_modules package-lock.json
npm install

# Vérifier les variables d'environnement
# Le fichier .env doit être dans frontend/
# Les variables doivent commencer par VITE_
```

### Erreur CORS

Si vous voyez des erreurs CORS :
- Vérifiez que `FRONTEND_URL=http://localhost:3000` est dans le `.env` du backend
- Vérifiez que `VITE_API_URL=http://localhost:8000` est dans le `.env` du frontend

### Erreur de connexion à Supabase

- Vérifiez que `SUPABASE_URL` et `SUPABASE_ANON_KEY` sont corrects
- Vérifiez que le projet Supabase est actif
- Vérifiez les policies RLS dans Supabase

## Structure des Ports

- **Frontend** : 3000 (http://localhost:3000)
- **Backend** : 8000 (http://localhost:8000)
- **Prometheus** : 9090 (uniquement en Docker)

## Commandes Utiles

### Backend

```bash
# Activer l'environnement virtuel
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Lancer le serveur
uvicorn app.main:app --reload

# Lancer sur un port différent
uvicorn app.main:app --reload --port 8080

# Voir les logs détaillés
uvicorn app.main:app --reload --log-level debug
```

### Frontend

```bash
# Lancer en développement
npm run dev

# Build pour production
npm run build

# Prévisualiser le build
npm run preview
```

## Workflow de Développement

1. **Démarrer le backend** (Terminal 1)
   ```bash
   cd backend
   source venv/bin/activate  # ou activate selon votre OS
   uvicorn app.main:app --reload
   ```

2. **Démarrer le frontend** (Terminal 2)
   ```bash
   cd frontend
   npm run dev
   ```

3. **Développer**
   - Modifications backend → rechargement automatique
   - Modifications frontend → Hot Module Replacement (HMR)

4. **Tester**
   - Frontend : http://localhost:3000
   - API Docs : http://localhost:8000/docs

## Conseils

- Le backend avec `--reload` se recharge automatiquement lors des modifications
- Le frontend avec Vite a un Hot Module Replacement très rapide
- Utilisez les DevTools du navigateur pour déboguer
- Utilisez http://localhost:8000/docs pour tester l'API directement
