from sqlalchemy import *
from migrate import *
import migrate.changeset

metadata = MetaData(migrate_engine)

harvested_document_table = Table('harvested_document', metadata,
    Column('url', UnicodeText, nullable=False),
    Column('source_id', UnicodeText, ForeignKey('harvest_source.id')),
    Column('package_id', UnicodeText, ForeignKey('package.id')),
)

def upgrade():
    harvested_document_table.c.url.drop()
    harvested_document_table.c.source_id.add()
    harvested_document_table.c.package_id.add()

def downgrade():
    raise NotImplementedError()

