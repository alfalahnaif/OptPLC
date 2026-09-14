import React from "react";
import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

// Cold jsdom starts on the dev machine can exceed the 1 s default wait (D-021, temporary).
configure({ asyncUtilTimeout: 5000 });

const routerPushMock = vi.fn();

Object.defineProperty(globalThis, "__nextRouterPush", {
  configurable: true,
  value: routerPushMock
});

Object.defineProperty(globalThis, "__nextPathname", {
  configurable: true,
  writable: true,
  value: "/"
});

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  configurable: true,
  value: ResizeObserverMock
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  }))
});

vi.mock("next/navigation", () => ({
  usePathname: () => (globalThis as { __nextPathname?: string }).__nextPathname ?? "/",
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
    refresh: vi.fn()
  })
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

vi.mock("next/dynamic", () => ({
  default: () => {
    function DynamicMonacoMock({ value }: { value?: string }) {
      return (
        <div data-testid="monaco-editor">
          <pre>{value}</pre>
        </div>
      );
    }

    return DynamicMonacoMock;
  }
}));
