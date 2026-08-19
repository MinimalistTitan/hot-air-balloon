"""add RBAC tables for roles and site assignments

Revision ID: 20260818_0003
Revises: 20260814_0002
Create Date: 2026-08-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0003"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        "roles",
        sa.Column("name", sa.String(50), primary_key=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
    )

    # Create permissions table
    op.create_table(
        "permissions",
        sa.Column("name", sa.String(50), primary_key=True, nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
    )

    # Create role_permissions join table
    op.create_table(
        "role_permissions",
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.Column("permission_name", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_name"], ["roles.name"], name=op.f("fk_role_permissions_role_name_roles")
        ),
        sa.ForeignKeyConstraint(
            ["permission_name"],
            ["permissions.name"],
            name=op.f("fk_role_permissions_permission_name_permissions"),
        ),
        sa.PrimaryKeyConstraint("role_name", "permission_name", name=op.f("pk_role_permissions")),
    )

    # Create user_roles join table
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["role_name"], ["roles.name"], name=op.f("fk_user_roles_role_name_roles")
        ),
        sa.PrimaryKeyConstraint("user_id", "role_name", name=op.f("pk_user_roles")),
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)

    # Create user_sites join table for site scoping
    op.create_table(
        "user_sites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("site_code", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_sites_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["site_code"], ["sites.code"], name=op.f("fk_user_sites_site_code_sites")
        ),
        sa.PrimaryKeyConstraint("user_id", "site_code", name=op.f("pk_user_sites")),
    )
    op.create_index(op.f("ix_user_sites_user_id"), "user_sites", ["user_id"], unique=False)

    # Seed permissions
    permissions = [
        ("users:manage", "Manage users"),
        ("roles:manage", "Manage roles"),
        ("work_orders:read", "Read work orders"),
        ("work_orders:update", "Update work orders"),
        ("work_orders:change_status", "Change work order status"),
        ("work_orders:complete", "Complete work orders"),
        ("work_orders:cancel", "Cancel work orders"),
        ("maintenance_tickets:read", "Read maintenance tickets"),
        ("maintenance_tickets:update", "Update maintenance tickets"),
        ("assets:read", "Read assets"),
        ("assets:update", "Update assets"),
        ("spare_parts:read", "Read spare parts"),
        ("spare_parts:issue", "Issue spare parts"),
        ("spare_parts:adjust_inventory", "Adjust inventory"),
        ("production_schedule:read", "Read production schedules"),
        ("production_schedule:update", "Update production schedules"),
        ("production_schedule:publish", "Publish production schedules"),
        ("documents:read", "Read documents"),
        ("documents:upload", "Upload documents"),
        ("documents:delete", "Delete documents"),
        ("reports:read", "Read reports"),
        ("audit_logs:read", "Read audit logs"),
    ]

    for perm_name, description in permissions:
        op.execute(
            sa.insert(sa.table("permissions", sa.column("name"), sa.column("description"))).values(
                name=perm_name, description=description
            )
        )

    # Seed roles (permission assignments are defined in the domain, not seeded here)
    roles = [
        ("system_administrator", "System Administrator - all permissions"),
        ("operations_manager", "Operations Manager"),
        ("read_only_analyst", "Read-Only Analyst"),
        ("maintenance_technician", "Maintenance Technician"),
        ("maintenance_supervisor", "Maintenance Supervisor"),
    ]

    for role_name, description in roles:
        op.execute(
            sa.insert(sa.table("roles", sa.column("name"), sa.column("description"))).values(
                name=role_name, description=description
            )
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_sites_user_id"), table_name="user_sites")
    op.drop_table("user_sites")
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
