export function mockResolve<T>(value: T, delayMs = 350): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), delayMs));
}

/**
 * Deep-clones a value using JSON serialization.
 * Used in mock transport to prevent shared state mutations between calls.
 */
export function cloneMock<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}
