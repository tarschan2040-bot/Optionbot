"use client";

import { useEffect } from "react";

const SETTINGS_STORAGE_KEY = "optionbot-settings-preferences";

function resolveTheme(appearance: string) {
  if (appearance === "light" || appearance === "dark") return appearance;
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyStoredPreferences() {
  try {
    const stored = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    const preferences = stored ? JSON.parse(stored) : {};
    const appearance = preferences.appearance || "dark";
    const language = preferences.language || "en";
    document.documentElement.dataset.appearance = appearance;
    document.documentElement.dataset.theme = resolveTheme(appearance);
    document.documentElement.lang = language;
  } catch {
    document.documentElement.dataset.appearance = "dark";
    document.documentElement.dataset.theme = "dark";
    document.documentElement.lang = "en";
  }
}

export default function PreferenceBootstrap() {
  useEffect(() => {
    applyStoredPreferences();

    const media = window.matchMedia("(prefers-color-scheme: light)");
    const handlePreferenceChange = () => applyStoredPreferences();
    const handleStorage = (event: StorageEvent) => {
      if (event.key === SETTINGS_STORAGE_KEY) applyStoredPreferences();
    };

    media.addEventListener("change", handlePreferenceChange);
    window.addEventListener("storage", handleStorage);
    return () => {
      media.removeEventListener("change", handlePreferenceChange);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  return null;
}
