"use client";

import { useEffect, useState } from "react";

export type ResourceState = "loading" | "ready" | "empty" | "error";

export function useApiResource<T>(loader: () => Promise<T>, deps: React.DependencyList) {
  const [state, setState] = useState<ResourceState>("loading");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;
    setState("loading");
    setError(null);

    loader()
      .then((value) => {
        if (!active) return;
        const empty = Array.isArray(value) ? value.length === 0 : value == null;
        setData(value);
        setState(empty ? "empty" : "ready");
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason : new Error("Unknown API client error"));
        setState("error");
      });

    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { state, data, error };
}
