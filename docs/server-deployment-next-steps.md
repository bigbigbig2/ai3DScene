# Server Deployment Next Steps

This repository now contains the Stage 0-8 engineering skeleton and a Fake
Pipeline that exercises the full task lifecycle without GPU models.

Before treating Stage 5-8 as complete on the target server, verify the real
model path:

1. Create and activate `/home/ai3d/envs/scene-core`.
2. Install this package with development dependencies.
3. Copy `.env.example` to `.env` and adjust paths if needed.
4. Start the API and verify:

   ```bash
   /home/ai3d/envs/scene-core/bin/uvicorn scene_spatial.api.app:app --host 0.0.0.0 --port 8180
   curl http://127.0.0.1:8180/health
   curl http://127.0.0.1:8180/ready
   ```

5. Run the Fake Pipeline once:

   ```bash
   /home/ai3d/envs/scene-core/bin/python -m pytest tests/integration/test_fake_pipeline.py
   ```

6. Create `/home/ai3d/envs/scene-sam3` and replace the real body of
   `model_workers/sam3_worker.py`.
7. Create `/home/ai3d/envs/scene-moge2` and replace the real body of
   `model_workers/moge2_worker.py`.
8. Set `SCENE_FAKE_MODELS=false` only after both workers pass standalone smoke
   tests.
9. Install the two systemd units from `deploy/systemd/`.

The API and Worker should be the only long-running services. SAM and MoGe stay
short-lived subprocesses launched by the Worker.

Fake smoke helper:

```bash
/home/ai3d/envs/scene-core/bin/python scripts/smoke_fake_pipeline.py
```

Model smoke helpers:

```bash
/home/ai3d/envs/scene-core/bin/python scripts/verify_sam3.py --fake
/home/ai3d/envs/scene-core/bin/python scripts/verify_moge2.py --fake
bash scripts/inspect_gpu.sh
```
