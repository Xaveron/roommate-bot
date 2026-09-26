import { type ReactNode, useState } from "react";
import { api } from "../api";
import { Async, Avatar } from "../components/common";
import { type Actions, MainButton, Sheet, useActions } from "../components/controls";
import { shortDate } from "../format";
import { SLOW_REFRESH_MS, useLoad } from "../hooks";
import type { Key, Translator } from "../i18n";
import { haptic } from "../telegram";
import type {
  CategoryPatch,
  CategorySettings,
  MemberInfo,
  QuietHours,
  Room,
  RoomSettingsPatch,
  SettingsData,
} from "../types";

const WEEK = [0, 1, 2, 3, 4, 5, 6];

export function daysText(days: number[], i18n: Translator): string {
  if (days.length === WEEK.length) return i18n.t("days.every");
  return days.map((day) => i18n.t(`weekday.${day}` as Key)).join(", ");
}

const quietText = (quiet: QuietHours | null, i18n: Translator) =>
  quiet ? `${quiet.start}–${quiet.end}` : i18n.t("settings.off");

const repeatText = (hours: number, i18n: Translator) =>
  hours ? i18n.t("settings.repeatValue", { hours }) : i18n.t("settings.repeatOff");

const languageName = (code: string, i18n: Translator) =>
  i18n.has(`language.${code}`) ? i18n.t(`language.${code}` as Key) : code;

type SettingKind = "language" | "timezone" | "quiet" | "repeat" | "currency";
type Screen = { kind: SettingKind } | { kind: "category"; id: number } | { kind: "addCategory" } | null;

// --- the screen --------------------------------------------------------------------------

function Row({
  label,
  value,
  onClick,
  muted = false,
}: {
  label: ReactNode;
  value: ReactNode;
  onClick?: () => void;
  muted?: boolean;
}) {
  const content = (
    <>
      <span className="row-label">{label}</span>
      <span className="row-value">{value}</span>
      {onClick && (
        <span className="chevron" aria-hidden>
          ›
        </span>
      )}
    </>
  );
  return (
    <li className={muted ? "muted" : undefined}>
      {onClick ? (
        <button type="button" className="row" onClick={onClick}>
          {content}
        </button>
      ) : (
        <div className="row">{content}</div>
      )}
    </li>
  );
}

