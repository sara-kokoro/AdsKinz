import { useTranslation } from "react-i18next";
import { LANGUAGES, STORAGE_KEY } from "@/lib/i18n";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { IconCheck, IconGlobe, IconMoon, IconSun } from "@/components/icons";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";

/** Custom language menu — no native <select>, fully themed. */
export function LanguageSelect({ compact = false }: { compact?: boolean }) {
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== i18n.language) void i18n.changeLanguage(stored);
  }, [i18n]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = LANGUAGES.find((l) => l.code === i18n.language) ?? LANGUAGES[0];

  const pick = (code: string) => {
    localStorage.setItem(STORAGE_KEY, code);
    void i18n.changeLanguage(code);
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t("common.language")}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex min-h-11 items-center gap-2 rounded-xl border border-seam bg-transparent px-3 text-sm font-semibold transition-colors hover:bg-panel-2",
          compact && "min-h-9",
        )}
      >
        <IconGlobe className="text-paper-dim" width={16} height={16} />
        <span>{current.native}</span>
        <span className="num text-[10px] text-paper-dim">{current.flag}</span>
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-50 mt-2 min-w-44 overflow-hidden rounded-xl border border-seam bg-panel shadow-xl"
        >
          {LANGUAGES.map((l) => (
            <li key={l.code}>
              <button
                type="button"
                role="option"
                aria-selected={l.code === i18n.language}
                onClick={() => pick(l.code)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-semibold transition-colors hover:bg-panel-2",
                  l.code === i18n.language ? "text-signal" : "text-paper",
                )}
              >
                <span className="num w-6 text-[10px] text-paper-dim">{l.flag}</span>
                {l.native}
                {l.code === i18n.language && <IconCheck className="ml-auto" width={14} height={14} />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


export function ThemeToggle() {
  const { mode, setMode } = useTheme();
  const { t } = useTranslation();
  const opts: { m: ThemeMode; label: string; icon: React.ReactNode }[] = [
    { m: "dark", label: t("common.themeDark"), icon: <IconMoon width={15} height={15} /> },
    { m: "light", label: t("common.themeLight"), icon: <IconSun width={15} height={15} /> },
    { m: "system", label: t("common.themeSystem"), icon: <span className="text-[10px] font-extrabold">A</span> },
  ];
  return (
    <div role="group" aria-label={t("common.theme")} className="inline-flex rounded-xl border border-seam p-0.5">
      {opts.map((o) => (
        <button
          key={o.m}
          aria-label={o.label}
          aria-pressed={mode === o.m}
          onClick={() => setMode(o.m)}
          className={cn(
            "inline-flex size-9 items-center justify-center rounded-[10px] transition-colors",
            mode === o.m ? "bg-panel-2 text-signal" : "text-paper-dim hover:text-paper",
          )}
        >
          {o.icon}
        </button>
      ))}
    </div>
  );
}
