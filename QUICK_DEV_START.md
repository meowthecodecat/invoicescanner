# 🚀 Démarrage Rapide en Développement

## Configuration en 3 étapes

### 1️⃣ Variables d'Environnement

**Backend** (`backend/.env`) :
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=sk-your-key
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-secret
FRONTEND_URL=http://localhost:3000
```

**Frontend** (`frontend/.env`) :
```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

### 2️⃣ Installation (une seule fois)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 3️⃣ Lancer en Développement

**Option A : Deux terminaux séparés**

Terminal 1 - Backend :
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```
👉 Backend sur http://localhost:8000

Terminal 2 - Frontend :
```bash
cd frontend
npm run dev
```
👉 Frontend sur http://localhost:3000

**Option B : Un seul terminal (à la racine)**

```bash
npm install  # Installe concurrently
npm run dev  # Lance backend + frontend
```

## 🎯 Accès

- **Frontend** : http://localhost:3000
- **Backend API** : http://localhost:8000
- **API Docs** : http://localhost:8000/docs
- **Health Check** : http://localhost:8000/health

## ✅ Vérification

1. Ouvrez http://localhost:8000/docs → Vous devriez voir l'API Swagger
2. Ouvrez http://localhost:3000 → Vous devriez voir la page de login Google

## 🔧 Commandes Utiles

```bash
# Backend - Port différent
uvicorn app.main:app --reload --port 8080

# Frontend - Port différent (modifier vite.config.js)
# Ou: npm run dev -- --port 3001

# Réinstaller dépendances backend
cd backend && pip install -r requirements.txt --force-reinstall

# Réinstaller dépendances frontend
cd frontend && rm -rf node_modules && npm install
```

## 🐛 Problèmes Courants

**Backend ne démarre pas ?**
- ✅ Vérifiez Python 3.11+ : `python --version`
- ✅ Activez le venv : `source venv/bin/activate`
- ✅ Vérifiez `.env` dans `backend/`

**Frontend ne démarre pas ?**
- ✅ Vérifiez Node 18+ : `node --version`
- ✅ Vérifiez `.env` dans `frontend/`
- ✅ Variables doivent commencer par `VITE_`

**CORS errors ?**
- ✅ Vérifiez `FRONTEND_URL` dans backend `.env`
- ✅ Vérifiez `VITE_API_URL` dans frontend `.env`
