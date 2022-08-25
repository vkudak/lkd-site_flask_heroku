"""add sat update field

Revision ID: 63dc798dbe80
Revises: 7cd7f54cc01d
Create Date: 2022-08-21 13:25:09.161805

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63dc798dbe80'
down_revision = '7cd7f54cc01d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('satellite', sa.Column('updated', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('satellite', 'updated')
    # ### end Alembic commands ###