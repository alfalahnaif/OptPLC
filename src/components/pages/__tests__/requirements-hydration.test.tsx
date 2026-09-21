/**
 * P1-25, D-034: typed requirement text must survive the page load.
 *
 * The page used to copy the stored requirement into the form in a useEffect. When that effect ran after the
 * first keystroke, it overwrote the typed text. That happened when a timer ran before React's deferred task,
 * and it made planning-flow fail now and then. This test forces that order.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequirementsPage } from "@/components/pages/requirements-page";
import { requirement } from "@/lib/mock-data";

const TYPED = "Motor with emergency stop and fault lamp indication.";
const realSetTimeout = globalThis.setTimeout;

// A Node event loop turn in which an expired timer runs before React's setImmediate task.
function runZeroDelayTimersFirst() {
  globalThis.setTimeout = ((callback: (...args: unknown[]) => void, ms?: number, ...args: unknown[]) => {
    if (!ms) {
      queueMicrotask(() => callback(...args));
      return 0 as unknown as ReturnType<typeof setTimeout>;
    }
    return realSetTimeout(callback, ms, ...args);
  }) as typeof setTimeout;
}

describe("Requirements page load", () => {
  afterEach(() => {
    globalThis.setTimeout = realSetTimeout;
    vi.unstubAllEnvs();
  });

  it("keeps typed text and still loads the stored constraints when a timer runs first", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCK_API", "true");
    runZeroDelayTimersFirst();
    render(<RequirementsPage projectId="PRJ-0421" />);

    const textarea = (await screen.findByLabelText("Requirement text")) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: TYPED } });
    await new Promise((resolve) => realSetTimeout(resolve, 200));

    expect(textarea.value).toBe(TYPED);
    expect(screen.getAllByText(requirement.constraints[0]).length).toBeGreaterThan(0);
  });
});
