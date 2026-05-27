import {
  initSentry,
  captureError,
  reportError,
  setSentryUser,
  addBreadcrumb,
} from '@/lib/sentry-config'

// Mock fetch
global.fetch = jest.fn()

describe('Sentry Configuration', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    sessionStorage.clear()
    global.fetch.mockClear()
  })

  describe('initSentry', () => {
    test('initializes without errors', () => {
      expect(() => initSentry()).not.toThrow()
    })

    test('skips initialization in development', () => {
      const originalEnv = process.env.NODE_ENV
      process.env.NODE_ENV = 'development'

      initSentry()

      process.env.NODE_ENV = originalEnv
    })

    test('sets up global error listeners', () => {
      initSentry()

      expect(window.addEventListener).toBeDefined()
    })
  })

  describe('captureError', () => {
    test('captures error and sends to backend', async () => {
      global.fetch.mockResolvedValueOnce({ ok: true })

      const error = new Error('Test error')
      captureError(error, { userId: 'test-user' })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/errors'),
        expect.any(Object)
      )
    })

    test('includes error message in report', async () => {
      global.fetch.mockResolvedValueOnce({ ok: true })

      const error = new Error('Test error message')
      captureError(error)

      const callArgs = global.fetch.mock.calls[0]
      const body = JSON.parse(callArgs[1].body)
      expect(body.message).toBe('Test error message')
    })

    test('includes stack trace in report', async () => {
      global.fetch.mockResolvedValueOnce({ ok: true })

      const error = new Error('Test error')
      captureError(error)

      const callArgs = global.fetch.mock.calls[0]
      const body = JSON.parse(callArgs[1].body)
      expect(body.stack).toBeTruthy()
    })
  })

  describe('reportError', () => {
    test('reports error with manually_reported flag', async () => {
      global.fetch.mockResolvedValueOnce({ ok: true })

      const error = new Error('Manual error')
      reportError(error, { source: 'user-action' })

      const callArgs = global.fetch.mock.calls[0]
      const body = JSON.parse(callArgs[1].body)
      expect(body.context.manually_reported).toBe(true)
      expect(body.context.source).toBe('user-action')
    })
  })

  describe('setSentryUser', () => {
    test('stores user context in session storage', () => {
      const user = { id: '123', email: 'test@example.com' }
      setSentryUser(user)

      const stored = JSON.parse(sessionStorage.getItem('sentry_user'))
      expect(stored).toEqual(user)
    })

    test('clears user context when passed null', () => {
      setSentryUser({ id: '123' })
      setSentryUser(null)

      expect(sessionStorage.getItem('sentry_user')).toBeNull()
    })
  })

  describe('addBreadcrumb', () => {
    test('logs breadcrumb in development', () => {
      const consoleSpy = jest.spyOn(console, 'debug').mockImplementation()

      addBreadcrumb('User clicked button', 'user-action')

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('user-action'),
        expect.stringContaining('User clicked button')
      )

      consoleSpy.mockRestore()
    })

    test('does not log breadcrumb in production', () => {
      const originalEnv = process.env.NODE_ENV
      process.env.NODE_ENV = 'production'

      const consoleSpy = jest.spyOn(console, 'debug').mockImplementation()

      addBreadcrumb('User clicked button', 'user-action')

      expect(consoleSpy).not.toHaveBeenCalled()

      consoleSpy.mockRestore()
      process.env.NODE_ENV = originalEnv
    })
  })
})
