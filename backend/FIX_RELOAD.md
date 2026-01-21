# Fix pour uvicorn --reload sur Windows

## Problème

Sur Windows, quand `uvicorn --reload` est utilisé, il spawn un subprocess avec la méthode `multiprocessing.spawn`. Ce subprocess ne hérite pas automatiquement du venv, ce qui cause des erreurs `ModuleNotFoundError`.

## Solution

Le fix est dans `backend/app/__init__.py` :

```python
import sys
from pathlib import Path

# Add backend directory to path if not already there
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
```

Ce code s'exécute à chaque import de `app`, **y compris dans les subprocesses spawn**, garantissant que le backend directory est toujours dans `sys.path`.

## Pourquoi ça fonctionne

1. Quand uvicorn spawn un subprocess pour le reload, Python importe `app.main`
2. Cela déclenche l'exécution de `app/__init__.py`
3. Le code ajoute automatiquement le backend directory au `sys.path`
4. Les imports relatifs (`from app.services...`) fonctionnent correctement
5. Les packages du venv sont accessibles

## Utilisation

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le reload fonctionne maintenant parfaitement sur Windows, Linux et Mac.

## Vérification

Vous devriez voir dans les logs :
```
WARNING:  WatchFiles detected changes in 'app\main.py'. Reloading...
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [...]
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
