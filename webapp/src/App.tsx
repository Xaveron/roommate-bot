import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { Async, Gate } from "./components/common";
import { useLoad } from "./hooks";
import { type Key, type Translator, pickLanguage, translator } from "./i18n";
import { colorScheme, haptic, initData, webApp } from "./telegram";
import type { Me } from "./types";
import BalanceView from "./views/BalanceView";
import HistoryView from "./views/HistoryView";
import QueueView from "./views/QueueView";

// Charts (Recharts) are the heaviest part: load them only when the tab is opened.
const StatsView = lazy(() => import("./views/StatsView"));

const TABS = ["queue", "history", "balance", "stats"] as const;
type Tab = (typeof TABS)[number];

function useColorScheme(): "light" | "dark" {
  const [scheme, setScheme] = useState(colorScheme());
  useEffect(() => {
    webApp()?.onEvent("themeChanged", () => setScheme(colorScheme()));
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = scheme;
  }, [scheme]);
  return scheme;
}

/** ?tab=balance opens a specific tab (links from the bot). */
export function chooseTab(search: string): Tab {
  const wanted = new URLSearchParams(search).get("tab");
  return TABS.find((tab) => tab === wanted) ?? "queue";
}

/** ?room=<id> from the bot's button, else what the backend suggests. */
export function chooseRoom(me: Me, search: string): number | undefined {
  const wanted = Number(new URLSearchParams(search).get("room"));
  if (me.rooms.some((room) => room.id === wanted)) return wanted;
  return me.initial_room_id ?? me.rooms[0]?.id;
}

function Rooms({ me, scheme }: { me: Me; scheme: "light" | "dark" }) {
  const [roomId, setRoomId] = useState(() => chooseRoom(me, window.location.search));
  const [tab, setTab] = useState<Tab>(() => chooseTab(window.location.search));
  const room = me.rooms.find((r) => r.id === roomId);
  const i18n: Translator = useMemo(
    () => translator(pickLanguage(room?.language, me.language_code)),
    [room?.language, me.language_code],
  );
  useEffect(() => {
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  if (!room) {
    return <Gate emoji="🏠" title={i18n.t("gate.rooms.title")} text={i18n.t("gate.rooms.text")} />;
  }
  return (
    <div className="app">
      <header className="header">
        <h1>🏠 {room.name}</h1>
        {me.rooms.length > 1 && (
          <select
            className="room-select"
            aria-label={i18n.t("room.switch")}
            value={room.id}
            onChange={(event) => setRoomId(Number(event.target.value))}
          >
            {me.rooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        )}
      </header>
      <nav className="tabs" role="tablist">
        {TABS.map((name) => (
          <button
            type="button"
            role="tab"
            key={name}
            aria-selected={tab === name}
            onClick={() => {
              haptic();
              setTab(name);
            }}
          >
            {i18n.t(`tabs.${name}` as Key)}
          </button>
        ))}
      </nav>
      <main key={room.id}>
        {tab === "queue" && <QueueView roomId={room.id} i18n={i18n} />}
        {tab === "history" && <HistoryView roomId={room.id} i18n={i18n} />}
        {tab === "balance" && <BalanceView roomId={room.id} i18n={i18n} />}
        {tab === "stats" && (
          <Suspense fallback={<div className="center">{i18n.t("common.loading")}</div>}>
            <StatsView roomId={room.id} i18n={i18n} scheme={scheme} />
          </Suspense>
        )}
      </main>
    </div>
  );
}

function Signed({ scheme }: { scheme: "light" | "dark" }) {
  const state = useLoad(() => api.me(), []);
  const fallback = translator(pickLanguage(navigator.language));
  return <Async state={state} i18n={fallback}>{(me) => <Rooms me={me} scheme={scheme} />}</Async>;
}

export default function App() {
  const scheme = useColorScheme();
  if (!initData()) {
    const i18n = translator(pickLanguage(navigator.language));
    return <Gate emoji="📱" title={i18n.t("gate.telegram.title")} text={i18n.t("gate.telegram.text")} />;
  }
  return <Signed scheme={scheme} />;
}
