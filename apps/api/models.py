# -*- coding: utf-8 -*-
import uuid
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, ARRAY, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class WildcardInventory(Base):
    __tablename__ = "wildcard_inventories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    common = Column(Integer, default=0)
    uncommon = Column(Integer, default=0)
    rare = Column(Integer, default=0)
    mythic = Column(Integer, default=0)

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    oracle_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    oracle_text = Column(Text, nullable=True)
    mana_cost = Column(String, nullable=True)
    mana_value = Column(Float, default=0.0)
    colors = Column(ARRAY(String), default=[])
    color_identity = Column(ARRAY(String), default=[])
    types = Column(ARRAY(String), default=[])
    keywords = Column(ARRAY(String), default=[])
    released_at = Column(Date, nullable=True)

    printings = relationship("CardPrint", back_populates="card", cascade="all, delete-orphan")
    legalities = relationship("CardLegality", back_populates="card", uselist=False, cascade="all, delete-orphan")
    tags = relationship("CardTag", back_populates="card", cascade="all, delete-orphan")
    meta_stats = relationship("MetaCardStat", back_populates="card", cascade="all, delete-orphan")

class CardTag(Base):
    __tablename__ = "card_tags"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    tag = Column(String, index=True, nullable=False)
    score = Column(Float, default=1.0)
    source = Column(String, default="manual")

    card = relationship("Card", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("card_id", "tag", name="uq_card_tag"),
    )

class CardSynergy(Base):
    __tablename__ = "card_synergies"
    id = Column(Integer, primary_key=True, index=True)
    card_a_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    card_b_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    synergy_type = Column(String, nullable=False)
    score = Column(Float, default=0.0)
    confidence = Column(Float, default=1.0)
    reason = Column(String, nullable=True)
    format = Column(String, default="all", index=True)

    card_a = relationship("Card", foreign_keys=[card_a_id])
    card_b = relationship("Card", foreign_keys=[card_b_id])

    __table_args__ = (
        UniqueConstraint("card_a_id", "card_b_id", name="uq_card_synergy"),
    )

class CardPrint(Base):
    __tablename__ = "card_prints"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    scryfall_id = Column(String, unique=True, index=True)
    set_code = Column(String, index=True)
    collector_number = Column(String)
    rarity = Column(String, index=True)

    card = relationship("Card", back_populates="printings")

class CardLegality(Base):
    __tablename__ = "card_legalities"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, unique=True) # Unique constraint fixed here
    standard = Column(Boolean, default=False)
    alchemy = Column(Boolean, default=False)
    explorer = Column(Boolean, default=False)
    historic = Column(Boolean, default=False)
    timeless = Column(Boolean, default=False)
    brawl = Column(Boolean, default=False)
    rotates_on = Column(String, nullable=True)

    card = relationship("Card", back_populates="legalities")

class Deck(Base):
    __tablename__ = "decks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    archetype = Column(String, index=True, nullable=True)
    format = Column(String, index=True, nullable=False)
    tier = Column(Integer, nullable=True)
    winrate = Column(Float, nullable=True)
    meta_share = Column(Float, nullable=True)
    source = Column(String, nullable=True)
    source_url = Column(Text, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    cards = relationship("DeckCard", back_populates="deck", cascade="all, delete-orphan")
    analyses = relationship("DeckAnalysis", back_populates="deck", cascade="all, delete-orphan")

class DeckCard(Base):
    __tablename__ = "deck_cards"
    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, default=1)

    deck = relationship("Deck", back_populates="cards")
    card = relationship("Card")

class MetaCardStat(Base):
    __tablename__ = "meta_card_stats"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    format = Column(String, index=True, nullable=False)
    appearance_rate = Column(Float, default=0.0)
    winrate = Column(Float, default=0.0)
    decks_played = Column(Integer, default=0)

    card = relationship("Card", back_populates="meta_stats")

    __table_args__ = (
        UniqueConstraint("card_id", "format", name="uq_meta_card_format"),
    )

class DeckAnalysis(Base):
    __tablename__ = "deck_analyses"
    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    synergy_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    mana_score = Column(Float, default=0.0)
    meta_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)

    deck = relationship("Deck", back_populates="analyses")

class UserCollection(Base):
    __tablename__ = "user_collections"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card"),
    )

class MatchHistory(Base):
    __tablename__ = "match_histories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    player_id = Column(String, nullable=True)
    opponent_id = Column(String, nullable=True)
    deck_name = Column(String, index=True, nullable=True)
    result = Column(String, nullable=False) # Win / Loss
    format = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, nullable=True)
