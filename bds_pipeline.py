#!/usr/bin/env python3
"""
BDS Pipeline — Birdeye Data Sprint 3
====================================
Multi-source crypto data pipeline: fetch → convert → clean → validate → export.

Currently sources CoinGecko (public) as demo — drop-in replaceable with
Birdeye Data Services (BDS) API when key is provided.

Usage:
    python bds_pipeline.py
    python bds_pipeline.py --export csv --output dashboard.csv
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import urllib.request
from typing import Any

# ── Data-toolkit import ────────────────────────────────────
sys.path.insert(0, "/home/alexnexus/.openclaw/workspace/portfolio/data-toolkit/src")

from convert import DataConverter
from clean import DataCleaner
from validate import DataValidator

# ╔══════════════════════════════════════════════════════════╗
# ║  SOURCE A: COINGECKO (Demo)                            ║
# ║  Replace with BDS API when key is available             ║
# ╚══════════════════════════════════════════════════════════╝

COINGECKO_API = "https://api.coingecko.com/api/v3"

def fetch_coingecko_top100() -> list[dict]:
    """Fetch top 100 tokens from CoinGecko (free, no key)."""
    url = f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
    req = urllib.request.Request(url, headers={"User-Agent": "BDS-Pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_coingecko_global() -> dict:
    """Fetch global crypto market stats."""
    url = f"{COINGECKO_API}/global"
    req = urllib.request.Request(url, headers={"User-Agent": "BDS-Pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ╔══════════════════════════════════════════════════════════╗
# ║  SOURCE B: BIRDEYE DATA SERVICES (BDS)                 ║
# ║  Activate with: export BIRDEYE_API_KEY=your-key         ║
# ╚══════════════════════════════════════════════════════════╝

BIRDEYE_API = "https://public-api.birdeye.so"

def fetch_birdeye_tokenlist(api_key: str) -> list[dict]:
    """Fetch token list from Birdeye Data Services."""
    url = f"{BIRDEYE_API}/v1/tokenlist"
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_birdeye_price(token_address: str, api_key: str) -> dict:
    """Fetch price for a specific token from BDS."""
    url = f"{BIRDEYE_API}/v1/token_price?address={token_address}"
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ╔══════════════════════════════════════════════════════════╗
# ║  PIPELINE ENGINE                                        ║
# ╚══════════════════════════════════════════════════════════╝

class CryptoDataPipeline:
    """
    Multi-source crypto data pipeline.
    
    Flow:
      Fetch → Normalize → Clean (dedup/null/normalize) → Validate → Export
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.converter = DataConverter()
        self.cleaner = DataCleaner()
        self.validator = DataValidator()
        self.run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

    def run(self, use_birdeye: bool = False) -> dict:
        """Execute the full pipeline."""
        print("=" * 65)
        print("  BDS PIPELINE — Crypto Data Processing Engine")
        print(f"  Run: {self.run_id}")
        print("=" * 65)

        # ── STEP 1: FETCH ────────────────────────────────
        print("\n📡 STEP 1: Fetching data from sources...")
        
        raw_data = {}
        try:
            raw_data["coingecko_top100"] = fetch_coingecko_top100()
            print(f"   ✅ CoinGecko: {len(raw_data['coingecko_top100'])} tokens fetched")
        except Exception as e:
            print(f"   ⚠️  CoinGecko: {e}")
            raw_data["coingecko_top100"] = []

        try:
            raw_data["coingecko_global"] = fetch_coingecko_global()
            total_mcap = raw_data["coingecko_global"].get("data", {}).get("total_market_cap", {}).get("usd", 0)
            print(f"   ✅ Global stats: ${total_mcap:,.0f} total market cap")
        except Exception as e:
            print(f"   ⚠️  Global stats: {e}")

        if use_birdeye:
            api_key = os.getenv("BIRDEYE_API_KEY")
            if api_key:
                try:
                    raw_data["birdeye_tokens"] = fetch_birdeye_tokenlist(api_key)
                    print(f"   ✅ Birdeye: {len(raw_data['birdeye_tokens'])} tokens")
                except Exception as e:
                    print(f"   ⚠️  Birdeye: {e}")

        # ── STEP 2: NORMALIZE ─────────────────────────────
        print("\n🔄 STEP 2: Normalizing to unified schema...")
        normalized = self._normalize_tokens(raw_data.get("coingecko_top100", []))
        print(f"   ✅ {len(normalized)} tokens normalized")

        # Save raw
        raw_path = self.output_dir / f"raw_{self.run_id}.json"
        json.dump(raw_data, open(raw_path, "w"), indent=2, default=str)
        print(f"   📄 Raw data: {raw_path}")

        # ── STEP 3: CLEAN ────────────────────────────────
        print("\n🧹 STEP 3: Cleaning data...")
        
        # Remove duplicates (by symbol)
        before = len(normalized)
        normalized = self.cleaner.remove_duplicates(normalized, key="symbol")
        dupes_removed = before - len(normalized)
        
        # Handle nulls (numeric fields get 0, string fields get N/A)
        normalized = self.cleaner.handle_nulls(normalized, action="replace", replacement=0)
        
        # Normalize numbers (6 decimal precision for prices)
        normalized = self.cleaner.normalize_numbers(normalized, precision=6)
        
        print(f"   ✅ Removed {dupes_removed} duplicates")
        print(f"   ✅ Nulls replaced, numbers normalized (6dp)")
        print(f"   📊 {len(normalized)} clean tokens")

        # ── STEP 4: ENRICH ────────────────────────────────
        print("\n📈 STEP 4: Enriching with computed metrics...")
        enriched = self._enrich_with_metrics(normalized)
        
        # Clean strings AFTER enrichment (on non-numeric fields)
        enriched = self.cleaner.normalize_strings(enriched, ["trim"])
        top_gainers = sorted(enriched, key=lambda x: x.get("price_change_24h_pct", 0), reverse=True)[:5]
        print(f"   ✅ Added: volatility_flag, mcap_tier, price_category")
        print(f"   🔥 Top gainers: {', '.join(t['symbol'].upper() for t in top_gainers[:3])}")

        # ── STEP 5: VALIDATE ──────────────────────────────
        print("\n✅ STEP 5: Validating data quality...")
        
        rules = {
            "current_price": {"min": 0},
            "market_cap": {"min": 0},
            "total_volume": {"min": 0},
        }
        valid, errors = self.validator.validate_custom_rules(enriched, rules)
        
        if valid:
            print("   ✅ All data quality rules passed")
        else:
            print(f"   ⚠️  {len(errors)} validation issues:")
            for e in errors[:5]:
                print(f"      - {e}")

        # ── STEP 6: EXPORT ────────────────────────────────
        print("\n📤 STEP 6: Exporting...")
        self._export(enriched, self.run_id)
        
        # ── Summary ────────────────────────────────────────
        print("\n" + "=" * 65)
        print(f"  ✅ PIPELINE COMPLETE — {len(enriched)} tokens processed")
        print(f"  📂 Output: {self.output_dir}/")
        print("=" * 65)
        
        return {
            "run_id": self.run_id,
            "tokens_processed": len(enriched),
            "duplicates_removed": dupes_removed,
            "validation_passed": valid,
            "exported_formats": ["json", "csv"],
        }

    def _normalize_tokens(self, tokens: list[dict]) -> list[dict]:
        """Normalize raw token data to unified schema."""
        return [
            {
                "id": t.get("id", ""),
                "symbol": t.get("symbol", "").upper(),
                "name": t.get("name", ""),
                "current_price": t.get("current_price"),
                "market_cap": t.get("market_cap"),
                "market_cap_rank": t.get("market_cap_rank"),
                "total_volume": t.get("total_volume"),
                "high_24h": t.get("high_24h"),
                "low_24h": t.get("low_24h"),
                "price_change_24h": t.get("price_change_24h"),
                "price_change_24h_pct": t.get("price_change_percentage_24h"),
                "circulating_supply": t.get("circulating_supply"),
                "total_supply": t.get("total_supply"),
                "ath": t.get("ath"),
                "ath_change_pct": t.get("ath_change_percentage"),
                "ath_date": t.get("ath_date"),
                "source": "coingecko",
                "fetched_at": datetime.utcnow().isoformat(),
            }
            for t in tokens
        ]

    def _enrich_with_metrics(self, tokens: list[dict]) -> list[dict]:
        """Add computed metrics and flags."""
        for t in tokens:
            price = t.get("current_price") or 0
            mcap = t.get("market_cap") or 0
            vol = t.get("total_volume") or 0
            change = t.get("price_change_24h_pct") or 0

            # Volatility flag
            if abs(change) > 10:
                t["volatility_flag"] = "HIGH"
            elif abs(change) > 5:
                t["volatility_flag"] = "MEDIUM"
            else:
                t["volatility_flag"] = "LOW"

            # Market cap tier
            if mcap > 10_000_000_000:
                t["mcap_tier"] = "LARGE_CAP"
            elif mcap > 1_000_000_000:
                t["mcap_tier"] = "MID_CAP"
            elif mcap > 100_000_000:
                t["mcap_tier"] = "SMALL_CAP"
            else:
                t["mcap_tier"] = "MICRO_CAP"

            # Price category
            if price > 1000:
                t["price_category"] = "HIGH"
            elif price > 1:
                t["price_category"] = "MEDIUM"
            elif price > 0:
                t["price_category"] = "LOW"
            else:
                t["price_category"] = "ZERO"

            # Volume/MCap ratio (liquidity proxy)
            t["volume_mcap_ratio"] = round(vol / mcap, 4) if mcap > 0 else 0

        return tokens

    def _export(self, data: list[dict], run_id: str):
        """Export to multiple formats."""
        json_path = self.output_dir / f"tokens_{run_id}.json"
        csv_path = self.output_dir / f"tokens_{run_id}.csv"

        # JSON
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"   📄 JSON: {json_path} ({len(data)} records)")

        # CSV (with headers)
        if data:
            import csv
            keys = list(data[0].keys())
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
            print(f"   📊 CSV:  {csv_path} ({len(data)} rows, {len(keys)} columns)")

        # Console summary
        summary = self._generate_summary(data)
        summary_path = self.output_dir / f"summary_{run_id}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"   📋 Summary: {summary_path}")

    def _generate_summary(self, tokens: list[dict]) -> dict:
        """Generate human-readable summary."""
        total_mcap = sum(t.get("market_cap") or 0 for t in tokens)
        total_vol = sum(t.get("total_volume") or 0 for t in tokens)
        
        volatility = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        tiers = {"LARGE_CAP": 0, "MID_CAP": 0, "SMALL_CAP": 0, "MICRO_CAP": 0}
        for t in tokens:
            v = t.get("volatility_flag", "LOW")
            m = t.get("mcap_tier", "MICRO_CAP")
            volatility[v] = volatility.get(v, 0) + 1
            tiers[m] = tiers.get(m, 0) + 1

        return {
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_tokens": len(tokens),
            "total_market_cap_usd": total_mcap,
            "total_24h_volume_usd": total_vol,
            "volatility_breakdown": volatility,
            "mcap_tier_breakdown": tiers,
            "avg_volume_mcap_ratio": round(
                sum(t.get("volume_mcap_ratio", 0) for t in tokens) / max(len(tokens), 1), 4
            ),
        }


# ╔══════════════════════════════════════════════════════════╗
# ║  MAIN                                                     ║
# ╚══════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BDS Crypto Data Pipeline — Sprint 3")
    parser.add_argument("--birdeye", action="store_true", help="Use Birdeye BDS API (needs $BIRDEYE_API_KEY)")
    parser.add_argument("--export", default="all", choices=["json", "csv", "all"])
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    pipeline = CryptoDataPipeline(output_dir=args.output)

    try:
        result = pipeline.run(use_birdeye=args.birdeye)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
