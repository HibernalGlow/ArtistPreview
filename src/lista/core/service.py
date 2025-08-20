from __future__ import annotations
from pathlib import Path
from typing import List, Iterable
from .models import ArtistRecord
from .store import ArtistStore
from datetime import datetime
import json

class ArtistService:
    def __init__(self, store: ArtistStore, config: dict):
        self.store = store
        self.config = config

    def scan_folder(self, base: Path, category: str = 'auto') -> int:
        if not base.exists():
            return 0
        records: List[ArtistRecord] = []
        for f in base.iterdir():
            if f.is_dir() and f.name.startswith('['):
                clean_name = f.name[1:-1] if f.name.endswith(']') else f.name[1:]
                names: List[str] = []
                if '(' in clean_name:
                    circle_part = clean_name.split('(')[0].strip()
                    artist_part = clean_name.split('(')[1].rstrip(')').strip()
                    artist_names = [n.strip() for n in artist_part.split('、') if n.strip()]
                    circle_names = [n.strip() for n in circle_part.split('、') if n.strip()]
                    names.extend(artist_names + circle_names)
                else:
                    names = [clean_name]
                exclude = self.config.get('exclude_keywords', [])
                valid = [n for n in names if not any(k in n for k in exclude)]
                if not valid:
                    continue
                records.append(ArtistRecord(folder=f.name, names=valid, category=category, source='auto'))
        return self.store.bulk_upsert(records)

    def add_manual(self, folder: str, names: List[str], category: str):
        self.store.upsert(ArtistRecord(folder=folder, names=names, category=category, source='user'))

    def set_category(self, name_or_folder: str, category: str) -> int:
        return self.store.set_category(name_or_folder, category)

    def remove(self, name_or_folder: str) -> int:
        return self.store.remove(name_or_folder)

