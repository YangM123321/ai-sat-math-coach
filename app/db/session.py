from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
s=get_settings(); args={'check_same_thread':False} if s.database_url.startswith('sqlite') else {}
engine=create_engine(s.database_url,connect_args=args)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
