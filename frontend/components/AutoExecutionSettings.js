import React, { useState, useEffect } from 'react';

/**
 * Auto-Execution Settings Panel
 * Allows users to enable/disable automatic trade execution on high-confidence signals
 */
export default function AutoExecutionSettings() {
  const [autoExecutionEnabled, setAutoExecutionEnabled] = useState(false);
  const [walletBalance, setWalletBalance] = useState(10000);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [stats, setStats] = useState(null);

  // Load current settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/trading/auto-execution/status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('apiKey')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to load settings');
      const data = await response.json();

      setAutoExecutionEnabled(data.auto_execution_enabled);
      setWalletBalance(data.wallet_balance || 10000);
      setStats(data.stats || {});
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Failed to load auto-execution settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAutoExecution = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/trading/auto-execution?auto_execution_enabled=${!autoExecutionEnabled}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('apiKey')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) throw new Error('Failed to update setting');
      const data = await response.json();

      setAutoExecutionEnabled(data.auto_execution_enabled);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.message);
      console.error('Failed to toggle auto-execution:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateWalletBalance = async (newBalance) => {
    if (newBalance < 10 || newBalance > 10000000) {
      setError('Balance must be between $10 and $10M');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(
        `/api/trading/wallet/balance?wallet_balance=${newBalance}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('apiKey')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) throw new Error('Failed to update wallet balance');
      const data = await response.json();

      setWalletBalance(data.wallet_balance);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err.message);
      console.error('Failed to update wallet balance:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !stats) {
    return <div className="p-6 text-center text-gray-400">Loading settings...</div>;
  }

  return (
    <div className="space-y-6 p-6 bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg border border-slate-700">
      {/* Header */}
      <div className="border-b border-slate-700 pb-4">
        <h2 className="text-2xl font-bold text-white">⚡ Auto-Execution Settings</h2>
        <p className="text-sm text-gray-400 mt-1">
          Automatically execute trades when signal confidence reaches thresholds
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-900/30 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="p-4 bg-green-900/30 border border-green-700 rounded text-green-200 text-sm">
          ✓ Settings updated successfully
        </div>
      )}

      {/* Auto-Execution Toggle */}
      <div className="bg-slate-700/30 p-4 rounded border border-slate-600">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Enable Auto-Execution</h3>
            <p className="text-sm text-gray-300 mt-1">
              {autoExecutionEnabled
                ? '✓ Auto-executing signals with confidence ≥ 85'
                : '○ Manual execution only'}
            </p>
          </div>
          <button
            onClick={handleToggleAutoExecution}
            disabled={loading}
            className={`px-6 py-2 rounded font-semibold transition-all ${
              autoExecutionEnabled
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-gray-600 hover:bg-gray-700 text-white'
            } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {autoExecutionEnabled ? 'Enabled' : 'Disabled'}
          </button>
        </div>
      </div>

      {/* Execution Rules Info */}
      {autoExecutionEnabled && (
        <div className="bg-blue-900/20 p-4 rounded border border-blue-700/50">
          <h4 className="text-sm font-semibold text-blue-300 mb-2">Execution Rules:</h4>
          <ul className="text-sm text-blue-200 space-y-1">
            <li>• <span className="font-semibold">Confidence ≥ 85 (VERY_HIGH)</span> → Auto-execute at 100%</li>
            <li>• <span className="font-semibold">Confidence ≥ 75 (HIGH)</span> → Auto-execute at 80%</li>
            <li>• <span className="font-semibold">Recovery Mode (15-25% DD)</span> → Only VERY_HIGH at 50%</li>
            <li>• <span className="font-semibold">Pause Mode (>25% DD)</span> → All auto-execution disabled</li>
          </ul>
        </div>
      )}

      {/* Wallet Balance Settings */}
      <div className="bg-slate-700/30 p-4 rounded border border-slate-600">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Wallet Balance</h3>
            <p className="text-sm text-gray-300 mt-1">Used for position sizing in paper trading</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-green-400">
              ${walletBalance.toLocaleString('en-US', { maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            value={walletBalance}
            onChange={(e) => setWalletBalance(parseFloat(e.target.value) || 0)}
            min="10"
            max="10000000"
            step="100"
            className="flex-1 px-3 py-2 bg-slate-600 border border-slate-500 rounded text-white text-sm"
            disabled={loading}
          />
          <button
            onClick={() => handleUpdateWalletBalance(walletBalance)}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold text-sm transition-all disabled:opacity-50"
          >
            Update
          </button>
        </div>
      </div>

      {/* Statistics */}
      {stats && stats.total_attempts > 0 && (
        <div className="bg-slate-700/30 p-4 rounded border border-slate-600">
          <h3 className="text-lg font-semibold text-white mb-3">📊 Performance (Last 7 Days)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-600/50 p-3 rounded">
              <div className="text-xs text-gray-400">Total Attempts</div>
              <div className="text-2xl font-bold text-white">{stats.total_attempts}</div>
            </div>
            <div className="bg-slate-600/50 p-3 rounded">
              <div className="text-xs text-gray-400">Successful</div>
              <div className="text-2xl font-bold text-green-400">{stats.successful_executions}</div>
            </div>
            <div className="bg-slate-600/50 p-3 rounded">
              <div className="text-xs text-gray-400">Success Rate</div>
              <div className="text-2xl font-bold text-blue-400">
                {stats.success_rate.toFixed(1)}%
              </div>
            </div>
            <div className="bg-slate-600/50 p-3 rounded">
              <div className="text-xs text-gray-400">Avg Confidence</div>
              <div className="text-2xl font-bold text-yellow-400">{stats.avg_confidence}</div>
            </div>
          </div>
        </div>
      )}

      {/* Risk Warning */}
      <div className="bg-yellow-900/20 p-4 rounded border border-yellow-700/50">
        <p className="text-sm text-yellow-200">
          ⚠️ <span className="font-semibold">Warning:</span> Auto-execution will execute real trades on your Binance account in LIVE mode.
          Start with PAPER mode to test before enabling LIVE execution.
        </p>
      </div>
    </div>
  );
}
