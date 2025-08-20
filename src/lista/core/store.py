from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Iterable
from tinydb import TinyDB, Query
from .models import ArtistRecord
from datetime import datetime
import json

class ArtistStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db = TinyDB(self.db_path, ensure_ascii=False, indent=2, encoding='utf-8')
        self.table = self.db.table('artists')

    def upsert(self, record: ArtistRecord):
        q = Query()
        existing = self.table.get(q.folder == record.folder)
        if existing:
            record.created_at = existing.get('created_at', record.created_at)
            record.updated_at = datetime.now().isoformat()
            self.table.update(record.to_dict(), q.folder == record.folder)
        else:
            self.table.insert(record.to_dict())

    def bulk_upsert(self, records: Iterable[ArtistRecord]) -> int:
        count = 0
        for r in records:
            self.upsert(r)
            count += 1
        return count

    def list(self, category: Optional[str] = None) -> List[ArtistRecord]:
        if category in (None, 'all'):
            rows = self.table.all()
        else:
            q = Query()
            rows = self.table.search(q.category == category)
        return [ArtistRecord.from_dict(r) for r in rows]

    def search(self, keyword: str) -> List[ArtistRecord]:
        q = Query()
        kw = keyword.lower()
        rows = self.table.search(
            (q.folder.test(lambda v: kw in v.lower())) |
            (q.names.test(lambda arr: any(kw in n.lower() for n in arr)))
        )
        return [ArtistRecord.from_dict(r) for r in rows]

    def set_category(self, name_or_folder: str, category: str) -> int:
        q = Query()
        matched = self.table.search((q.folder == name_or_folder) | (q.names.any([name_or_folder])))
        for r in matched:
            self.table.update({'category': category, 'updated_at': datetime.now().isoformat()}, q.folder == r['folder'])
        return len(matched)

    def remove(self, name_or_folder: str) -> int:
        q = Query()
        removed = self.table.remove((q.folder == name_or_folder) | (q.names.any([name_or_folder])))
        return len(removed)

    def export(self, category: Optional[str], out_file: Path):
        data = [r.to_dict() for r in self.list(category)]
        out_file = Path(out_file)
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

