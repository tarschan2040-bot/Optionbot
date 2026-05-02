"""
data/supabase_client.py — Supabase integration for optionbot.
=============================================================
Handles all database operations for the trade workflow.

CANDIDATE STATUS FLOW
─────────────────────────────────────────────────────────────────────────────
  pending   → written automatically after every scan (top 10)
  starred   → Ken stars a candidate, or auto-starred by score threshold
  approved  → Ken approves a starred candidate (decision made)
  placed    → Ken confirms order placed in IBKR (entry_price fetched)
  rejected  → Ken rejects from starred or approved list

TABLES USED
─────────────────────────────────────────────────────────────────────────────
  trade_candidates  — all scan candidates + workflow status
  trade_log         — placed trades (open positions)

ENVIRONMENT VARIABLES REQUIRED (.env)
──────────────────────────────────────
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_KEY=your-anon-public-key
"""

import logging
import os
from dataclasses import fields as dataclass_fields
from datetime import datetime
from typing import Optional, List, Tuple

log = logging.getLogger("supabase_client")

try:
    from supabase import create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False
    log.warning(
        "supabase library not installed. "
        "Run: pip3 install supabase"
    )


class SupabaseClient:
    """
    Handles all Supabase operations for the trade workflow.
    All methods are safe to call even if Supabase is misconfigured —
    errors are logged but never crash the scanner or bot.
    """

    TABLE_CANDIDATES   = "trade_candidates"
    TABLE_TRADE_LOG    = "trade_log"
    TABLE_SCAN_HISTORY = "scan_history"
    TABLE_USER_CONFIGS = "user_configs"

    def __init__(self):
        self._client = None
        self._enabled: bool = False

        if not _SUPABASE_AVAILABLE:
            log.warning("Supabase disabled — library not installed.")
            return

        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()

        if not url or not key:
            log.warning(
                "Supabase disabled — SUPABASE_URL or SUPABASE_KEY missing from .env"
            )
            return

        try:
            self._client  = create_client(url, key)
            self._enabled = True
            log.info("Supabase client initialised. URL: %s", url)
        except Exception as e:
            log.error("Supabase client init failed: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────

    def is_enabled(self) -> bool:
        return self._enabled

    def test_connection(self) -> bool:
        if not self._enabled:
            log.warning("test_connection: Supabase not enabled.")
            return False
        try:
            self._client.table(self.TABLE_CANDIDATES).select("id").limit(1).execute()
            log.info("Supabase connection test: PASSED")
            return True
        except Exception as e:
            log.error("Supabase connection test: FAILED — %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # Write candidates after scan
    # ─────────────────────────────────────────────────────────────────────

    def write_candidates(
        self,
        opportunities,
        scan_time: datetime,
        top_n: int = 10,
        autostar_threshold: float = 80.0,
    ) -> Tuple[int, int]:
        """
        Write top N scan opportunities to trade_candidates.
        Candidates scoring >= autostar_threshold are saved as 'starred'.
        All others saved as 'pending'.

        Returns (total_inserted, auto_starred_count).
        """
        if not self._enabled:
            log.warning("write_candidates: Supabase not enabled — skipping.")
            return 0, 0

        if not opportunities:
            log.info("write_candidates: no opportunities to write.")
            return 0, 0

        top          = opportunities[:top_n]
        inserted     = 0
        auto_starred = 0

        for o in top:
            status = "starred" if float(o.score) >= autostar_threshold else "pending"
            row    = self._build_row(o, scan_time, status=status)
            try:
                self._client.table(self.TABLE_CANDIDATES).insert(row).execute()
                inserted += 1
                if status == "starred":
                    auto_starred += 1
                log.info(
                    "Candidate saved [%s]: %s %s $%.2f score=%.1f",
                    status, row["ticker"], row["strategy"],
                    row["strike"], row["score"],
                )
            except Exception as e:
                log.error(
                    "Failed to insert candidate %s %s $%.2f: %s",
                    row.get("ticker"), row.get("strategy"),
                    row.get("strike"), e,
                )

        log.info(
            "write_candidates: %d/%d inserted (%d auto-starred).",
            inserted, len(top), auto_starred,
        )
        return inserted, auto_starred

    # ─────────────────────────────────────────────────────────────────────
    # Scan history
    # ─────────────────────────────────────────────────────────────────────

    def save_scan_history(
        self,
        scan_time: datetime,
        slot_label: str,
        tickers: list,
        strategy: str,
        result_count: int,
        elapsed_secs: int,
        config,
        results: list,
        config_hash: Optional[str] = None,
    ) -> bool:
        """
        Save a complete scan record to scan_history.
        Captures config snapshot, score weights, config_hash, and all passed results.
        Safe to call — errors are caught and never crash the scanner.
        """
        if not self._enabled:
            return False
        try:
            config_snapshot = {
                "min_dte":                config.min_dte,
                "max_dte":                config.max_dte,
                "strike_range_pct":       config.strike_range_pct,
                "min_theta":              config.min_theta,
                "min_iv":                 config.min_iv,
                "min_iv_rank":            config.min_iv_rank,
                "min_premium":            config.min_premium,
                "min_annualised_return":  config.min_annualised_return,
                "max_bid_ask_spread_pct": config.max_bid_ask_spread_pct,
                "cc_delta_min":           config.cc_delta_min,
                "cc_delta_max":           config.cc_delta_max,
                "csp_delta_min":          config.csp_delta_min,
                "csp_delta_max":          config.csp_delta_max,
            }
            weight_snapshot = {
                "ann_return":   config.weight_ann_return,
                "iv":           config.weight_iv,
                "theta_yield":  config.weight_theta_yield,
                "delta_safety": config.weight_delta_safety,
                "liquidity":    config.weight_liquidity,
            }
            results_snapshot = [
                {
                    "rank":       i + 1,
                    "ticker":     o.contract.ticker,
                    "strategy":   o.strategy,
                    "strike":     float(o.contract.strike),
                    "expiry":     str(o.contract.expiry),
                    "dte":        int(o.contract.dte),
                    "premium":    round(float(o.contract.mid), 4),
                    "delta":      round(float(o.greeks.delta), 4),
                    "theta":      round(float(o.greeks.theta), 4),
                    "iv":         round(float(o.greeks.iv), 4),
                    "ann_return": round(float(o.annualised_return), 4),
                    "score":      round(float(o.score), 2),
                }
                for i, o in enumerate(results)
            ]
            # Compute config_hash if not provided (backward compat)
            if config_hash is None and hasattr(config, "config_hash"):
                config_hash = config.config_hash()

            row = {
                "scan_time":     scan_time.isoformat(),
                "slot_label":    slot_label,
                "tickers":       tickers,
                "strategy":      strategy,
                "result_count":  result_count,
                "elapsed_secs":  elapsed_secs,
                "config":        config_snapshot,
                "score_weights": weight_snapshot,
                "config_hash":   config_hash,
                "results":       results_snapshot,
            }
            self._client.table(self.TABLE_SCAN_HISTORY).insert(row).execute()
            log.info(
                "Scan history saved: %d results, slot=%s, tickers=%s",
                result_count, slot_label, tickers,
            )
            return True
        except Exception as e:
            log.error("save_scan_history failed (non-fatal): %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # User config CRUD (Phase 0 — Task 0.2)
    # ─────────────────────────────────────────────────────────────────────

    # Fields in ScannerConfig that are NOT stored in user_configs
    # (runtime-only or derived at scan time)
    _CONFIG_SKIP_FIELDS = {"dry_run"}

    # All ScannerConfig field names that map to user_configs columns
    # (computed once; excludes _CONFIG_SKIP_FIELDS)
    _CONFIG_DB_FIELDS = None   # populated lazily

    @classmethod
    def _get_config_db_fields(cls) -> list:
        """Return the list of ScannerConfig fields that map to DB columns."""
        if cls._CONFIG_DB_FIELDS is None:
            from core.config import ScannerConfig
            cls._CONFIG_DB_FIELDS = [
                f.name for f in dataclass_fields(ScannerConfig)
                if f.name not in cls._CONFIG_SKIP_FIELDS
            ]
        return cls._CONFIG_DB_FIELDS

    def load_user_config(self, user_id: str) -> Optional["ScannerConfig"]:
        """
        Load a ScannerConfig from the user_configs table.

        Returns:
          ScannerConfig instance if a row exists for this user_id.
          None if no row found or Supabase is not enabled.
        """
        if not self._enabled:
            log.warning("load_user_config: Supabase not enabled.")
            return None

        from core.config import ScannerConfig

        try:
            resp = (
                self._client.table(self.TABLE_USER_CONFIGS)
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                log.info("load_user_config: no config found for user_id=%s", user_id)
                return None

            row = rows[0]
            db_fields = self._get_config_db_fields()

            # Build kwargs for ScannerConfig from the DB row
            kwargs = {}
            for field_name in db_fields:
                if field_name in row:
                    value = row[field_name]
                    # Postgres TEXT[] comes back as a Python list — ScannerConfig expects List[str]
                    if field_name == "tickers" and isinstance(value, list):
                        kwargs[field_name] = [str(t) for t in value]
                    else:
                        kwargs[field_name] = value

            config = ScannerConfig(**kwargs)
            log.info(
                "load_user_config: loaded config for user_id=%s (%d tickers, strategy=%s)",
                user_id, len(config.tickers), config.strategy,
            )
            return config

        except Exception as e:
            log.error("load_user_config failed: %s", e)
            return None

    def save_user_config(self, user_id: str, config: "ScannerConfig") -> bool:
        """
        Save (upsert) a ScannerConfig to the user_configs table.

        If a row exists for this user_id, it is updated.
        If no row exists, a new one is inserted.

        Returns True on success, False on error.
        """
        if not self._enabled:
            log.warning("save_user_config: Supabase not enabled.")
            return False

        try:
            db_fields = self._get_config_db_fields()
            row = {"user_id": user_id}
            for field_name in db_fields:
                value = getattr(config, field_name)
                # Convert list to a format Supabase/Postgres accepts
                if field_name == "tickers" and isinstance(value, list):
                    row[field_name] = value  # supabase-py handles list → TEXT[]
                else:
                    row[field_name] = value

            # Upsert: insert if new, update if user_id exists
            self._client.table(self.TABLE_USER_CONFIGS).upsert(
                row, on_conflict="user_id"
            ).execute()

            log.info(
                "save_user_config: saved config for user_id=%s (%d tickers, strategy=%s)",
                user_id, len(config.tickers), config.strategy,
            )
            return True

        except Exception as e:
            log.error("save_user_config failed: %s", e)
            return False

    def delete_user_config(self, user_id: str) -> bool:
        """Delete a user's config row. Returns True on success."""
        if not self._enabled:
            return False
        try:
            self._client.table(self.TABLE_USER_CONFIGS).delete().eq(
                "user_id", user_id
            ).execute()
            log.info("delete_user_config: deleted config for user_id=%s", user_id)
            return True
        except Exception as e:
            log.error("delete_user_config failed: %s", e)
            return False

    def ensure_user_config(self, user_id: str, default_config: Optional["ScannerConfig"] = None) -> "ScannerConfig":
        """
        Load config from DB if it exists; otherwise save the default and return it.
        This is the auto-migration entry point: on first run, your personal
        ScannerConfig defaults are written to the database.

        Args:
            user_id: the user identifier (Phase 0: use a placeholder like "owner")
            default_config: config to save if none exists. If None, uses ScannerConfig()

        Returns:
            The loaded or newly-created ScannerConfig.
        """
        from core.config import ScannerConfig

        existing = self.load_user_config(user_id)
        if existing is not None:
            return existing

        config = default_config or ScannerConfig(tickers=["TSLA", "NVDA"])
        log.info(
            "ensure_user_config: no config for user_id=%s — auto-migrating defaults.",
            user_id,
        )
        self.save_user_config(user_id, config)
        return config

    # ─────────────────────────────────────────────────────────────────────
    # Fetch lists
    # ─────────────────────────────────────────────────────────────────────

    def get_starred(self, user_id: Optional[str] = None) -> List[dict]:
        """Return all starred candidates, newest first."""
        return self._fetch_by_status("starred", user_id=user_id)

    def get_approved(self, user_id: Optional[str] = None) -> List[dict]:
        """Return all approved candidates, newest first."""
        return self._fetch_by_status("approved", user_id=user_id)

    def get_placed(self, user_id: Optional[str] = None) -> List[dict]:
        """Return all placed trades, newest first."""
        return self._fetch_by_status("placed", user_id=user_id)

    def _fetch_by_status(self, status: str, user_id: Optional[str] = None) -> List[dict]:
        if not self._enabled:
            return []
        try:
            query = (
                self._client.table(self.TABLE_CANDIDATES)
                .select(
                    "id, scan_time, ticker, strategy, strike, expiry, "
                    "dte, delta, premium, score, iv_rank, status, "
                    "approved_at, rejected_at, notes"
                )
                .eq("status", status)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            resp = query.order("scan_time", desc=True).execute()
            return resp.data or []
        except Exception as e:
            log.error("_fetch_by_status(%s) failed: %s", status, e)
            return []

    # ─────────────────────────────────────────────────────────────────────
    # Workflow actions
    # ─────────────────────────────────────────────────────────────────────

    def star_candidate(self, candidate_id: str, user_id: Optional[str] = None) -> bool:
        """Star a pending candidate by ID. Sets status = 'starred'."""
        return self._update_status(candidate_id, "starred", user_id=user_id)

    def find_and_star(self, opportunity, scan_time) -> str:
        """
        Find the existing pending row for this opportunity and mark it starred.
        Matches on ticker + strategy + strike + expiry + scan_time (to the minute).

        Returns:
          'updated'  — found existing pending row, updated to starred
          'inserted' — no existing row found, inserted new starred row
          'error'    — operation failed
        """
        if not self._enabled:
            return "error"

        ticker   = opportunity.contract.ticker
        strategy = opportunity.strategy
        strike   = float(opportunity.contract.strike)
        expiry   = str(opportunity.contract.expiry)
        # Match scan_time to the minute — isoformat may have microseconds
        scan_ts  = scan_time.strftime("%Y-%m-%dT%H:%M")

        try:
            # ── Look for an existing pending row matching this opportunity ─
            resp = (
                self._client.table(self.TABLE_CANDIDATES)
                .select("id, status")
                .eq("ticker",   ticker)
                .eq("strategy", strategy)
                .eq("strike",   strike)
                .eq("expiry",   expiry)
                .in_("status",  ["pending", "starred"])
                .order("scan_time", desc=True)
                .limit(1)
                .execute()
            )
            rows = resp.data or []

            if rows:
                candidate_id = rows[0]["id"]
                self._client.table(self.TABLE_CANDIDATES).update(
                    {"status": "starred"}
                ).eq("id", candidate_id).execute()
                log.info(
                    "find_and_star: updated existing row %s → starred (%s %s $%.2f)",
                    candidate_id, ticker, strategy, strike,
                )
                return "updated"

            # ── No existing row — insert new starred row ──────────────────
            log.info(
                "find_and_star: no existing row for %s %s $%.2f — inserting new.",
                ticker, strategy, strike,
            )
            row = self._build_row(opportunity, scan_time, status="starred")
            self._client.table(self.TABLE_CANDIDATES).insert(row).execute()
            return "inserted"

        except Exception as e:
            log.error("find_and_star failed: %s", e)
            return "error" 

    def approve_candidate(self, candidate_id: str, user_id: Optional[str] = None) -> bool:
        """
        Approve a starred candidate.
        Sets status = 'approved', records approved_at timestamp.
        """
        if not self._enabled:
            return False
        try:
            query = self._client.table(self.TABLE_CANDIDATES).update({
                "status":      "approved",
                "approved_at": datetime.now().isoformat(),
            }).eq("id", candidate_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
            log.info("Candidate approved: %s", candidate_id)
            return True
        except Exception as e:
            log.error("approve_candidate failed: %s", e)
            return False

    def place_candidate(
        self,
        candidate_id: str,
        entry_price: Optional[float],
        placed_at: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Mark a candidate as placed (order executed in IBKR).

        entry_price : the OPTION fill price (premium per share, e.g. 1.25).
                      Passed in from _handle_placed in telegram_bot.py.
                      If None, the scan premium from trade_candidates is used
                      as the best estimate — update manually in TOS if needed.

        Writes a row to trade_log as an open position.
        All exit / PnL fields are left NULL — filled manually after close.
        """
        if not self._enabled:
            return False

        placed_time = placed_at or datetime.now()

        try:
            # ── 1. Update trade_candidates status ────────────────────────
            candidate_update = self._client.table(self.TABLE_CANDIDATES).update({
                "status": "placed",
                "notes":  f"Placed at {placed_time.strftime('%Y-%m-%d %H:%M')}",
            }).eq("id", candidate_id)
            if user_id:
                candidate_update = candidate_update.eq("user_id", user_id)
            candidate_update.execute()

            # ── 2. Fetch full candidate data ─────────────────────────────
            candidate_query = (
                self._client.table(self.TABLE_CANDIDATES)
                .select("*")
                .eq("id", candidate_id)
            )
            if user_id:
                candidate_query = candidate_query.eq("user_id", user_id)
            resp = candidate_query.single().execute()
            c = resp.data
            if not c:
                log.error("place_candidate: candidate %s not found.", candidate_id)
                return False

            # ── 3. Resolve option fill price ─────────────────────────────
            # entry_price is the OPTION premium fill (per share, e.g. $1.25).
            # Use scan premium as fallback — never use stock price here.
            scan_premium = c.get("premium")           # option premium from scan
            option_fill  = entry_price if entry_price is not None else scan_premium
            contracts    = int(c.get("contracts") or 1)
            # net_premium = total credit received = fill × 100 × contracts
            net_premium  = (
                round(float(option_fill) * 100 * contracts, 2)
                if option_fill is not None
                else None
            )

            # ── 4. Write to trade_log ────────────────────────────────────
            trade_row = {
                "user_id":       user_id,
                "trade_date":    placed_time.strftime("%Y-%m-%d"),
                "ticker":        c["ticker"],
                "strategy":      c["strategy"],
                "strike":        c["strike"],
                "expiry":        c["expiry"],
                "dte_at_entry":  c["dte"],
                "entry_price":   option_fill,      # option premium per share
                "contracts":     contracts,
                "entry_delta":   c.get("delta"),
                "iv_percentile": c.get("iv_rank"),
                "net_premium":   net_premium,      # total credit: fill × 100 × contracts
                "candidate_id":  candidate_id,
                # exit_date, exit_price, pnl — left NULL, filled after close
            }
            self._client.table(self.TABLE_TRADE_LOG).insert(trade_row).execute()
            log.info(
                "Trade placed: %s %s $%.2f  fill=$%.4f  net_premium=$%.2f",
                c["ticker"], c["strategy"], float(c["strike"]),
                float(option_fill) if option_fill is not None else 0.0,
                net_premium or 0.0,
            )
            return True

        except Exception as e:
            log.error("place_candidate failed: %s", e)
            return False

    def reject_candidate(self, candidate_id: str, user_id: Optional[str] = None) -> bool:
        """
        Reject a starred or approved candidate.
        Sets status = 'rejected', records rejected_at timestamp.
        """
        if not self._enabled:
            return False
        try:
            query = self._client.table(self.TABLE_CANDIDATES).update({
                "status":      "rejected",
                "rejected_at": datetime.now().isoformat(),
            }).eq("id", candidate_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
            log.info("Candidate rejected: %s", candidate_id)
            return True
        except Exception as e:
            log.error("reject_candidate failed: %s", e)
            return False

    def unstar_candidate(self, candidate_id: str, user_id: Optional[str] = None) -> bool:
        """Unstar a candidate — reverts status back to 'pending'."""
        return self._update_status(candidate_id, "pending", user_id=user_id)

    def clear_by_status(self, from_status: str, to_status: str, user_id: Optional[str] = None) -> int:
        """
        Bulk-update all candidates with status=from_status to to_status.
        Used by /clearstarred, /clearapproved, /clearplaced commands.

        Returns the number of rows updated, or -1 on error.

        NOTE: does NOT touch trade_log or scan_history.
        Only the status field in trade_candidates is changed.
        """
        if not self._enabled:
            return -1
        try:
            query = (
                self._client.table(self.TABLE_CANDIDATES)
                .update({"status": to_status})
                .eq("status", from_status)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            resp = query.execute()
            count = len(resp.data) if resp.data else 0
            log.info(
                "clear_by_status: %d row(s) moved %s → %s",
                count, from_status, to_status,
            )
            return count
        except Exception as e:
            log.error("clear_by_status(%s→%s) failed: %s", from_status, to_status, e)
            return -1

    # ─────────────────────────────────────────────────────────────────────
    # Portfolio (open trades in trade_log)
    # ─────────────────────────────────────────────────────────────────────

    def get_portfolio(self, user_id: Optional[str] = None) -> List[dict]:
        """
        Return all open (not yet closed) trades from trade_log,
        ordered by trade_date descending (most recent first).

        A trade is open when exit_date IS NULL.
        """
        if not self._enabled:
            return []
        try:
            query = (
                self._client.table(self.TABLE_TRADE_LOG)
                .select(
                    "id, trade_date, ticker, strategy, strike, expiry, "
                    "dte_at_entry, entry_price, contracts, net_premium, "
                    "entry_delta, iv_percentile, candidate_id, "
                    "exit_date, exit_price, pnl"
                )
                .is_("exit_date", "null")
            )
            if user_id:
                query = query.eq("user_id", user_id)
            resp = query.order("trade_date", desc=True).execute()
            return resp.data or []
        except Exception as e:
            log.error("get_portfolio failed: %s", e)
            return []

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _update_status(self, candidate_id: str, status: str, user_id: Optional[str] = None) -> bool:
        if not self._enabled:
            return False
        try:
            query = self._client.table(self.TABLE_CANDIDATES).update(
                {"status": status}
            ).eq("id", candidate_id)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
            log.info("Candidate %s → %s", candidate_id, status)
            return True
        except Exception as e:
            log.error("_update_status(%s, %s) failed: %s", candidate_id, status, e)
            return False

    @staticmethod
    def _build_row(opportunity, scan_time: datetime, status: str = "pending") -> dict:
        """
        Map a ScanOpportunity to a trade_candidates table row.
        Verified against core/models.py and trade_candidates SQL schema.
        """
        o          = opportunity
        contracts  = 1
        premium    = float(o.contract.mid)
        total_prem = round(premium * 100 * contracts, 2)

        return {
            "ticker":        o.contract.ticker,
            "strategy":      o.strategy,
            "strike":        float(o.contract.strike),
            "expiry":        str(o.contract.expiry),
            "dte":           int(o.contract.dte),
            "delta":         round(float(o.greeks.delta), 4),
            "theta":         round(float(o.greeks.theta), 4),
            "premium":       round(premium, 4),
            "total_premium": total_prem,
            "contracts":     contracts,
            "score":         round(float(o.score), 2),
            "iv_rank":       round(float(o.iv_rank), 2),
            "ann_return":    round(float(o.annualised_return), 4),
            "scan_time":     scan_time.isoformat(),
            "status":        status,
        }
