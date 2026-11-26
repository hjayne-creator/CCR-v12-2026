"""Seed SGS Engineering client from machine-readable rules pack."""
from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.engine.rules import load_client_rules
from app.models.db import Client, get_engine, init_db

logger = logging.getLogger(__name__)

SGS_SETTINGS = {
    "definitive_identifiers": ["manufacturer product code", "manufacturer model"],
    "banned_unsupported_claims": [
        "best", "safest", "professional-grade", "industrial", "UK-made", "commercial use",
    ],
    "uk_spelling": True,
    "allowed_site_benefits": [
        "UK customer support",
        "Derby showroom / trade counter",
        "Available warranty and service support",
        "Delivery options",
        "Return policy",
    ],
}


def seed_sgs() -> Client:
    init_db()
    pack = load_client_rules("sgs-engineering")
    with Session(get_engine()) as session:
        client = session.exec(select(Client).where(Client.slug == "sgs-engineering")).first()
        if client is None:
            client = Client(
                slug="sgs-engineering",
                name="SGS Engineering",
                domain="sgs-engineering.com",
                client_domains=["sgs-engineering.com"],
                untrusted_domains=[
                    "ebay.co.uk", "ebay.com", "gumtree.com", "preloved.co.uk",
                    "facebook.com", "reddit.com", "youtube.com", "quora.com",
                ],
                owned_brands=["SGS", "NitroLift", "Rikä", "Rika"],
                market_country="uk",
                language="en-GB",
                google_domain="google.co.uk",
                currency="GBP",
                competitor_count=3,
                max_words=1500,
                title_max_chars=150,
                rules_version=pack.version,
                settings=SGS_SETTINGS,
            )
            session.add(client)
            session.commit()
            session.refresh(client)
            logger.info("Seeded SGS Engineering client id=%s rules=%s", client.id, pack.version)
        else:
            client.rules_version = pack.version
            client.settings = SGS_SETTINGS
            session.add(client)
            session.commit()
            session.refresh(client)
            logger.info("Updated SGS Engineering client id=%s", client.id)
        return client


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_sgs()
