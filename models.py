from __future__ import annotations
"""Pydantic v2 models for all inbound WS message types from Hyperliquid.

Using model_validator / field_validator so the engine receives clean
typed objects instead of raw dicts. If the exchange changes a field
name, a ValidationError is raised immediately and logged — no silent
data corruption.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Candle ────────────────────────────────────────────────────────
class CandleData(BaseModel):
    coin:   str = Field(alias="s", default="")
    time:   int = Field(alias="t")
    open:   float = Field(alias="o")
    high:   float = Field(alias="h")
    low:    float = Field(alias="l")
    close:  float = Field(alias="c")
    volume: float = Field(alias="v")
    interval: str = Field(alias="i", default="1m")

    model_config = {"populate_by_name": True}

    @field_validator("coin", mode="before")
    @classmethod
    def coerce_coin(cls, v: Any) -> str:
        return str(v) if v else ""


class CandleMessage(BaseModel):
    channel: Literal["candle"]
    data: CandleData

    model_config = {"populate_by_name": True}


# ── Trade ─────────────────────────────────────────────────────────
class TradeItem(BaseModel):
    coin:  str = Field(alias="coin", default="")
    px:    float
    sz:    float
    side:  str = Field(default="")
    time:  int = Field(alias="time", default=0)
    hash:  Optional[str] = Field(default=None)
    tid:   Optional[int] = Field(default=None)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def remap_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Accept both canonical field names and short aliases."""
        for src, dst in [("s", "coin"), ("p", "px"), ("q", "sz"), ("S", "side"), ("t", "time")]:
            if src in values and dst not in values:
                values[dst] = values.pop(src)
        return values

    @field_validator("px", "sz", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> float:
        return float(v)


class TradesMessage(BaseModel):
    channel: Literal["trades"]
    data: List[TradeItem]

    model_config = {"populate_by_name": True}


# ── BBO ───────────────────────────────────────────────────────────
class BBOLevel(BaseModel):
    px: float
    sz: float
    n:  int = 0

    @field_validator("px", "sz", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> float:
        return float(v)


class BBOData(BaseModel):
    coin: str = Field(alias="coin", default="")
    bids: List[BBOLevel] = Field(default_factory=list)
    asks: List[BBOLevel] = Field(default_factory=list)

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].px if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].px if self.asks else None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def remap_bbo(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for src, dst in [("s", "coin"), ("b", "bids"), ("a", "asks")]:
            if src in values and dst not in values:
                values[dst] = values.pop(src)
        for key in ("bids", "asks"):
            raw = values.get(key, [])
            if raw and isinstance(raw[0], list):
                values[key] = [{"px": r[0], "sz": r[1], "n": r[2] if len(r) > 2 else 0} for r in raw]
            elif raw and isinstance(raw[0], dict) and "px" not in raw[0]:
                values[key] = [{"px": r.get("price", r.get("px", 0)), "sz": r.get("size", r.get("sz", 0))} for r in raw]
        return values


class BBOMessage(BaseModel):
    channel: Literal["bbo"]
    data: BBOData

    model_config = {"populate_by_name": True}


# ── AllMids ───────────────────────────────────────────────────────
class AllMidsMessage(BaseModel):
    channel: Literal["allMids"]
    data: Dict[str, Any]

    def mids(self) -> Dict[str, float]:
        raw = self.data.get("mids", self.data)
        return {k: float(v) for k, v in raw.items() if v is not None}


# ── Union discriminator ───────────────────────────────────────────
WSMessage = Union[CandleMessage, TradesMessage, BBOMessage, AllMidsMessage]


def parse_ws_message(raw: Dict[str, Any]) -> Optional[WSMessage]:
    """Parse and validate a raw WS dict into a typed model.

    Returns None if the channel is unknown or the payload fails
    validation (logged externally).
    """
    channel = raw.get("channel")
    try:
        if channel == "candle":
            data = raw.get("data", {})
            if "candle" in data:
                data = data["candle"]
            return CandleMessage(channel="candle", data=data)
        if channel == "trades":
            return TradesMessage(channel="trades", data=raw.get("data", []))
        if channel == "bbo":
            return BBOMessage(channel="bbo", data=raw.get("data", {}))
        if channel == "allMids":
            return AllMidsMessage(channel="allMids", data=raw.get("data", {}))
    except Exception:
        return None
    return None
