const MOCK_LATENCY_MS = 20;

export async function mockResolve<T>(value: T): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
  return value;
}

export function cloneMock<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
