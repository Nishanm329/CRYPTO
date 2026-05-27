-- Migration: Add auto-execution fields to binance_credentials table
-- Description: Adds auto_execution_enabled and wallet_balance columns for auto-execution feature
-- Compatible with: PostgreSQL 12+, SQLite 3.35+

BEGIN TRANSACTION;

-- Add auto_execution_enabled column if it doesn't exist
ALTER TABLE binance_credentials
ADD COLUMN IF NOT EXISTS auto_execution_enabled BOOLEAN DEFAULT FALSE;

-- Add wallet_balance column if it doesn't exist
ALTER TABLE binance_credentials
ADD COLUMN IF NOT EXISTS wallet_balance NUMERIC(15,2) DEFAULT 10000.0;

-- Create audit log table for tracking all auto-executed trades
CREATE TABLE IF NOT EXISTS auto_execution_audit (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    confidence_score INTEGER NOT NULL,
    recovery_state VARCHAR(20) NOT NULL,
    position_size_multiplier NUMERIC(5,2) NOT NULL,
    execution_trigger VARCHAR(50) NOT NULL,
    executed BOOLEAN NOT NULL,
    execution_error TEXT,
    order_id VARCHAR(100),
    entry_price NUMERIC(18,8),
    quantity NUMERIC(18,8),
    trading_mode VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_auto_execution_user_id
ON auto_execution_audit(user_id);

CREATE INDEX IF NOT EXISTS idx_auto_execution_symbol
ON auto_execution_audit(symbol);

CREATE INDEX IF NOT EXISTS idx_auto_execution_created_at
ON auto_execution_audit(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auto_execution_user_symbol
ON auto_execution_audit(user_id, symbol, created_at DESC);

COMMIT;

-- Verification queries (run after migration to verify success):
-- SELECT COUNT(*) FROM binance_credentials WHERE auto_execution_enabled IS NOT NULL;
-- SELECT COUNT(*) FROM binance_credentials WHERE wallet_balance IS NOT NULL;
-- SELECT COUNT(*) FROM auto_execution_audit;