export function RoomScreen({
  data,
  i18n,
  busy = null,
  onOpen = () => {},
  onSummary = () => {},
  onRemove = () => {},
  onLeave = () => {},
  onExport = () => {},
}: {
  data: SettingsData;
  i18n: Translator;
  busy?: string | null;
  onOpen?: (screen: Screen) => void;
  onSummary?: (enabled: boolean) => void;
  onRemove?: (member: MemberInfo) => void;
  onLeave?: () => void;
  onExport?: () => void;
}) {
  const manage = data.can_manage;
  const open = (screen: Screen) => (manage ? () => onOpen(screen) : undefined);
  const { room } = data;
  return (
    <>
      <h3 className="section-title">
        👥 {i18n.t("room.members")} · {data.members.length}
      </h3>
      <section className="card">
        <ul className="rows">
          {data.members.map((member) => {
            const me = member.member_id === data.me_member_id;
            const id = `remove-${member.member_id}`;
            return (
              <li key={member.member_id} className="member">
                <Avatar name={member.name} />
                <div className="grow">
                  <div className="name">
                    {member.name}
                    {me && ` (${i18n.t("common.you")})`}
                  </div>
                  <div className="tags">
                    {member.username && <span className="sub">@{member.username}</span>}
                    {member.is_creator && <span className="chip">👑 {i18n.t("room.creator")}</span>}
                    {member.away_until && (
                      <span className="chip">🏖 {i18n.t("room.awayUntil", { date: shortDate(member.away_until) })}</span>
                    )}
                    {!member.dm_available && <span className="chip warn">⚠️ {i18n.t("room.noDm")}</span>}
                  </div>
                </div>
                {manage && !me && (
                  <button
                    type="button"
                    className="button small danger"
                    disabled={busy !== null}
                    aria-label={`${i18n.t("room.remove")}: ${member.name}`}
                    onClick={() => onRemove(member)}
                  >
                    {busy === id ? "…" : i18n.t("room.remove")}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
        <div className="actions">
          <button type="button" className="button danger" disabled={busy !== null} onClick={onLeave}>
            {busy === "leave" ? "…" : i18n.t("room.leave")}
          </button>
        </div>
      </section>

      <h3 className="section-title">⚙️ {i18n.t("room.settings")}</h3>
      {!manage && <p className="hint">🔒 {i18n.t("room.adminsOnly")}</p>}
      <section className="card">
        <ul className="rows">
          <Row
            label={i18n.t("settings.language")}
            value={languageName(room.language, i18n)}
            onClick={open({ kind: "language" })}
          />
          <Row label={i18n.t("settings.timezone")} value={room.timezone} onClick={open({ kind: "timezone" })} />
          <Row
            label={i18n.t("settings.quiet")}
            value={quietText(data.quiet_hours, i18n)}
            onClick={open({ kind: "quiet" })}
          />
          <Row
            label={i18n.t("settings.repeat")}
            value={repeatText(data.repeat_after_hours, i18n)}
            onClick={open({ kind: "repeat" })}
          />
          <Row label={i18n.t("settings.currency")} value={room.currency} onClick={open({ kind: "currency" })} />
          <li>
            <label className="row">
              <span className="row-label">{i18n.t("settings.summary")}</span>
              <input
                type="checkbox"
                role="switch"
                className="switch"
                checked={data.weekly_summary}
                disabled={!manage || busy !== null}
                onChange={(event) => onSummary(event.target.checked)}
              />
            </label>
          </li>
        </ul>
      </section>

      <h3 className="section-title">📋 {i18n.t("room.categories")}</h3>
      <section className="card">
        <ul className="rows">
          {data.categories.map((category) => (
            <Row
              key={category.id}
              muted={!category.is_active}
              label={
                <>
                  {category.emoji} {category.name}
                </>
              }
              value={
                category.is_active
                  ? `${category.reminder_time} · ${daysText(category.reminder_days, i18n)}${category.mode === "fair" ? " · ⚖️" : ""}`
                  : `⏸ ${i18n.t("category.paused")}`
              }
              onClick={open({ kind: "category", id: category.id })}
            />
          ))}
        </ul>
        <div className="actions">
          <button type="button" className="button" disabled={busy !== null} onClick={() => onOpen({ kind: "addCategory" })}>
            {i18n.t("room.addCategory")}
          </button>
        </div>
      </section>

      <h3 className="section-title">📦 {i18n.t("room.export")}</h3>
      <section className="card">
        <p className="hint flush">{i18n.t("room.exportText")}</p>
        <div className="actions">
          <button type="button" className="button" disabled={busy !== null} onClick={onExport}>
            {busy === "export" ? "…" : i18n.t("room.exportButton")}
          </button>
        </div>
      </section>
    </>
  );
}

// --- forms -------------------------------------------------------------------------------

/** A group of chips of which one is chosen. */
function Choice<T extends string | number>({
  label,
  options,
  value,
  onChange,
  name = (option) => String(option),
}: {
  label: string;
  options: readonly T[];
  value: T | null;
  onChange: (value: T) => void;
  name?: (option: T) => string;
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button
          type="button"
          role="radio"
          key={String(option)}
          aria-checked={option === value}
          onClick={() => {
            haptic.select();
            onChange(option);
          }}
        >
          {name(option)}
        </button>
      ))}
    </div>
  );
}

interface FormProps {
  data: SettingsData;
  i18n: Translator;
  actions: Actions;
  onClose: () => void;
  /** The room itself changed (e.g. its language): the app reloads the room list. */
  onSaved: () => void;
}

/** A setting of the room on its own screen: the MainButton saves what was chosen. */
function SettingSheet({
  title,
  hint,
  patch,
  data,
  i18n,
  actions,
  onClose,
  onSaved,
  children,
}: FormProps & { title: string; hint: string; patch: RoomSettingsPatch | null; children: ReactNode }) {
  const save = async () => {
    if (!patch) return;
    if (await actions.run("settings", () => api.updateSettings(data.room.id, patch))) {
      onClose();
      onSaved();
    }
  };
  return (
    <Sheet title={title} onClose={onClose} i18n={i18n}>
      <p className="hint">{hint}</p>
      {children}
      <MainButton
        text={i18n.t("settings.save")}
        disabled={patch === null}
        progress={actions.busy === "settings"}
        onClick={() => void save()}
      />
    </Sheet>
  );
}

function LanguageSheet(props: FormProps) {
  const { data, i18n } = props;
  const [language, setLanguage] = useState(data.room.language);
  return (
    <SettingSheet
      {...props}
      title={i18n.t("settings.language")}
      hint={i18n.t("settings.languageHint")}
      patch={language !== data.room.language ? { language } : null}
    >
      <Choice
        label={i18n.t("settings.language")}
        options={data.options.languages}
        value={language}
        onChange={setLanguage}
        name={(code) => languageName(code, i18n)}
      />
    </SettingSheet>
  );
}

function TimezoneSheet(props: FormProps) {
  const { data, i18n } = props;
  const presets = data.options.timezones;
  const [zone, setZone] = useState(data.room.timezone);
  const cleaned = zone.trim();
  return (
    <SettingSheet
      {...props}
      title={i18n.t("settings.timezone")}
      hint={i18n.t("settings.timezoneHint")}
      patch={cleaned && cleaned !== data.room.timezone ? { timezone: cleaned } : null}
    >
      <Choice label={i18n.t("settings.timezone")} options={presets} value={zone} onChange={setZone} />
      <label className="field">
        <span>{i18n.t("settings.timezoneOther")}</span>
        <input
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          maxLength={64}
          placeholder="Europe/Paris"
          value={presets.includes(zone) ? "" : zone}
          onChange={(event) => setZone(event.target.value)}
        />
      </label>
    </SettingSheet>
  );
}

const sameQuiet = (a: QuietHours | null, b: QuietHours | null) =>
  a === b || (a !== null && b !== null && a.start === b.start && a.end === b.end);

function QuietSheet(props: FormProps) {
  const { data, i18n } = props;
  const [quiet, setQuiet] = useState<QuietHours | null>(data.quiet_hours);
  const presets = data.options.quiet_hours;
  const chosen = presets.find((preset) => sameQuiet(preset, quiet)) ?? (quiet === null ? "off" : null);
  const valid = quiet === null || (quiet.start !== "" && quiet.end !== "" && quiet.start !== quiet.end);
  const edge = (which: "start" | "end", value: string) =>
    setQuiet((now) => ({ start: now?.start ?? "23:00", end: now?.end ?? "08:00", [which]: value }));
  return (
    <SettingSheet
      {...props}
      title={i18n.t("settings.quiet")}
      hint={i18n.t("settings.quietHint")}
      patch={valid && !sameQuiet(quiet, data.quiet_hours) ? { quiet_hours: quiet } : null}
    >
      <Choice
        label={i18n.t("settings.quiet")}
        options={[...presets.map((_, index) => index), "off" as const]}
        value={chosen === "off" ? "off" : chosen === null ? null : presets.indexOf(chosen)}
        onChange={(option) => setQuiet(option === "off" ? null : (presets[option] ?? null))}
        name={(option) => (option === "off" ? i18n.t("settings.quietDisable") : quietText(presets[option] ?? null, i18n))}
      />
      <div className="field-row">
        <label className="field">
          <span>{i18n.t("settings.quietFrom")}</span>
          <input type="time" value={quiet?.start ?? ""} onChange={(event) => edge("start", event.target.value)} />
        </label>
        <label className="field">
          <span>{i18n.t("settings.quietTo")}</span>
          <input type="time" value={quiet?.end ?? ""} onChange={(event) => edge("end", event.target.value)} />
        </label>
      </div>
    </SettingSheet>
  );
}

function RepeatSheet(props: FormProps) {
  const { data, i18n } = props;
  const [hours, setHours] = useState(data.repeat_after_hours);
  const options = [...new Set([...data.options.repeat_hours, data.repeat_after_hours, 0])].sort(
    (a, b) => (a || 99) - (b || 99),
  );
  return (
    <SettingSheet
      {...props}
      title={i18n.t("settings.repeat")}
      hint={i18n.t("settings.repeatHint")}
      patch={hours !== data.repeat_after_hours ? { repeat_after_hours: hours } : null}
    >
      <Choice
        label={i18n.t("settings.repeat")}
        options={options}
        value={hours}
        onChange={setHours}
        name={(option) => repeatText(option, i18n)}
      />
    </SettingSheet>
  );
}

function CurrencySheet(props: FormProps) {
  const { data, i18n } = props;
  const [currency, setCurrency] = useState(data.room.currency);
  const options = [...new Set([...data.options.currencies, data.room.currency])];
  return (
    <SettingSheet
      {...props}
      title={i18n.t("settings.currency")}
      hint={i18n.t("settings.currencyHint")}
      patch={currency !== data.room.currency ? { currency } : null}
    >
      <Choice label={i18n.t("settings.currency")} options={options} value={currency} onChange={setCurrency} />
    </SettingSheet>
  );
}

const SETTING_SHEETS: Record<SettingKind, (props: FormProps) => ReactNode> = {
  language: LanguageSheet,
  timezone: TimezoneSheet,
  quiet: QuietSheet,
  repeat: RepeatSheet,
  currency: CurrencySheet,
};

function NameFields({
  name,
  emoji,
  maxName,
  i18n,
  onName,
  onEmoji,
}: {
  name: string;
  emoji: string;
  maxName: number;
  i18n: Translator;
  onName: (value: string) => void;
  onEmoji: (value: string) => void;
}) {
  return (
    <div className="field-row name-row">
      <label className="field emoji-field">
        <span>{i18n.t("category.emoji")}</span>
        <input
          autoComplete="off"
          maxLength={8}
          placeholder="📌"
          value={emoji}
          onChange={(event) => onEmoji(event.target.value)}
        />
      </label>
      <label className="field">
        <span>{i18n.t("category.name")}</span>
        <input autoComplete="off" maxLength={maxName} value={name} onChange={(event) => onName(event.target.value)} />
      </label>
    </div>
  );
}

/** The changes made in the form, or null when there are none. */
export function categoryPatch(
  category: CategorySettings,
  form: { name: string; emoji: string; time: string; days: number[]; mode: CategorySettings["mode"] },
): CategoryPatch | null {
  const patch: CategoryPatch = {};
  const name = form.name.trim().replace(/\s+/g, " ");
  const emoji = form.emoji.trim();
  const days = [...form.days].sort((a, b) => a - b);
  if (name !== category.name) patch.name = name;
  if (emoji !== category.emoji && !(emoji === "" && category.emoji === "📌")) patch.emoji = emoji;
  if (form.time !== category.reminder_time) patch.reminder_time = form.time;
  if (days.join() !== category.reminder_days.join()) patch.reminder_days = days;
  if (form.mode !== category.mode) patch.mode = form.mode;
  return Object.keys(patch).length ? patch : null;
}

function CategorySheet({
  category,
  data,
  i18n,
  actions,
  onClose,
}: Omit<FormProps, "onSaved"> & { category: CategorySettings }) {
  const [name, setName] = useState(category.name);
  const [emoji, setEmoji] = useState(category.emoji);
  const [time, setTime] = useState(category.reminder_time);
  const [days, setDays] = useState(category.reminder_days);
  const [mode, setMode] = useState(category.mode);
  const patch = categoryPatch(category, { name, emoji, time, days, mode });
  const valid = name.trim() !== "" && days.length > 0 && /^\d\d:\d\d$/.test(time);
  const roomId = data.room.id;
  const title = `${category.emoji} ${category.name}`;

  const run = async (id: string, request: Parameters<Actions["run"]>[1], confirm?: string) => {
    if (await actions.run(id, request, confirm)) onClose();
  };
  const toggleDay = (day: number) => {
    haptic.select();
    setDays((now) => (now.includes(day) ? now.filter((d) => d !== day) : [...now, day]));
  };

  return (
    <Sheet title={title} onClose={onClose} i18n={i18n}>
      <NameFields
        name={name}
        emoji={emoji}
        maxName={data.options.max_category_name}
        i18n={i18n}
        onName={setName}
        onEmoji={setEmoji}
      />
      <label className="field">
        <span>{i18n.t("category.time")}</span>
        <input type="time" value={time} onChange={(event) => setTime(event.target.value)} />
      </label>
      <Choice label={i18n.t("category.timePresets")} options={data.options.reminder_times} value={time} onChange={setTime} />

      <div className="field-label">{i18n.t("category.days")}</div>
      <div className="chips" role="group" aria-label={i18n.t("category.days")}>
        {WEEK.map((day) => (
          <button type="button" key={day} aria-pressed={days.includes(day)} onClick={() => toggleDay(day)}>
            {i18n.t(`weekday.${day}` as Key)}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={days.length === WEEK.length}
          onClick={() => {
            haptic.select();
            setDays(WEEK);
          }}
        >
          {i18n.t("category.everyDay")}
        </button>
      </div>

      <div className="field-label">{i18n.t("category.mode")}</div>
      <Choice
        label={i18n.t("category.mode")}
        options={["round_robin", "fair"] as const}
        value={mode}
        onChange={setMode}
        name={(option) => i18n.t(`category.mode.${option}`)}
      />

      {!category.is_active && <p className="hint">{i18n.t("category.pausedHint")}</p>}
      <div className="actions">
        <button
          type="button"
          className="button"
          disabled={actions.busy !== null}
          onClick={() => void run("toggle", () => api.updateCategory(roomId, category.id, { is_active: !category.is_active }))}
        >
          {actions.busy === "toggle" ? "…" : i18n.t(category.is_active ? "category.disable" : "category.enable")}
        </button>
        <button
          type="button"
          className="button danger"
          disabled={actions.busy !== null}
          onClick={() =>
            void run("delete", () => api.deleteCategory(roomId, category.id), i18n.t("confirm.delete", { title }))
          }
        >
          {actions.busy === "delete" ? "…" : i18n.t("category.delete")}
        </button>
      </div>

      <MainButton
        text={i18n.t("settings.save")}
        disabled={patch === null || !valid}
        progress={actions.busy === "category"}
        onClick={() => {
          if (patch)
            void run(
              "category",
              () => api.updateCategory(roomId, category.id, patch),
              patch.mode ? i18n.t("confirm.mode") : undefined,
            );
        }}
      />
    </Sheet>
  );
}

function AddCategorySheet({ data, i18n, actions, onClose }: Omit<FormProps, "onSaved">) {
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("");
  const add = async () => {
    if (await actions.run("addCategory", () => api.addCategory(data.room.id, { name, emoji }))) onClose();
  };
  return (
    <Sheet title={i18n.t("category.addTitle")} onClose={onClose} i18n={i18n}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) void add();
        }}
      >
        <NameFields
          name={name}
          emoji={emoji}
          maxName={data.options.max_category_name}
          i18n={i18n}
          onName={setName}
          onEmoji={setEmoji}
        />
      </form>
      <p className="hint">
        {i18n.t("category.emojiHint")}. {i18n.t("category.addHint")}
      </p>
      <MainButton
        text={i18n.t("category.add")}
        disabled={!name.trim()}
        progress={actions.busy === "addCategory"}
        onClick={() => void add()}
      />
    </Sheet>
  );
}

// --- the tab -------------------------------------------------------------------------------

export default function RoomView({
  roomId,
  i18n,
  onRoomChange,
}: {
  roomId: number;
  i18n: Translator;
  /** The room's own data changed (its language, the caller left it): reload the room list. */
  onRoomChange: () => void;
}) {
  const state = useLoad(() => api.settings(roomId), [roomId], { refreshEvery: SLOW_REFRESH_MS });
  const actions = useActions(i18n, state.reload);
  const [screen, setScreen] = useState<Screen>(null);
  const close = () => setScreen(null);

  return (
    <Async state={state} i18n={i18n}>
      {(data) => {
        const form = { data, i18n, actions, onClose: close };
        const category = screen?.kind === "category" ? data.categories.find((c) => c.id === screen.id) : undefined;
        const SettingForm = screen && screen.kind in SETTING_SHEETS ? SETTING_SHEETS[screen.kind as SettingKind] : null;
        return (
          <>
            <RoomScreen
              data={data}
              i18n={i18n}
              busy={actions.busy}
              onOpen={setScreen}
              onSummary={(enabled) =>
                void actions.run("summary", () => api.updateSettings(roomId, { weekly_summary: enabled }))
              }
              onRemove={(member) =>
                void actions.run(
                  `remove-${member.member_id}`,
                  () => api.removeMember(roomId, member.member_id),
                  i18n.t("confirm.remove", { name: member.name }),
                )
              }
              onLeave={async () => {
                if (await actions.run("leave", () => api.leave(roomId), i18n.t("confirm.leave"))) onRoomChange();
              }}
              onExport={() => void actions.run("export", () => api.exportCsv(roomId))}
            />
            {SettingForm && <SettingForm {...form} onSaved={onRoomChange} />}
            {category && <CategorySheet {...form} key={category.id} category={category} />}
            {screen?.kind === "addCategory" && <AddCategorySheet {...form} />}
          </>
        );
      }}
    </Async>
  );
}

// --- joining ---------------------------------------------------------------------------------

/** "I live here" for somebody from the room's group chat who opened the app on it. */
export function JoinScreen({
  room,
  i18n,
  onJoined,
  onLater,
}: {
  room: Room;
  i18n: Translator;
  onJoined: () => void;
  onLater?: () => void;
}) {
  const actions = useActions(i18n);
  const [joined, setJoined] = useState(false);
  const join = async () => {
    if (await actions.run("join", () => api.join(room.id))) {
      setJoined(true); // until the room list is reloaded
      onJoined();
    }
  };
  return (
    <div className="gate">
      <div className="emoji" aria-hidden>
        🏠
      </div>
      <h1>{i18n.t("join.title", { room: room.name })}</h1>
      <p>{i18n.t("join.text")}</p>
      {onLater && (
        <p>
          <button type="button" className="link-button" onClick={onLater}>
            {i18n.t("join.later")}
          </button>
        </p>
      )}
      <MainButton text={i18n.t("join.button")} progress={joined || actions.busy === "join"} onClick={() => void join()} />
    </div>
  );
}
