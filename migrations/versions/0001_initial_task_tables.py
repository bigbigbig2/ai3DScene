from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_task_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("domain", sa.String(length=128), nullable=False),
        sa.Column("input_image_path", sa.Text(), nullable=False),
        sa.Column("semantic_mode", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "stage_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("worker_pid", sa.Integer(), nullable=True),
        sa.Column("gpu_id", sa.Integer(), nullable=True),
        sa.Column("peak_gpu_memory_mib", sa.Integer(), nullable=True),
        sa.Column("request_path", sa.Text(), nullable=True),
        sa.Column("response_path", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback_path", sa.Text(), nullable=True),
    )
    op.create_index("ix_stage_runs_task_id", "stage_runs", ["task_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])

    op.create_table(
        "corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("correction_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_corrections_task_id", "corrections", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_corrections_task_id", table_name="corrections")
    op.drop_table("corrections")
    op.drop_index("ix_artifacts_task_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_stage_runs_task_id", table_name="stage_runs")
    op.drop_table("stage_runs")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
