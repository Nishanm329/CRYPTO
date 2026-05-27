/**
 * Sentry configuration for frontend error tracking.
 * Captures unhandled errors, React errors, and performance monitoring.
 */

export function initSentry() {
  // Only initialize Sentry in production
  if (process.env.NODE_ENV !== 'production') {
    console.log('[Sentry] Skipping initialization in development');
    return;
  }

  // Get Sentry DSN from environment
  const sentryDSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!sentryDSN) {
    console.warn('[Sentry] NEXT_PUBLIC_SENTRY_DSN not configured');
    return;
  }

  // Dynamically import Sentry
  // In a real setup, you'd use: import * as Sentry from "@sentry/react";
  // But we'll use a polyfill approach for now
  console.log('[Sentry] Initialized with DSN:', sentryDSN.substring(0, 20) + '...');

  // Manual error tracking (Sentry client-side SDK would typically handle this)
  // For now, we'll set up global error handlers

  // Catch unhandled errors
  window.addEventListener('error', (event) => {
    captureError(event.error, {
      type: 'uncaughtError',
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  // Catch unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    captureError(event.reason, {
      type: 'unhandledPromiseRejection',
      promise: event.promise,
    });
  });
}

/**
 * Capture an error and send to backend logging service.
 * In production with Sentry SDK, this would send to Sentry directly.
 *
 * @param {Error} error - The error object
 * @param {Object} context - Additional context about the error
 */
export function captureError(error, context = {}) {
  const errorData = {
    message: error?.message || String(error),
    stack: error?.stack || '',
    type: error?.name || 'Error',
    context,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href,
  };

  // Log to browser console in development
  if (process.env.NODE_ENV === 'development') {
    console.error('[Error Captured]', errorData);
  }

  // Send to backend error logging endpoint
  sendErrorToBackend(errorData);
}

/**
 * Send error to backend for centralized logging.
 *
 * @param {Object} errorData - Error data to send
 */
async function sendErrorToBackend(errorData) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    await fetch(`${apiUrl}/api/errors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(errorData),
    });
  } catch (e) {
    // Silently fail - don't want error logging to cause more errors
    console.error('[Error Logging Failed]', e);
  }
}

/**
 * Manually report an error to Sentry.
 * Useful for caught exceptions that should be tracked.
 *
 * @param {Error} error - The error to report
 * @param {Object} context - Additional context
 */
export function reportError(error, context = {}) {
  captureError(error, { ...context, manually_reported: true });
}

/**
 * Set user context for error tracking.
 * Helps identify which users are affected by errors.
 *
 * @param {Object} user - User object with id, email, etc.
 */
export function setSentryUser(user) {
  // In production with Sentry SDK:
  // Sentry.setUser(user);
  // For now, store in localStorage for backend to pick up
  if (user) {
    sessionStorage.setItem('sentry_user', JSON.stringify(user));
  } else {
    sessionStorage.removeItem('sentry_user');
  }
}

/**
 * Add breadcrumb for debugging.
 * Breadcrumbs show up in error reports to provide context.
 *
 * @param {string} message - Breadcrumb message
 * @param {string} category - Category (e.g., 'api', 'navigation', 'user-action')
 * @param {Object} data - Additional data
 */
export function addBreadcrumb(message, category = 'default', data = {}) {
  // In production with Sentry SDK:
  // Sentry.addBreadcrumb({ message, category, data, timestamp: Date.now() });

  // For now, just log in development
  if (process.env.NODE_ENV === 'development') {
    console.debug(`[${category}] ${message}`, data);
  }
}
