from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime

Category = str  # could be narrowed later

@dataclass
class ArtistRecord:
    folder: str
    names: List[str]
    category: Category = "auto"
    source: Literal['auto','user'] = 'auto'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'folder': self.folder,
            'names': self.names,
            'category': self.category,
            'source': self.source,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ArtistRecord':
        return ArtistRecord(
            folder=data['folder'],
            names=list(data.get('names', [])),
            category=data.get('category','auto'),
            source=data.get('source','auto'),
            created_at=data.get('created_at', datetime.now().isoformat()),
            updated_at=data.get('updated_at', datetime.now().isoformat()),
        )
