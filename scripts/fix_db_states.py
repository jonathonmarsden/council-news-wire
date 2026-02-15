
from sqlalchemy import update, func

from core.database import Database
from core.models import Article

def fix_state_case():
    db = Database()
    session = db.get_session()

    print("Updating state codes to uppercase...")
    result = session.execute(update(Article).values(state=func.upper(Article.state)))
    print(f"Updated {result.rowcount} rows.")

    session.commit()
    session.close()

if __name__ == "__main__":
    fix_state_case()
