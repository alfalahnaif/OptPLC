"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronDown, ChevronsLeft, Folder, Moon, PanelLeft, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ACTIVE_PROJECT_ID, projectPath, type ProjectRouteSegment } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { currentProject, headerActions, sidebarSections } from "@/lib/mock-data";

type NavItem = {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [dark, setDark] = useState(false);
  const mobileNavItems = sidebarSections.map((section) => section.items as unknown as NavItem[]).flat();

  useEffect(() => {
    const stored = window.localStorage.getItem("optplc-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const nextDark = stored ? stored === "dark" : prefersDark;
    setDark(nextDark);
    document.documentElement.classList.toggle("dark", nextDark);
  }, []);

  function toggleTheme() {
    const nextDark = !dark;
    setDark(nextDark);
    document.documentElement.classList.toggle("dark", nextDark);
    window.localStorage.setItem("optplc-theme", nextDark ? "dark" : "light");
  }

  function resolveNavHref(href: string) {
    const pipelineSegments = [
      "requirements",
      "plan",
      "workflow",
      "code",
      "validation",
      "debugging",
      "optimization",
      "metrics",
      "report"
    ];
    const segment = href.replace("/", "");
    return pipelineSegments.includes(segment) ? projectPath(ACTIVE_PROJECT_ID, segment as ProjectRouteSegment) : href;
  }

  return (
    <TooltipProvider delayDuration={150}>
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-card lg:flex lg:flex-col">
        <Link href="/" className="flex h-16 items-center gap-3 border-b px-5">
          <span className="grid size-8 place-items-center rounded-md bg-foreground text-background">
            <PanelLeft className="size-4" />
          </span>
          <span>
            <span className="block text-sm font-bold leading-none">OptPLC</span>
            <span className="mt-1 block font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
              Agent Optimizer
            </span>
          </span>
        </Link>

        <ScrollArea className="flex-1 px-3 py-4">
        <nav className="space-y-5">
          {sidebarSections.map((section) => (
            <div key={section.label}>
              <div className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                {section.label}
              </div>
              <div className="space-y-1">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const href = resolveNavHref(item.href);
                  const active = pathname === href || pathname === item.href;
                  return (
                    <Link
                      href={href}
                      key={item.href}
                      className={cn(
                        "flex h-9 items-center gap-3 rounded-md px-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                        active && "bg-muted text-foreground"
                      )}
                    >
                      <span className={cn("size-1.5 rounded-full", active ? "bg-primary" : "bg-transparent")} />
                      <Icon className="size-4" />
                      <span>{item.title}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        </ScrollArea>

        <div className="border-t p-4 text-xs text-muted-foreground">
          <button className="mb-4 flex items-center gap-2">
            <ChevronsLeft className="size-4" />
            Collapse
          </button>
          <Separator className="mb-4" />
          <div>
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-emerald-600" />
              All systems nominal
            </div>
            <div className="mt-3 font-mono text-[11px]">v1.4.0 - build 2026.05.17</div>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Button variant="ghost" size="icon" className="lg:hidden">
              <PanelLeft />
            </Button>
            <span>OptPLC</span>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <div className="hidden h-9 items-center gap-2 rounded-md border bg-card px-3 text-sm font-medium shadow-sm md:flex">
              <Folder className="size-4 text-muted-foreground" />
              <span className="max-w-56 truncate">{currentProject.name}</span>
              <Badge className="font-mono" tone="neutral">
                {currentProject.id}
              </Badge>
              <ChevronDown className="size-4 text-muted-foreground" />
            </div>
            <HeaderIcon label="Search">
              <Search />
            </HeaderIcon>
            <HeaderIcon label="Toggle theme" onClick={toggleTheme}>
              <Moon />
            </HeaderIcon>
            {headerActions.map((action) => {
              const Icon = action.icon;
              return (
                <HeaderIcon key={action.label} label={action.label}>
                  <Icon />
                </HeaderIcon>
              );
            })}
            <Button variant="outline" className="hidden gap-2 md:flex">
              <span className="grid size-6 place-items-center rounded-full bg-muted text-xs">LP</span>
              L. Park
              <ChevronDown className="size-4" />
            </Button>
          </div>
        </header>
        <div className="sticky top-16 z-10 border-b bg-background/95 px-4 py-2 backdrop-blur lg:hidden">
          <div className="flex gap-2 overflow-x-auto">
            {mobileNavItems.map((item) => {
              const href = resolveNavHref(item.href);
              const active = pathname === href || pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={href}
                  className={cn(
                    "shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium text-muted-foreground",
                    active && "border-primary bg-primary/10 text-primary"
                  )}
                >
                  {item.title}
                </Link>
              );
            })}
          </div>
        </div>
        <main className="mx-auto w-full max-w-[1680px] px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
    </TooltipProvider>
  );
}

function HeaderIcon({
  label,
  children,
  onClick
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline" size="icon" aria-label={label} onClick={onClick}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
