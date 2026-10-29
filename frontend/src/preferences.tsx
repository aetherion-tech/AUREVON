import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./state";
import { Card } from "./ui";
import type { Layers } from "./Chart";
export const layerDefaults: Layers = {
  trend: true,
  bias: true,
  events: true,
  levels: true,
};
export function readLayers(): Layers {
  try {
    const saved = JSON.parse(
      localStorage.getItem("aurevon.chart.layers") || "{}",
    );
    return Object.fromEntries(
      Object.entries(layerDefaults).map(([k, v]) => [
        k,
        typeof saved[k] === "boolean" ? saved[k] : v,
      ]),
    ) as Layers;
  } catch {
    return layerDefaults;
  }
}
export function saveLayers(value: Layers) {
  try {
    localStorage.setItem("aurevon.chart.layers", JSON.stringify(value));
  } catch {
    /* optional */
  }
  window.dispatchEvent(new Event("aurevon:layers"));
}
type Preferences = {
  palette: "standard" | "accessible";
  sounds: boolean;
  notifications: boolean;
};
function readPreferences(): Preferences {
  try {
    const p = JSON.parse(localStorage.getItem("aurevon.preferences") || "{}");
    return {
      palette: p.palette === "accessible" ? "accessible" : "standard",
      sounds: p.sounds === true,
      notifications: p.notifications === true,
    };
  } catch {
    return { palette: "standard", sounds: false, notifications: false };
  }
}
function savePreferences(p: Preferences) {
  try {
    localStorage.setItem("aurevon.preferences", JSON.stringify(p));
  } catch {
    /* optional */
  }
  document.documentElement.dataset.palette = p.palette;
}
let audio: AudioContext | undefined;
function beep() {
  if (!audio || audio.state !== "running") return;
  const oscillator = audio.createOscillator(),
    gain = audio.createGain();
  oscillator.frequency.value = 550;
  gain.gain.value = 0.04;
  oscillator.connect(gain);
  gain.connect(audio.destination);
  oscillator.start();
  oscillator.stop(audio.currentTime + 0.12);
}
export function PreferencesRuntime() {
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: ({ signal }) => api.get("/api/settings", undefined, { signal }),
  });
  useEffect(() => {
    document.documentElement.dataset.theme =
      settings.data?.settings.display?.theme ?? "dark";
  }, [settings.data]);
  useEffect(() => {
    document.documentElement.dataset.palette = readPreferences().palette;
    const event = (raw: Event) => {
      const preferences = readPreferences(),
        kind = (raw as CustomEvent<string>).detail;
      if (preferences.sounds) beep();
      if (
        preferences.notifications &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        try {
          new Notification("AUREVON paper desk", {
            body: `New paper ${kind} event. Open the dashboard to review.`,
            tag: "aurevon-paper",
          });
        } catch {
          /* browser unsupported */
        }
      }
    };
    window.addEventListener("aurevon:paper-event", event);
    return () => window.removeEventListener("aurevon:paper-event", event);
  }, []);
  return null;
}
export function DisplayPreferences() {
  const [preferences, setPreferences] = useState(readPreferences),
    [layers, setLayers] = useState(readLayers),
    [message, setMessage] = useState("");
  const update = (next: Preferences) => {
    setPreferences(next);
    savePreferences(next);
  };
  return (
    <Card title="Browser display and notifications">
      <p>
        These preferences apply to this browser. Notifications and sounds run
        only while this signed-in dashboard is open; no background delivery is
        configured.
      </p>
      <label htmlFor="chart-color-palette">Chart color palette</label>
      <select
        id="chart-color-palette"
        value={preferences.palette}
        onChange={(e) =>
          update({
            ...preferences,
            palette: e.target.value as Preferences["palette"],
          })
        }
      >
        <option value="standard">Green / red</option>
        <option value="accessible">Blue / orange</option>
      </select>
      <fieldset>
        <legend>Chart layers</legend>
        {Object.entries(layers).map(([k, v]) => (
          <label className="check" key={k}>
            <input
              type="checkbox"
              checked={v}
              onChange={(e) => {
                const next = { ...layers, [k]: e.target.checked };
                setLayers(next);
                saveLayers(next);
              }}
            />
            {k}
          </label>
        ))}
      </fieldset>
      <button
        onClick={async () => {
          if (preferences.sounds) {
            update({ ...preferences, sounds: false });
            return;
          }
          try {
            audio ??= new AudioContext();
            await audio.resume();
            update({ ...preferences, sounds: true });
            beep();
            setMessage(
              "Event sounds enabled for this browser session. After reopening, enable audio again if the browser blocks playback.",
            );
          } catch {
            setMessage("Audio is unavailable in this browser.");
          }
        }}
      >
        {preferences.sounds
          ? "Disable event sounds"
          : "Enable and test event sounds"}
      </button>
      <button
        onClick={async () => {
          if (preferences.notifications) {
            update({ ...preferences, notifications: false });
            return;
          }
          if (!("Notification" in window)) {
            setMessage("Browser notifications are unavailable.");
            return;
          }
          try {
            const permission = await Notification.requestPermission();
            update({ ...preferences, notifications: permission === "granted" });
            setMessage(
              permission === "granted"
                ? "Notifications enabled while the dashboard is open."
                : "Notification permission was not granted. No notifications enabled.",
            );
          } catch {
            setMessage("Notification permission is unavailable.");
          }
        }}
      >
        {preferences.notifications
          ? "Disable browser notifications"
          : "Enable browser notifications"}
      </button>
      {message && <p role="status">{message}</p>}
    </Card>
  );
}
