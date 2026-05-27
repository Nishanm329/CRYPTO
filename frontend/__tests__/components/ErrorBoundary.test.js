import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBoundary from '@/components/ErrorBoundary'

// Component that throws error
const ThrowError = () => {
  throw new Error('Test error message')
}

// Component that renders normally
const WorkingComponent = () => {
  return <div>Working component</div>
}

describe('ErrorBoundary', () => {
  // Suppress console.error for error boundary tests
  beforeEach(() => {
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    console.error.mockRestore()
  })

  test('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <WorkingComponent />
      </ErrorBoundary>
    )

    expect(screen.getByText('Working component')).toBeInTheDocument()
  })

  test('renders error UI when child throws error', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
  })

  test('displays error message in fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/Test error message/i)).toBeInTheDocument()
  })

  test('has retry button in error UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    const retryButton = screen.getByRole('button', { name: /Try Again/i })
    expect(retryButton).toBeInTheDocument()
  })

  test('retry button attempts to recover', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    const retryButton = screen.getByRole('button', { name: /Try Again/i })
    fireEvent.click(retryButton)

    // After retry, should show error again (since component still throws)
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
  })

  test('displays stack trace in development mode', () => {
    // Set NODE_ENV to development
    const originalEnv = process.env.NODE_ENV
    process.env.NODE_ENV = 'development'

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    // Stack trace should be visible in development
    const stackTraceArea = screen.queryByText(/Stack Trace:/i)
    expect(stackTraceArea).toBeInTheDocument()

    // Restore environment
    process.env.NODE_ENV = originalEnv
  })
})
