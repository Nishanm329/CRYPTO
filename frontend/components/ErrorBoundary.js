import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: this.state.retryCount + 1
    });
  };

  render() {
    if (this.state.hasError) {
      const errorMsg = this.state.error?.message || 'Unknown error';
      const isChartError = errorMsg.includes('chart') || errorMsg.includes('lightweight');

      return (
        <div className="flex items-center justify-center h-full p-4 bg-bg-card border border-border rounded-xl">
          <div className="text-center">
            <div className="text-red-400 mb-3">
              <svg width="32" height="32" fill="currentColor" viewBox="0 0 24 24" className="mx-auto mb-3">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-tx mb-2">
              {isChartError ? 'Chart Error' : 'Component Error'}
            </h3>
            <p className="text-xs text-tx-muted mb-4 max-w-xs">
              {errorMsg}
            </p>
            <div className="flex gap-2 justify-center">
              <button
                onClick={this.handleRetry}
                className="px-3 py-1.5 text-xs font-medium bg-brand-blue text-white rounded hover:bg-brand-blue/80 transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-3 py-1.5 text-xs font-medium border border-brand-blue text-brand-blue rounded hover:bg-brand-blue/10 transition-colors"
              >
                Reload Page
              </button>
            </div>
            {process.env.NODE_ENV === 'development' && (
              <details className="mt-4 text-left text-[10px] text-tx-dim">
                <summary className="cursor-pointer">Stack trace</summary>
                <pre className="mt-2 p-2 bg-bg rounded overflow-auto max-w-xs">
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
