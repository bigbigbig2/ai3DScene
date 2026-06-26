# Scene Spatial Debug Console

Vue 3 + Vite frontend for debugging the Scene Spatial PoC backend.

Default backend target:

```text
http://10.7.3.50:8181
```

Run locally:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5174
```

The Vite dev server proxies these paths to the backend:

```text
/api
/health
/ready
```

First-version capabilities:

1. Check backend `/health` and `/ready`.
2. Upload an image and create a task.
3. Import a semantic proposal JSON.
4. Run or rerun a task from any pipeline stage.
5. Poll task status and artifacts.
6. Preview image, JSON, text, and log artifacts.
7. Load `SpatialSceneObservation` result JSON.
8. Submit correction payloads.


