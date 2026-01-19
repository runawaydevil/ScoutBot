"""Add file codes and security fields to pentaract_uploads

Revision ID: 20260119_112133
Revises: previous_revision
Create Date: 2026-01-19 11:21:33

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260119_112133'
down_revision = None  # Update this with your previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new fields to pentaract_uploads table"""
    
    # Add new columns
    with op.batch_alter_table('pentaract_uploads') as batch_op:
        # Add file_code column (unique code for each file)
        batch_op.add_column(sa.Column('fileCode', sa.String(), nullable=True))
        
        # Add original_filename column (preserve original name)
        batch_op.add_column(sa.Column('originalFilename', sa.String(), nullable=True))
        
        # Add mime_type column
        batch_op.add_column(sa.Column('mimeType', sa.String(), nullable=True))
        
        # Create index on file_code for fast lookups
        batch_op.create_index('idx_file_code', ['fileCode'], unique=True)
    
    # Migrate existing data: generate codes for existing files
    connection = op.get_bind()
    
    # Get existing records
    result = connection.execute(sa.text(
        "SELECT id, filePath, remotePath FROM pentaract_uploads WHERE fileCode IS NULL"
    ))
    
    import secrets
    import string
    from pathlib import Path
    
    def generate_code():
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(6))
    
    # Update each record
    for row in result:
        upload_id = row[0]
        file_path = row[1]
        remote_path = row[2]
        
        # Generate unique code
        code = generate_code()
        
        # Extract original filename from file_path
        original_filename = Path(file_path).name if file_path else "unknown"
        
        # Update record
        connection.execute(
            sa.text(
                "UPDATE pentaract_uploads "
                "SET fileCode = :code, originalFilename = :filename "
                "WHERE id = :id"
            ),
            {"code": code, "filename": original_filename, "id": upload_id}
        )
    
    # Make fileCode and originalFilename NOT NULL after migration
    with op.batch_alter_table('pentaract_uploads') as batch_op:
        batch_op.alter_column('fileCode', nullable=False)
        batch_op.alter_column('originalFilename', nullable=False)


def downgrade() -> None:
    """Remove new fields from pentaract_uploads table"""
    
    with op.batch_alter_table('pentaract_uploads') as batch_op:
        # Drop index
        batch_op.drop_index('idx_file_code')
        
        # Drop columns
        batch_op.drop_column('mimeType')
        batch_op.drop_column('originalFilename')
        batch_op.drop_column('fileCode')
