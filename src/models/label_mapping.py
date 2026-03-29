from sqlalchemy import Column, Integer, Sequence, String

from src.db import Base, metadata


class LabelMapping(Base):
    """Maps raw label strings to canonical forms.

    match_type values:
      word         — word-token normalisation (applied word-by-word to label tokens)
      strip_suffix — strip raw_label suffix from the input label to get canonical form
      substring    — if raw_label is a substring of the input label, return canonical_label
    """

    __tablename__ = "label_mapping"
    __table_args__ = {"extend_existing": True}

    id = Column(
        Integer,
        Sequence("label_mapping_seq", metadata=metadata),
        primary_key=True,
        index=True,
        unique=True,
    )
    raw_label = Column(String(255), unique=True, nullable=False, index=True)
    canonical_label = Column(String(255), nullable=False)
    match_type = Column(String(32), nullable=False)
    exclude_pattern = Column(String(255), nullable=True)

    def __eq__(self, other):
        return (
            self.id == other.id and self.__class__.__name__ == other.__class__.__name__
        )

    def __hash__(self):
        return hash(self.__class__.__name__ + str(self.id))
