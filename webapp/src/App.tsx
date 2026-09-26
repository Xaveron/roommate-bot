import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { Async, Gate } from "./components/common";
import { ToastProvider } from "./components/controls";
import { useLoad } from "./hooks";
import { type Key, type Translator, pickLanguage, translator } from "./i18n";
import { colorScheme, haptic, initData, webApp } from "./telegram";
import type { Me } from "./types";
import BalanceView from "./views/BalanceView";
import HistoryView from "./views/HistoryView";
import QueueView from "./views/QueueView";
import RoomView, { JoinScreen } from "./views/RoomView";
import ShoppingView from "./views/ShoppingView";

// Charts (Recharts) are the heaviest part: load them only when the tab is opened.
const StatsView = lazy(() => import("./views/StatsView"));

const TABS = ["queue", "shopping", "balance", "history", "stats", "room"] as const;
type Tab = (typeof TABS)[number];
const TAB_ICONS: Record<Tab, string> = {
  queue: "📋",
  shopping: "🛒",
  balance: "💰",
  history: "📜",
  stats: "📊",
  room: "⚙️",
};

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

/** ?room=<id>: the room the bot's button opened the app on. */
export function roomParam(search: string): number | undefined {
  const wanted = Number(new URLSearchParams(search).get("room"));
  return Number.isInteger(wanted) && wanted > 0 ? wanted : undefined;
}

/** ?room=<id> from the bot's button, else what the backend suggests. */
export function chooseRoom(me: Me, search: string): number | undefined {
  const wanted = roomParam(search);
  if (me.rooms.some((room) => room.id === wanted)) return wanted;
  return me.initial_room_id ?? me.rooms[0]?.id;
}

function Rooms({ me, scheme, reloadMe }: { me: Me; scheme: "light" | "dark"; reloadMe: () => void }) {
  const [roomId, setRoomId] = useState(() => chooseRoom(me, window.location.search));
  const [tab, setTab] = useState<Tab>(() => chooseTab(window.location.search));
  const [later, setLater] = useState(false);
  // The chosen room, or the first one left (e.g. after leaving the chosen one).
  const room = me.rooms.find((r) => r.id === roomId) ?? me.rooms[0];
  const invite = later ? null : (me.invite ?? null);
  const shown = invite ?? room;
  const i18n: Translator = useMemo(
    () => translator(pickLanguage(shown?.language, me.language_code)),
    [shown?.language, me.language_code],
  );
  useEffect(() => {
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  const switchRoom = (id: number) => {
    setRoomId(id);
    // The bot's private chat follows the app (like /room); nothing to tell if it fails.
    api.chooseRoom(id).catch(() => undefined);
  };

  if (invite) {
    return (
      <JoinScreen
        room={invite}
        i18n={i18n}
        onJoined={() => {
          setRoomId(invite.id);
          reloadMe();
        }}
        onLater={me.rooms.length > 0 ? () => setLater(true) : undefined}
      />
    );
  }
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
            onChange={(event) => switchRoom(Number(event.target.value))}
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
              haptic.select();
              setTab(name);
            }}
          >
            <span className="icon" aria-hidden>
              {TAB_ICONS[name]}
            </span>
            <span className="label">{i18n.t(`tabs.${name}` as Key)}</span>
          </button>
        ))}
      </nav>
      <main key={room.id}>
        {tab === "queue" && <QueueView roomId={room.id} i18n={i18n} />}
        {tab === "shopping" && <ShoppingView roomId={room.id} i18n={i18n} />}
        {tab === "balance" && <BalanceView roomId={room.id} i18n={i18n} />}
        {tab === "history" && <HistoryView roomId={room.id} i18n={i18n} />}
        {tab === "stats" && (
          <Suspense fallback={<div className="center">{i18n.t("common.loading")}</div>}>
            <StatsView roomId={room.id} i18n={i18n} scheme={scheme} />
          </Suspense>
        )}
        {tab === "room" && <RoomView roomId={room.id} i18n={i18n} onRoomChange={reloadMe} />}
      </main>
    </div>
  );
}

function Signed({ scheme }: { scheme: "light" | "dark" }) {
  const state = useLoad(() => api.me(roomParam(window.location.search)), []);
  const fallback = translator(pickLanguage(navigator.language));
  return (
    <Async state={state} i18n={fallback}>
      {(me) => <Rooms me={me} scheme={scheme} reloadMe={state.reload} />}
    </Async>
  );
}

export default function App() {
  const scheme = useColorScheme();
  if (!initData()) {
    const i18n = translator(pickLanguage(navigator.language));
    return <Gate emoji="📱" title={i18n.t("gate.telegram.title")} text={i18n.t("gate.telegram.text")} />;
  }
  return (
    <ToastProvider>
      <Signed scheme={scheme} />
    </ToastProvider>
  );
}
