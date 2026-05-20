import React from "react";
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

const routerPushMock = vi.fn();

Object.defineProperty(globalThis, "__nextRouterPush", {
  configurable: true,
  value: routerPushMock
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
  usePathname: () => "/",
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
