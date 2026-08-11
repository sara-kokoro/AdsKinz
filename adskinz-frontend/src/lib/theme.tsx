import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeMode = "dark" | "light" | "system";
const KEY = "adskinz.theme";

type Ctx = { mode: ThemeMode; setMode: (m: ThemeMode) => void; resolved: "dark" | "light" };
const ThemeContext = createContext<Ctx>({ mode: "dark", setMode: () => {}, resolved: "dark" });

function systemPref(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("system");
  const [resolved, setResolved] = useState<"dark" | "light">("dark");

  const apply = useCallback((m: ThemeMode) => {
    const r = m === "system" ? systemPref() : m;
    setResolved(r);
    const root = document.documentElement;
    root.classList.toggle("dark", r === "dark");
    root.style.colorScheme = r;
  }, []);

  useEffect(() => {
    const stored = (localStorage.getItem(KEY) as ThemeMode | null) ?? "system";
    setModeState(stored);
    apply(stored);
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if ((localStorage.getItem(KEY) as ThemeMode | null) ?? "system") apply("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [apply]);

  const setMode = useCallback(
    (m: ThemeMode) => {
      localStorage.setItem(KEY, m);
      setModeState(m);
      apply(m);
    },
    [apply],
  );

  return <ThemeContext.Provider value={{ mode, setMode, resolved }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
