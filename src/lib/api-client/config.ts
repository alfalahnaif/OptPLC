export const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

export function isMockApiEnabled() {
  const value = process.env.NEXT_PUBLIC_USE_MOCK_API;
  if (value == null || value === "") return true;

  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

